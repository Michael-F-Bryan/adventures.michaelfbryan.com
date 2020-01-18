---
title: "Reviewing Unsafe Rust"
date: "2020-01-18T20:38:06+08:00"
draft: true
---

There has recently been a bit of a kerfuffle in the Rust community around the
actix-web project. Rather than talking about the public outcry and nasty
things being said on Reddit or the author's fast-and-loose attitude towards
writing `unsafe` code (Steve Klabnik has [already explained it][sad-day] much
better than I could) I would like to discuss some technical aspects of `unsafe`
Rust.

In particular a lot of people say we should be reviewing our dependencies for
possibly unsound code, but nobody seems to explain *how* such a review is done
or how to reason about correctness.

There's also a tendency to understate how much effort is required to review code
in enough detail that the review can be relied on. To that end, the [crev][crev]
project has done a lot of work to help distribute the review effort and build a
*Web of Trust* system.

I'll also be keeping track of the time taken using an app called
[clockify][clockify], that way at the end we can see a rough breakdown of
time spent and get a more realistic understanding of the effort required to
review code.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Introducing the `memchr` Crate

## Time Taken

## Conclusions

[sad-day]: https://words.steveklabnik.com/a-sad-day-for-rust
[crev]: https://github.com/crev-dev/crev
[clockify]: https://clockify.me/