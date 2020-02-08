---
title: "I Made A Thing: Markedit"
date: "2020-02-08T13:06:16+08:00"
draft: true
tags:
- rust
- "I made a thing"
---

A couple days ago I released [markedit][crates-io], a small crate for
manipulating unstructured markdown documents. This is a useful enough library
that I thought I'd explain the main ideas behind it and potential use cases.

This originally came about when I was at work, preparing our application's
change log before a release for the umpteenth time (we've found the [keep a
changelog][kac] format really useful) and on the drive home I started thinking
of ways to automate things.

{{< figure
    src="https://imgs.xkcd.com/comics/automation.png"
    link="https://xkcd.com/1319/"
    caption="(obligatory XKCD reference)"
    alt="Automation"
>}}

To put this into context, we've tried to automate the release process as much
as possible to minimise friction and avoid using the time required to cut a
release as an excuse for putting it off. It's now at the point where the
fairly involved process of generating a release (compiling independent
projects written in multiple languages, rendering docs, bumping version
numbers, tagging commits, generating installers, uploading assets to a file
server, etc.) can be done with a single click.

Everything's automated. The whole system functions like a well-oiled machine...
Except for that annoying change log.

See, I still need to manually promote everything under the `[Unreleased]`
section to its own named release (e.g. `[v1.2.3] - 2020-02-09`) and update
links so `[Unreleased]` now points to the diff between the `v1.2.3` tag and
`master`, and `[v1.2.3]` shows the diff between `v1.2.2` and `v1.2.3`. The
linked pages look kinda [like this][gitlab-compare] and are surprisingly useful
when trying to track down regressions or get an overview of what code changed
between releases.

It's only a couple find-and-replace operations, but needing to spend an extra
60 seconds manually editing files before a release acts as a speed bump.

{{% notice note %}}
The code written in this article is available [on GitHub][repo] and
[published on crates.io][crate]. Feel free to browse through and steal code
or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/markedit
[crate]: https://crates.io/crates/markedit
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Main Concepts

Now that I've explained the initial inspiration for this project, let's have
a high-level look at the implementation.

There are a couple fundamental concepts, but the central one is the stream of
[markdown `Event`s][event] emitted by [pulldown-cmark][pc]'s markdown parser.
This is just an iterator over things like `Event::Start(Tag::Heading(1))`,
`Event::Text("some text")`, and `Event::End(Tag::Link(...))`.

Reusing the `Iterator` interface from the standard library already makes
`pulldown-cmark` quite easy to use but when you're trying to look for a
specific pattern (e.g. *"the first line after a level 1 heading"*) the code
starts to get pretty gnarly.

For example, [the logic in `mdbook`][parse-summary] for parsing a
`SUMMARY.md` and discovering the book's structure is particularly hard to
understand, and the fact it's barely been touched in two years is a good
indicator of that. I feel a bit guilty for writing such a code monster 😔

To ease this problem of matching sequences of events we introduce the concept
of a *Matcher*, something which can be fed `Event`s and will tell you when it
finds a match. It's essentially a fancy predicate.

To actually do something once you've found a match we have rewriting rules. This
is a bit of code which lets you manipulate the stream of events in-place (e.g.
by skipping certain items or adding new ones).

Something to note is this entire process is built upon the `Iterator` trait. At
no point should the `markedit` crate assume you've parsed an entire document
into memory beforehand.

My primary reasons for this were:

- Memory usage - a document contains *a lot* of `Event`s, and by not reading
  everything into memory we can avoid large amounts of memory (memory overhead
  with iterators is ammortised `O(1)` instead of `O(n)`)
- Flexibility - the core algorithms shouldn't need to care if the events are
  already in a buffer, streamed from the network, or the caller has already
  done some pre-processing of the events via the various iterator combinators
- Because I can - I mean, why else do we do half the things we do?

## Matchers

At its core the `Matcher` trait is quite trivial.

```rust
// src/matchers/mod.rs

pub trait Matcher {
    fn process_next(&mut self, event: &Event<'_>) -> bool;
}
```

However if combined with closures and ideas from functional programming we
can build something reminiscent of [Parser Combinators][pc].

```rust
// src/matchers/mod.rs

impl<F> Matcher for F
where
    F: FnMut(&Event<'_>) -> bool,
{
    fn process_next(&mut self, event: &Event<'_>) -> bool { self(event) }
}
```

For example, here is the definition for the `text()` function for getting a
`Matcher` which applies a predicate to every `Event::Text` node.

```rust
// src/matchers/mod.rs

/// Match a [`Event::Text`] node using an arbitrary predicate.
pub fn text<P>(mut predicate: P) -> impl Matcher
where
    P: FnMut(&str) -> bool,
{
    move |ev: &Event<'_>| match ev {
        Event::Text(text) => predicate(text.as_ref()),
        _ => false,
    }
}
```

This lets us build a `Matcher` which will return `true` when it encounters an
exact string, or a piece of text containing our desired string.

