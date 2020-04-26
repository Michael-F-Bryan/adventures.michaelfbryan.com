---
title: "Creating a Reusable Link-checker"
date: "2020-04-23T21:59:54+08:00"
draft: true
tags:
- Rust
- I Made a Thing
---

With around 63,544 downloads, one of my most successful Rust projects is a
nondescript little program called [mdbook-linkcheck][mdbook-linkcheck]. This
is a link-checker for [mdbook][mdbook], the tool powering a lot of
documentation in the Rust community, including [*The Rust Programming
Language*][trpl] and [*The Rustc Dev Book*][rustc-dev].

As an example of what it looks like, I recently found [a couple][pr-408]
broken links in [the documentation][chalk-book] for Chalk. When the tool
detects broken links in your markdown it'll emit error messages that point
you at the place the link is defined and explain what the issue is.

![Broken Links in Chalk's Documentation](chalk-broken-links.png)

This tool has been around for a while and works quite well, so when I was
fixing a bug the other day I decided it's about time to extract the core logic
into a standalone library that others can use.

{{% notice note %}}
The code written in this article is available [on GitHub][repo] and published
[on crates.io][crate]. Feel free to browse through and steal code or
inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[crate]: https://crates.io/crates/linkcheck
[repo]: https://github.com/Michael-F-Bryan/linkchecker
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## What Belongs in a Library?

When you start building a library it's good to think about what problem the
library is trying to solve. That way you know what features belong in the
library and, more importantly, what doesn't.

The [`linkchecker`][crate] crate's primary objective is to find links in a
document and check that they point to something valid. There seem to be two
concepts here:

- `Scanner` - some sort of function which can consume text and return a stream
  of links that are found.
- `Validator` - something which can take a batch of links and tell you whether
  they are valid or not

{{% notice note %}}
For diagnostic purposes we'll also want to know *where* each link occurs in
the source document. So instead of just being a `String`, a link will need to
drag its `Span` along with it.

The [`codespan`][codespan] crate contains a lot of powerful tools for
managing source code and emitting diagnostics, so I imagine I'll be leaning
on it quite a bit.

[codespan]: https://crates.io/crates/codespan
{{% /notice %}}

In the long run, it'd be nice to include scanners for most popular formats,
however to keep things manageable I'm going to constrain this to plain text
and markdown for now. I imagine HTML would also be a nice addition because
it'll let people check their websites, but I'll leave that as an exercise for
later.

As far as I can tell, there are only really two types of links,

- *Local Files* - a link to another file on disk
- *Web Links* - a URL for some resource on the internet

Validating web links should be rather easy, we can send a GET request to the
appropriate website and our web client (probably [`reqwest`][reqwest]) will let
us know if we've got a dead link or not.

## Extracting Links from Plain Text

I thought I'd start with plain text because that's easiest. We want to create
some sort of iterator which yields all the bits of text that resemble a URL.

Originally I thought it'd just be a case of writing a regular expression and
mapping the [`Matches`][regex::Matches] iterator from the [`regex`][regex]
crate, but it turns out URLs aren't that easy to work with.

After searching google for about 10 minutes and scanning through dozens of
StackOverflow questions I wasn't able to find an expression which would
match *all* the types of URLs I expected while also avoiding punctuation
like a trailing full stop or when a link is in parentheses.

This reminds me of a popular quote...

> Some people, when confronted with a problem, think *"I know, I'll use
> regular expressions."* Now they have two problems.
>
> <cite>Jamie Zawinski</cite>

Luckily for me, this problem has [already been solved][linkify-repo] and [the
`linkify` crate][linkify] is available on crates.io!

Looking through the source code, it seems like they've written a lot of
manual code to take into account how URLs may be embedded in bodies of text.
This mainly consists of scanning for certain "trigger characters" (`:` for a
URL, `@` for an email address) then backtracking to find the start of the
item. There are also [lots of tests][linkify-tests] to make sure only the
desired text is detected as a match.

The end result means the implementation of our `plaintext` scanner is almost
trivial:

```rust
// src/scanners/plaintext.rs

use crate::codespan::Span;
use linkify::{LinkFinder, LinkKind};

pub fn plaintext(src: &str) -> impl Iterator<Item = (&str, Span)> + '_ {
    LinkFinder::new()
        .kinds(&[LinkKind::Url])
        .links(src)
        .map(|link| {
            (
                link.as_str(),
                Span::new(link.start() as u32, link.end() as u32),
            )
        })
}
```

I also threw in tests for a couple examples:

```rust
// src/scanners/plaintext.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn detect_urls_in_some_text() {
        let src = "hello http://localhost/ world. this is file://some/text.";
        let should_be = vec![
            ("http://localhost/", Span::new(6, 23)),
            ("file://some/text", Span::new(39, 55)),
        ];

        let got: Vec<_> = plaintext(src).collect();

        assert_eq!(got, should_be);
    }
}
```

## Extracting Links from Markdown

For parsing markdown my go-to library is [`pulldown-cmark`][pulldown-cmark].
This exposes an iterator-based API, yielding `Event`s like *"start of
paragraph tag"*, *"end of inline code"*, *"horizontal rule"*, and so on.

This API is pretty low level and you'll need to do a lot of work yourself if
you want to create some sort of semantic model (e.g. a DOM) of the document,
but if you're just wanting to scan through a document and extract specific
bits like we are, it's ideal.

The `pulldown-cmark` parser also provides an ["offset"
iterator][pulldown-offset-iter] who's `Item` is a `(Event<'a>,
Range<usize>)`. This should give us enough information to provide developers
with useful diagnostics.

My initial `markdown` scanner looked something like this:

```rust
// src/scanners/markdown.rs

