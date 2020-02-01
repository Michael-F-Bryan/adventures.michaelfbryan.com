---
title: "Creating Interactive Applications While Maintaining Your Sanity"
date: "2020-01-31T22:22:11+08:00"
draft: true
tags:
- rust
- architecture
---

One of the primary reasons computers are so ubiquitous in modern society is
their ability to let humans and software cooperate to achieve a desired goal.
That is, to be interactive.

Creating interactive applications can be pretty annoying for a programmer.
Unlike a computer which is predictable and will blindly follow any
instructions given to it,

- Humans are unpredictable. They like to press buttons and push features further
  than they were originally intended
- Humans have a habit of asking for special cases (*"Feature X works really
  well, but when I click on this triangle while holding shift and tilting my
  head at an angle it should really do Y instead. It's not a big feature, can
  you just add?"*)
- Humans often don't know what they want, meaning even if you implement
  something exactly as described to you, users will still complain about it not
  doing the right thing
- The real world is messy, and letting users interact with your program is a
  really effective way of mixing the messy outside world with the nice
  structured world inside a computer
- Also, users are the ones funding your pay check so you should probably try
  to keep them happy 😁

The actual code shown in this article isn't anything a 2nd year Computer
Science student hasn't seen before. However, the difference between an
"ordinary" programmer and a Software Engineer is the ability to identify a
pattern, understand why it exists, and employ it to solve a problem in a way
which won't make them sad 6 months from now when they need to revisit the code
because the boss has asked for a shiny new feature.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Coming Up With A Design

Before we write any code we need to do two things,

1. Define what we mean by making a program "interactive"
2. Come up with a formal model to implement this interactivity

This step is arguably the most important. Many a project has been ruined

I work in the CNC industry, and one of my tasks is the development and
maintenance of an application for Computer Aided Design. So when I say the
word *"interactive"* I often think of the ability to activate different "tools"
and add or update items on a drawing through a sequence of mouse clicks and
key presses, while receiving visual feedback in real time.

For example, if you wanted to draw an arc on the canvas you might

1. Select the arc tool
2. Click where you want the arc's centre to be on the canvas (this draws a dot
   where you clicked)
3. Click another location to set the arc's start point (drawing another dot,
   plus a line between the two dots to indicate the arc's radius)
4. Move the cursor to where you want the arc's end point to be (as you move the
   cursor a temporary arc is drawn on the canvas to show what it would look like
   if you placed the arc's end point at the cursor location)
5. Click to place the end point, actually adding the arc to the drawing

{{< figure
    src="/img/solidworks-arc.gif"
    caption="Drawing an arc using SolidWorks"
    alt="Drawing an arc using SolidWorks"
>}}

The typical way to implement this is with a state machine. You'll add a variable
(typically an integer) to your window, then when something happens (e.g. a mouse
click) there is a switch statement which will execute the desired code depending
on the current state.

This kinda works, but doesn't foster robustness or long term maintainability.

The cause for this is two-fold, a "state" is scattered around half a dozen
different event handlers and buried inside large switch-case statements. That
means adding a new state or adjusting an existing one tends to look a lot like
[shotgun surgery][shotgun] with changes spread out across the app.

The second reason using a simple integer to track the current state is that a
"state" often constitutes more than a simple "I am doing X".

See those lines and annotations used to provide the user with visual feedback
in the gif? Where do you think they're stored? If a "state" is just an
integer these temporary variables will typically be stored as fields attached
to the `Window`. Not only does this add a lot of unnecessary fields to an
already bloated object, a lot of these fields are only valid during specific
states and we have no way to statically ensure that a field will be
initialized or destroyed at the correct time.

This becomes especially painful when writing Rust because you can't just ignore
a `null` field... Almost as if the code is trying to tell us something 🤔

```rust
const STATE_IDLE: u32 = 0;
const STATE_SELECTING_ARC_CENTRE: u32 = 2;
const STATE_SELECTING_ARC_START_POINT: u32 = 3;
const STATE_SELECTING_ARC_END_POINT: u32 = 4;

struct Window {
    /// Which state we are currently in.
    current_state: u32,
    /// The temporary dot we draw when the arc's centre point is selected.
    temp_arc_centre: Option<Point>,
    /// The temporary radial line drawn after the arc's start point is selected.
    temp_arc_radius: Option<Line>,
    /// A preview of the arc we're drawing when the user is moving their cursor
    /// to the arc's end point.
    temp_arc_preview: Option<Arc>,
    /// The angle annotation that hovers near the cursor while selecting the end
    /// point.
    temp_arc_angle_annotation: Option<Annotation>,

    // 50 more fields containing variables needed by the other states
    ...
}
```

I have seen such code monsters inside 10,000+ line `Window` classes in the
wild. They are not fun to maintain or debug.

