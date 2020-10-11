---
title: "Embedding Futhark in Rust"
date: "2020-10-11T23:45:54+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
- FFI
- Futhark
---

Over the last year or so I've been keeping an eye on the [Futhark][futhark]
programming language, a small programming language designed to be compiled to
efficient parallel code that can be run on a GPU.

Something I really like about this language is that it isn't trying to solve
all your problems or replace existing general-purpose languages. Instead it
has been designed to fill the niche of hardware accelerated data processing
and enable easy integration with non-Futhark code for the rest of your
application logic.

Their [blog posts][futhark-blog] are also quite well written, too.

To help raise awareness for this young project (and so I have notes to look
back on six months from now) I thought I'd go through the steps for embedding
Futhark code in a Rust program for rendering [the Mandelbrot set][wiki].

{{% notice note %}}
The code written in this article is available on GitHub
([futhark-rs][f]/[mandelbrot][m]). Feel free to browse through and steal code
or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[f]: https://github.com/Michael-F-Bryan/futhark-rs
[m]: https://github.com/Michael-F-Bryan/mandelbrot
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

[futhark]:https://futhark-lang.org/
[futhark-blog]: https://futhark-lang.org/blog.html
[wiki]: https://en.wikipedia.org/wiki/Mandelbrot_set
