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

To turn the gcode commands into something more usable we're going to need a
type to represent a 3-dimensional point in space. We *could* pull in a 3rd party
geometry library for this, but sometimes [*"a little copying is better than a
little dependency"*][proverbs].

```rust
// motion/src/movements/point.rs

use core::ops::Add;
use uom::{si::{f32::Length, length::Unit}, Conversion};

pub struct Point {
    pub x: Length,
    pub y: Length,
    pub z: Length,
}

impl Point {
    /// Create a new [`Point`] in a particular unit system.
    pub fn new<N>(x: f32, y: f32, z: f32) -> Self
    where
        N: Unit + Conversion<f32, T = f32>,
    {
        Point {
            x: Length::new::<N>(x),
            y: Length::new::<N>(y),
            z: Length::new::<N>(z),
        }
    }

    /// Get the underlying values in a particular unit system.
    ///
    /// # Examples
    ///
    /// ```rust
    /// use aimc_motion::movements::Point;
    /// use uom::si::length::{inch, millimeter};
    ///
    /// let p = Point::new::<inch>(10.0, 20.0, 30.0);
    /// # let p = p.round::<millimeter>(); // ugh, floating point math...
    /// assert_eq!(p.converted_to::<millimeter>(), (254.0, 254.0*2.0, 254.0*3.0));
    /// ```
    pub fn converted_to<N>(self) -> (f32, f32, f32)
    where
        N: Unit + Conversion<f32, T = f32>,
    {
        (self.x.get::<N>(), self.y.get::<N>(), self.z.get::<N>())
    }

    /// Round `x`, `y`, and `z` to the nearest integer when converted to `N`
    /// units.
    pub fn round<N>(self) -> Self
    where
        N: Unit + Conversion<f32, T = f32>,
    {
        Point {
            x: self.x.round::<N>(),
            y: self.y.round::<N>(),
            z: self.z.round::<N>(),
        }
    }
}

impl Add<Point> for Point { ... }
```

We also need some helper enums to keep track of the coordinate system and units
being used.

```rust
// motion/movements/translator.rs

enum CoordinateMode {
    Absolute,
    Relative,
}

impl Default for CoordinateMode {
    fn default() -> CoordinateMode { CoordinateMode::Absolute }
}

enum Units {
    Millimetres,
    Inches,
}

impl Default for Units {
    fn default() -> Units { Units::Millimetres }
}
```

Next, let's add a couple methods which use these enums to calculate absolute
locations and the end position for a *motion* command. The `Translator` type
will need a couple new fields too.

```rust
// motion/src/movements/translator.rs

pub struct Translator {
    current_location: Point,
    coordinate_mode: CoordinateMode,
    units: Units,
    feed_rate: Velocity,
}

impl Translator {
    ...

    fn calculate_end(&self, command: &GCode) -> Point {
        let x = command.value_for('X').unwrap_or(0.0);
        let y = command.value_for('Y').unwrap_or(0.0);
        let z = command.value_for('Z').unwrap_or(0.0);
        self.absolute_location(x, y, z)
    }

    fn absolute_location(&self, x: f32, y: f32, z: f32) -> Point {
        let raw = match self.units {
            Units::Millimetres => Point::new::<millimeter>(x, y, z),
            Units::Inches => Point::new::<inch>(x, y, z),
        };

        match self.coordinate_mode {
            CoordinateMode::Absolute => raw,
            CoordinateMode::Relative => raw + self.current_location,
        }
    }

    fn calculate_feed_rate(&self, command: &GCode) -> Velocity {
        let raw = match command.value_for('F') {
            Some(f) => f,
            None => return self.feed_rate,
        };

        // there's no inch_per_minute unit, so calculate inch/minute manually
        let time = Time::new::<minute>(1.0);

        match self.units {
            Units::Inches => Length::new::<inch>(raw) / time,
            Units::Millimetres => Length::new::<millimeter>(raw) / time,
        }
    }

    /// Gets the centre of a circular interpolate move (G02, G03), bailing out
    /// if the centre coordinates aren't provided.
    fn get_centre(&self, command: &GCode) -> Result<Point, char> {
        let x = command.value_for('I').ok_or('I')?;
        let y = command.value_for('J').ok_or('J')?;

        // TODO: Take the plane into account (G17, G18, G19)
        Ok(Point {
            x: self.to_length(x),
            y: self.to_length(y),
            z: self.current_location.z,
        })
    }
}
```

We need a way to notify the caller when a motion is translated, so the 
`Callbacks` trait needs a couple more methods.

```rust
// motion/src/movements/translator.rs

pub trait Callbacks {
    fn unsupported_command(&mut self, _command: &GCode) {}
    fn invalid_argument(
        &mut self,
        _command: &GCode,
        _arg: char,
        _reason: &'static str,
    ) {
    }

    fn end_of_program(&mut self) {}
    fn linear_interpolate(
        &mut self,
        _start: Point,
        _end: Point,
        _feed_rate: Velocity,
    ) {
    }
    fn circular_interpolate(
        &mut self,
        _start: Point,
        _centre: Point,
        _end: Point,
        _direction: Direction,
        _feed_rate: Velocity,
    ) {
    }
    fn dwell(&mut self, _period: Duration) {}
}