Please don't do this.

A much better solution is to use the [*State Pattern*][state].

{{% notice tip %}}
It may sound weird for someone who is both a Functional Programming fan and
diehard Rust coder to be promoting a stereotypically object-oriented pattern,
but bear with me.

There is method to this madness.
{{% /notice %}}

The idea is actually pretty simple, encapsulate everything about a particular
"state" into an object which can respond to events and trigger transitions to
other states.

In code the state pattern looks something like this:

```rust
trait State {
    fn on_mouse_down(&mut self, cursor: Vector2D, drawing: &mut Drawing) -> Transition;
    fn on_mouse_up(&mut self, cursor: Vector2D, drawing: &mut Drawing) -> Transition;
    fn on_mouse_move(&mut self, cursor: Vector2D, drawing: &mut Drawing) -> Transition;
    ...
}

enum Transition {
    ChangeState(Box<dyn State>),
    DoNothing,
}
```

To complete the pattern, our `Window` just needs to propagate events to the
current state and possibly switch to a new state based on the returned
`Transition`.

{{% notice info %}}
Although all code in this article is written in Rust, there's nothing really
Rust-specific going on here.

I just happen to be working on adding interactivity to the WebAssembly demo
for [arcs][arcs], a CAD library I'm writing from scratch based on my
experiences in other languages.

[arcs]: https://github.com/Michael-F-Bryan/arcs
{{% /notice %}}

Another very important aspect of this pattern is how it is completely
*decoupled* from the `Window` (as far as each `State` is concerned, it doesn't
even know the `Window` exists).

When your `State` doesn't know anything about the rest of the world and can
only interact with data passed to it as parameters it becomes almost trivial
to test. Create a dummy drawing in memory, instantiate the `State`, then call
an event handler and make sure it behaves as expected.

### Nested States

At this point you need to look at your application and ask whether it makes
sense for a state to have a "sub-state", and how you want to represent
sub-states.

To make this idea of nested states more concrete, consider the example from
before where we were adding an arc to the canvas. Clicking the *"Arc"* tool
transitioned to the *"Adding Arc"* state, but we hadn't actually started drawing
anything on the canvas at that point. It was only after clicking that we started
the process of drawing an arc.

