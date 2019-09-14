---
title: "Simple Automation Sequences"
date: "2019-09-14:23:55+08:00"
draft: false
---

Now we can communicate with the outside world, let's start interacting with the 
"hardware" attached to our motion controller. This will be the beginning of our
*Motion* system.

The simplest way to interact with the world is by executing a pre-defined
routine, and one of the simplest useful routines is to move all axes to the
home position.

## System Inputs and Outputs

From our [initial requirements gathering][requirements] we know that our 3D 
printer will have three linear axes (X, Y, and Z), with limit switches at the
ends of each axis. This gives our new *Motion* system six inputs to deal with.

Stepper motors don't usually come with an [encoder][encoder] (a device for
tracking position), meaning we don't really have any way of determining where
an axis is other than by counting the number of stepper pulses sent. Let's
assume that the actual sending of pulses is done by a stepper motor driver
component, and it tells us how many pulses it has sent since the last `poll()`
of the application.

{{% notice note %}}
For technical reasons (the browser won't trigger our `App::poll()` more 
frequently than 60Hz) we won't be implementing a "true" stepper motor driver
component. Instead, we can emulate its behaviour from JavaScript.
{{% /notice %}}

```rust
// (not real code)

trait Inputs {
    // the number of pulses sent since the last tick
    fn x_pulses_sent(&self) -> i32;
    fn y_pulses_sent(&self) -> i32;
    fn z_pulses_sent(&self) -> i32;

    fn at_x_lower_limit(&self) -> bool;
    fn at_x_upper_limit(&self) -> bool;

    fn at_y_lower_limit(&self) -> bool;
    fn at_y_upper_limit(&self) -> bool;

    fn at_z_lower_limit(&self) -> bool;
    fn at_z_upper_limit(&self) -> bool;
}
```

Stepper are controlled by sending pulses to the motor, and the frequency these
pulses are sent out (e.g. 42 pulses/second) is the parameter usually used to
control this motion. This will typically be done on a motion controller using
timers, setting the timer period to trigger an interrupt *exactly* when the
next pulse needs to be sent.

This means we'll be using a control regime called *Velocity Control*. This is
essentially where you control the system purely via velocity, as opposed to
controlling the position or acceleration (or rather motor torque/force).

{{% notice tip %}}
You may want to read [Position Control vs Velocity Control vs Torque Control][1]
on the *Robotics* section of *StackExchange* to find out about the other
control regimes, and where one particular regime might be chosen over another.

[1]: https://robotics.stackexchange.com/questions/10052/position-control-vs-velocity-control-vs-torque-control
{{% /notice %}}

```rust
// (not real code)

trait Outputs {
    fn set_x_motion(&mut self, steps_per_second: f32);
    fn set_y_motion(&mut self, steps_per_second: f32);
    fn set_z_motion(&mut self, steps_per_second: f32);
}
```

One downside of *Velocity Control* is that you have less control over position
and unless you have specific hardware which provides feedback (e.g. an
[encoder][encoder]), the only way to know an axis' position is by counting it
yourself based on time between ticks and the current speed (i.e. 
`position += velocity*dt`). 

Keep in mind that positional accuracy will depend directly on the `poll()`
frequency. This is one of the big differentiators between realtime systems
and "normal" systems, `poll()` frequency (and by extension performance in
general) is a determining factor in whether something will fulfill its
requirements.

## Planning

Now we've got a better idea of the inputs and outputs available to our
system, we need to figure out how to implement *"Go To Home"*. We'll want to
choose a consistent well-known spot for our home position, and based on the
inputs available moving all axes to the end of travel seems logical.

There are a couple ways we could implement this:

1. Move one axis to its home position at a time
2. Move all axes simultaneously, stopping each axis when it reaches its 
   corresponding limit in turn

The former would be simpler to implement, but for a small increase in complexity
the latter could potentially take 1/3 the time.

In pseudo-code, this would look something like:

```python
while not (at_x_lower_limit and at_y_lower_limit and at_z_lower_limit):
    move_x_backwards()
    move_y_backwards()
    move_z_backwards()
```

## Implementing a *Go To Home* Sequence

There are a couple tricks we'll use to make the implementation if this homing
sequence easier. 

First we'll abstract over the exact type of axis this sequence works on. That
means it doesn't matter whether we're controlling a stepper motor attached to
a gearbox or a simple servo. We should be able to tell the axis to move home
at a particular velocity in human-friendly units like mm/sec, and leave the
calculation of stepper frequency and trauma speeds to some *Stepper Motor
Driver* component.

{{% notice note %}}
From here on we'll also be using the [uom][uom] crate for all dimensions and
motion parameters. It helps to document what a particular variable
corresponds to (i.e. the `speed = distance/time` calculation would be done
with `Velocity`, `Length`, and `Time`, instead of `f32`, `f32`, and `f32`)
and makes it almost impossible to mess up units (e.g. `mm` vs `in`, or `mm/s`
vs `m/s`).

