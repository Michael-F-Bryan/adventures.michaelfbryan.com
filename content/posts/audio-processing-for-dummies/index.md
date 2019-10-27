---
title: "Audio Processing for Dummies"
date: "2019-10-26T17:59:06+08:00"
draft: true
tags:
- rust
- audio
---

In my spare time I'm an emergency services volunteer, and one of the tasks our
unit has is to run the radio network and keep track of what's happening. This
can be a pretty stressful job, especially when there's lots of radio traffic,
and it's not unusual to miss words or entire transmissions.

To help make the job easier I'd like to implement a basic component of audio
processing, the [Noise Gate][wiki].

The basic idea is to scan through an audio stream and split it into chunks
based on volume, similar to the algorithm mentioned [on this Rust Audio
discourse thread][thread].

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's 
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/noise-gate
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Finding Sample Data

If we want to implement a noise gate we're going to need some sample clips to
test it on.

I've found the Air Traffic Controller recordings from [LiveATC.net][lan] are 
reasonably similar to my target, with the added bonus that they're publicly
available.

One example: 

<audio controls>
  <source src="a-turtle-of-an-issue.mp3" type="audio/mp3">
  Your browser does not support the audio tag.
</audio>

Our end goal is to create a library that can break audio streams up into
chunks based on volume without caring where the audio originally came from
(MP3 file, microphone, another function, etc.). We'll start by using [the WAV
format][wav] because it's simple and a really good crate ([hound][hound])
already exists for working with WAV files.

You can download the sample clip and convert it to WAV using `ffmpeg`:

```console
$ mkdir -p tests/data
$ curl "https://forums.liveatc.net/index.php?action=dlattach;topic=15455.0;attach=10441" > a-turtle-of-an-issue.mp3
$ ffmpeg -i a-turtle-of-an-issue.mp3 a-turtle-of-an-issue.wav
```

## What Even Is Audio?

TODO: Talk about samples, frames, and PCM.

## The Rough Algorithm

For now, our *Noise Gate* will have two knobs for tweaking its behaviour:

- `open_threshold` - the (absolute) noise value above which the gate should open
- `release_time` - how long to hold the gate open after dropping below the 
  `open_threshold`. This will manifest itself as the gate being in a sort of
  half-open state for the next `release_time` samples, where new samples
  above the `open_threshold` will re-open the gate.

The awesome thing about this algorithm is that it can be represented using a
simple state machine.

```rust
// src/lib.rs

enum State {
    Open,
    Closing { remaining_samples: usize },
    Closed,
}
```

Our state machine diagram looks roughly like this:

{{< mermaid >}}
graph TD;

  linkStyle default interpolate basis;

  Open[Open];
  Closing(Closing);

  Open-- below threshold -->Closing;
  Open-- above threshold -->Open;
  Closing-- above threshold -->Open;
  Closing-- remaining_samples = 0 -->Closed;
  Closing-- remaining_samples > 0 -->Closing;
  Closed-- above threshold -->Open;
  Closed-- below threshold -->Closed;
{{< /mermaid >}}

We'll be using some abstractions, namely [`Frame`][frame] and
[`Sample`][sample] from the [`sample` crate][sample-crate], to make the
*Noise Gate* work with multiple channels and any type of audio input.

Let's define a helper which will take a `Frame` of audio input and tell us 
whether all audio channels are below a certain threshold.

```rust
// src/lib.rs

use sample::{Frame, SignedSample};

fn below_threshold<F>(frame: F, threshold: F::Sample) -> bool
where
    F: Frame,
{
    let threshold = abs(threshold.to_signed_sample());

    frame
        .channels()
        .map(|sample| sample.to_signed_sample())
        .map(abs)
        .all(|sample| sample < threshold)
}

fn abs<S: SignedSample>(sample: S) -> S {
    let zero = S::equilibrium();
    if sample >= zero {
        sample
    } else {
        -sample
    }
}
```

The `State` transitions are done using one big `match` statement and are almost 
a direct translation of the previous state machine diagram.

```rust
// src/lib.rs

fn next_state<F: Frame>(
    state: State,
    frame: F,
    open_threshold: F::Sample,
    release_time: usize,
) -> State {
    match state {
        State::Open => {
            if below_threshold(frame, open_threshold) {
                State::Closing {
                    remaining_samples: release_time,
                }
            } else {
                State::Open
            }
        }

        State::Closing { remaining_samples } => {
            if below_threshold(frame, open_threshold) {
                if remaining_samples == 0 {
                    State::Closed
                } else {
                    State::Closing {
                        remaining_samples: remaining_samples - 1,
                    }
                }
            } else {
                State::Open
            }
        }

        State::Closed => {
            if below_threshold(frame, open_threshold) {
                State::Closed
            } else {
                State::Open
            }
        }
    }
}
```