You *could* make every possible tool and action part of the same state machine,
but if we were to draw the state machine diagram it'd require a massive
whiteboard. It also wouldn't fit in your head. Especially when you consider that
users should be able to cancel drawing an arc midway through (e.g. if they put
the centre in the wrong spot or didn't mean to enter arc mode at all).

Another way to structure this is to introduce some form of nesting. That way
when the user is in the *"Arc Mode"* you just need to consider the states and
transitions related to the arc mode's sub-states.

{{< mermaid >}}
graph TD;
    Idle;
    arc[Arc Mode];
    point[Point Mode];

    arc_idle[Arc Mode Idle State];
    arc_selected_centre[Selected Centre];
    arc_selected_start[Selected Start Point];
    arc_selected_e[Selected End Point];

    arc --> arc_idle;

    subgraph Top-Level;
        arc --> Idle;
        point --> Idle;
        Idle --> arc;
        Idle --> point;
    end;

    subgraph Arc Mode;
        arc_idle --> arc_selected_centre;
        arc_selected_centre --> arc_selected_start;
        arc_selected_centre -- Cancel --> arc_idle;
        arc_selected_start --> arc_selected_e;
        arc_selected_start -- Cancel --> arc_idle;
        arc_selected_e -- Arc added to drawing --> arc_idle;
    end;
{{< /mermaid >}}

There are a couple ways you can implement nesting, both with their pros and
cons,

1. Give a top-level state ("mode") its own set of nested state machines as
   required
2. Go one step higher in the ladder of abstraction and use a *stack* of `State`s
   (also called a [Pushdown Automata][pda]), introducing `Push` and `Pop`
   operations to `Transition`

Using nested state machines means your states can be custom-tailored for the
current mode and make assumptions based on the other states within their state
machine.

On the other hand, pushdown automata promote code reuse. If you want to share
behaviour between different modes it's just a case of pushing the state onto
the stack and when the set of interactions triggered by the state are done it
will "return" to the original state by popping itself from the stack.

This reusability means you can avoid a lot of code duplication but because
your states need to be more generic, by their very nature you aren't able to
make as many assumptions about what is going on in the big picture.

Like a lot of things where the real world is involved there are trade-offs,
and it's the Software Engineer's job to figure out which alternative would be
the least bad in the long term.

## A Note On Optimising and Dynamic Dispatch

## The Infrastructure

The first step in making our application interactive is to create the
fundamental infrastructure our code will be built on top of.

The `arcs` demo app won't be *too* complex, so we'll take the nested state
machine route instead of using pushdown automata. In this case we're
preferring to make the app easier to reason about at the cost of writing
duplicate code when modes have behaviour in common.

We don't want our `State`s to be coupled to any particular implementation of
the `Drawing`, instead it just needs to know what can be done with a drawing.
This makes testing a lot easier because we can insert mocks if necessary.

For now the `Drawing` trait can be left empty. We'll add things to it as the
various modes are implemented.

```rust
// demo/src/modes/mod.rs

/// A basic drawing canvas, as seen by the various [`State`]s.
pub trait Drawing { }
```

For now we only care about four events,

- The left mouse button was pressed
- The left mouse button was released
- The mouse has moved
- A button was pressed on the keyboard

This gives us a nice starting point for the `State` trait.

```rust
// demo/src/modes/mod.rs

pub trait State {
    /// The left mouse button was pressed.
    fn on_mouse_down(
        &mut self,
        _drawing: &mut dyn Drawing,
        _event_args: &MouseEventArgs,
    ) -> Transition {
        Transition::DoNothing
    }

    /// The left mouse button was released.
    fn on_mouse_up(
        &mut self,
        _drawing: &mut dyn Drawing,
        _event_args: &MouseEventArgs,
    ) -> Transition {
        Transition::DoNothing
    }

    /// The mouse moved.
    fn on_mouse_move(
        &mut self,
        drawing: &mut dyn Drawing,
        _event_args: &MouseEventArgs,
    ) -> Transition {
        Transition::DoNothing
    }

    /// A button was pressed on the keyboard.
    fn on_key_pressed(&mut self, _drawing: &mut dyn Drawing) -> Transition {
        Transition::DoNothing
    }
}

/// Instructions to the state machine returned by the various event handlers
/// in [`State`].
#[derive(Debug)]
pub enum Transition {
    ChangeState(Box<dyn State>),
    DoNothing,
}
```

{{% notice tip %}}
You'll notice we've given each event handler a default implementation which
just returns `Transition::DoNothing`. This is just a convenience thing so states
can ignore events they don't care about without needing to explicitly write
a no-op event handler.
{{% /notice %}}

We also need to create types which provide information about the event that has
occurred.

```rust
// demo/src/modes/mod.rs

use arcs::{CanvasSpace, DrawingSpace};
use euclid::Point2D;

#[derive(Debug, Clone, PartialEq)]
pub struct MouseEventArgs {
    /// The mouse's location on the drawing.
    pub location: Point2D<f64, DrawingSpace>,
    /// The mouse's location on the canvas.
    pub cursor: Point2D<f64, CanvasSpace>,
    /// The state of the mouse buttons.
    pub button_state: MouseButtons,
}

bitflags::bitflags! {
    /// Which mouse button (or buttons) are pressed?
    pub struct MouseButtons: u8 {
        const LEFT_BUTTON = 0;
        const RIGHT_BUTTON = 1;
        const MIDDLE_BUTTON = 2;
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct KeyboardEventArgs {
    pub shift_pressed: bool,
    pub control_pressed: bool,
    /// The semantic meaning of the key currently being pressed, if there is
    /// one.
    pub key: Option<VirtualKeyCode>,
}

#[derive(Debug, Copy, Clone, PartialEq, Eq, Hash)]
pub enum VirtualKeyCode {
    Escape,
    Left,
    Up,
    Right,
    Down,
    Back,
    Return,
    Space,
    A,
    B,
    ...
    Key9,
}
```

{{% notice info %}}
You may have noticed the `MouseEventArgs` has two fields for the mouse's
location. That's because the mouse has both a physical location on the screen
(referred to as `CanvasSpace` by `arcs`) and an equivalent location on the
drawing (referred to as `DrawingSpace`).

The `euclid` library exposes types which can be "tagged" with the coordinate
space they belong to, ensuring you can't accidentally mix up coordinates in
`DrawingSpace` and `CanvasSpace`.

For examples of why we might want to avoid this, look up [*The Mars Climate
Orbiter*][mco]. For more details on the various coordinate spaces, see the
[`arcs` crate docs][docs].

[mco]: https://en.wikipedia.org/wiki/Mars_Climate_Orbiter
[docs]: https://michael-f-bryan.github.io/arcs/arcs/index.html
{{% /notice %}}

We'll almost certainly want to print the state of the world to the console at
some point (you have no idea how helpful this is when debugging complex
interactions!), so let's also require that all `State`s implement `Debug`.

```rust
// demo/src/modes/mod.rs

use std::fmt::Debug;

pub trait State: Debug {
    ...
}
```

## Idle Mode

## Wiring it Up to the UI

## Add Point Mode

## Conclusions

[shotgun]: https://refactoring.guru/smells/shotgun-surgery
[state]: https://refactoring.guru/design-patterns/state
[pda]: https://en.wikipedia.org/wiki/Pushdown_automaton