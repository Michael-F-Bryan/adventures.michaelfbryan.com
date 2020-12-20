---
title: "Exception Safety and Poisoning"
date: "2020-12-21T04:08:24+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
- FFI
---

In [a previous article][previous] we came up with a FFI-safe way to create
polymorphic Rust types, but I glossed over one very important aspect of
designing a *Foreign Function Interface*; something called [*Exception
Safety*][exception-safety].

There is a lot of code out there which may trigger a *panic* and unwind the
stack. Normally this is fine and a completely normal way to gracefully crash
the program in the face of an unrecoverable error (e.g. a programming bug),
however it is currently *Undefined Behaviour* for a Rust function to unwind
into a stack frame from another language.

The [*Project "FFI-Unwind"*][project-unwind] working group have been created to
come up with an all-encompassing solution to this tricky problem, but in the
meantime I'll be coming up with our own solution.

The technique I'll be employing is the same one used by `std::sync::Mutex`,
[*Poisoning*][poison].

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/thin-trait-objects
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Why Do We Care About Exception Safety?

## Detecting Panics in Our FFI Code

## Implementing Poisoning Properly

## Conclusions

Special thanks go to [`@Mart-Bogdan`][mart] for raising
[`Michael-F-Bryan/thin-trait-objects#1][initial-issue]!

[previous]: {{< ref "/posts/ffi-safe-polymorphism-in-rust.md" >}}
[exception-safety]: https://doc.rust-lang.org/nomicon/exception-safety.html
[project-unwind]: https://github.com/rust-lang/project-ffi-unwind
[poison]: https://doc.rust-lang.org/std/sync/struct.Mutex.html#poisoning
[mart]: https://github.com/Mart-Bogdan
[initial-issue]: https://github.com/Michael-F-Bryan/thin-trait-objects/issues/1
