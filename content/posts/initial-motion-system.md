---
title: "Initial Motion System"
date: "2019-09-18T23:44:10+08:00"
draft: true
tags:
- adventures-in-motion-control
- rust
---

Now we've got [some simple automation][previous] code, lets start a proper
*Motion* system.

Most *Motion* systems are designed around a *"control mode"*, a fancy term for
*"what is the machine doing right now?"* Common control modes are:

- `Idle` - the default control mode, machines revert to `Idle` whenever they're
  not doing anything
- `Automation` - running an automation sequence
- `Recipe` - executing a job (a set of instructions for how to execute a job
  and the motion parameters that should be used is often referred to as a
  *Recipe*)
- `Manual` - manual movement, where velocity may be controlled via a handset
  or the user invokes a *"jog to position"* function

There are several ways to transition between control modes.

- An `AutomationSequence` can end and we transition to `Idle`
- The machine may encounter a fault (e.g. by hitting a limit switch)
  returning to `Idle` and latching some fault flag
- The user may send a recipe to the machine and press the *GO* button (switching
  to the `Recipe` control mode)
- The current recipe finishes successfully (transition to `Idle`),
- and many more...

This all combines to make an interesting state machine diagram.

{{< mermaid >}}
graph LR;
    A[Automation];
    I((Idle));
    R[Recipe];
    M[Manual];

    I-- Start Automation Sequence -->A;
    A-- Fault -->I;
    linkStyle 1 stroke:red;
    A-- Completed -->I;
    linkStyle 2 stroke:green;

    I-- GO -->R;
    R-- Recipe Finished -->I;
    linkStyle 4 stroke:green;
    R-- Fault -->I;
    linkStyle 5 stroke:red;

    I-- Jog -->M;
    I-- Handset Button Pressed -->M;
    M-- Handset Button Released -->I;
    linkStyle 8 stroke:green;
    M-- Jog Position Reached -->I;
    linkStyle 9 stroke:green;
    M-- Fault -->I;
    linkStyle 10 stroke:red;
{{< /mermaid >}}

You may also notice that a lot of the transitions are in response to a message
from the user via our *Communications* system. This means we'll end up declaring
several new message types and handle them using the 
`aimc_hal::messaging::Handler` trait.

For now, we can keep things simple with just a set of `GoHome` and `AbortMotion`
messages. The controller will need to switch control modes and ack or nack
the messages, depending on whether the desired transition is supported at the
time.

## Implementation

In its current form, the *Motion* system is rather simple. We haven't 
implemented recipes or manual motion yet, so the only states are `Idle` and
`Home` (our only automation sequence).

```rust
// motion/src/lib.rs

pub struct Motion {
    control_mode: ControlMode,
}

pub enum ControlMode {
    Idle,
    Home(Home),
}

impl<L: Limits, A: Axes> System<L, A> for Motion {
    fn poll(&mut self, inputs: &L, outputs: &mut A) {
        match self.control_mode {
            ControlMode::Idle => {}
            ControlMode::Home(ref mut home) => match home.poll(inputs, outputs) {
                Transition::Complete => {
                    self.control_mode = ControlMode::Idle
                } 
                Transition::Fault(_) => {
                    // TODO: we should probably do something about this fault...
                    self.control_mode = ControlMode::Idle
                }
                _ => {}
            },
        }
    }
}
```

We're polling the `Home` automation sequence and handling the `Complete` and
`Fault` transition, but there's no way to actually get into the `Home` state.

Usually this would be done in response to a message from the user, so... let's
add a new message to our `Communications` module and wire it up to the `Router`.

