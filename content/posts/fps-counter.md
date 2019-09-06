---
title: "FPS Counter"
date: "2019-09-03T08:50:00+08:00"
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
    let start = Duration::new(42, 0);
    let period = Duration::from_millis(20);
    let now = start + period;
    let mut fps = FpsCounter::with_start_time(start);
    let mut sink = Sink::default();
    let time = DummyClock(now);

    fps.poll(&time, &mut sink);

    assert_eq!(sink.0.len(), 1);
    assert_eq!(
        sink.0[0],
        Fps {
            frequency: 1000.0 / 20.0,
        }
    );
    assert_eq!(fps.last_tick, now);
}
```

Updating `FpsCounter::poll()` to make the test pass is left as an exercise for
the reader.

A further extension would be to add an `average_poll_duration` field to `Fps`.
That way `sim::App` can record when `App::poll()` starts and poll the 
`FpsCounter` as the last thing before `App::poll()` exits. Embedded systems
won't generally have access to an allocator, so you may want to checkout
[`arraydeque`][arraydeque] as a `#[no_std]` alternative.

## Wiring up to the Application

Now we've got an FPS counter it's time to show the FPS in our window.

First, let's give the FPS counter somewhere to be displayed. This means adding
a dummy element to `frontend/index.html`.

```diff
 <body>
   <noscript>This page contains webassembly and javascript content, please enable javascript in your browser.</noscript>
 
-  <div>
-    <span id="fps-counter"></span>
-  </div>
-
   <script src="./bootstrap.js"></script>
 </body>
```

The `Browser` will also need updating so it takes a reference to the
`#fps-counter` span in its constructor.

```rust
// sim/src/browser.rs

use fps_counter::{Fps, FpsSink};
use wasm_bindgen::JsValue;
use web_sys::Element;

#[derive(Debug, Clone)]
pub struct Browser {
    fps_div: Element,
}

impl Browser {
    pub fn from_element(fps_selector: &str) -> Result<Browser, &'static str> {
        let document = web_sys::window()
            .ok_or("Can't get a reference to the window")?
            .document()
            .ok_or("Can't get a reference to the document")?;

        let element = document
            .query_selector(fps_selector)
            .map_err(|_| "Invalid selector")?
            .ok_or("Can't find the FPS element")?;

        Ok(Browser { fps_div: element })
    }
}
```

While we're at it, we should probably implement `fps_counter::FpsSink` for
`Browser`...

```rust
// sim/src/browser.rs

impl FpsSink for Browser {
    fn emit_fps(&mut self, fps: Fps) {
        let mut buffer = ArrayString::<[u8; 128]>::default();

        let result = write!(buffer, "FPS: {:.1}Hz", fps.frequency);

        if result.is_ok() {
            self.fps_div.set_inner_html(&buffer);
        } else {
            self.fps_div.set_inner_html("FPS: ? Hz");
        }
    }
}
```

We'll need to propagate possible errors now that constructing a `Browser` may
fail. 

The idiomatic way to do this is by returning a `Result<T, JsValue>` from a
`#[wasm_bindgen]` function. That way, the shims generated by `wasm-bindgen`
will be notified of failure and raise the `JsValue` as an exception.

```rust
// sim/src/lib.rs

#[wasm_bindgen]
pub fn setup_world(fps_div: &str) -> Result<App, JsValue> {
    let browser = Browser::from_element(fps_div)?;
    let inputs = Inputs::default();

    Ok(App::new(inputs, browser))
}
```

And of course `setup_world()`'s signature changed, so we'll need to pass in the
`#fps-counter` selector from our JavaScript.

```js
// frontend/index.js

function init() {
    console.log("Initializing the world");
    world = wasm.setup_world("#fps-counter");
    requestAnimationFrame(animate);
}
```

With any luck, this should be everything required to wire the `FpsCounter` up
to the UI.

Reloading the window shows some rapidly changing text in the top-left corner.

```
FPS: 55.56Hz 
```

The label itself isn't overly pleasing to look at, but it gets the job done.
If the text itself seems to flicker, remember that we're updating it every
time the `App` gets polled (about 60 times per second). 

As an exercise for the reader, try implementing a [moving average][mov-avg] to
smooth that flicker out.

## The Next Step

Now we've got a better feel for the work required to add new systems to the
application and wire them up to the UI, the next step is probably going to be
the *Communications* system. 

The real world tends to be messy with lots of places where errors can enter the
*Communications* system, but lots of people have solved the problem in the past
so we should be okay.

[the-next-step]: {{< ref "top-level-infrastructure/index.md#the-next-step" >}}
[layers]: {{< ref "top-level-infrastructure/index.md#layers" >}}
[arraydeque]: https://docs.rs/arraydeque/0.4.5/arraydeque/
[mov-avg]: https://en.wikipedia.org/wiki/Moving_average