---
title: "Using Webassembly in the Modern World"
date: "2022-03-13T19:34:21+08:00"
draft: true
tags:
- Rust
- WebAssembly
- Architecture
---

- Mention using WebAssembly at work
- Obligatory "We're hiring!"
-

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/modern-webassembly
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Problem Space

- Use [`hannobraun/Fornjot#71`](https://github.com/hannobraun/Fornjot/issues/71)
  as a case study
- Imagine you want people to provide functionality while satisfying a particular
  interface
  - C APIs tend to contain UB (functions not type checked, `unsafe`, struct
    layouts change, etc.)
- Language-agnostic
- Sandboxed
- Need some mechanism for plugin management

## Architecture

- The Guest
  - Library that gets compiled to WebAssembly
  - Can only use functionality provided by the host
- The Host
  - Normal executable running on the developer's machine
  - Loads one or more guest modules at runtime
  - Uses Wasmer for executing WebAssembly
- Interfaces are defined using WIT files

## Defining our Interfaces

- `guest-v1.wit`
  - `on-loaded: function() -> Metadata`
  - `run: function(args: list<tuple<string, f64>>) -> expected<vertices, error>`
- `host-v1.wit`
  - `log: function(level: log-level, msg: string, arguments: list<argument>)`

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
