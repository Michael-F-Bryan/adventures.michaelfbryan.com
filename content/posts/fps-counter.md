---
title: "FPS Counter"
date: "2019-09-02T23:55:42+08:00"
draft: true
tags:
- adventures-in-motion-control
- rust
---

As mentioned in [the previous article][the-next-step] the next task is to
implement our first proper `System`, the `FpsCounter`.

> A relatively easy, yet important, component is some sort of FPS counter.
> Ideally there’ll be a bit of text in the corner showing the number of
> `poll()`s per second and the average duration. That way we can get a better
> feel for our simulator’s performance characteristics.

An `FpsCounter` has two responsibilities,

- Keep track of the last `n` poll times
- Calculate some statistics on the poll times and display it in the browser

## Creating The System

Instead of making the `FpsCounter` part of our top-level `sim` application,
it should be given its own crate. This means the `FpsCounter` won't need to care
about JavaScript, and lets us maintain distinct layers of abstraction (see 
[*Top-Level Infrastructure - Layers*][layers] for more).

First up, lets create the crate.

```console
cargo new --lib fps-counter
cd fps-counter
cargo add ../hal
```

We'll also make simplest system that compiles.

```rust
// fps-counter/src/lib.rs 

#![no_std]

use aimc_hal::{Clock, System};

#[derive(Debug, Clone, PartialEq)]
pub struct FpsCounter;

impl<In, Out> System<In, Out> for FpsCounter {
    fn poll(&mut self, inputs: &In, outputs: &mut Out) {
        unimplemented!()
    }
}
```

Next, we want to make sure the `FpsCounter` tracks the time of the last tick.

```rust
use aimc_hal::clock::DummyClock;

#[test]
fn track_time_of_last_tick() {
    let mut fps = FpsCounter::default();
    let should_be = Duration::new(1, 23);
    let time = DummyClock(should_be);

    fps.poll(&time, &mut ());

    assert_eq!(fps.last_tick, should_be);
}
```

{{% notice note %}}
The `aimc_hal::clock::DummyClock` type is a helper `Clock` that always
returns the same `Duration`.
{{% /notice %}}

To make this test pass, we'll need to update our `FpsCounter` to track the last
tick. It'll also need a source of time, we constrain the `In` type using
`aimc_hal::clock::HasClock`. This means `input` will have a getter that yields
a `Clock`.

```rust
#[derive(Debug, Clone, Default, PartialEq)]
pub struct FpsCounter {
    last_tick: Duration,
}

impl<In: HasClock, Out> System<In, Out> for FpsCounter {
    fn poll(&mut self, inputs: &In, outputs: &mut Out) {
        self.last_tick = inputs.clock().elapsed();
    }
}
```

The next step is to calculate the corresponding FPS and send the result
somewhere.

We'll wrap the calculated result in its own `Fps` struct, then make sure the
`outputs` can handle it.

```rust
#[derive(Debug, Copy, Clone, Default, PartialEq)]
pub struct Fps {
    pub frequency: f32,
}

pub trait FpsSink {
    fn emit_fps(&mut self, fps: Fps);
}
```

And the corresponding test:

```rust
#[cfg(test)]
#[macro_use]
extern crate std;

use std::prelude::v1::*;

#[derive(Debug, Default)]
pub struct Sink(Vec<Fps>);

impl FpsSink for Sink {
    fn emit_fps(&mut self, fps: Fps) { self.0.push(fps); }
}

#[test]
fn record_fps() {
    let mut fps = FpsCounter::default();
    let mut sink = Sink::default();
    let time = DummyClock(Duration::new(2, 500_000_000));

    fps.poll(&time, &mut sink);

    assert_eq!(sink.0.len(), 1);
    assert_eq!(sink.0[0], Fps { frequency: 1.0 / 2.5 });
}
```

Updating `FpsCounter::poll()` to make the test pass is left as an exercise for
the reader.

[the-next-step]: {{< ref "top-level-infrastructure/index.md#the-next-step" >}}
[layers]: {{< ref "top-level-infrastructure/index.md#layers" >}}