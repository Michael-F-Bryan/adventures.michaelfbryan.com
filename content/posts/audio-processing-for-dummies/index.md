---
title: "Audio Processing for Dummies"
date: "2019-10-27T23:34:00+08:00"
tags:
- Rust
- audio
---

In my spare time I'm an emergency services volunteer, and one of the tasks our
unit has is to run the radio network and keep track of what's happening. This
can be a pretty stressful job, especially when there's lots of radio traffic,
and it's not unusual to miss words or entire transmissions.

To help with a personal project that could make the job easier I'd like to
implement a basic component of audio processing, the [Noise Gate][wiki].

The basic idea is to scan through an audio stream and split it into individual
clips based on volume, similar to the algorithm mentioned [on this Rust Audio
discourse thread][thread].

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration. It's also been published as a
crate [on crates.io][crate].

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/noise-gate
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
[crate]: https://crates.io/crates/noise-gate
{{% /notice %}}

## What Even Is Audio?

We've all consumed audio media at some point, but have you ever stopped and
wondered how it works under the hood?

At its core, audio works by rapidly reading the volume level (a "sample"),
typically 44,100 times per second (44.1 kHz is called the [*Sample
Rate*][sr]). These samples are then encoded using [*Pulse Code
Modulation*][pcm].

According to Wikipedia:

> Pulse-code modulation (PCM) is a method used to digitally represent sampled
> analog signals. It is the standard form of digital audio in computers,
> compact discs, digital telephony and other digital audio applications. In a
> PCM stream, the amplitude of the analog signal is sampled regularly at
> uniform intervals, and each sample is quantized to the nearest value within a
> range of digital steps.

{{% notice tip %}}
If it helps, a sample can be thought of as how far a speaker/microphone's
membrane is deflected at a particular point in time.
{{% /notice %}}

It's not uncommon to record multiple audio tracks at a time, for example
imagine multiple microphones were used to provide a sense of
direction/perspective (see [Sound Localisation][sl] for more). These multiple
tracks are usually referred to as *Channels*.

**TL;DR:** In Rust lingo, you can think of an audio stream as:

```rust
type AudioStream = Vec<Frame>;
type Frame = [Sample; N]; // where `N` is the number of channels in the stream
type Sample = i16 | f32;
```

The audio formats you are used to (MP3, WAV, OGG) are just different ways to
store an `AudioStream` on disk, along with some metadata describing the audio
(artist, year, etc.), typically using tricks like compression or [Delta
Encoding][de] to make the resulting file as small as possible.

If you're wondering why compression is important, these are the numbers for a
simple uncompressed audio stream with:

- 30 seconds of audio
- 44.1 kHz sample rate
- 2 channels (e.g. left and right speaker)
- bit depth of 16 (i.e. the samples are `i16`)

```text
sizeof(Sample) = 2 bytes
sizeof(Frame) = 2 * sizeof(Sample) = 4 bytes
sizeof(1 second) = sizeof(Frame) * 44100 = 176400 bytes
full clip = 30 * sizeof(1 second) = 5292000 bytes = 5.3 MB
```

... That's a lot of data!

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
$ ffmpeg -i a-turtle-of-an-issue.mp3 -ac 1 a-turtle-of-an-issue.wav
```

## Implementing the Noise Gate Algorithm

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

## Measuring Performance

If we want to use the `NoiseGate` in realtime applications we'll need to make
sure it can handle typical sample rates.

I don't expect our algorithm to add much in terms of a performance overhead, but
it's always a good idea to check.

The gold standard for benchmarking in Rust is [criterion][criterion], so let's
add that as a dev dependency.

```toml
# Cargo.toml

[dev-dependencies]
criterion = "0.3"

[[bench]]
name = "throughput"
harness = false
```

We'll need a `Sink` implementation which will add as little overhead as
possible without being completely optimised out by the compiler.

```rust
// benches/throughput.rs

struct Counter {
    samples: usize,
    chunks: usize,
}

impl<F> Sink<F> for Counter {
    fn record(&mut self, _: F) {
        self.samples += criterion::black_box(1);
    }

    fn end_of_transmission(&mut self) {
        self.chunks += criterion::black_box(1);
    }
}
```

We've already downloaded a handful of example WAV files to the `data/`
directory, so we can register a new benchmark group (a group of related
benchmarks which should be graphed together) and register a benchmark for every
WAV file in the `data/` directory.

```rust
// benches/throughput.rs

const DATA_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/data/");

fn bench_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("throughput");

    for entry in fs::read_dir(DATA_DIR).unwrap() {
        let entry = entry.unwrap();
        let path = entry.path();

        if path.is_file() {
            let name = path.file_stem().unwrap().to_str().unwrap();
            add_benchmark(&mut group, name, &path);
        }
    }
}
```

The setup work for each WAV file benchmark is non-trivial, so we've pulled it
out into its own function. To set things up we'll use [`hound`][hound] to read
the entire audio clip into a `Vec<[i16; 1]>` in memory and guess a reasonable
`release_time` and `noise_threshold`.

Then it's just a case of telling the `BenchmarkGroup` how many samples we're
working with (throughput) and processing the frames.

```rust
// benches/throughput.rs

