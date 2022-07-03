---
title: "Breaking Dependency Cycles With The Linker Trick"
publishDate: "2022-07-04T00:07:49+08:00"
draft: true
tags:
- Daily Rust
- Rust
series:
- Daily Rust
---

- Couple months back
- Ran into a cyclic dependency problem at work
- Unable to restructure the code because the core was maintained by a 3rd party
- Couldn't afford to spend a week restructuring the upstream code and making a
  PR
- Take inspiration from how [Rust's `#[global_allocator] works`][global-alloc]
- Used all the time in C programs
- Titbit, mentioned in *Working Effectively with Legacy Code* under the name
  *"Link Seams"*
- Forward declare `extern "Rust"` functions and make the linker figure it out

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## Some Context

The background for this problem isn't really relevant to the solution, but it
might help to provide examples for where this trick is useful.

At [Hammer of the Gods][hotg], we have developed a containerisation technology
backed by WebAssembly which lets us compile various operations in a data
processing pipeline once, then execute these operations on a variety of
platforms (desktop, browser, mobile, etc.)[^1].

A key part of this is [the `wit-bindgen` project][wit-bindgen] which lets us
define host and guest interfaces in `*.wit` files, then generate Rust code that
satisfies the interfaces. If you are familiar with gRPC and Protocol Buffers,
`wit-bindgen` is like `protoc` and `*.wit` files are like `*.proto` files.

Now, we've got 30+ different operations and it would be really nice if we could
put the generated glue code in one common crate. That way we can add nice things
like constructors, helper methods, and trait implementations to the generated
types, wire up nicer error handling with the `?` operator, and so on.

This has a massive benefit for developer ergonomics, but turned out to be very
difficult because of the way `wit-bindgen`'s glue code works.

- ...

[^1]: For example, imagine making a pipeline which takes an audio clip,
normalises the volume level, converts the audio samples into a spectrum, then
passes the spectrum to a ML model which can recognise particular words.

    Each of these steps is compiled into its own WebAssembly module and our
    "runtime" chains them together.

    We also use the [*WebAssembly Package Manager*][wapm] to distribute
    WebAssembly modules and manage versions.

[global-alloc]: https://github.com/rust-lang/rust/blob/3a8b0144c82197a70e919ad371d56f82c2282833/library/alloc/src/alloc.rs#L22-L39
[hotg]: https://hotg.ai/
[wapm]: https://wapm.io/
[wit-bindgen]: https://github.com/bytecodealliance/wit-bindgen
