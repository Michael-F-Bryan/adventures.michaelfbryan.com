---
title: "Bringing include_dir Into the Modern Era"
date: "2021-11-03T20:16:16+08:00"
draft: true
tags:
- Rust
---

Way back in mid-2017 I created [a crate called `include_dir`][include-dir] with
a single goal in mind - give users an `include_dir!()` macro that lets them
embed an entire directory in their binary.

By most metrics, we've been doing phenomenally well. The crate has received a
fair amount of engagement on GitHub via pull requests and issues, and it has had
over 1 million downloads and 127 direct dependents published to crates.io alone.

However, due to work commitments and low motivation, the `include_dir` crate
hasn't received as much love as I'd like to give it over the last year or so 😞


I recently[^1], I found myself with a free weekend and a desire to be
productive, so I thought I'd take advantage of how Rust has evolved since 2017
and work through some of `include_dir`'s backlog.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/include_dir
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Project Goals and Values

I've written a fair amount of Rust code in my time and [reviewed a lot
more][u.rl.o], and that has left me with some strong opinions about authoring
crates:

1. Don't pull in unnecessary dependencies
2. Make the happy path simple and intuitive
3. Don't make me pay for what I don't use
4. Unless you have a good reason, cross-compilation should *Just Work* without
   any extra configuration or fiddling

In the past, several people have asked if I can add a level of configurability
to the `include_dir!()` macro (e.g. excluding files or using a different base
directory when resolving paths), but most of these proposals involve creating
multiple macros or overloading the existing `include_dir!()` macro with an
optional config argument. According to rule 2, these proposals would be
non-starters because there are now multiple ways of doing things.

Points 1, 3, and 4 all relate to how compilation and where the crate can be
used.

At work, my main project has a component that is compiled to WebAssembly and
deliberately doesn't use the standard library (i.e. it is a `no_std` crate).  We
have a second component that depends on TensorFlow and needs to be
cross-compiled to Windows/Linux/MacOS desktops, mobile devices, and the web.

Targeting such a large variety of platforms makes you appreciate libraries that
are platform-agnostic where cross-compiling *Just Works*, and you *really*
notice when they don't. That second component reminded me just how lucky Rust
is to have `cargo` instead of the mish-mash of Bazel, CMake, Makefiles, and
random shell scripts.

## Migrating to Newer Language Features

### Function-like Procedural Macros

Procedural macros have evolved a lot since `include_dir` was first created and
as of Rust 1.45 we no longer need hacks like [the `proc-macro-hack` crate][pmh]
to use them in expressions.

Most notably, this lets the `include_dir!()` macro parse its input directly as
a string literal instead of needing to go through a custom derive. It sounds
boring, but this means we get to drop the `syn` dependency altogether and reduce
our compile times quite a bit.

Once [the `proc_macro_quote` feature][rust-54722] is stabilised we should be
able to drop our macro's final two dependencies, `quote` and `proc_macro2`, and
just use the `proc_macro` crate directly.

Either way, dropping dependencies without losing functionality is nice.

### Const Functions

In Rust 1.46 (September 2020), a really cool feature was stabilised - the
ability to write functions which can be evaluated at compile time and in a
`const` context.

Previously, the `include_dir!()` macro would take an expression like
`include_dir!("./assets/")` and expand it to an object literal that looks
something like this:

```rs
static ASSETS: Dir<'_> = Dir {
  path: "",
  children: &[
    DirEntry::File(File {
      path: "index.html",
      contents: b"<html>..."
    }),
    DirEntry::Dir(Dir {
      path: "img",
      children: &[
        ...
      ]
    }),
  ]
};
```

On its own this seems rather innocuous, but because macros are evaluated within
the context of wherever they are called and because we are setting fields
directly, it means everything needs to be publicly accessible otherwise your
macro runs into *" field `path` of struct `Dir` is private"* errors.