pub enum Direction {
    Clockwise,
    Anticlockwise,
}
```

From here on out, processing a `GCode` command becomes mostly a mechanical 
process of:

1. `match`ing on the `Mnemonic`
2. `match`ing on the `major_number`
3. Convert arguments to `uom` types
4. Depending on the operation:
   - If it is a *motion* command, notify the caller via the callbacks
   - Update some internal state (e.g. if changing from inches to millimetres)
   - Maybe notify the caller if something unexpected/invalid was encountered

Let's handle the *Miscellaneous* commands first, seeing as there's only one
of them (`M30`).

```rust
// motion/src/movements/translator.rs

impl Translator {
    pub fn translate<C: Callbacks>(&mut self, command: &GCode, mut cb: C) {
        match command.mnemonic() {
            Mnemonic::Miscellaneous => self.handle_miscellaneous(command, cb),
            _ => cb.unsupported_command(command),
        }
    }

    fn handle_miscellaneous<C: Callbacks>(
        &mut self,
        command: &GCode,
        mut cb: C,
    ) {
        match command.major_number() {
            30 => cb.end_of_program(),
            _ => cb.unsupported_command(command),
        }
    }
}
```

Handling the motion commands requires us to massage the arguments a bit to take
into account things like units and coordinate systems, so when `match`ing on the
`major_number` we'll pull the handling code into their own methods.

```rust
// motion/src/movements/translator.rs

impl Translator {
    pub fn translate<C: Callbacks>(&mut self, command: &GCode, mut cb: C) {
        match command.mnemonic() {
            Mnemonic::Miscellaneous => self.handle_miscellaneous(command, cb),
            Mnemonic::General => self.handle_general(command, cb),
            _ => cb.unsupported_command(command),
        }
    }

    fn handle_general<C: Callbacks>(&mut self, command: &GCode, mut cb: C) {
        match command.major_number() {
            0 | 1 => self.handle_linear_interpolate(command, cb),
            2 | 3 => self.handle_circular_interpolate(command, cb),
            4 => self.handle_dwell(command, cb),

            20 => self.units = Units::Inches,
            21 => self.units = Units::Millimetres,
            90 => self.coordinate_mode = CoordinateMode::Absolute,
            91 => self.coordinate_mode = CoordinateMode::Relative,

            _ => cb.unsupported_command(command),
        }
    }

    fn handle_dwell<C: Callbacks>(&mut self, command: &GCode, mut cb: C) { ... }
    fn handle_linear_interpolate<C: Callbacks>(
        &mut self,
        command: &GCode,
        mut cb: C,
    ) { ... }
    fn handle_circular_interpolate<C: Callbacks>(
        &mut self,
        command: &GCode,
        mut cb: C,
    ) { ... }
}
```

The dwell command (`G04`) is easiest to handle. It has a single required 
argument, `P`, the time to wait in seconds.

```rust
// motion/src/movements/translator.rs

impl Translator {
    ...

    fn handle_dwell<C: Callbacks>(&mut self, command: &GCode, mut cb: C) {
        match command.value_for('P') {
            Some(dwell_time) => cb.dwell(Duration::from_secs_f32(dwell_time)),
            None => {
                cb.invalid_argument(command, 'P', "Dwell time not provided")
            },
        }
    }
}
```

The linear interpolate commands (`G00` and `G01`) are a bit more complicated.
We need to determine the end point and feed rate (using the helpers defined
earlier) then after notifying the caller, the `Translator`'s state needs to be
updated with the new values.

```rust
// motion/src/movements/translator.rs

impl Translator {
    ...

    fn handle_linear_interpolate<C: Callbacks>(
        &mut self,
        command: &GCode,
        mut cb: C,
    ) {
        let end = self.calculate_end(command);
        let feed_rate = self.calculate_feed_rate(command);
        cb.linear_interpolate(self.current_location, end, feed_rate);

        self.current_location = end;
        self.feed_rate = feed_rate;
    }
}
```

And finally, we need to implement the circular interpolation commands (`G02` and
`G03`). Circular interpolation is handled in much the same way as linear
interpolation, except we also need to account for the centre point and direction
of movement.

To make things simpler, we'll require the user to specify the centre location
using `I` and `J`. Working with different definitions or in different planes is
left as an exercise for later.

```rust
// motion/src/movements/translator.rs

impl Translator {
    ...

    fn handle_circular_interpolate<C: Callbacks>(
        &mut self,
        command: &GCode,
        mut cb: C,
    ) {
        let end = self.calculate_end(command);
        let start = self.current_location;
        let feed_rate = self.calculate_feed_rate(command);
        let direction = if command.major_number() == 2 {
            Direction::Clockwise
        } else {
            Direction::Anticlockwise
        };

        match self.get_centre(command) {
            Ok(centre) => {
                cb.circular_interpolate(
                    start, centre, end, direction, feed_rate,
                );

                self.feed_rate = feed_rate;
                self.current_location = end;
            },
            Err(arg) => cb.invalid_argument(command, arg, "Missing"),
        }
    }
}
```


[next-step]: {{< ref "wiring-up-communication/index.md#the-next-step" >}}
[gcode]: https://crates.io/crates/gcodekk
[proverbs]: https://go-proverbs.github.io/