[uom]: https://docs.rs/uom/
{{% /notice %}}

The interface for our limit switches and axes is rather simple:

```rust
// hal/src/axes.rs

use uom::si::f32::Velocity;

/// A driver for controlling axis motion using *velocity control*.
pub trait Axes {
    /// Tell the specified axis to move at a desired velocity.
    fn set_target_velocity(&mut self, axis_number: usize, velocity: Velocity);

    /// Get the actual velocity a particular axis is moving at.
    fn velocity(&self, axis_number: usize) -> Option<Velocity>;
}

/// A driver which tracks the limit switch state.
pub trait Limits {
    fn limit_switches(&self, axis_number: usize) -> Option<LimitSwitchState>;
}

/// The state of a set of limit switches.
#[derive(Debug, Copy, Clone, PartialEq, Eq, Hash, Default)]
pub struct LimitSwitchState {
    pub at_lower_limit: bool,
    pub at_upper_limit: bool,
}
```

We'll also create a generic automation sequence which moves just one axis
to its home position.

Automation sequences work by being polled frequently in order to make
progress, eventually reaching a *Success* state or stopping early with some
sort of *Fault*.

```rust
// hal/src/automation.rs

/// An automation sequence which will either be polled to completion or abort
/// early with a fault.
pub trait AutomationSequence<Input, Output> {
    /// Extra info attached to a fault.
    type FaultInfo;

    fn poll(&mut self, inputs: &Input, outputs: &mut Output) -> Transition<Self::FaultInfo>;
}

#[derive(Debug, Copy, Clone, PartialEq)]
pub enum Transition<F> {
    /// The [`AutomationSequence`] completed successfully.
    Complete,
    /// The [`AutomationSequence`] failed with a particular fault code.
    Fault(F),
    /// The [`AutomationSequence`] is still running.
    Incomplete,
}
```
Next we'll create a `MoveAxisHome` automation sequence which will try to move
the `axis_number`'th axis to its lower limit (in the negative direction) at
a specific `homing_speed`.

```rust
// motion/src/lib.rs

#[derive(Debug, Clone, PartialEq)]
pub struct MoveAxisHome {
    homing_speed: Velocity,
    axis_number: usize,
}
```

When neither limit switch is actuated our `MoveAxisHome` automation sequence
should tell the corresponding axis to move backwards.

```rust
// motion/src/lib.rs

#[test]
fn polling_without_hitting_limits_makes_an_axis_move_backwards() {
    let mut seq = MoveAxisHome::new(Velocity::new::<millimeter_per_second>(100.0), 7);
    let mut axes = DummyAxes::default();
    let mut limits = DummyLimits::default();
    limits.0.insert(7, LimitSwitchState::default());

    let trans = seq.poll(&limits, &mut axes);

    assert_eq!(trans, Transition::Incomplete);
    assert_eq!(axes.0.len(), 1);
    assert_eq!(axes.0.get(&7).copied(), Some(-1.0 * seq.homing_speed));
}
```

Additionally, we want to be moving towards the lower limit so hitting the upper
limit means something has gone wrong. Typically this means the limits are wired
backwards.

```rust
// motion/src/lib.rs

#[test]
fn actuating_the_upper_limit_is_a_fault() {
    let mut seq = MoveAxisHome::new(Velocity::new::<millimeter_per_second>(100.0), 7);
    let mut axes = DummyAxes::default();
    let mut limits = DummyLimits::default();
    limits.0.insert(
        7,
        LimitSwitchState { at_lower_limit: false, at_upper_limit: true },
    );

    let trans = seq.poll(&limits, &mut axes);

    assert_eq!(trans, Transition::Fault(Fault::unexpected_upper_limit(7)));
    assert_eq!(axes.velocity(7), Some(Velocity::default()));
}
```

And finally, reaching the lower limit should complete the sequence.

```rust
// motion/src/lib.rs

#[test]
fn actuating_the_lower_limit_completes_the_sequence() {
    let mut seq = MoveAxisHome::new(Velocity::new::<millimeter_per_second>(100.0), 7);
    let mut axes = DummyAxes::default();
    let mut limits = DummyLimits::default();
    limits.0.insert(
        7,
        LimitSwitchState { at_lower_limit: true, at_upper_limit: false },
    );

    let trans = seq.poll(&limits, &mut axes);

    assert_eq!(trans, Transition::Complete);
    assert_eq!(axes.velocity(7), Some(Velocity::default()));
}
```

We've now got enough tests to implement a basic `MoveAxisHome` sequence. There
are still a couple edge cases to cover (e.g. what happens if we start the 
sequence on the upper limit?) but they can be an exercise for the reader.

A quick'n'dirty implementation that makes all the tests pass:

```rust
// motion/src/lib.rs

impl<L: Limits, A: Axes> AutomationSequence<L, A> for MoveAxisHome {
    type FaultInfo = Fault;

    fn poll(&mut self, inputs: &L, outputs: &mut A) -> Transition<Self::FaultInfo> {
        let limits = match inputs.limit_switches(self.axis_number) {
            Some(l) => l,
            None => {
                return Transition::Fault(Fault::axis_not_found(self.axis_number))
            },
        };

        if limits.at_upper_limit {
            outputs.set_target_velocity(self.axis_number, Velocity::default());
            Transition::Fault(Fault::unexpected_upper_limit(self.axis_number))
        } else if limits.at_lower_limit {
            outputs.set_target_velocity(self.axis_number, Velocity::default());
            Transition::Complete
        } else {
            outputs.set_target_velocity(self.axis_number, -1.0 * self.homing_speed);
            Transition::Incomplete
        }
    }
}
```

## Combining Automation Sequences

Because we're moving multiple axes at a time, it'd be nice to have a helper
that lets us execute several `AutomationSequence`s simultaneously. A good
analogy would be the `and_then()` and `join()` combinators commonly used with
`futures`.

The general idea is:

- Create an array of `Option<AutomationSequence>`s 
- to implement `AutomationSequence::poll()`, iterate over the sequences, polling
  each sequence that is present
- If any sequence returns a `Transition::Fault`, halt immediately with that
  fault
- If a sequence returns `Transition::Complete`, "remove" it from the array using
  `Option::take()`
- Repeat until all sequences are completed

The actual declaration for this `All` combinator gets a little messy because
we need to use `AsMut` and some other trait-level trickery to work around the
lack of proper const generics. It also leaks some implementation details like
needing to provide the `[Option<A>; N]` storage buffer in the constructor
instead of just taking a list of `AutomationSequence`s.

```rust
// hal/src/automation.rs

#[derive(Debug, Clone, PartialEq)]
pub struct All<A, V, I, O> {
    sequences: V,
    _automation_type: PhantomData<A>,
    _input_type: PhantomData<I>,
    _output_type: PhantomData<O>,
}

impl<A, V, I, O> All<A, V, I, O>
where
    V: AsMut<[Option<A>]>,
    A: AutomationSequence<I, O>,
{
    pub fn new(items: V) -> Self {
        All {
            sequences: items,
            _automation_type: PhantomData,
            _input_type: PhantomData,
            _output_type: PhantomData,
        }
    }
}
```

The `AutomationSequence::poll()` method itself isn't overly complicated though.

```rust
// hal/src/automation.rs

impl<I, O, A: AutomationSequence<I, O>, V: AsMut<[Option<A>]>>
    AutomationSequence<I, O> for All<A, V, I, O>
{
    type FaultInfo = A::FaultInfo;

    fn poll(
        &mut self,
        inputs: &I,
        outputs: &mut O,
    ) -> Transition<Self::FaultInfo> {
        let variants = self.sequences.as_mut();

        for variant in variants.iter_mut() {
            if let Transition::Fault(f) = poll_variant(variant, inputs, outputs)
            {
                return Transition::Fault(f);
            }
        }

        if variants.iter().all(|v| v.is_none()) {
            Transition::Complete
        } else {
            Transition::Incomplete
        }
    }
}

fn poll_variant<I, O, A>(
    variant: &mut Option<A>,
    inputs: &I,
    outputs: &mut O,
) -> Transition<A::FaultInfo>
where
    A: AutomationSequence<I, O>,
{
    let trans = match variant {
        Some(ref mut sequence) => sequence.poll(inputs, outputs),
        None => Transition::Complete,
    };

    if trans.at_end_state() {
        let _ = variant.take();
    }

    trans
}
```

Now we've got a useable `All` combinator, it's almost trivial to make a wrapper
that runs our *Go To Home* sequence on each axis concurrently.

```rust
// motion/src/lib.rs

pub struct Home<L: Limits, A: Axes> {
    inner: All<MoveAxisHome, [Option<MoveAxisHome>; 3], L, A>,
}

impl<L: Limits, A: Axes> Home<L, A> {
    pub fn new(
        x_axis: usize,
        y_axis: usize,
        z_axis: usize,
        homing_speed: Velocity,
    ) -> Self {
        Home {
            inner: All::new([
                Some(MoveAxisHome::new(homing_speed, x_axis)),
                Some(MoveAxisHome::new(homing_speed, y_axis)),
                Some(MoveAxisHome::new(homing_speed, z_axis)),
            ]),
        }
    }
}

impl<L: Limits, A: Axes> AutomationSequence<L, A> for Home<L, A> {
    type FaultInfo = Fault;

    fn poll(
        &mut self,
        inputs: &L,
        outputs: &mut A,
    ) -> Transition<Self::FaultInfo> {
        self.inner.poll(inputs, outputs)
    }
}
```

## The Next Step

Now we're able to work with automation sequences we should create a *Motion*
system which can invoke those sequences in response to requests from the
frontend.

[requirements]: {{< ref "announcing-adventures-in-motion-control.md#identifying-requirements-and-subsystems" >}}
[encoder]: https://en.wikipedia.org/wiki/Encoder