pub fn markdown(src: &str) -> impl Iterator<Item = (String, Span)> + '_ {
    Parser::new(src)
    .into_offset_iter()
    .filter_map(|(event, range)| match event {
        Event::Start(Tag::Link(_, dest, _))
        | Event::Start(Tag::Image(_, dest, _)) => Some((
            dest.to_string(),
            Span::new(range.start as u32, range.end as u32),
        )),
        _ => None,
    })
}
```

The chain of iterator combinators and `match` statement make the code look
complicated, the idea itself is quite simple... Filter out everything but the
start of `Link` and `Image` tags, then transform them to a tuple containing
the link itself and its location in the source text.

The `pulldown-cmark` parser also lets you provide a callback that can will be
triggered whenever it encounters a footnote-style link (e.g. `[some
text][link]`) with no corresponding link definition (e.g. `[link]:
https://example.com`). This is normally meant as a mechanism for *fixing* the
broken reference, but we can use it to emit diagnostics.

The updated scanner:

```rust
// src/scanners/markdown.rs

use crate::codespan::Span;
use pulldown_cmark::{Event, Options, Parser, Tag};

pub fn markdown(src: &str) -> impl Iterator<Item = (String, Span)> + '_ {
    markdown_with_broken_link_callback(src, &|_, _| None)
}

pub fn markdown_with_broken_link_callback<'a, F>(
    src: &'a str,
    on_broken_link: &'a F,
) -> impl Iterator<Item = (String, Span)> + 'a
where
    F: Fn(&str, &str) -> Option<(String, String)>,
{
    Parser::new_with_broken_link_callback(
        src,
        Options::ENABLE_FOOTNOTES,
        Some(on_broken_link),
    )
    .into_offset_iter()
    .filter_map(|(event, range)| match event {
        Event::Start(Tag::Link(_, dest, _))
        | Event::Start(Tag::Image(_, dest, _)) => Some((
            dest.to_string(),
            Span::new(range.start as u32, range.end as u32),
        )),
        _ => None,
    })
}
```

{{% notice info %}}
Unfortunately, the `on_broken_link` callback doesn't provide span information
so that'll make it a bit tricky to provide useful error messages.

I had to deal with this in `mdbook-linkcheck` as well and ended up using [a
hacky workaround][hack] consisting of a call to
`src.index_of(broken_reference)` and hoping for the best.

Hopefully [raphlinus/pulldown-cmark#165][pd-cmark-165] will be solved some
time soon and they'll change the signature to something more useful, because
it's kinda clunky at the moment. I've seen at least [one case][issue-478]
where these sorts of broken links occur in real world documents, so it'd be
nice to have a solid solution.

[hack]: https://github.com/Michael-F-Bryan/mdbook-linkcheck/blob/d39af0a48ce8b83db1e54f723d994258689f825a/src/validate.rs#L317-L332
[pd-cmark-165]: https://github.com/raphlinus/pulldown-cmark/issues/165
[issue-478]: https://github.com/rust-lang/rustc-dev-guide/issues/478
{{% /notice %}}

## Validating Links to Local Files

## Validating Links on the Web

## Conclusions

[mdbook-linkcheck]: https://github.com/Michael-F-Bryan/mdbook-linkcheck
[mdbook]: https://github.com/rust-lang/mdBook
[trpl]: https://doc.rust-lang.org/book/
[rustc-dev]: https://rustc-dev-guide.rust-lang.org/
[chalk-book]: https://rust-lang.github.io/chalk/book/html/index.html
[pr-408]: https://github.com/rust-lang/chalk/pull/408/
[crate]: https://crates.io/crates/linkcheck
[codespan]: https://crates.io/crates/codespan
[reqwest]: https://crates.io/crates/reqwest
[regex::Matches]: https://docs.rs/regex/1.3.7/regex/struct.Matches.html
[regex]: https://crates.io/crates/regex
[linkify]: https://crates.io/crates/linkify
[linkify-repo]: https://github.com/robinst/linkify
[linkify-tests]: https://github.com/robinst/linkify/blob/a08b343bb524f267130d67ad3e1a752c34dd49ac/tests/url.rs
[pulldown-cmark]: https://crates.io/crates/pulldown-cmark
[pulldown-offset-iter]: https://docs.rs/pulldown-cmark/0.7.0/pulldown_cmark/struct.OffsetIter.html
