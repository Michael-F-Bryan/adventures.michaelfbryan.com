---
title: "Bringing include_dir Into the Modern Era"
date: "2021-11-03T20:16:16+08:00"
draft: true
tags:
- Rust
---

Way back in mid-2017 I created a crate called `include_dir` with a single goal
in mind - give users an `include_dir!()` macro that lets them embed an entire
directory in their binary.

- almost 1 million total downloads
- hasn't been given much love of late
- Rust has evolved since then, especially around procedural macros
- I've also learned a lot through my day job, generating Rust code that gets
  compiled to WebAssembly

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/include_dir
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## What is `include_dir!()` and Why Should I Care?

The sole purpose of the `include_dir` crate is to expose a macro called
(\*surprise, surprise\*) `include_dir!()`.

This is directly analogous to the [`include_str!()`][include-str] and
[`include_bytes!()`][include-bytes] macros from the standard library, except
instead of embedding a single file in your binary, it will embed an entire
folder.

I've written a fair amount of Rust code in my time and [reviewed a lot
more][u.rl.o], and that has left me with some strong opinions about authoring
crates:

1. Don't pull in unnecessary dependencies
2. Make the happy path simple and intuitive
3. Don't make me pay for what I don't use
4. Unless you have a good reason, crates should be usable without the standard
   library and cross-compilation should *Just Work* without any extra
   configuration or fiddling

In the past, several people have asked if I can add a level of configurability
to the `include_dir!()` macro (e.g. excluding files or using a different base
directory when resolving paths), but most of these proposals involve creating
multiple macros or overloading the existing `include_dir!()` macro with an
optional config argument. According to rule 2, these proposals would be
non-starters.

Points 1, 3, and 4 all relate to how compilation and where the crate can be
used.

At work, my main project has a component that is compiled to WebAssembly and
deliberately doesn't use the standard library (i.e. it is a `no_std` crate).
We have another component that is compiled to Windows/Linux/MacOS desktops,
mobile devices, and the web.

Targeting such a large variety of platforms makes you appreciate libraries that
are platform-agnostic where cross-compiling *Just Works*, and you *really*
notice when they don't.

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
directly, it means everything needs to be publicly accessible (otherwise you
run into *" field `path` of struct `Dir` is private"*).

However, making all your fields public means it is possible for *anyone* to use
the internals of `Dir` and `File`, meaning people will complain about broken
builds if we ever want to restructure things or change assumptions made about a
field.

As a ~~hack~~ workaround, we can use the `#[doc(hidden)]` attribute to [hide our
internal fields][hide] from a crate's documentation. That means people can still
technically access them, but only if they have deliberately read the source code
and chosen to access hidden fields anyway.

Now, with the ability to call functions when initializing `static` or
`const` variables we can just give `Dir` and `File` constructors while keeping
internal details internal.

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
all ambiguity. It also solves the `$OUT_DIR` problem quite elegantly (if I do
say so myself).

## File Metadata

- Embed things like the last modified/created/accessed time
- Hidden behind a feature flag
- The method returns an `Option<Metadata>` containing a bunch of `SystemTime`'s
- Can store times as a duration since `UNIX_EPOCH` because
  `Duration::from_secs()` is a `const fn`
- https://github.com/Michael-F-Bryan/include_dir/pull/63

## Nightly Features

As well as all the normal functionality, we've created an opt-in feature flag
which lets people use `nightly`-only features to improve their developer
experience.

### Better Dependency Tracking

Something I like about build scripts is that you can tell `cargo` to only re-run
when a particular environment variable or file has changed. This helps cut down
on unnecessary recompiles by giving tools like `cargo` and `rust-analyzer` a
better idea of your dependencies so they can improve caching accuracy.

- Use the `tracked_env` and `tracked_path` features to tell the compiler when
  we need to be recomputed
- Use `doc_cfg` for better docs
- Use `span.source_file()` for relative imports

## Conclusion

[include-bytes]: https://doc.rust-lang.org/std/macro.include_bytes.html
[include-str]: https://doc.rust-lang.org/std/macro.include_str.html
[u.rl.o]: https://users.rust-lang.org/u/michael-f-bryan/summary
[pmh]: https://github.com/dtolnay/proc-macro-hack
[literal]: https://docs.rs/proc-macro2/1.0.32/proc_macro2/struct.Literal.html
[rust-54722]: https://github.com/rust-lang/rust/issues/54722
[hide]: https://github.com/Michael-F-Bryan/include_dir/blob/9fb457c1ca618a90b6e6f571c45389af9cdfada5/include_dir/src/file.rs#L7-L12
[crate_root_join]: https://github.com/Michael-F-Bryan/include_dir/blob/9fb457c1ca618a90b6e6f571c45389af9cdfada5/include_dir_impl/src/lib.rs#L22-L24
[out-dir]: https://github.com/Michael-F-Bryan/include_dir/issues/55