There's a bit more rightward drift here than I'd like, but the function itself
is quite self-contained and readable enough.

That said, as a sanity check it's a good idea to write some tests exercising
each state machine transition.

```rust
// src/lib.rs

#[cfg(test)]
mod tests {
    use super::*;

    const OPEN_THRESHOLD: i16 = 100;
    const RELEASE_TIME: usize = 5;

    test_state_transition!(open_to_open: State::Open, 101 => State::Open);
    test_state_transition!(open_to_closing: State::Open, 40 => State::Closing { remaining_samples: RELEASE_TIME });
    test_state_transition!(closing_to_closed: State::Closing { remaining_samples: 0 }, 40 => State::Closed);
    test_state_transition!(closing_to_closing: State::Closing { remaining_samples: 1 }, 40 => State::Closing { remaining_samples: 0 });
    test_state_transition!(reopen_when_closing: State::Closing { remaining_samples: 1 }, 101 => State::Open);
    test_state_transition!(closed_to_closed: State::Closed, 40 => State::Closed);
    test_state_transition!(closed_to_open: State::Closed, 101 => State::Open);
}
```

{{% notice tip %}}
When writing these sorts of tests you'll probably want to minimise boilerplate
by pulling the testing code out into a macro. That way you just need to write
to case being tested, inputs, and expected outputs, and the macro will do the
rest.

This is the definition for `test_state_transition!()`:

```rust
macro_rules! test_state_transition {
    ($name:ident, $from:expr, $sample:expr => $expected:expr) => {
        #[test]
        fn $name() {
            let start: State = $from;
            let expected: State = $expected;
            let frame: [i16; 1] = [$sample];

            let got = next_state(start, frame, OPEN_THRESHOLD, RELEASE_TIME);

            assert_eq!(got, expected);
        }
    };
}
```
{{% /notice %}}

To implement the *Noise Gate*, we'll wrap our state and configuration into a
single `NoiseGate` struct.

```rust
// src/lib.rs

pub struct NoiseGate<S> {
    /// The volume level at which the gate will open (begin recording).
    pub open_threshold: S,
    /// The amount of time (in samples) the gate takes to go from open to fully
    /// closed.
    pub release_time: usize,
    state: State,
}

impl<S> NoiseGate<S> {
    /// Create a new [`NoiseGate`].
    pub const fn new(open_threshold: S, release_time: usize) -> Self {
        NoiseGate {
            open_threshold,
            release_time,
            state: State::Closed,
        }
    }

    /// Is the gate currently passing samples through to the [`Sink`]?
    pub fn is_open(&self) -> bool {
        match self.state {
            State::Open | State::Closing { .. } => true,
            State::Closed => false,
        }
    }

    /// Is the gate currently ignoring silence?
    pub fn is_closed(&self) -> bool {
        !self.is_open()
    }
}
```

We'll need to declare a `Sink` trait that can be implemented by consumers of
our *Noise Gate* in the next step.

```rust
// src/lib.rs

pub trait Sink<F> {
    /// Add a frame to the current recording, starting a new recording if
    /// necessary.
    fn record(&mut self, frame: F);
    /// Reached the end of the samples, do necessary cleanup (e.g. flush to disk).
    fn end_of_transmission(&mut self);
}
```

Processing frames is just a case of iterating over each frame, updating the
state, and checking whether we need to pass the frame through to the `Sink` or
detect an `end_of_transmission`.

```rust
// src/lib.rs

impl<S: Sample> NoiseGate<S> {
    pub fn process_frames<K, F>(&mut self, frames: &[F], sink: &mut K)
    where
        F: Frame<Sample = S>,
        K: Sink<F>,
    {
        for &frame in frames {
            let previously_open = self.is_open();

            self.state = next_state(self.state, frame, self.open_threshold, self.release_time);

            if self.is_open() {
                sink.record(frame);
            } else if previously_open {
                // the gate was previously open and has just closed
                sink.end_of_transmission();
            }
        }
    }
}
```

[wiki]: https://en.wikipedia.org/wiki/Noise_gate
[thread]: https://rust-audio.discourse.group/t/splitting-an-audio-stream-based-on-volume-silence/171?u=michael-f-bryan
[lan]: https://www.liveatc.net/recordings.php
[wav]: https://en.wikipedia.org/wiki/WAV
[hound]: https://crates.io/crates/hound
[sample-crate]: https://crates.io/crates/sample
[frame]: https://docs.rs/sample/latest/sample/frame/trait.Frame.html
[sample]: https://docs.rs/sample/latest/sample/trait.Sample.html