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

## Creating Message types

If we want to send g-code programs between the frontend and backend we'll need 
to make a couple message definitions.

```rust
// motion/src/gcode.rs

/// A message containing part of a g-code program.
#[derive(Debug, Default, Copy, Clone, PartialEq, Eq)]
pub struct GcodeProgram<'a> {
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
    pub fn new(first_line: u32, text: &'a str) -> GcodeProgram<'a> {
        assert!(text.len() < Self::MAX_TEXT_SIZE);

        GcodeProgram { first_line, text }
    }
}
```

We'll also need to add the same definitions to the frontend code. For the sake
of convenience, the `sim` crate will expose a WASM function for writing a
`GcodeProgram` message to a `Uint8Array`.

```rust
// sim/src/utils.rs

#[wasm_bindgen]
pub fn encode_gcode_program(first_line: u32, text: &str) -> Uint8Array {
    let mut buffer = [0; anpp::Packet::MAX_PACKET_SIZE];
    let msg = GcodeProgram::new(first_line, text);
    let bytes_written = buffer
        .pwrite_with(msg, 0, Endian::network())
        .expect("Will always succeed");

    // note: this is effectively a &[u8] slice into the buffer on the stack,
    // hence the seemingly redundant copy
    let view_into_stack_buffer = Uint8Array::from(&buffer[..bytes_written]);
    Uint8Array::new(&view_into_stack_buffer )
}
```

{{% notice note %}}
The `Pwrite` trait from `scroll` is used here to copy the `GcodeProgram`
message's fields directly to a byte buffer. `GcodeProgram` uses a `&str`
borrowed string so we actually needed to manually implement
`scroll::ctx::TryIntoCtx` instead of using the custom derive.

The details have been elided for simplicity (and because the implementation is
rather straightforward), but check [`motion/src/gcode.rs`][1] out on GitHub if
you're interested in how `scroll`'s `TryIntoCtx` trait can be implemented.

[1]: https://github.com/Michael-F-Bryan/adventures-in-motion-control/blob/d95e8805f866ed92a73a5e7a060163a262796f8d/motion/src/gcode.rs
{{% /notice %}}

Next, we'll add the corresponding TypeScript class and a method for converting
it to an ANPP `Packet`.

```ts
// frontend/src/messaging.ts

export type Request = GoHome | GcodeProgram;

export class GcodeProgram {
    public readonly firstLine: number;
    public readonly text: Uint8Array;
}

// frontend/src/CommsBus.ts

import * as wasm from "aimc_sim";

function toPacket(request: Request): Packet {
    if (request instanceof GoHome) {
        ...
    } else if (request instanceof GcodeProgram) {
        const { firstLine, text } = request;
        return new Packet(5, wasm.encode_gcode_program(firstLine, text));
    } else {
        ...
    }
}
```

## Sending the Messages

Now we've got definitions for a `GcodeProgram` message, we'll need a way to 
construct and send those messages from the frontend to the backend.

Let's add a text input to the `Controls` panel which can be used to send g-code
to the backend one line at a time.

```vue
// frontend/src/components/Control.vue

<template>
  <div>
    ...

    <b-form inline @submit="onSendGcode">
      <label class="sr-only" for="gcode-send">Manually send g-code</label>
      <b-input-group prepend="Manual g-code" class="mb-2 mr-sm-2 mb-sm-0">
        <b-input id="gcode" v-model="gcodeProgram"></b-input>
      </b-input-group>

      <b-button type="submit" variant="primary">Send</b-button>
    </b-form>
  </div>
</template>

<script lang="ts">
@Component
export default class Controls extends Vue {
  public gcodeProgram: string = "";
  ...

  public onSendGcode(e: Event) {
    e.preventDefault();

    const program = this.gcodeProgram;
    this.gcodeProgram = "";

    if (program.length > 0) {
      console.log("Sending", program);
      this.sendGcode(program)
        .then(resp => console.log(resp.toString(), resp))
        .catch(console.error);
    }
  }

  private sendGcode(program: string) {
    const buffer = new TextEncoder().encode(program);
    return this.send(new GcodeProgram(0, 0, buffer));
  }
}
</script>
```

That's about all the frontend code we'll need to write today. Let's move on to
the backend.

At the moment, our `Router` isn't letting the `Motion` system know when a 
`GcodeProgram` message is received. Let's fix that.


```rust
// sim/src/router.rs

impl<'a> MessageHandler for Router<'a> {
    fn handle_message(&mut self, msg: &Packet) -> Result<Packet, CommsError> {
        match msg.id() {
            ...
            GcodeProgram::ID => dispatch::<_, GcodeProgram, _>(
                self.motion,
                msg.contents(),
                map_result,
            ),
            ...
        }
```

To make the compiler happy, we'll implement 
`aimc_hal::messaging::Handler<GcodeProgram<'_>>` for `Motion` though using the
good old `unimplemented!()` macro. We can use the panic message and backtrace as
a crude sanity check to make sure everything is wired up correctly.

```rust
// motion/src/motion.rs

impl Handler<GcodeProgram<'_>> for Motion {
    type Response = Result<Ack, Nack>;

    fn handle(&mut self, gcode: GcodeProgram<'_>) -> Self::Response {
        unimplemented!("Received a {:?}", gcode);
    }
}
```

Typing `G90 asdf` into the *"Manual g-code"* box and pressing enter gives us a
nice stack trace containing the `GcodeProgram` message:

