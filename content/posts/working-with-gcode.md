---
title: "Working With G-Code"
date: "2019-10-13T16:55:25+08:00"
draft: true
tags:
- adventures-in-motion-control
- rust
---

As mentioned in [the previous post][next-step] there are a handful of tasks 
which may be tackled next, but only one of them really allows us to make progress
towards our goal of implementing the simulated firmware for a 3D Printer.

Let's send the motion controller some g-code.

## Messaging

If we want to send g-code programs between the frontend and backend we'll need 
to make a couple message definitions.

```rust
// motion/src/gcode.rs

/// A message containing part of a g-code program.
#[derive(Debug, Default, Copy, Clone, PartialEq, Eq)]
pub struct GcodeProgram<'a> {
    /// A number used to indicate which chunk of the program this is.
    ///
    /// The `chunk_number` should be reset to `0` when sending a new program
    /// and incremented for every chunk thereafter, wrapping back to `0` on
    /// overflow.
    chunk_number: u16,
    /// The (zero-based) line number this chunk starts on.
    ///
    /// Primarily used for error messages and progress reporting.
    first_line: u32,
    /// The g-code program itself.
    text: &'a str,
}
```

Something to keep in mind is the full `GcodeProgram` message needs to fit
inside an `anpp::Packet`. That means we'll need to limit the length of the
`text` field.

```rust
// motion/src/gcode.rs

impl<'a> GcodeProgram<'a> {
    /// The message ID used with [`anpp::Packet::id()`].
    pub const ID: u8 = 5;
    /// The maximum amount of text a [`GcodeProgram`] message can contain.
    pub const MAX_TEXT_SIZE: usize = anpp::Packet::MAX_PACKET_SIZE
        - mem::size_of::<u16>()
        - mem::size_of::<u32>();

    /// Create a new [`GcodeProgram`] message.
    ///
    /// # Panics
    ///
    /// The `text` must be smaller than [`GcodeProgram::MAX_TEXT_SIZE`] bytes
    /// long.
    pub fn new(
        chunk_number: u16,
        first_line: u32,
        text: &'a str,
    ) -> GcodeProgram<'a> {
        assert!(text.len() < Self::MAX_TEXT_SIZE);

        GcodeProgram { chunk_number, first_line, text }
    }
}
```

We'll also need to add the same definitions to the frontend code.


[next-step]: {{< ref "wiring-up-communication/index.md#the-next-step" >}}