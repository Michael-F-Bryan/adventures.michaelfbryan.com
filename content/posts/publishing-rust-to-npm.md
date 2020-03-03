---
title: "Publishing Rust to NPM"
date: "2020-03-03T23:22:37+08:00"
draft: true
tags:
- rust
- typescript
- WebAssembly
---

Based on a lot of the articles and comments I've read online, the general
sentiment seems to be that [WebAssembly][wa] is a shiny new tool with lots of
promise, but the ecosystem is nonexistent and nobody ([other than malware
authors][malware-use]) is really using it in the wild.

I don't think that's the case, though.

A while back I made [a library][gcode-rs] for parsing [G-code][wiki], the
language that most computer-controlled machines (CNC mills, 3D printers, etc.)
use. This library is written in Rust and targeted at embedded devices, but
I've been wanting to leverage the hard work done by Rust's [WebAssembly Working
Group][wasm-wg] to compile the crate to WebAssembly and publish it to NPM. 

That way others have access to battle-tested G-code parser, and it'll make it a
lot easier to create a browser-based demo in the future. It's also a good way
to see what it takes to publish WebAssembly in 2020.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/gcode-rs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Planning

## Setting Up the Build

## Creating a Minimal Wrapper

## Testing, Examples, and Benchmarks

## Conclusions

[gcode-rs]: https://github.com/Michael-F-Bryan/gcode-rs
[wiki]: https://en.wikipedia.org/wiki/G-code
[wa]: https://webassembly.org/
[malware-use]: https://www.zdnet.com/article/half-of-the-websites-using-webassembly-use-it-for-malicious-purposes/
[wasm-wg]: https://github.com/rustwasm