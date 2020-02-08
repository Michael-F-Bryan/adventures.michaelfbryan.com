---
title: "I Made A Thing: Markedit"
date: "2020-02-08T13:06:16+08:00"
draft: true
tags:
- rust
- "I made a thing"
---

A couple days ago I released [markedit][crates-io], a small crate for editing
unstructured markdown documents. This is a useful enough library that I
thought I'd explain the main ideas behind it and potential use cases.

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
60 seconds manually editing files before a release acts as a speed bump and
means you can't just hit the *"Release"* button and grab a coffee. There's
also a real chance that we could forget to update the change log before
cutting a release, and that'd be embarrassing.

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
`pulldown-cmark` quite easy to use, but when you're trying to look for a
specific pattern (e.g. *"the first line after a level 1 heading"*) the code
starts to get pretty gnarly.

For example, [the logic in `mdbook`][parse-summary] for parsing a
`SUMMARY.md` and discovering the book's structure is particularly hard to
understand, and the fact it's barely been touched in two years is a good
indicator of that... I'd be lying if I said I didn't feel a bit guilty for
writing such a code monster 😔

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
    fn matches_event(&mut self, event: &Event<'_>) -> bool;
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
    fn matches_event(&mut self, event: &Event<'_>) -> bool { self(event) }
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
    fn matches_event(&mut self, event: &Event<'_>) -> bool {
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
        (Event::Start(Tag::Link(LinkType::Inline, "https://example.com".into(), "".into())), false),
        (Event::Text("And a link".into()), false),
        (Event::End(Tag::Link(LinkType::Inline, "https://example.com".into(), "".into())), false),
        (Event::End(Tag::Paragraph), false),
    ];

    let mut matcher = Heading::any_level();

    for (tag, should_be) in inputs {
        let got = matcher.matches_event(&tag);
        assert_eq!(got, should_be, "{:?}", tag);
    }
}
```

### Matching a Falling Edge

Remember that we want to select items between two headings, that means we'll
need to a falling edge signal from the `Heading`s matcher.

This can be done generically using some `FallingEdge` matcher which wraps
another matcher.

```rust
// src/matchers/falling_edge.rs

#[derive(Debug, Clone, PartialEq)]
pub struct FallingEdge<M> {
    inner: M,
    previous_was_matched: bool,
}

impl<M> FallingEdge<M> {
    pub const fn new(inner: M) -> Self {
        FallingEdge {
            inner,
            previous_was_matched: false,
        }
    }
}
```

From here, detecting a falling edge pretty straightforward.

```rust
// src/matchers/falling_edge.rs

impl<M: Matcher> Matcher for FallingEdge<M> {
    fn matches_event(&mut self, event: &Event<'_>) -> bool {
        let current_is_matched = self.inner.matches_event(event);
        let is_falling_edge = self.previous_was_matched && !current_is_matched;
        self.previous_was_matched = current_is_matched;
        is_falling_edge
    }
}
```

For convenience we can add a combinator method to the `Matcher` trait. This will
allow users to compose matchers using method syntax instead of needing to write
the more verbose `FallingEdge::new(...)`.

```rust
// src/matchers/mod.rs

pub trait Matcher {
    ...

    /// Get a [`Matcher`] which returns `true` when `self` goes from `true` to
    /// `false`.
    fn falling_edge(self) -> FallingEdge<Self>
    where
        Self: Sized,
    {
        FallingEdge::new(self)
    }
}
```

By combining the `Heading` and `FallingEdge` matchers we now have all the tools
necessary to find the items between two headings in a markdown document.

Once you reach this point it's easy to get carried away making more and more
elaborate `Matcher` primitives (i.e. `text()` and `Heading`) and combinators
(i.e. `FallingEdge`), so let's discuss document manipulation.

## Rewrite Rules

It took a bit of thinking to come up with an API flexible enough to allow
updating items in-place (imagine auto-correcting text), removing items, and
adding items, all without reading the full document into memory or seeking back
and forth.

This is the API I eventually came up with:

```rust
// src/rewriters/mod.rs

/// Something which can rewrite events.
pub trait Rewriter<'src> {
    /// Process a single [`Event`].
    ///
    /// This may mean ignoring it, mutating it, or adding new events to the
    /// [`Writer`]'s buffer.
    ///
    /// The [`Writer`] is used as a temporary buffer that will then be streamed
    /// to the user via [`rewrite()`].
    fn rewrite_event(&mut self, event: Event<'src>, writer: &mut Writer<'src>);
}
```

Again, seeing as this trait only has a single method it's an ideal candidate for
allowing people to use concise closures instead of needing to create a full
type.

```rust
// src/rewriters/mod.rs

