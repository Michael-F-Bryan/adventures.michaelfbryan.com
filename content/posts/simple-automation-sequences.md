---
title: "Simple Automation Sequences"
date: "2019-09-10T23:08:55+08:00"
draft: true
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
component. Instead, we can emulate it by 
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

Additionally because our stepper motor driver is the one sending out pulses, we
have complete control over *how many* pulses should be sent out between now and
the next tick (e.g. imagine you only need 2 more steps to reach the desired
location, but at the current frequency 10 steps would normally be sent between
"ticks").

```rust
// (not real code)

trait Outputs {
    fn set_x_motion(&mut self, step_frequency: f32, amount: i32);
    fn set_y_motion(&mut self, step_frequency: f32, amount: i32);
    fn set_z_motion(&mut self, step_frequency: f32, amount: i32);
}
```

{{% notice note %}}
You may have noticed everything is defined in terms of "steps" of a stepper 
motor, not actual linear distance (e.g. millimetres). 

For a homing sequence this isn't a concern, but later on we'll need to
"calibrate" our stepper motor to determine the number of millimetres moved
per step. Due to mechanical reasons (stretching, wear, temperature changes,
what you had for breakfast, etc.) it's better to determine this calibration
value empirically with a calibration sequence than trying to calculate it
based on machine design.
{{% /notice %}}

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

[requirements]: {{< ref "announcing-adventures-in-motion-control.md#identifying-requirements-and-subsystems" >}}
[encoder]: https://en.wikipedia.org/wiki/Encoder