```rust
// src/matchers/mod.rs

pub fn exact_text<S: AsRef<str>>(needle: S) -> impl Matcher {
    text(move |text| AsRef::<str>::as_ref(text) == needle.as_ref())
}

pub fn text_containing<S: AsRef<str>>(needle: S) -> impl Matcher {
    text(move |text| text.contains(needle.as_ref()))
}
```

{{% notice tip %}}
You'll notice that we're using the `impl Trait` pattern all over the place.
This lets us create complex types while preserving the ability to change our
underlying implementation (e.g. imagine we decide to use an explicit type
instead of a closure) while maintaining backwards compatibility.

As an added bonus, because `impl Trait` uses static dispatch the optimiser
should hopefully be able to generate machine code as good as what a human
could write manually.
{{% /notice %}}

### Matching Headings

When I'm moving items from the `[Unreleased]` section to their own named release
I'll select everything between the end of the `[Unreleased]` section header and
the start of the next header.

To create a `Matcher` which will match those items I'll first need to detect
when we're inside a heading. This is a little more complicated than a simple
yes/no predicate, so for readability I've decided to implement this using a
struct instead of a closure.

```rust
// src/matchers/heading.rs

/// Matches the items inside a heading tag, including the start and end tags.
#[derive(Debug, Clone, PartialEq)]
pub struct Heading {
    inside_heading: bool,
    level: Option<u32>,
}

impl Heading {
    /// Create a new [`Heading`].
    const fn new(level: Option<u32>) -> Self {
        Heading {
            level,
            inside_heading: false,
        }
    }

    /// Matches any heading.
    pub const fn any_level() -> Self { Heading::new(None) }

    /// Matches only headings with the desired level.
    pub const fn with_level(level: u32) -> Self { Heading::new(Some(level)) }
}
```

The implementation is also pretty simple. When we see the start of a header with
the desired level, keep returning `true` until we see the end tag.

```rust
// src/matchers/heading.rs

impl Matcher for Heading {
    fn process_next(&mut self, event: &Event<'_>) -> bool {
        match event {
            Event::Start(Tag::Heading(level)) if self.matches_level(*level) => {
                self.inside_heading = true;
            },
            Event::End(Tag::Heading(level)) if self.matches_level(*level) => {
                self.inside_heading = false;
                // make sure the end tag is also matched
                return true;
            },
            _ => {},
        }

        self.inside_heading
    }
}

impl Heading {
    ...

    fn matches_level(&self, level: u32) -> bool {
        match self.level {
            Some(expected) => level == expected,
            None => true,
        }
    }
}
```

While we're at it, we should probably write a test to make sure we match a
all the items inside a header. I just printed the `Event`s generated by a string
of text then manually marked each event as `true` or `false` depending on what
I'd expect.

```rust
// src/matchers/heading.rs

#[test]
fn match_everything_inside_a_header() {
    // The original text for these events was:
    //
    // This is some text.
    //
    // ## Then a *header*
    //
    // [And a link](https://example.com)
    let inputs = vec![
        (Event::Start(Tag::Paragraph), false),
        (Event::Text("This is some text.".into()), false),
        (Event::End(Tag::Paragraph), false),
        (Event::Start(Tag::Heading(2)), true),
        (Event::Text("Then a ".into()), true),
        (Event::Start(Tag::Emphasis), true),
        (Event::Text("header".into()), true),
        (Event::End(Tag::Emphasis), true),
        (Event::End(Tag::Heading(2)), true),
        (Event::Start(Tag::Paragraph), false),
        (
            Event::Start(Tag::Link(
                LinkType::Inline,
                "https://example.com".into(),
                "".into(),
            )),
            false,
        ),
        (Event::Text("And a link".into()), false),
        (
            Event::End(Tag::Link(
                LinkType::Inline,
                "https://example.com".into(),
                "".into(),
            )),
            false,
        ),
        (Event::End(Tag::Paragraph), false),
    ];

    let mut matcher = Heading::any_level();

    for (tag, should_be) in inputs {
        let got = matcher.process_next(&tag);
        assert_eq!(got, should_be, "{:?}", tag);
    }
}
```

## Rewrite Rules

## Possible Uses

## Benchmarking

## Conclusions

[crates-io]: https://crates.io/crates/markedit
[kac]: https://keepachangelog.com/en/1.0.0/
[gitlab-compare]: https://gitlab.com/gitlab-org/gitlab/-/compare/10-2-stable-ee...10-1-stable-ee
[event]: https://docs.rs/pulldown-cmark/0.6.1/pulldown_cmark/enum.Event.html
[pc]: https://crates.io/crates/pulldown-cmark
[parse-summary]: https://github.com/rust-lang/mdBook/blob/d5999849d9fa4b40986e53fe6c4001bb48cbd73f/src/book/summary.rs#L293-L357
[pc]: https://en.wikipedia.org/wiki/Parser_combinator