impl<'src, F> Rewriter<'src> for F
where
    F: FnMut(Event<'src>, &mut Writer<'src>),
{
    fn rewrite_event(&mut self, event: Event<'src>, writer: &mut Writer<'src>) {
        self(event, writer);
    }
}
```

You may be wondering what this `Writer` is for, well that's where a lot of the
rewriting magic comes in.

```rust
// src/rewriters/writer.rs

use pulldown_cmark::Event;
use std::collections::VecDeque;

/// The output buffer given to [`Rewriter::rewrite_event()`].
#[derive(Debug)]
pub struct Writer<'a> {
    pub(crate) buffer: VecDeque<Event<'a>>,
}

impl<'a> Writer<'a> {
    pub(crate) fn new() -> Writer<'a> {
        Writer {
            buffer: VecDeque::new(),
        }
    }

    /// Queue an [`Event`] to be emitted.
    pub fn push(&mut self, event: Event<'a>) { self.buffer.push_back(event); }
}

impl<'a> Extend<Event<'a>> for Writer<'a> {
    fn extend<I: IntoIterator<Item = Event<'a>>>(&mut self, iter: I) {
        self.buffer.extend(iter);
    }
}
```

This innoculous `Writer` struct serves as a temporary holding place for events
that needed to be spliced into the resulting stream of `Event`s. We can combine
the `Writer` and our `Rewrite` trait to create a `Rewritten` stream of `Event`s.

```rust
// src/rewriters/rewritten.rs

/// A stream of [`Event`]s that have been modified by a [`Rewriter`].
pub struct Rewritten<'src, E, R>
where
    E: Iterator<Item = Event<'src>>,
{
    events: E,
    rewriter: R,
    writer: Writer<'src>,
}

impl<'src, E, R> Iterator for Rewritten<'src, E, R>
where
    E: Iterator<Item = Event<'src>>,
    R: Rewriter<'src>,
{
    type Item = Event<'src>;

    fn next(&mut self) -> Option<Self::Item> {
        // we're still working through items buffered by the rewriter
        if let Some(ev) = self.writer.buffer.pop_front() {
            return Some(ev);
        }

        // we need to pop another event and process it
        let event = self.events.next()?;
        self.rewriter.rewrite_event(event, &mut self.writer);

        self.writer.buffer.pop_front()
    }
}
```

The idea is to keep popping `Event`s from the `Writer` buffer until there are no
more, then fetch the next `Event` from the underlying stream and ask our
`Rewriter` to process it, updating the buffer in the process. Repeat until the
inner stream runs out.

### Making A Rewriter

Probably the easiest `Rewriter` to implement is something that will splice new
events into the event stream before every match.

This lets us use something like the `Heading::any_level().falling_edge()`
matcher to insert something immediately after a heading (we match the first
item after the heading's close tag).

```rust
// src/rewriters/mod.rs

/// Splice some events into the resulting event stream before every match.
pub fn insert_before<'src, M>(
    to_insert: Vec<Event<'src>>,
    mut matcher: M,
) -> impl Rewriter<'src> + 'src
where
    M: Matcher + 'src,
{
    move |ev: Event<'src>, writer: &mut Writer<'src>| {
        if matcher.matches_event(&ev) {
            writer.extend(to_insert.iter().cloned());
        }
        writer.push(ev);
    }
}
```

Once you get past the various `'src` lifetime annotations, `impl Trait`, and
closure syntax, this function is pretty simple. Whenever we get another event
check whether our matcher matches it, and add a copy of the desired events to
the stream. We want the matched event to also be outputted so we always need
to add it to the `Writer` buffer.

Let's also create an `insert_markdown_before()` function which takes a string
of markdown text. Most users won't want to be generating a list of `Event`s
manually, so this allows us to present a more user-friendly interface.

