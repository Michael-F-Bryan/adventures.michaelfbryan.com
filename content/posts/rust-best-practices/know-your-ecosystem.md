---
title: "Common Newbie Mistakes and Bad Practices in Rust: Know your Ecosystem"
publishDate: "2021-09-16T23:44:27+08:00"
draft: true
tags:
- Rust
series:
- Rust Best Practices
---

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## Implement The Conversion Traits

- `From`
- `FromStr`
- `TryFrom`
- Trait miss-use: implementing `TryFrom<&str>` instead of `FromStr`.

## Clippy Is Your Friend

- When you review newbie code and 99% of things you’ll tell them would’ve been
  suggested by `clippy` as well.

## Manual Argument Parsing

- w.r.t. CLI, parsing arguments manually, or even trying to configure
  `clap` manually, instead of using `structopt` to create a strongly-typed
  input/config struct.
