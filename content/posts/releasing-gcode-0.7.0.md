---
title: 'gcode 0.7: one parser core for streaming visitors and a thin AST'
date: '2026-03-21T21:00:00+08:00'
lastmod: '2026-08-26T15:15:33+08:00'
tags:
- Rust
- G-Code
- Open Source
---
`gcode` 0.7.0 is on [crates.io](https://crates.io/crates/gcode). If you have been on 0.6.1 (the last stable line that matched the mental model I shipped years ago), this release will break your build on purpose. That is intentional semver: the crate still parses G-code, but the way you plug into parsing is new.

In 0.6 the public surface was built around a command iterator. That was workable, but it sat awkwardly next to what a lot of callers actually need: block-shaped structure (line numbers, comments, modal `X5.0`-style words), predictable allocation behaviour, and a clean place to pause or resume. The low-allocation path and the "give me a tree" path had drifted apart.

0.7 fixes that by unifying everything on one engine in [`gcode::core`](https://docs.rs/gcode/latest/gcode/core/). The parser pushes events into your code. If you want an AST, `gcode::parse` is still there; it is a thin visitor on top of the same core, not a parallel implementation.

## Why 0.7 exists

- 0.6 exposed a stream of commands, but many tools think in blocks (lines), comments, and bare word addresses tied to spans.
- Keeping both a friendly AST and a serious embedded-style parser without duplicating grammar knowledge stopped scaling; tweaks to the facade were not enough.
- 0.7 makes one parser authoritative: visitor-driven core first, optional `Program` AST when `alloc` is acceptable.

## Who this release is for

Existing 0.6.x users deciding whether the breakage is worth it, tooling authors who want block-aware structure, and anyone who cares about deterministic memory or streaming. If you only need a parsed program and allocating is fine, you can stay on `gcode::parse` and ignore the visitor traits.

## One parser, two ways to consume it

The line I want you to leave with: there is a single parse engine, and you either implement visitors against it or you call `gcode::parse`, which implements those visitors for you. No second lexer, no forked grammar.

Try it:

```console
$ cargo add gcode@0.7
```

```rust
fn main() -> Result<(), gcode::Diagnostics> {
    let src = "G90\nG0 X50.0 Y-10";
    let program = gcode::parse(src)?;

    for block in &program.blocks {
        for code in &block.codes {
            println!("{code:?}");
        }
    }
    Ok(())
}
```

{{% notice note %}}
The `gcode` crate lives [on GitHub][repo]. Feel free to browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/gcode-rs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}


## What 0.6 felt like in practice

The old public API centered on an iterator: `gcode::parse(src)` yielded `GCode` values, and if you wanted line structure, comments, or error callbacks, you reached for `full_parse_with_callbacks` and a `Callbacks` implementation. If you needed bounded or fixed memory, you wired up `Buffers` and a `Parser` with your own buffer types.

That design was honest about constraints. It also pushed applications into an awkward shape. Example: a line like `G90 (absolute mode) X10` mixes a command, a parenthesized comment, and a modal axis word. In a command-first iterator, reconstructing "what belonged to this line" and preserving comment text next to span-accurate diagnostics took extra bookkeeping. Plenty of tools want that shape for free because post-processors, simulators, and linters think per-block, not "give me the next G-code."

I lived with that API for a long time. At some point incremental tweaks stopped helping. The right move was to delete the facade and build a core that matches the grammar.

## Which API should you use?

Use `gcode::parse` when:

- you want a complete `Program` / `Block` / `Code` tree,
- allocation is acceptable,
- you are writing tooling, analysis, transforms, or tests.

Use `gcode::core::parse` (with `default-features = false` on the dependency when you want to turn off `alloc`/`serde` defaults) when:

- you need bounded or deterministic memory,
- you want streaming-style consumption, early pause, or resume,
- you are building firmware parsers, interpreters, or a custom front-end that should own its own semantic layer.

If you are on the AST path, you can treat the visitor traits as implementation details. If you outgrow the tree, you are already using the same engine the AST uses.

## The visitor-driven core (without the full trait tour)

In 0.7, low-level parsing lives in [`gcode::core`](https://docs.rs/gcode/latest/gcode/core/). The model is push-based: you hand it a `&str`, it calls into your visitor as it walks the grammar.

```rust
gcode::core::parse(src, &mut visitor);
```

I took a lot of inspiration from serde's `Deserializer` / `Visitor` split: the parser drives the walk, and you supply types that handle the next level of structure. At a high level, the parser announces each block (roughly a line), then commands inside that block, then arguments on each command. Nested visitors line up with nested grammar rules, so the API stays explicit about block boundaries and command scope.

The important outcomes:

1. Deterministic memory. The parser does not secretly fill `Vec`s while pretending to be low-level. If your visitor does not allocate for structure, you are not paying allocation for structure in the engine.
2. Pause and resume. Visitors can return `ControlFlow::Break`; you keep a `ParserState` and call `gcode::core::resume` when you are ready to continue (bounded buffers, incremental I/O, cooperative scheduling).

Diagnostics still flow through the visitor via `HasDiagnostics`. Recoverable issues are reported and the parser keeps going when it can; syntax errors can be described in terms of `TokenType` expectations instead of ad-hoc strings.

For the exact method order and the terminal-vs-non-terminal breakdown, the [`gcode::core` module docs](https://docs.rs/gcode/latest/gcode/core/) are the right place. This post is the map; those docs are the turn-by-turn directions.

## Example: count commands without building a tree

This is the same idea as the counter example in the `gcode::core` documentation: increment integers in visitor state, return lightweight child visitors that borrow that state, and never allocate a `Program`.

```rust
use gcode::core::{
    BlockVisitor, CommandVisitor, ControlFlow, HasDiagnostics, Noop, Number,
    ProgramVisitor,
};

#[derive(Default)]
struct Counter {
    blocks: usize,
    commands: usize,
    diag: Noop,
}

impl HasDiagnostics for Counter {
    fn diagnostics(&mut self) -> &mut dyn gcode::core::Diagnostics {
        &mut self.diag
    }
}

struct BlockCounter<'a>(&'a mut Counter);

impl ProgramVisitor for Counter {
    fn start_block(&mut self) -> ControlFlow<BlockCounter<'_>> {
        self.blocks += 1;
        ControlFlow::Continue(BlockCounter(&mut *self))
    }
}

impl HasDiagnostics for BlockCounter<'_> {
    fn diagnostics(&mut self) -> &mut dyn gcode::core::Diagnostics {
        &mut self.0.diag
    }
}

struct CommandCounter<'a>(&'a mut Counter);

impl BlockVisitor for BlockCounter<'_> {
    fn start_general_code(&mut self, _number: Number) -> ControlFlow<CommandCounter<'_>> {
        self.0.commands += 1;
        ControlFlow::Continue(CommandCounter(&mut *self.0))
    }
    fn start_miscellaneous_code(&mut self, _number: Number) -> ControlFlow<CommandCounter<'_>> {
        self.0.commands += 1;
        ControlFlow::Continue(CommandCounter(&mut *self.0))
    }
    fn start_tool_change_code(&mut self, _number: Number) -> ControlFlow<CommandCounter<'_>> {
        self.0.commands += 1;
        ControlFlow::Continue(CommandCounter(&mut *self.0))
    }
}

impl HasDiagnostics for CommandCounter<'_> {
    fn diagnostics(&mut self) -> &mut dyn gcode::core::Diagnostics {
        &mut self.0.diag
    }
}

impl CommandVisitor for CommandCounter<'_> {}

let src = "G90\nG01 X5\nM3";
let mut counter = Counter::default();
gcode::core::parse(src, &mut counter);
assert_eq!(counter.blocks, 3);
assert_eq!(counter.commands, 3);
```

That is the embedded and tooling story in miniature: block structure is explicit, you can see every G/M/T entry point, and the only allocations are the ones you choose.

## The AST path is the same engine (not a second system)

The default path is `gcode::parse` behind the `alloc` feature (on by default). It returns:

```text
Result<Program, Diagnostics>
```

Internally it runs `gcode::core::parse` with an `AstBuilder` visitor and collects the tree and diagnostics. The implementation is short enough to quote in full:

```rust
pub fn parse(src: &str) -> Result<Program, Diagnostics> {
    let mut visitor = AstBuilder::new();
    core::parse(src, &mut visitor);
    visitor.finish()
}
```

That is literally `src/lib.rs`: `core::parse` is the in-crate path to `gcode::core::parse`.

So the ergonomic layer is not a toy API sitting beside a "real" parser. Learning how the core thinks about blocks and commands pays off even if you mostly use `gcode::parse`, because it is the same walk underneath.

## The document model (syntax-level on purpose)

`Program` is a list of `Block` values. Each block can carry:

- an optional line number (`N`),
- comments (semicolon or parentheses),
- G/M/T commands as `Code` variants (`General`, `Miscellaneous`, `ToolChange`),
- `word_addresses` - bare addresses like `X10.5` that appear at block level without a fresh G/M/T prefix (modal, dialect-shaped input shows up here).

This crate still does not interpret what those codes mean for your machine. Controllers disagree; modal rules disagree. Staying at syntax keeps the crate useful across dialects: the parser tells you what was written, with `Span`s anchored to every element in the original source, and your simulator or post-processor owns semantics downstream.

On the formatting side, `Display` on the AST types is there so you can round-trip sensibly when that is what you need.

## Upgrading from 0.6.x

If you are skimming for the migration table, this is it in words:

| You used to…                              | You will…                                                                                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Iterate `gcode::parse(src)` for `GCode`   | Walk `gcode::parse(src)?` for `Program.blocks`, then `block.codes`                                |
| Use `Line`                                | Think `Block`                                                                                     |
| Thread `Callbacks` for errors             | Implement diagnostics on your visitor, or use `Diagnostics` from the AST path                     |
| Tune `Buffers` / `Parser` for fixed sizes | Put your fixed-size policy in your visitor state, or rely on `Program` when `alloc` is acceptable |

How much work is that in practice?

- If you treated `gcode::parse` as a lightweight iterator over commands, expect a moderate rewrite: the top-level document model is block-oriented now, so you will remap how you thread modal state and comments.
- If you mostly need parsed structure and were heading toward an AST anyway, the `gcode::parse` path should keep you out of the visitor traits for day-to-day code; you are mostly renaming concepts and walking `blocks`.
- If you depended on the callback/buffer stack for hard memory limits, the redesign is more invasive at the type level, but the resulting visitor shape is usually simpler than bolting those concerns onto an iterator facade.

A tiny before/after helps. Old world (0.6-style iterator):

```rust
// gcode 0.6.1 — illustrative; API differs in 0.7
use gcode::Mnemonic;

let src = "G90\nG0 X50.0 Y-10";
let got: Vec<_> = gcode::parse(src).collect();
assert_eq!(got[0].mnemonic(), Mnemonic::General);
assert_eq!(
    got[0].args,
    vec![
        Argument::new('X', Value::Literal(50.0)),
        Argument::new('Y', Value::Literal(-10.0)),
    ],
);
```

New default world (0.7 with `alloc`):

```rust
use gcode::{Code, Value};

fn main() -> Result<(), gcode::Diagnostics> {
    let src = "G90 (absolute)\nG0 X50.0 Y-10";
    let program = gcode::parse(src)?;

    for block in &program.blocks {
        for code in &block.codes {
            if let Code::General(g) = code {
                let args = &g.args;
                assert_eq!(args[0].letter, 'X');
                assert_eq!(args[0].value, Value::Literal(50.0));
                assert_eq!(args[1].letter, 'Y');
                assert_eq!(args[1].value, Value::Literal(-10.0));
            }
        }
    }
    Ok(())
}
```

If you want to stay allocation-free, skip `gcode::parse` and implement the visitor traits. The `pretty_print_visitor` example in the repo is the readable reference—run `cargo run --example pretty_print_visitor`.

The AST entry point on crates.io is `gcode::parse` at the crate root (the AST types live at the top level of the crate).

## Tooling, MSRV, features

- Rust 1.85+, edition 2024. The bump is tied to this release line (see the changelog): staying current on stable keeps the crate aligned with the 2024 edition and the std/library patterns the rewrite uses.
- Default features: `alloc`, `serde`. For the core-only story, depend with `default-features = false` and call `gcode::core::parse`.

## What disappeared (and why I am mentioning it)

The WebAssembly build and npm wrapper with TypeScript bindings that existed around 0.6.1 are removed in this repo layout (called out in the [changelog](https://github.com/Michael-F-Bryan/gcode-rs/blob/main/CHANGELOG.md)). If you depended on that JavaScript surface, you will need a separate plan; the Rust crate's breaking change is only part of your migration. I am not shipping a replacement wrapper in this release; if something wasm-shaped comes back, it will be its own decision and its own versioning story.

On the plus side, there is a lot more fixture and snapshot testing in-tree now, which is what I want before telling people to trust a parser rewrite.

## What you get in one pass

- Grammar-aligned structure: blocks, commands, and arguments match how sources are written, not only how iterators are easy to write.
- One engine, two consumption modes: visitors for control, `gcode::parse` when you want a tree.
- Explicit allocation behaviour: the parser does not allocate structure for you unless you do it in a visitor.
- Better fit for line-oriented tooling and dialect-shaped input (comments, modal words, spans).
- Cooperative pause/resume at the core when you need streaming or bounded buffers.

## Where to go next

- Docs: [docs.rs/gcode](https://docs.rs/gcode/)
- Changelog: [CHANGELOG.md](https://github.com/Michael-F-Bryan/gcode-rs/blob/main/CHANGELOG.md)
- Crate: [crates.io/crates/gcode](https://crates.io/crates/gcode)

If something in real G-code trips the new lexer or block boundaries, open an issue with a small repro file. Dialects are the hard part; the fastest way to make 0.7.x better is to feed it the weird programs you actually run.
