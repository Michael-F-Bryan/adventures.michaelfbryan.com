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

To actually process

[wiki]: https://en.wikipedia.org/wiki/Noise_gate
[thread]: https://rust-audio.discourse.group/t/splitting-an-audio-stream-based-on-volume-silence/171?u=michael-f-bryan
[lan]: https://www.liveatc.net/recordings.php
[wav]: https://en.wikipedia.org/wiki/WAV
[hound]: https://crates.io/crates/hound
[sample-crate]: https://crates.io/crates/sample
[frame]: https://docs.rs/sample/latest/sample/frame/trait.Frame.html
[sample]: https://docs.rs/sample/latest/sample/trait.Sample.html