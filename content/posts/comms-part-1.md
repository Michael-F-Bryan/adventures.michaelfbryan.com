---
title: "The Communications System: Part 1"
date: "2019-09-06T23:00:00+08:00"
tags:
- adventures-in-motion-control
- Rust
---

## Prelude

The *Communications* system is arguably one of the most important parts of
our simulator. After all, it's kinda hard to debug a program when you can't
ask it why something isn't working.

The user will interact with our simulated motion controller via a single
*Serial Port*, which we'll be modelling as a simple thing which sends and
receives bytes. Serial ports are a fairly old technology, and have several
drawbacks compared to the Ethernet and TCP protocols that most programmers
are familiar with.

- There are no "packets" (i.e. bring your own [frames][framing])
- There's no guarantee the other side has received a message (i.e. bring your
  own [ACKs][ack]) - or even that there's anyone on the other end!
- If you receive data, there's no guarantee it wasn't garbled during
  transmission (i.e. bring your own [error detection and correction][er])

This all combines to make the *Serial* protocol an [unreliable][reliability]
one. Reliable protocols can be built on top of unreliable ones, we just need to
be smarter.

For simplicity, we'll design the communications system using request-response
pairs. This means:

- For every message sent to the simulator, there will be a corresponding
  response message
  - This implies that no response means the request wasn't received and should
    be resent (or ignored if non-critical)
- Responses will always be sent in the order their requests arrived in

## Building Reliability

The way we'll be adding reliability to the underlying error-prone stream of
bytes received from the *Serial* connection is by using a protocol called the
*Advanced Navigation Packet Protocol* (ANPP). This is a handy little protocol
*published by [*Advanced Navigation*][an] under the MIT license, with an
[open-source Rust port][anpp-rs].

Each message sent using ANPP will be laid out as:

| Offset | Size  | Description                             |
| ------ | ----- | --------------------------------------- |
| `0x0`  | 1     | Packet ID                               |
| `0x1`  | 1     | Length                                  |
| `0x2`  | 2     | CRC-16 checksum                         |
| `0x4`  | 1     | Header check-byte (XOR of bytes `0..4`) |
| `0x5`  | < 256 | Body                                    |