However, making all your fields public means it is possible for *anyone* to use
them and due to [Hyrum's Law][hyrums-law] we know someone will invariably depend
on these internals. Therefore, if we ever want to restructure things or change
assumptions made about a *semantically-internal-but-technically-public* field
we'll have people complaining about broken builds.

{{< figure
    src="https://imgs.xkcd.com/comics/workflow.png"
    link="https://xkcd.com/1172"
    caption="(obligatory XKCD reference)"
    alt="Workflow"
>}}

As a ~~hack~~ workaround, we can use the `#[doc(hidden)]` attribute to [hide our
internal fields][hide] from a crate's documentation. That means people can still
technically access them, but only if they have deliberately read the source code
and opted in to accessing those hidden fields anyway.

Now, with the ability to call functions when initializing `static` or
`const` variables, we can just give `Dir` and `File` constructors while keeping
internal details inaccessible from the outside.

## Environment Variable Interpolation

After using `include_dir` in the wild for a while, we found a couple of
limitations with we convert the provided string into a path.

The biggest issue was that Rust doesn't guarantee which folder a procedural
macro will be executed from, meaning all relative paths would be [implicitly
resolved relative to `$CARGO_MANIFEST_DIR`][crate_root_join].

That meant your `src/lib.rs` file might look like this...

```rs
// src/lib.rs
static SRC_DIR: Dir<'_> = include_dir!(".");
```

... and looking up `lib.rs` would fail at runtime because the actual directory
structure is something completely different.

```
.
├── Cargo.lock
├── Cargo.toml
├── README.md
└── src
    └── lib.rs
```

Users also wanted to resolve paths relative to different directories, [namely
`$OUT_DIR`][out-dir], and were proposing alternate macros like
`include_dir_from_out_dir!()` or adding configuration arguments to
`include_dir!()`.

However, both of those proposals complicate the crate by creating multiple ways
to accomplish similar things, which clashes with my *Make the happy path simple
and intuitive* goal.

I ended up choosing an alternative solution that should be familiar to anyone
that has used a terminal before - environment variable interpolation.

The idea is you can write `include_dir!("$CARGO_MANIFEST_DIR/src/")` and avoid
all ambiguity. It also solves the `$OUT_DIR` problem quite elegantly if I do
say so myself.

## File Metadata

Some people were asking if we could record filesystem metadata when embedding
a directory tree.

Adding hidden fields and extra methods to a type doesn't have much of an impact
on the way people use the `include_dir!()` macro, but because it adds a level of
non-determinism to builds I opted to put this behind its own feature flag.

There are some technical difficulties in that `std::time::SystemTime` doesn't
have any public `const fn` constructors so we end up storing time as a duration
since the `UNIX_EPOCH`, but other than that it's pretty straightforward.

## Nightly Features

As well as all the normal functionality, we've created an opt-in feature flag
which lets people use `nightly`-only features to improve their developer
experience.

### Better Dependency Tracking

Something I like about build scripts is that you can tell `cargo` to only re-run
when a particular environment variable or file has changed. This helps cut down
on unnecessary recompiles by giving tools like `cargo` and `rust-analyzer` a
better idea of your dependencies, letting them improve caching accuracy.

Procedural macros have similar functionality that is currently unstable,
namely...

- [the `tracked_env` feature][tracked-env] which enables the
  `proc_macro::tracked_env::var()` function for reading environment variables,
  and
- [the `tracked_path` feature][track-path] which enables the
  `proc_macro::tracked_path::path()` function for telling the compiler that this
  build script depends on a specific path

Personally, I would prefer if the `tracked_path` feature exposed wrappers around
the `std::fs` module (e.g. `std::fs::read_dir()` and
`std::fs::read_to_string()`) because it means using a resource automatically
notifies the compiler of the dependency instead of needing to "remember" to
call `proc_macro::tracked_path::path()`, but it's a start.

My hope is that down the track, `rust-analyzer` will be able to hook into these
APIs and avoid unnecessarily reading a directory tree into memory and compiling
it into Rust constants (a fairly memory-intensive task).

### Document Feature-gated APIs

The tool used to generate pretty HTML documentation for Rust code, `rustdoc`,
has a feature which lets users see when particular functions and types are
feature-gated.

If you have ever browsed the standard library's API docs, you will be familiar
with the `This is a nightly-only experimental API` annotations that guard
unstable features.

{{< figure
    src="/img/nightly-experimental-api.png"
    link="https://doc.rust-lang.org/stable/proc_macro/tracked_path/fn.path.html"
    caption="Unstable feature annotation used in proc_macro::tracked_path::path()"
    alt="A screenshot of the proc_macro::tracked_path::path() docs" >}}

By adding `#![feature(doc_cfg)]` to the top of your `lib.rs`, any crate can get
similar annotations for code guarded by `#[cfg(...)]`.

{{< figure
    src="/img/tokio-time-sleep.png"
    link="https://docs.rs/tokio/latest/tokio/time/fn.sleep.html"
    caption="Annotation on the Tokio crate's &quot;time&quot; feature"
    alt="The Tokio crate's time feature" >}}

In version 0.7 of the `include_dir` crate I've enabled this annotation whenever
the `nightly` feature flag is enabled.

Most end users won't actually use this directly, instead they'll get the
annotations for free whenever they visit [the online API docs][docs-rs].

## Conclusion

This release introduces several big improvements, but more than that I think
it's helped me solidify my goals and values for the project.

Unfortunately, that means I will probably be closing several PRs and issues as
*"won't fix"*. I'm apologising ahead of time to those affected because I know
what it's like to really want a feature only to have the project maintainer
reject it, however I think it's important in the overall goal of making this
crate as nice to use as possible.

In my opinion, the best thing a person can say about a library or product is
that it *Just Works*, and I'm hoping this 0.7 release will bring us one step
closer to that goal.

I'd also like to use this blog post as an opportunity to ask for reviews. It
would be really nice to have extra eyes on this crate, and using a public review
system like [CREV][crev] would give people more confidence that they can use
`include_dir` in production. You can check out their [Getting Started
guide][crev-getting-started] for more.

[^1]: Well... "recently" when I started writing this post. It's been about 4
months since then 😅

[include-bytes]: https://doc.rust-lang.org/std/macro.include_bytes.html
[include-str]: https://doc.rust-lang.org/std/macro.include_str.html
[u.rl.o]: https://users.rust-lang.org/u/michael-f-bryan/summary
[pmh]: https://github.com/dtolnay/proc-macro-hack
[literal]: https://docs.rs/proc-macro2/1.0.32/proc_macro2/struct.Literal.html
[rust-54722]: https://github.com/rust-lang/rust/issues/54722
[hide]: https://github.com/Michael-F-Bryan/include_dir/blob/9fb457c1ca618a90b6e6f571c45389af9cdfada5/include_dir/src/file.rs#L7-L12
[crate_root_join]: https://github.com/Michael-F-Bryan/include_dir/blob/9fb457c1ca618a90b6e6f571c45389af9cdfada5/include_dir_impl/src/lib.rs#L22-L24
[out-dir]: https://github.com/Michael-F-Bryan/include_dir/issues/55
[hyrums-law]: https://www.hyrumslaw.com/
[include-dir]: https://crates.io/crates/include-dir
[tracked-env]: https://github.com/rust-lang/rust/issues/74690
[track-path]: https://github.com/rust-lang/rust/issues/73921
[docs-rs]: https://docs.rs/include_dir
[crev]: https://web.crev.dev/rust-reviews/
[crev-getting-started]: https://github.com/crev-dev/cargo-crev/blob/master/cargo-crev/src/doc/getting_started.md
