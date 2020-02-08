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
  with iterators is `O(1)` instead of `O(n)`)
- Performance - there's no need for unnecessary copies and buffering
- Flexibility - the core algorithms don't care if the events are already in a
  buffer, streamed from the network, or the caller has already done some
  pre-processing of the events via the various iterator combinators
- Because I can - I just curious to see how far I can push the language and my
  own skills

## Matchers

## Rewrite Rules

## Possible Uses

## Performance

## Conclusions

[crates-io]: https://crates.io/crates/markedit
[kac]: https://keepachangelog.com/en/1.0.0/
[gitlab-compare]: https://gitlab.com/gitlab-org/gitlab/-/compare/10-2-stable-ee...10-1-stable-ee
[event]: https://docs.rs/pulldown-cmark/0.6.1/pulldown_cmark/enum.Event.html
[pc]: https://crates.io/crates/pulldown-cmark
[parse-summary]: https://github.com/rust-lang/mdBook/blob/d5999849d9fa4b40986e53fe6c4001bb48cbd73f/src/book/summary.rs#L293-L357