fn add_benchmark(
    group: &mut BenchmarkGroup<WallTime>,
    name: &str,
    path: &Path,
) {
    let reader = WavReader::open(path).unwrap();

    let desc = reader.spec();
    assert_eq!(desc.channels, 1, "We've hard-coded frames to be [i16; 1]");
    let release_time = 2 * desc.sample_rate as usize;

    let samples = reader
        .into_samples::<i16>()
        .map(|s| [s.unwrap()])
        .collect::<Vec<_>>();

    let noise_threshold = average(&samples);

    group
        .throughput(Throughput::Elements(samples.len() as u64))
        .bench_function(name, |b| {
            b.iter(|| {
                let mut counter = Counter::default();
                let mut gate = NoiseGate::new(noise_threshold, release_time);
                gate.process_frames(&samples, &mut counter);
            });
        });
}

/// A fancy way to add up all the channels in all the frames and get the average
/// sample value.
fn average<F>(samples: &[F]) -> F::Sample
where
    F: Frame,
    F::Sample: FromSample<f32>,
    F::Sample: ToSample<f32>,
{
    let sum: f32 = samples.iter().fold(0.0, |sum, frame| {
        sum + frame.channels().map(|s| s.to_sample()).sum::<f32>()
    });
    (sum / samples.len() as f32).round().to_sample()
}
```

Finally, we need to invoke a couple macros to register the `"throughput"`
benchmark group and create a `main` function (remember when declaring the
`[[bench]]` table we told `rustc` not to write `main()` for us with `harness
= false`).

```rust
// benches/throughput.rs

