---
title: "PID for Programmers"
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
Rust we'll get something like [this][pid-1]:

```rust
// src/lib.rs

#![no_std]
use core::time::Duration;

#[derive(Debug, Clone, PartialEq)]
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
    pub fn compute(&mut self, input: f32, now: f32) -> f32 {
        // how much time has passed since the last tick?
        let dt = now - self.last_tick;

        // compute all the working error variables
        let error = self.set_point - input;
        self.cummulative_error += error * dt;
        let delta_error = (error - self.last_error) / dt;

        // Remember some variables for next time
        self.last_error = error;
        self.last_tick = now;

        // Compute the PID output
        self.k_p * error
            + self.k_i * self.cummulative_error
            + self.k_d * delta_error
    }
}
```

## Getting a Feeling for the PID Controller

A big part of the PID controller is tuning those three variables, \\(k_p\\),
\\(k_p\\), and \\(k_d\\), and the easiest way to understand how each knob
affects the overall evolution of the system. We'll do this using a command-line
program that generates graphs.

[intro]: http://brettbeauregard.com/blog/2011/04/improving-the-beginners-pid-introduction/
[pid-1]: https://github.com/Michael-F-Bryan/pid/blob/2cf54e8556d01b495e35384305649c7605f239b5/src/main.rs