---
title: "The Communications System"
date: "2019-09-05T23:15:00+08:00"
draft: true
---

## Prelude

The *Communications* system is arguably one of the most important parts of our
simulator. After all, it's kinda hard to debug a problem when you can't ask the
simulator why it isn't working.

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

## Building Reliability

The way we'll be adding reliability to the underlying error-prone stream of
bytes received from the *Serial* connection is by using a protocol called the
*Advanced Navigation Packet Protocol* (ANPP). This is a handly little protocol
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

ANPP gives us a nice way of detecting when a message has been recieved 
successfully, but we also need a higher-level mechanism for detecting
transmission failures and correcting them. 

The easiest way to do this is using [Automatic Repeat reQuest][arq], i.e. tell
the sender to resend because an error was detected, and/or automatically resend
the previous message if it hasn't been answered after X seconds.

[framing]: https://en.wikipedia.org/wiki/Frame_(networking)
[ack]: https://en.wikipedia.org/wiki/Acknowledgement_(data_networks)
[reliability]: https://en.wikipedia.org/wiki/Reliability_(computer_networking)
[er]: https://en.wikipedia.org/wiki/Error_detection_and_correction
[an]: https://www.advancednavigation.com/
[anpp-rs]: https://crates.io/crates/anpp
[arq]: https://en.wikipedia.org/wiki/Error_detection_and_correction#Automatic_repeat_request_(ARQ)