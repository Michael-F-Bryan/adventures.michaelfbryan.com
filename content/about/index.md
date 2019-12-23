---
title: "About Me"
---

I am a self-taught programmer and avid contributor to the open-source
community. I originally started out studying Mechanical Engineering but after
3 years of a 4 year degree found it wasn't for me and took advantage of a
Software Engineering job offer (gained thanks to my work in the software
community and involvement in the [Curtin Motorsport Team][cmt]) to change
career path.

I still enjoy learning about how the world works and leveraging my
engineering knowledge wherever I can, whether that is in the geometry and
calculus required to write a CAD/CAM program at work, or using the equations
of motion and control theory to simulate a motion controller.

In my spare time I like to learn more about computer science, in particular
embedded systems, high performance applications (e.g. games), and compilers.
It's not uncommon for me to explore a particular niche over a weekend then
write an in-depth article about what I've learned (e.g. [Audio
Processing][audio], [embedding a WebAssembly runtime][wasm], or
[Rust's Const-Generics][cg]).

My top 4 favourite programming languages at the moment:

1. [Rust](https://rust-lang.org)
2. [Go](https://golang.org)
3. [C#](https://docs.microsoft.com/en-us/dotnet/csharp/)
4. [TypeScript](https://www.typescriptlang.org/)

Some projects I've been involved in:

- [mdbook][mdbook] - a program for compiling a set of *Markdown* files into a
  website which can be viewed online. I was the maintainer from November 2017 to
  January 2019
- [The Rust FFI Guide][ffi-guide] - A tutorial which teaches people how to
  interoperate between Rustand other languages via C APIs
- [gcode-rs][gcode] - A crate for parsing g-code programs without allocations,
  primarily designed for embedded devices
- [libsignal-protocol-rs][libsignal] - An idiomatic Rust wrapper around the
  `libsignal-protocol-c` library, the canonical implementation of the
  [*Signal Protocol*][libsignal-c] (the crypto library underneath WhatsApp and
  Signal)

## Resume

You can look me up on [GitHub][gh] or [GitLab][gl] to see examples of my
work. To get a feel for my involvement in the software community you may want to
look me up on the [Rust User Forums][urlo] or [Reddit][reddit].

If you want a more formal view, check out [my resume][resume-pdf]. The entire
repository is [publicly available][resume-repo], and uses GitLab's CI system
to automatically re-compile the PDF whenever new changes are pushed to
`master`.

[resume-repo]: https://gitlab.com/Michael-F-Bryan/resume/
[resume-pdf]: https://michael-f-bryan.gitlab.io/resume/resume.pdf
[ffi-guide]: https://michael-f-bryan.github.io/rust-ffi-guide/
[mdbook]: https://crates.io/crates/mdbook
[libsignal]: https://github.com/Michael-F-Bryan/libsignal-protocol-rs
[libsignal-c]: https://github.com/signalapp/libsignal-protocol-c
[gcode]: https://github.com/Michael-F-Bryan/gcode-rs
[gh]: https://github.com/Michael-F-Bryan
[gl]: https://gitlab.com/Michael-F-Bryan
[urlo]: https://users.rust-lang.org/u/michael-f-bryan/
[reddit]: https://www.reddit.com/user/Michael-F-Bryan
[wasm]: {{< ref "/posts/wasm-as-a-platform-for-abstraction.md" >}}
[cg]: {{< ref "/posts/const-arrayvec.md" >}}
[audio]: {{< ref "/posts/audio-processing-for-dummies/index.md" >}}
[cmt]: https://www.curtinmotorsport.com