```
panicked at 'not yet implemented: Received a GcodeProgram { first_line: 0, text: "G90 asdf" }', motion/src/motion.rs:85:9

Stack:

__wbg_new_59cb74e423758ede@webpack-internal:///../sim/pkg/aimc_sim.js:306:13
__wbg_new_59cb74e423758ede@http://localhost:8080/app.js:774:74
console_error_panic_hook::hook::h84b8e021e326f0d3@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[36]:0x3b71
core::ops::function::Fn::call::hd092999f4ce770e6@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[253]:0xa677
std::panicking::rust_panic_with_hook::hd6b16d2853327786@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[74]:0x75ab
std::panicking::continue_panic_fmt::h70cda879a43284ba@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[110]:0x8dea
rust_begin_unwind@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[250]:0xa65b
core::panicking::panic_fmt::hddbe1a30080e00b8@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[142]:0x99f6
<aimc_motion::motion::Motion as aimc_hal::messaging::Handler<aimc_motion::gcode::GcodeProgram>>::handle::hc98bbf6472c174d6@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[104]:0x8b04
<aimc_sim::router::Router as aimc_comms::MessageHandler>::handle_message::hf38b3f9dfc446397@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[33]:0x33f2
<aimc_comms::Communications as aimc_hal::system::System<I,aimc_comms::Outputs<T,M>>>::poll::h2b779ff57286c828@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[42]:0x47f4
aimc_sim::app::App::poll::hb2d5c96993e5ecd2@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[55]:0x5cc0
poll@http://localhost:8080/62ee0e08a150c8392d23.module.wasm:wasm-function[135]:0x97ce
poll@webpack-internal:///../sim/pkg/aimc_sim.js:91:52
animate@webpack-internal:///./node_modules/cache-loader/dist/cjs.js?!./node_modules/babel-loader/lib/index.js!./node_modules/ts-loader/index.js?!./node_modules/cache-loader/dist/cjs.js?!./node_modules/vue-loader/lib/index.js?!./src/App.vue?vue&type=script&lang=ts&:108:48
```

Excellent!

## Processing the G-Code Program

Now we're able to send a gcode program as text to the backend we need to turn
it into something more machine-readable. Fortunately most of the heavy lifting
of parsing is already handled for us, courtesy of the [`gcode`][gcode] crate.


The first step is to create a `Translator` for turning the generic
*"received the number `01` `G` command with arguments `(X, 42.0)` and `(Y,
-3.14)` on line 123"* message into something more specific to our use case.

```rust
// motion/src/movements/mod.rs

#[derive(Debug, Clone, PartialEq)]
pub struct Translator {}

impl Translator {
    pub fn translate<C: Callbacks>(&mut self, _command: &GCode, _cb: C) {
        unimplemented!()
    }
}

pub trait Callbacks {}

impl<'a, C: Callbacks + ?Sized> Callbacks for &'a mut C {}
```

{{% notice note %}}
If you are familiar with parsers, this would be referred to as a *Push
Parser*. We're notifying the caller of parse results via callbacks that get
invoked during the parsing process.

An alternative approach is called *Pull Parsing*. This is where the caller 
will ask the parse for the next item, typically implemented using the 
`Iterator` trait.

*Push Parsing* happens to be slightly easier to implement and test in this
case, so that's what we'll go with.
{{% /notice %}}

We'll also want a way to report warnings (e.g. unsupported commands) or
errors (e.g. *"this command would move an axis out of bounds"*) back to the
user.

```rust
// motion/src/movements/mod.rs

pub trait Callbacks {
    fn unsupported_command(&mut self, _command: &GCode) {}
    fn invalid_argument(
        &mut self,
        _command: &GCode,
        _arg: char,
        _reason: &'static str,
    ) {}
}
```

For convenience, we'll make a helper method which uses parses text using the
`gcode` crate then iterates over every command invoking `translate()`.

```rust
// motion/src/movements/mod.rs

impl Translator {
    ...

    pub fn translate_src<C, G>(
        &mut self,
        src: &str,
        cb: &mut C,
        parse_errors: &mut G,
    ) where
        C: Callbacks + ?Sized,
        G: gcode::Callbacks + ?Sized,
    {
        for line in gcode::parse_with_callbacks(src, parse_errors) {
            for command in line.gcodes() {
                self.translate(&command, &mut *cb);
            }
        }
    }
}
```

Annoyingly, the gcode language is only loosly specified with each vendor using
their own dialect and associating different meanings to different commands. 

For our purposes we'll only need to support the most common commands, though.

These are:

| Command             | Parameters             | Description                              |
| ------------------- | ---------------------- | ---------------------------------------- |
| *Motions*           | *(X Y Z apply to all)* |                                          |
| G00                 |                        | Rapid Move                               |
| G01                 |                        | Linear Interpolation                     |
| G02,G03             | I J K  or R            | Circular Interpolation (CW or ACW)       |
| G04                 | P                      | Pause for `P` seconds                    |
| *Coordinate System* |                        |                                          |
| G20                 |                        | Inches                                   |
| G21                 |                        | Millimeters                              |
| G90                 |                        | Absolute coordinates                     |
| G91                 |                        | Relative coordinates                     |
| *Miscellaneous*     |                        |                                          |
| M30                 |                        | End of program. <br/> (Stops all motion) |

{{% notice info %}}
Some links for further reading:

- [Wikipedia](https://en.wikipedia.org/wiki/G-code)
- [LinuxCNC "G-Code" Quick Reference](http://linuxcnc.org/docs/html/gcode.html)
- [The flavour of gcode recognised by RepRap firmware](https://reprap.org/wiki/G-code)
- [The NIST RS274NGC Interpreter](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=823374)
{{% /notice %}}


[next-step]: {{< ref "wiring-up-communication/index.md#the-next-step" >}}
[gcode]: https://crates.io/crates/gcodekk