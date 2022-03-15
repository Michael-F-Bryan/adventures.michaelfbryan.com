---
title: "Using Webassembly in the Modern World"
date: "2022-03-13T19:34:21+08:00"
draft: true
tags:
- Rust
- WebAssembly
- Architecture
---

It's been 3 years since [the WebAssembly spec reached 1.0][wasm-1.0] and the
community has grown in leaps and bounds. Back when [I first
started][first-article] playing with WebAssembly there were only a handful of
immature implementations and you needed to write a non-trivial amount of
`unsafe` code in order to get anything working.

Nowadays, we've got nice things like [`wit-bindgen`][wit-bindgen] for defining
interfaces and generating all that `unsafe` glue code, a multitude of high
quality WebAssembly runtimes (e.g. [`wasmer`][wasmer], [`wasmtime`][wasmtime],
and [`wasmi`][wasmi] - check [Awesome Wasm][awesome] for more), and even [a
package manager][wapm] for distributing compiled `*.wasm` binaries!

{{% notice error %}}
TODO:
- Come up with a strong "thesis statement" for the article
- Make this flow nicely
- Relate it to an architecture I want to use at HOTG
{{% /notice %}}

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/modern-webassembly
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## The Problem

While browsing the Rust User Forums the other day, I came across
[Fornjot][fornjot], a code-first CAD program written by a friend, and one of
their issues jumped out at me - [*Switch model system to WASM
(hannobraun/Fornjot#71)*][Fornjot-71].

The way Fornjot currently works is by implementing each primitive component
(sketches, cuboids, cylinders, etc.) in its shared library which is loaded and
executed at runtime. That way Fornjot can provide a stable set of core
abstractions for manipulating shapes, then users can modify their models and
reload them at runtime (often called ["Hot Module Replacement"][hmr] in the
JavaScript world).

You could easily imagine an ecosystem evolving around Fornjot where users
develop their own models and share them with others.

The current system of natively compiled libraries has a couple flaws,
though:

- You need to recompile the model for every platform it may be used on
- Users will be literally downloading and executing untrusted code
- The current interface is kinda unsound because it passes Rust types across
  the FFI boundary. This is unsound because there is no guarantee the code for
  manipulating a `HashMap` in Fornjot will match up with the code for
  manipulating `HashMap` inside the model (I've been bitten by this before - see
  [`rust-lang/rust#67179`][rust-67179])

Fortunately, these are exactly the problems WebAssembly was intended to solve!

## Defining our Interfaces

If we want to solve Fornjot's model problem our first task is to define the
interfaces used by our various components to communicate, and the way we will
do this is via [WIT files][wit].

If you are familiar with gRPC, a `*.wit` file fills the same role as a
`*.proto` file. You use a domain specific language to declare the interface
between both sides, then use a code generator to generate strongly-typed glue
code.

We'll start by defining the host (Fornjot) interface because it's easiest.

```
// fornjot-v1.wit

/// Log a message at the specified verbosity level.
log: function(level: log-level, msg: string)

enum log-level {
  verbose,
  debug,
  info,
  warning,
  error,
}
```

Although the syntax is a bit unfamiliar, you should be able to get the gist.
All our host provides is a `log()` function for printing messages.

The guest's WIT file is going to be a bit more interesting. For our purposes,
each model should provide a function for finding out more about it (name,
description, version number, etc.) and a function for generating the shape.

First comes the `metadata()` function:

```
// model-v1.wit

record metadata {
    name: string,
    description: string,
    version: string,
}

/// A callback that is fired when a model is first loaded, allowing Fornjot to
/// find out more about it.
on-load: function() -> metadata
```

{{% notice info %}}
Depending on the target language, a [record][record] is normally converted into
a struct or class by the code generator. It's just a "plain old data" type with
no attached behaviour.

[record]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md#item-record-bag-of-named-fields
{{% /notice %}}

Next up we have the function that will be called by the host when it wants to
generate a model, `run()`.

```
// model-v1.wit

run: function(ctx: run-context) -> expected<shape, error>

record error {
    message: string,
}

resource run-context {
    get-argument: function(name: string) -> optional<string>
}

record shape {
    vertices: list<vertex>,
    faces: list<tuple<u32, u32, u32>>,
}

record vertex {
    x: f32,
    y: f32,
    z: f32,
}
```

The `run()` function is given a [resource][resource] called `run-context`. While
a `record` contains just data with no attached behaviour, a `resource` is more
akin to an interface object and can *only* have methods... In this case, all you
can do with a `run-context` object is use `get-argument()` to get the value of a
named argument.

{{% notice note %}}
For those that are familiar with some of the ongoing WebAssembly proposals, you
might recognise that a `resource` is meant to represent a [*WebAssembly
Interface Type*][wit-proposal].

The `wit-bindgen` tool currently implements them by manually managing the memory
of these objects and referring to them via indices, but you can imagine how one
day we'll be able to update `wit-bindgen` and magically gain access to interface
types with no extra code changes.

[wit-proposal]: https://github.com/WebAssembly/interface-types/blob/main/proposals/interface-types/Explainer.md
{{% /notice %}}

The `expected<shape, error>` should look familiar to Rustaceans. Functions in a
WIT file signal errors by returning something which is either the OK value
(`shape`) or the unsuccessful value (`error`). In Rust we might call this a
`Result`.

## Implementing The Guest

- Metadata just tells you the name, version number, and description
- Copy the [cuboid model](https://github.com/hannobraun/Fornjot/blob/main/models/cuboid/src/lib.rs)
- Errors out if there are missing parameters or negative values

## Implementing The Host

- CLI tool that you point at a `plugin/` folder
- It loads each WebAssembly file in the `plugin/` folder and extracts metadata
- When the user runs `./host some-model x=5 y=7` it will look for the
  `some-model` model and run it with `[("x", 5.0), ("y", 7.0)]` as the arguments

## Deploying using WAPM

- Publish the guest to WAPM
  - Hint that it'd be really nice if Wasmer provided a `cargo wapm` subcommand
    for publishing a crate to WAPM 😉
- Use `wapm install` to add our `guest.wasm` file to `wapm_packages/`

## Conclusions

[wasm-1.0]: https://github.com/WebAssembly/spec/releases/tag/wg-1.0
[first-article]: {{< ref "/posts/wasm-as-a-platform-for-abstraction" >}}
[wit-bindgen]: https://github.com/bytecodealliance/wit-bindgen
[wapm]: https://wapm.io/
[wasmer]: https://wasmer.io/
[wasmtime]: https://wasmtime.dev/
[wasmi]: https://github.com/paritytech/wasmi
[awesome]: https://github.com/mbasso/awesome-wasm#non-web-embeddings
[Fornjot]: https://github.com/hannobraun/Fornjot/
[Fornjot-71]: https://github.com/hannobraun/Fornjot/issues/71
[hmr]: https://webpack.js.org/concepts/hot-module-replacement/
[rust-67179]: https://github.com/rust-lang/rust/issues/67179
[wit]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md
[resource]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md#item-resource
