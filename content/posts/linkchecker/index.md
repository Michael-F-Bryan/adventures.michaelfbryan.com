---
title: "Creating a Reusable Linkchecker"
date: "2020-04-23T21:59:54+08:00"
draft: true
tags:
- Rust
- I Made a Thing
---

With around 63,544 downloads, one of my most successful Rust projects is a
nondescript little program called [mdbook-linkcheck][mdbook-linkcheck]. This
is a linkchecker for [mdbook][mdbook], the tool powering a lot of
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

## Extracting Links from Plain Text

## Extracting Links from Markdown

## Validating Links to Local Files

## Validating Links on the Web

## Conclusions

[mdbook-linkcheck]: https://github.com/Michael-F-Bryan/mdbook-linkcheck
[mdbook]: https://github.com/rust-lang/mdBook
[trpl]: https://doc.rust-lang.org/book/
[rustc-dev]: https://rustc-dev-guide.rust-lang.org/
[chalk-book]: https://rust-lang.github.io/chalk/book/html/index.html
[pr-408]: https://github.com/rust-lang/chalk/pull/408/