```rust
// src/rewriters/mod.rs

/// Inserts some markdown text before whatever is matched by the [`Matcher`].
///
/// # Examples
///
/// ```rust
/// use markedit::Matcher;
/// let src = "# Heading\nsome text\n";
///
/// let first_line_after_heading = markedit::exact_text("Heading")
///     .falling_edge();
/// let rewriter = markedit::insert_markdown_before(
///     "## Second Heading",
///     first_line_after_heading,
/// );
///
/// let events = markedit::parse(src);
/// let rewritten: Vec<_> = markedit::rewrite(events, rewriter).collect();
///
/// // if everything went to plan, the output should contain "Second Heading"
/// assert!(markedit::exact_text("Second Heading").is_in(&rewritten));
/// ```
pub fn insert_markdown_before<'src, M, S>(
    markdown_text: S,
    matcher: M,
) -> impl Rewriter<'src> + 'src
where
    M: Matcher + 'src,
    S: AsRef<str> + 'src,
{
    let events = crate::parse(markdown_text.as_ref())
        .collect();
    insert_before(events, matcher)
}
```

## Possible Applications

Now you've got a better understanding of the abstractions provided by the
`markedit` crate, you should have a better idea of where they can be applied.

The `Matcher` idea is especially powerful when you want to extract information
from a markdown document.

Unlike structured data formats like protobufs, the items in a markdown
document don't have a well defined order and you can't make any sweeping
assumptions about the `Event` stream coming from the parser. Instead we rely
on conventions (a project README might have a level 1 header with the title,
then a paragraph or two of description, then a level 2 header with getting
started instructions, etc.) and need a concise, flexible mechanism for
extracting data. That mechanism is the `Matcher`.

In the same way that you can build up an [XPath][xpath] query for searching
an XML document or chain of `sed`, `grep`, and `awk` commands for searching
plain text, the various `Matcher` combinators let you build up a markdown
query.

The `Rewriter` mechanism lets you (surprise, surprise) rewrite part of a
document. You can think of it as a markdown-aware `sed`, and as such can be used
for a lot of the same operations.

After rewriting part of an `Event` you'll need a way to turn it back into
markdown text. The `markedit` crate doesn't (yet!) have a pretty-printer,
however you can leverage existing solutions like [pulldown-cmark-to-cmark][pc2c]
for the same effect.

Some places you might want to use the `markedit` crate instead of working with
raw events from `pulldown-cmark` are,

- extracting structured information from Rust docstrings (e.g.
  [killercup/rust-docstrings](https://github.com/killercup/rust-docstrings))
- [`mdbook` preprocessors](https://rust-lang.github.io/mdBook/for_developers/preprocessors.html)
- extracting links from markdown documents to verify they are still valid
  ([mdbook-linkcheck](https://github.com/Michael-F-Bryan/mdbook-linkcheck))
- automatically correcting spelling mistakes
- Merging several markdown documents and updating inter-doc links so they point
  to their new location ([mdcollate](https://github.com/cetra3/mdcollate)),
  and of course
- Rewriting part of your `CHANGELOG.md` file in preparation for a release

## Conclusions

This was a fun project to make and I'm pretty happy with the resulting
abstractions. Preparing this write-up was also a great way to formalise the
main concepts in my head and identify bugs or better ways of formulating the
crate's API.

If you're working on a new project I'd definitely recommend writing up a blog
post explaining how it works. A blog post also doubles as good high-level
documentation.

I'm already using it in a couple places, but it needs a lot more use in the
real world before it's ready for `1.0`. I'd really like to know if you use it
in your own projects and find places it can be improved, especially in areas
like ergonomics or documentation.

[crates-io]: https://crates.io/crates/markedit
[kac]: https://keepachangelog.com/en/1.0.0/
[gitlab-compare]: https://gitlab.com/gitlab-org/gitlab/-/compare/10-2-stable-ee...10-1-stable-ee
[event]: https://docs.rs/pulldown-cmark/0.6.1/pulldown_cmark/enum.Event.html
[pc]: https://crates.io/crates/pulldown-cmark
[parse-summary]: https://github.com/rust-lang/mdBook/blob/d5999849d9fa4b40986e53fe6c4001bb48cbd73f/src/book/summary.rs#L293-L357
[pc]: https://en.wikipedia.org/wiki/Parser_combinator
[xpath]: https://en.wikipedia.org/wiki/XPath
[krd]: https://github.com/killercup/rust-docstrings
[pc2c]: https://crates.io/crates/pulldown-cmark-to-cmark