---
title: 'Rewriting the gcode crate: why 0.7 was rebuilt from the ground up'
date: '2026-03-21T21:00:00+08:00'
tags:
- Rust
- G-code
- Open Source
---
`gcode` 0.7.0 is on [crates.io](https://crates.io/crates/gcode). If you have been on 0.6.1 (the last stable line that matched the mental model I shipped years ago), this release will break your build on purpose. Semver is doing what it is for: the crate still parses G-code, but the way you plug into parsing is new, and I hope it lines up with how programs actually look on the wire.

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

The point of the rewrite is not a marketing bullet list. It is a different parser boundary: a visitor-driven core, and an optional AST on top that is allowed to stay thin because it is just another consumer of that core.

{{% notice note %}}
The `gcode` crate lives [on GitHub][repo]. Feel free to browse through and
steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/gcode-rs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}


## What 0.6 felt like in practice

The old public API centered on an iterator: `gcode::parse(src)` yielded `GCode` values, and if you wanted line structure, comments, or error callbacks, you reached for `full_parse_with_callbacks` and a `Callbacks` implementation. If you were serious about fixed memory, you wired up `Buffers` and a `Parser` with your own buffer types.

That design was honest about constraints. It also pushed applications into an awkward shape: you got a stream of commands, but a lot of real tools think in lines and blocks, modal state, and diagnostics tied to spans - not "give me the next G-code."

I lived with that API for a long time. At some point, incremental tweaks stopped helping. The right move was to delete the facade and build a core that matches the grammar.

## The new shape: visitor core first

In 0.7, parsing lives in [`gcode::core`](https://docs.rs/gcode/latest/gcode/core/). The engine is push-based: you hand it a `&str`, it hands you events.

The entry point is:

```rust
gcode::core::parse(src, &mut visitor);
```

I took a lot of inspiration from serde's `Deserializer` / `Visitor` split: the parser drives the walk, and you answer with types that describe what to do next at each step.

The visitor types are wired to the g-code grammar itself. **Terminals** show up as methods you implement—plain callbacks for tokens and leaf data. **Non-terminals** are different: when the parser enters a subtree (a block, a command, and so on), you return a fresh visitor object scoped to that non-terminal, and the engine keeps calling into *that* visitor until the rule finishes. Nesting in the API mirrors nesting in the grammar.

Your visitor implements a small trait hierarchy:

- `ProgramVisitor` — start of each block (roughly: a line of source).
- `BlockVisitor` — line numbers, comments, program numbers, `%` delimiters, modal `word_address` calls, and the starts of G/M/T commands.
- `CommandVisitor` — arguments on a single G/M/T command until `end_command`.

Concretely: when you enter a command, you return a new `CommandVisitor`; when the line ends, the block visitor is consumed in `end_line`. The module docs spell out the call order. The gist: the parser never builds a tree for you unless you allocate in the visitor.

That matters for two reasons:

1. Deterministic memory. The parser is not secretly filling `Vec`s while pretending to be low-level just because you enabled a feature flag. If you do not allocate in your visitor, you are not allocating for structure. Full stop.
2. Streaming and pause. The API supports `ControlFlow::Break` and resuming with `ParserState` / `resume` when you need to stop mid-program and pick up later (bounded buffers, incremental I/O, that sort of thing).

Diagnostics sit in the same story. Visitors expose a `Diagnostics` implementation; the parser emits recoverable issues and keeps going when it can. Syntax errors talk about expectations in terms of `TokenType`, not ad-hoc strings, which makes "what went wrong?" easier to handle mechanically.

## The ergonomic layer is just a visitor

If you are not wiring a CNC firmware parser this afternoon, you probably want the default path: `gcode::parse` behind the `alloc` feature (on by default). It returns:

```text
Result<Program, Diagnostics>
```

Internally, this is nothing fancy: it runs the same `core::parse` engine with an `AstBuilder` visitor and collects the tree and diagnostics. The implementation is short enough to quote in full:

```rust
pub fn parse(src: &str) -> Result<Program, Diagnostics> {
    let mut visitor = AstBuilder::new();
    core::parse(src, &mut visitor);
    visitor.finish()
}
```

That is literally `src/lib.rs`: `core::parse` is the in-crate path to `gcode::core::parse`.

One parser, two ways to consume it. No second grammar, no duplicated lexer hiding in a "high-level" module.

## The document model (syntax-level on purpose)

`Program` is a list of `Block` values. Each block can carry:

- an optional line number (`N`),
- comments (semicolon or parentheses),
- G/M/T commands as `Code` variants (`General`, `Miscellaneous`, `ToolChange`),
- `word_addresses` - bare addresses like `X10.5` that appear at block level without a fresh G/M/T prefix (modal, dialect-shaped input shows up here).

This crate still does not interpret what those codes mean for your machine. Controllers disagree; modal rules disagree. The parser's job is to tell you what was written, with `Span`s anchored in the original source, so your simulator or post-processor can take it from there.

On the formatting side, `Display` on the AST types is there so you can round-trip sensibly when that is what you need.

## Upgrading from 0.6.x

If you are skimming for the migration table, this is it in words:

| You used to…                              | You will…                                                                                         |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Iterate `gcode::parse(src)` for `GCode`   | Walk `gcode::parse(src)?` for `Program.blocks`, then `block.codes`                                |
| Use `Line`                                | Think `Block`                                                                                     |
| Thread `Callbacks` for errors             | Implement diagnostics on your visitor, or use `Diagnostics` from the AST path                     |
| Tune `Buffers` / `Parser` for fixed sizes | Put your fixed-size policy in your visitor state, or rely on `Program` when `alloc` is acceptable |

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

- Rust 1.85+, edition 2024.
- Default features: `alloc`, `serde`. For the core-only story, depend with `default-features = false` and call `gcode::core::parse`.

## What disappeared (and why I am mentioning it)

The wasm npm wrapper that existed around 0.6.1 is gone in this repo layout. If you depended on that JavaScript surface, you will need a separate plan - the Rust crate's breaking change is only part of your migration.

On the plus side, there is a lot more fixture and snapshot testing in-tree now, which is what I want before telling people to trust a parser rewrite.

## Where to go next

- Docs: [docs.rs/gcode](https://docs.rs/gcode/)
- Changelog: [CHANGELOG.md](https://github.com/Michael-F-Bryan/gcode-rs/blob/main/CHANGELOG.md)
- Crate: [crates.io/crates/gcode](https://crates.io/crates/gcode)

If something in real G-code trips the new lexer or block boundaries, open an issue with a small repro file. Dialects are the hard part; the fastest way to make 0.7.x better is to feed it the weird programs you actually run.
