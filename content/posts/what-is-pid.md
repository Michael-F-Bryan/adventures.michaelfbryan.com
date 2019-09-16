---
title: "What Is PID?"
date: "2019-09-16T20:42:04+08:00"
draft: true
tags:
  - algorithms
---

PID, short for *proportional-integral-derivative* is a mathematical tool for
taking a measured input and a desired setpoint and figuring out an output which
will make the input closer to the setpoint.

The canonical example is a cruise control on a car. Ascending a hill would
lower the car's current speed (i.e. move the actual velocity away from the
desired velocity), the controller's PID algorithm would increase the throttle
to restore the measured speed to the desired speed with minimal delay and
overshoot.

{{% notice tip %}}
In practical terms, PID automatically applies accurate and responsive
corrections to a control function in order to minimise the error between the
desired input and its actual value.
{{% /notice %}}

The textbook description for a PID controller is done using math:

{{% latex %}}
Output = K_P e(t) + K_I \int e(t) dt + K_D \frac{d}{dt} e(t)
{{% /latex %}}

This article will be building on top of Brett Beauregard's 
[Improving the Beginner’s PID][intro]. If we translate the above equations into
Rust we'll get something like this:

```rust
pub struct Pid {
    k_i: f32,
    k_d: f32,
    k_p: f32,
    set_point: f32,
    cummulative_error: f32,
    last_error: f32,
    last_tick: Duration,
}

impl Pid {
    pub fn compute(&self, input: f32, now: Duration) -> f32 {
        // how much time has passed since the last tick?
        let dt = now - self.last_tick;
        let dt = dt.as_secs_f32();

        // compute all the working error variables
        let error = self.set_point - input;
        self.cummulative_error += error * dt;
        let deltaError = (error - self.last_error) / dt;

        // Remember some variables for next time
        self.last_error = error;
        self.last_tick = now;

        // Compute the PID output
        self.k_p * error
            + self.k_i * self.cummulative_error
            + self.k_d * deltaError
    }
}

```

[intro]: http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/