```rust
// motion/src/lib.rs

#[derive(Debug, Default, Copy, Clone, PartialEq, Eq, Pread, Pwrite, IOread, IOwrite, SizeWith)]
pub struct StartHomingSequence {}

impl StartHomingSequence {
    pub const ID: u8 = 4;
}

// sim/src/router.rs

pub(crate) struct Router<'a> {
    pub(crate) fps: &'a mut FpsCounter,
    pub(crate) motion: &'a mut Motion,
}

impl<'a> MessageHandler for Router<'a> {
    fn handle_message(&mut self, msg: &Packet) -> Result<Packet, CommsError> {
        match msg.id() {
            ...
            StartHomingSequence::ID => {
                dispatch::<_, StartHomingSequence, _>(self.motion, msg.contents(), map_result)
            }
            ...
        }
    }
}

fn map_result<A, B>(result: Result<A, B>) -> Packet
where
    A: Into<Packet>,
    B: Into<Packet>,
{
    match result {
        Result::Ok(a) => a.into(),
        Result::Err(b) => b.into(),
    }
}
```

{{% notice note %}}
Because `Motion` will need to return a `Result<Ack, Nack>`, we've had to update
the `dispatch()` helper so we can manually specify the function for turning
`H::Response` back into a `Packet`. 

Previously it would always just use `response.into()`, but for the `Motion`
we want to use `map_result()` instead.

Adding more generics to an already complicated `dispatch()` function isn't great
though, we may want to revisit it in the future and try to make things less
clever...
{{% /notice %}}

The `Motion` system is now part of our application state, so we'll also need to 
update the `App` appropriately.

```rust
// sim/src/app.rs

#[wasm_bindgen]
pub struct App {
    ...
    motion: Motion, // the motion system is now part of our app state
}

impl App {
    ...

    fn handle_comms(&mut self) {
        let mut router = Router {
            fps: &mut self.fps,
            motion: &mut self.motion, // <-- New!
        };
        let mut outputs =
            aimc_comms::Outputs::new(&mut self.browser, &mut router);
        self.comms.poll(&self.inputs, &mut outputs);
    }
}
```

To actually handle the `StartHomingSequence` message and switch to the `Home`
control mode we'll need to remember how the machine is wired up (e.g. axis
numbers and speeds). 

This requires adding a new `MotionParameters` struct to the `Motion` system.
Later on we'll let the user configure the motion parameters, but for now it's
okay to hard-code some defaults.

```rust
// motion/src/lib.rs

pub struct Motion {
    motion_params: MotionParameters, // <-- new!
    control_mode: ControlMode,
}

pub struct MotionParameters {
    pub x_axis: usize,
    pub y_axis: usize,
    pub z_axis: usize,
    pub homing_speed: Velocity,
}

impl MotionParameters {
    pub fn homing_sequence(&self) -> Home {
        Home::new(self.x_axis, self.y_axis, self.z_axis, self.homing_speed)
    }
}

impl Default for MotionParameters {
    fn default() -> MotionParameters {
        MotionParameters {
            x_axis: 0,
            y_axis: 1,
            z_axis: 2,
            homing_speed: Velocity::new::<millimeter_per_second>(10.0),
        }
    }
}
```

And now we should have everything we need to handle a `StartHomingSequence`.

```rust
// motion/src/lib.rs

impl Handler<StartHomingSequence> for Motion {
    type Response = Result<Ack, Nack>;

    fn handle(&mut self, _: StartHomingSequence) -> Self::Response {
        match self.control_mode {
            ControlMode::Idle => {
                let home = self.motion_params.homing_sequence();
                self.control_mode = ControlMode::Home(home);
                Ok(Ack::default())
            }
            // it doesn't make sense to start a homing sequence if we're already
            // doing something else...
            _ => Err(Nack::default()),
        }
    }
}
```

## The Next Step

If you've done this sort of thing before, you'll know we've got all the basic
components for an embedded motion controller. There is:

- A *Communications* system which talks to the outside world and can be used to
  send message to the various parts of the application
- Some *Automation Sequences*
- A *Motion* system which implements a state machine that can be used to move
  things around and interact with the outside world

We've got one big problem though...

This is a simulation that runs in the browser and at the moment all we can see
is a white screen with a rapidly changing [FPS Counter][fps-counter] in one
corner. There's currently no way to interact with our simulator, set motion
parameters, or even see what it's doing. 

That'll be our goal for next time.

[previous]: {{< ref "simple-automation-sequences.md#the-next-step" >}}
[fps-counter]: {{< ref "fps-counter.md" >}}
