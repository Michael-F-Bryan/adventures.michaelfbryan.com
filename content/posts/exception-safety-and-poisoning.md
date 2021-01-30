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
polymorphic Rust types and used the equivalent of a `Box<dyn Write>` as a
case study , but I glossed over one very important aspect of designing a
*Foreign Function Interface* in general; something called [*Exception
Safety*][exception-safety].

There is a lot of code out there which may trigger a *panic* and unwind the
stack. Normally this is fine and a completely normal way to gracefully crash
the program in the face of an unrecoverable error (e.g. a programming bug),
however it is currently *Undefined Behaviour* for a Rust function to unwind
into a stack frame from another language. Maintaining memory safety in the face
of an exception (a *panic* in Rust parlance) is an important part of writing
robust code.

The [*Project "FFI-Unwind"*][project-unwind] working group have been created to
come up with an all-encompassing solution to this tricky problem, but in the
meantime we'll be coming up with our own solution.

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

## Exception Safety

Exception safety doesn't really come up in day-to-day Rust programming, so it's
worth explaining what it is and why it could be a problem for our *Thin Trait
Objects* code.

### What Is It?

The general idea behind exception safety is that you might temporarily break
an invariant, but some other code triggers a panic before you can fix things
up.

Normally this isn't a problem because a panic will abort the current thread
of execution meaning you can no longer access the data, but mechanisms like
`std::panic::catch_unwind()` and concurrency get around that.

There are roughly two levels of exception safety in Rust; minimal and
maximal exception safety.

In `unsafe` code, *Minimal Exception Safety* means you **must** guarantee
that a panic can't break memory safety. For example, say you were removing
specific objects from a vector and temporarily leaving uninitialised memory
behind so we can amortise the cost of shuffling objects down. Even if the
code panics it should be impossible to observe that uninitialised memory.

In safe code, *Maximal Exception Safety* means there are some guarantees that
it'd be really nice if we upheld, but failing to uphold those guarantees
won't result in [nasal demons][nasal-demon]. Imagine creating a list which
guarantees it will always be sorted, but you encounter a panic while mutating
something in place. The function will now exit and leave your list
potentially unsorted, and if the list can be accessed later on (e.g. because
you stopped unwinding with `std::panic::catch_unwind()`) it might cause a
later binary search to return incorrect results.

### How Does It Affect Us?

Normal Rust code may panic, and panicking into C is *Undefined Behaviour* so
we need to stop all panics at the FFI boundary and generate an appropriate
error code.

That's fine and easy enough to do, but let's take a step back and ask a
question... What happens if we try to keep using something afterwards?

We're going to have a bad time if, by sheer bad luck, the Rust code triggered
a panic while an invariant was temporarily broken.

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
[nasal-demon]: https://en.wikipedia.org/wiki/Undefined_behavior