criterion_group!(benches, bench_throughput);
criterion_main!(benches);
```

These are the WAV files I've downloaded to the `data/` directory:

```console
$ ls -l data
.rw-r--r-- 1.6M michael 27 Oct 21:21 a-turtle-of-an-issue.wav
.rw-r--r-- 4.2M michael 27 Oct 21:17 KBDL-B17-Tribute-20191005.wav
.rw-r--r-- 7.6M michael 27 Oct 21:17 N11379_KSCK.wav
.rw-r--r--  12M michael 27 Oct 21:26 tornado-warning-ground.wav
$ file data/*
data/a-turtle-of-an-issue.wav:      RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 22050 Hz
data/KBDL-B17-Tribute-20191005.wav: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 24000 Hz
data/N11379_KSCK.wav:               RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 22050 Hz
data/tornado-warning-ground.wav:    RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 44100 Hz
```

Now let's run the benchmarks.

```console
$ cargo bench
     Running target/release/deps/throughput-dbdb305fc8a0e002
Benchmarking throughput/a-turtle-of-an-issue: Warming up for 3.0000 s
Warning: Unable to complete 100 samples in 5.0s. You may wish to increase target time to 37.5s or reduce sample count to 20
throughput/a-turtle-of-an-issue
                        time:   [7.0509 ms 7.1617 ms 7.2892 ms]
                        thrpt:  [113.14 Melem/s 115.15 Melem/s 116.96 Melem/s]
                 change:
                        time:   [-6.5194% -3.2691% -0.1646%] (p = 0.07 > 0.05)
                        thrpt:  [+0.1648% +3.3796% +6.9740%]
                        No change in performance detected.
Found 9 outliers among 100 measurements (9.00%)
  8 (8.00%) high mild
  1 (1.00%) high severe

...
```

If you've got `gnuplot` installed, this also generates [a report][bench-report]
under `target/criterion`.

On my machine the report says our `NoiseFilter` can process 103.47 million
samples per second. This is about 2000 times faster than we need, so it gives us
hope that the *algorithm* won't add any unnecessary overhead... Of course
that just moves the bottleneck from `NoiseFilter` to the caller's `Sink`
implementation.

## Experimenting With Our Sample Data

We're now at the point where we have a fully implemented *Noise Gate*. Let's
create an example program for splitting WAV files and see what happens when
we point it at our sample data!

Even though it's an example, we should probably implement proper command-line
argument handling to make experimentation easier. By far the easiest way to
do this is with [the structopt crate][structopt].

```rust
// examples/wav-splitter.rs

#[derive(Debug, Clone, StructOpt)]
pub struct Args {
    #[structopt(help = "The WAV file to read")]
    pub input_file: PathBuf,
    #[structopt(short = "t", long = "threshold", help = "The noise threshold")]
    pub noise_threshold: i16,
    #[structopt(
        short = "r",
        long = "release-time",
        help = "The release time in seconds",
        default_value = "0.25"
    )]
    pub release_time: f32,
    #[structopt(
        short = "o",
        long = "output-dir",
        help = "Where to write the split files",
        default_value = "."
    )]
    pub output_dir: PathBuf,
    #[structopt(
        short = "p",
        long = "prefix",
        help = "A prefix to insert before each clip",
        default_value = "clip_"
    )]
    pub prefix: String,
}
```

Now we'll need a `Sink` type. The general idea is every time the `record()`
method is called we'll write another frame to a cached `hound::WavWriter`. If
the `WavWriter` doesn't exist we'll need to create a new one which writes to
a file named like `output_dir/clip_1.wav`. An `end_of_transmission()` tells
us to `finalize()` the `WavWriter` and remove it from our cache.

```rust
// examples/wav-splitter.rs

pub struct Sink {
    output_dir: PathBuf,
    clip_number: usize,
    prefix: String,
    spec: WavSpec,
    writer: Option<WavWriter<BufWriter<File>>>,
}

impl Sink {
    pub fn new(output_dir: PathBuf, prefix: String, spec: WavSpec) -> Self {
        Sink {
            output_dir,
            prefix,
            spec,
            clip_number: 0,
            writer: None,
        }
    }

    fn get_writer(&mut self) -> &mut WavWriter<BufWriter<File>> {
        if self.writer.is_none() {
            let filename = self
                .output_dir
                .join(format!("{}{}.wav", self.prefix, self.clip_number));
            self.clip_number += 1;
            self.writer = Some(WavWriter::create(filename, self.spec).unwrap());
        }

        self.writer.as_mut().unwrap()
    }
}

impl<F> noise_gate::Sink<F> for Sink
where
    F: Frame,
    F::Sample: hound::Sample,
{
    fn record(&mut self, frame: F) {
        let writer = self.get_writer();

        for channel in frame.channels() {
            writer.write_sample(channel).unwrap();
        }
    }

    fn end_of_transmission(&mut self) {
        if let Some(writer) = self.writer.take() {
            writer.finalize().unwrap();
        }
    }
}
```

From there the `main` function is quite simple. It parses some arguments, reads
the WAV file into memory, then throws it at our `NoiseGate` so the `Sink` can
write the clips to the `output/` directory.

```rust
// examples/wav-splitter.rs

fn main() -> Result<(), Box<dyn Error>> {
    let args = Args::from_args();

    let reader = WavReader::open(&args.input_file)?;
    let header = reader.spec();
    let samples = reader
        .into_samples::<i16>()
        .map(|result| result.map(|sample| [sample]))
        .collect::<Result<Vec<_>, _>>()?;

    let release_time = (header.sample_rate as f32 * args.release_time).round();

    fs::create_dir_all(&args.output_dir)?;
    let mut sink = Sink::new(args.output_dir, args.prefix, header);

    let mut gate = NoiseGate::new(args.noise_threshold, release_time as usize);
    gate.process_frames(&samples, &mut sink);

    Ok(())
}
```

Let's take this for a test-run.

The original clip:

<audio controls>
  <source src="N11379_KSCK.mp3" type="audio/mp3">
  Your browser does not support the audio tag.
</audio>

Now let's split it into pieces with our `wav-splitter` program. At this point
I don't really know what values of `noise_threshold` or `release_time` are
acceptable for this audio, but I figure `50` and `0.3s` should be usable?

```console
$ ./target/release/examples/wav-splitter -o output --threshold 50 --release-time 0.3 data/N11379_KSCK.wav
$ ls output
clip_0.wav clip_3.wav clip_6.wav clip_9.wav clip_12.wav clip_15.wav
clip_18.wav clip_21.wav clip_1.wav clip_4.wav clip_7.wav clip_10.wav
clip_13.wav clip_16.wav clip_19.wav clip_22.wav clip_2.wav clip_5.wav
clip_8.wav clip_11.wav clip_14.wav clip_17.wav clip_20.wav
```

<audio controls>
  <source src="split/clip_0.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_1.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_2.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_3.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_4.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_5.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_6.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_7.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_8.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_9.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_10.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_11.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_12.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_13.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_14.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_15.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_16.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_17.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_18.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_19.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_20.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_21.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_22.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_23.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_24.wav" type="audio/wav">
</audio>

<audio controls>
  <source src="split/clip_25.wav" type="audio/wav">
</audio>

Wow it actually worked on the first try. Now that's something you don't see
every day.

[wiki]: https://en.wikipedia.org/wiki/Noise_gate
[thread]: https://rust-audio.discourse.group/t/splitting-an-audio-stream-based-on-volume-silence/171?u=michael-f-bryan
[lan]: https://www.liveatc.net/recordings.php
[wav]: https://en.wikipedia.org/wiki/WAV
[hound]: https://crates.io/crates/hound
[structopt]: https://crates.io/crates/structopt
[sample-crate]: https://crates.io/crates/sample
[frame]: https://docs.rs/sample/latest/sample/frame/trait.Frame.html
[sample]: https://docs.rs/sample/latest/sample/trait.Sample.html
[pcm]: https://en.wikipedia.org/wiki/Pulse-code_modulation
[sl]: https://en.wikipedia.org/wiki/Sound_localization
[sr]: https://en.wikipedia.org/wiki/Sampling_(signal_processing)#Sampling_rate
[de]: https://en.wikipedia.org/wiki/Delta_encoding
[criterion]: https://github.com/bheisler/criterion.rs
[bench-report]: /criterion/report/index.html