This lets us receive bytes one-by-one over the *Serial* port, then we can
periodically scan through the received bytes looking for a valid header
(sequence of 5 bytes which equal `0` when XOR'd together). From there we can
identify the message body (the next `Length` bytes) and identify transmission
errors using the CRC-16 checksum.

ANPP gives us a nice way of detecting when a message has been received
successfully, but we also need a higher-level mechanism for detecting
transmission failures and correcting them.

The easiest way to do this is called [Automatic Repeat reQuest][arq], i.e. tell
the sender to resend because an error was detected, and/or automatically resend
the previous message if it hasn't been answered after X seconds.

## Sending Data to the Communications System

Data can be received at any time in a normal microcontroller. The typical way to
handle this is by either frequently polling the pins wired up to our serial
port, or to configure the microcontroller to automatically invoke a callback
whenever a byte is received.

In this case the interrupt approach seems quite natural due to JavaScript's
callback-based nature.

All bytes the simulator receives will need to be stored in a buffer until the
next tick.

We can model the way data is passed to the `Communications` system by giving
the new `comms` crate a `Rx` trait:

```rust
// comms/src/lib.rs

/// The receiving end of a *Serial Connection*.
pub trait Rx {
    /// Get all bytes received by the simulator since the last tick.
    ///
    /// # Note to Implementors
    ///
    /// To prevent reading data twice, this buffer should be cleared after every
    /// tick.
    fn receive(&self) -> &[u8];
}
```

We'll also give the WASM code a way to write data to a buffer owned by our
`App`.

```rust
// sim/src/app.rs

#[wasm_bindgen]
impl App {
    pub fn on_data_received(&mut self, data: &[u8]) {
        self.inputs.on_data_received(data);
    }
}

// sim/src/inputs.rs

#[derive(Debug, Clone, Default)]
pub struct Inputs {
    clock: PerformanceClock,
    last_tick: Cell<Duration>,
    rx_buffer: ArrayVec<[u8; 256]>, // <-- new field!
}

impl Inputs {
    ...

    pub(crate) fn on_data_received(&mut self, data: &[u8]) {
        // writes up to `capacity` bytes to the buffer. Extra items are
        // silently dropped on the floor.
        self.rx_buffer.extend(data.into_iter().copied());
    }
}
```

{{% notice note %}}
In most microcontrollers an *Interrupt Service Routine* is a function that
takes no arguments and returns nothing (`fn()`), meaning the only way to send
data from the ISR to the main application is via `static` memory.

This is more of an implementation detail than anything else. For our purposes
using a method on `App` makes things simpler and easier to test, so we'll do
that. At the end of the day, thanks to the `Rx` trair our `Communications`
system doesn't really care *where* bytes come from, just that we can give it
a buffer of recently received data.
{{% /notice %}}

## Decoding Received Data

Now we've got a way to send data between the frontend and the backend, lets
start coding the `Communications` system which is in charge of decoding packets.

```rust
// comms/src/lib.rs

use aimc_hal::System;
use anpp::Decoder;

#[derive(Debug, Default, Clone, PartialEq)]
pub struct Communications {
    decoder: Decoder,
}

impl<I: Rx, O> System<I, O> for Communications {
    fn poll(&mut self, inputs: &I, outputs: &mut O) {
        unimplemented!();
    }
}
```

The `poll()` method for `Communications` is really simple. You copy data from
`inputs.received()` into `self.decoder` (using
[`Decoder::push_data()`][push_data]), then keep calling
[`Decoder::decode()`][decode] to read packets until it returns a
[`DecodeError::RequiresMoreData`][needs-data].

```rust
// comms/src/lib.rs

impl<I: Rx, O> System<I, O> for Communications {
    fn poll(&mut self, inputs: &I, _outputs: &mut O) {
        // A: how do we want to handle overflows?
        let _ = self.decoder.push_data(inputs.receive());

        loop {
            match self.decoder.decode() {
                Ok(pkt) => unimplemented!("B: What do we do now?"),
                Err(DecodeError::InvalidCRC) => {
                    unimplemented!("C: How do we handle corrupted packets?")
                },
                Err(DecodeError::RequiresMoreData) => break,
            }
        }
    }
}
```

This looks fairly straightforward, but it's raised three questions:

- **A:** how do we want to handle decoder buffer overflows? If we're
  receiving more data than we can process and can't increase the buffer size
  (buffers have a size defined at compile-time) then we need to drop data. The
  question then becomes whether to drop data already in the buffer, or drop
  data we haven't had a chance to look at yet?
- **B:** We've got a valid packet... now what?
- **C:** Invalid CRCs indicate that a message was garbled in transit. Should we
  just ignore the error, or do we want to keep track of how many CRC errors
  we've had and report it to the frontend at some point?

For now, lets handle **A** by clearing the `Decoder` buffer. This lets us get
rid of garbled data left over from previous `poll()`s and start with a clean
slate.

```rust
// comms/src/lib.rs

impl<I: Rx, O> System<I, O> for Communications {
    fn poll(&mut self, inputs: &I, _outputs: &mut O) {
        let received = inputs.receive();

        if self.decoder.push_data(received).is_err() {
            // we've run out of space in the decoder buffer, clear out leftovers
            // from previous runs and copy in as much new data as possible
            self.decoder.clear();
            let len = core::cmp::min(
                received.len(),
                self.decoder.remaining_capacity(),
            );
            let _ = self.decoder.push_data(&received[..len]);
        }

        ...
    }
}
```

{{% notice tip %}}
Either way, this situation isn't ideal. We don't want to drop data at all, so
ideally the frontend wouldn't send more data than the `Communications` system
can handle.

This gives us an effective limit of
[`anpp::Decoder::DEFAULT_DECODER_BUFFER_SIZE`][buffer-size] (512 bytes) per
`poll()` of the `Communications` system. Considering will be polling the
simulator from `requestAnimationFrame()`, and `requestAnimationFrame()` only
fires when the browser redraws (about 60Hz, or every 16ms), this limits the
entire application to a maximum transfer rate of `512*60 = 30720` bytes per
second.

[buffer-size]: https://docs.rs/anpp/1.0.1/anpp/struct.Decoder.html#associatedconstant.DEFAULT_DECODER_BUFFER_SIZE
{{% /notice %}}

**B** is easy enough to solve. The `Communications` system is only concerned
with the receiving and transmitting of messages, so it should let the rest of
the application decide *how* a message should be handled and what to reply with.

```rust
// comms/src/lib.rs

pub trait MessageHandler {
    fn handle_message(&mut self, msg: &Packet) -> Result<Packet, CommsError>;
}

#[derive(Debug, Copy, Clone, PartialEq)]
pub enum CommsError {
    /// The [`MessageHandler`] doesn't know how to handle the message.
    UnknownMessageType,
}
```

Now we can handle the message and send back a response.

```rust
// comms/src/lib.rs

impl<I, T, M> System<I, Outputs<T, M>> for Communications
where
    I: Rx,
    T: Tx,
    M: MessageHandler,
{
    fn poll(&mut self, inputs: &I, outputs: &mut Outputs<T, M>) {
        ...

        loop {
            match self.decoder.decode() {
                Ok(request) => {
                    let response = outputs
                        .message_handler
                        .handle_message(&request)
                        .expect("Unhandled message");
                    outputs.send(response);
                },
                ...
            }
        }
    }
}

/// The receiving end of a *Serial Connection*.
pub trait Rx {
    /// Get all bytes received by the simulator since the last tick.
    ///
    /// # Note to Implementors
    ///
    /// To prevent reading data twice, this buffer should be cleared after every
    /// tick.
    fn receive(&self) -> &[u8];
}

/// The transmitting end of a *Serial Connection*.
pub trait Tx {
    /// Queue some data to be sent to the frontend.
    ///
    /// There is no guarantee that the data will all be sent. This may happen if
    /// the receiver isn't listening or they aren't able to receive at this
    /// time.
    fn send(&mut self, data: &[u8]);
}

pub struct Outputs<T, M> {
    message_handler: M,
    tx: T,
}

impl<T: Tx, M> Outputs<T, M> {
    fn send(&mut self, packet: &Packet) {
        let mut buffer = [0; Packet::MAX_PACKET_SIZE + 5];
        debug_assert!(buffer.len() >= packet.total_length());

        let bytes_written = packet
            .write_to_buffer(&mut buffer)
            .expect("our buffer should always be big enough");

        self.tx.send(&buffer[..bytes_written]);
    }
}
```

{{% notice note %}}
Later on we may want to deal with a `CommsError::UnknownMessageType` by sending
back some sort of *"Not Acknowledged"* message, but for now we'll panic.
{{% /notice %}}

To represent the transfer side of a serial port we'll introduce a `Tx` trait.
We *could* have merged `handle_message()` and `send()` into a single trait,
but that wouldn't make logical sense. The `Tx` trait is implemented by some
bit of hardware that connects to the outside world, while a `MessageHandler`
is used to communicate with the rest of the application.

To make things more ergonomic, `Tx` and `MessageHandler` are implemented for
mutable references. That lets a caller just pass in a mutable reference to
existing types, i.e. `Outputs::new(&mut some_tx, &mut some_handler)`.

```rust
// comms/src/lib.rs

impl<'a, T: Tx> Tx for &'a mut T {
    fn send(&mut self, data: &[u8]) { (*self).send(data); }
}

impl<'a, M: MessageHandler> MessageHandler for &'a mut M {
    fn handle_message(&mut self, msg: &Packet) -> Result<Packet, CommsError> {
        (*self).handle_message(msg)
    }
}
```

To handle **C** (CRC errors), we'll give the `MessageHandler` a method that'll
be called whenever a CRC error occurs. That way the component in charge of
routing messages can note down how many errors have occurred within a single
run.

```rust
// comms/src/lib.rs

impl<I, T, M> System<I, Outputs<T, M>> for Communications
where ...
{
    fn poll(&mut self, inputs: &I, outputs: &mut Outputs<T, M>) {
        ...

        loop {
            match self.decoder.decode() {
                ...
                Err(DecodeError::InvalidCRC) => {
                    outputs.message_handler.on_crc_error()
                },
                ...
            }
        }
    }
}

pub trait MessageHandler {
    fn handle_message(&mut self, msg: &Packet) -> Result<Packet, CommsError>;
    /// Callback used to notify the application whenever a CRC error occurs.
    fn on_crc_error(&mut self) {}
}
```

## The Next Step

We've now set things up so we can receive input from the frontend and decode the
data into raw `Packet`s, the next step is to start defining the various messages
our system will use and wire up a `MessageHandler`.

[framing]: https://en.wikipedia.org/wiki/Frame_(networking)
[ack]: https://en.wikipedia.org/wiki/Acknowledgement_(data_networks)
[reliability]: https://en.wikipedia.org/wiki/Reliability_(computer_networking)
[er]: https://en.wikipedia.org/wiki/Error_detection_and_correction
[an]: https://www.advancednavigation.com/
[anpp-rs]: https://crates.io/crates/anpp
[arq]: https://en.wikipedia.org/wiki/Error_detection_and_correction#Automatic_repeat_request_(ARQ)
[push_data]: https://docs.rs/anpp/1.0.1/anpp/struct.Decoder.html#method.push_data
[decode]: https://docs.rs/anpp/1.0.1/anpp/struct.Decoder.html#method.decode
[needs-data]: https://docs.rs/anpp/1.0.1/anpp/errors/enum.DecodeError.html#variant.RequiresMoreData
