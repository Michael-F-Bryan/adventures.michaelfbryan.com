---
title: "Creating Interactive Applications While Maintaining Your Sanity"
date: "2020-02-06T23:43:00+08:00"
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
  head at an angle, it should really do Y instead. It's not a big feature, can
  you just add?"*)
- Humans often don't know what they want, meaning even if you implement
  something exactly as described to you users will still complain about it not
  doing the right thing
- The real world is messy, and letting users interact with your program is a
  really effective way of mixing the messy outside world with the nice
  structured world inside a computer
- Also, users are the ones funding your pay check so you should probably try
  to keep them happy 😁

The ideas and concepts shown in this article aren't overly advanced. In fact,
if you've been programming for a couple months (especially if it's part of a
formal Computer Science program) you're probably already familiar with them.

The difference between an "ordinary" programmer and a Software Engineer isn't
in how many advanced concepts they know, it's the ability to identify a
pattern, understand why it exists, and employ it to solve a problem. The
experienced software engineer will do this in a way which won't make them sad
6 months from now when they need to revisit the code because the boss has
asked for a shiny new feature.

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
word *"interactive"* I think of the user being able to adding items to a
drawing through a sequence of mouse clicks and key presses while receiving
visual feedback in real time.

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

To be fair, this kinda works. However it doesn't foster robustness or long
term maintainability.

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

A much better solution is to use something like the [*State Pattern*][state].

{{% notice tip %}}
It may sound weird for someone who is both a Functional Programming fan and
diehard Rust coder to be promoting object-oriented design patterns, but bear
with me.

There is method to this madness.
{{% /notice %}}

The idea behind the *State Pattern* is pretty simple, encapsulate everything
about a particular "state" into an object which can respond to events and
trigger transitions to other states.

In code the state pattern looks something like this:

```rust
struct Window {
    current_state: Box<dyn State>,
    ...
}

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

You *could* make every possible tool and action part of the same state
machine, but if we were to draw the state machine diagram it'd require a
massive whiteboard. It also wouldn't fit in your head. Especially when you
consider that users should be able to cancel pretty much any action midway
through (e.g. if they put the arc's centre in the wrong spot or didn't mean
to enter arc mode at all).

Another way to structure this is to introduce some form of nesting. That way
when the user is in the *"Arc Mode"* you just need to consider the states and
transitions related to the arc mode's sub-states.

{{< mermaid >}}
stateDiagram
    state "Idle" as idle
    state "Arc Mode" as arc
    state "Point Mode" as point

    [*] --> idle
    idle --> arc
    idle --> point

    state arc {
        state "Arc Mode Idle State" as arc_idle
        state "Selected Centre" as arc_selected_centre
        state "Selected Start Point" as arc_selected_start
        state "Selected End Point" as arc_selected_e

        arc_idle --> arc_selected_centre
        arc_selected_centre --> arc_selected_start
        arc_selected_centre --> arc_idle: Cancel
        arc_selected_start --> arc_selected_e
        arc_selected_start --> arc_idle: Cancel
        arc_selected_e --> arc_idle: Arc added to drawing
    }

    state point { }
{{< /mermaid >}}

There are a couple ways you can implement nesting, both with their pros and
cons,

1. Give a top-level state ("mode") its own set of nested state machines as
   required
2. Go one step higher in the ladder of abstraction and use a *stack* of `State`s
   (also called a [Pushdown Automata][pda]), introducing `Push` and `Pop`
   operations to `Transition` and sending events to the top-most `State`

Using nested state machines means your states can be custom-tailored for the
current mode and make assumptions based on the other states within their state
machine.

On the other hand, pushdown automata promote code reuse. If you want to share
behaviour between different modes it's just a case of pushing the state onto
the stack and when the set of interactions triggered by the state are done it
will "return" to the original state by popping itself from the stack.

This reusability means you can avoid a lot of code duplication. However, because
your states need to be more generic by their very nature you aren't able to
make as many assumptions about what is going on in the big picture.

{{% notice tip %}}
Something else to consider is whether it's possible to trigger a transition
from outside the state machine.

A typical example of this is when the user clicks a toolbar button to start
using a different tool. In this case if a transition is triggered you need a
way to tell the current mode it has been cancelled and it needs to clean up
after itself, otherwise you risk leaving temporary artifacts around which the
user can't interact.

The way this is implemented will change depending on whether you're using
nested state machines or a pushdown automata.
{{% /notice %}}

Like a lot of things where the real world is involved there are trade-offs,
and it's the Software Engineer's job to figure out which alternative would be
the least bad in the long term.

## The Infrastructure

The first step in making our application interactive is to create the
fundamental infrastructure our code will be built on top of.

The `arcs` demo app won't be *too* complex, so we'll take the nested state
machine route instead of using pushdown automata. In this case we're
preferring to make the app easier to reason about at the cost of writing
duplicate code when modes have behaviour in common.

{{% notice info %}}
A lot of the content from now on will be focused around [the `arcs` CAD
library][arcs] because I want to make a demo people can use when evaluating the library
and as a form of [dogfooding][df].

In [a previous article][prev] I've gone into a fair amount of detail
regarding its design, in particular the use of an *Entity Component System*
architecture, so you may want to have a skim through that if you start
feeling lost.

[arcs]: https://github.com/Michael-F-Bryan/arcs
[df]: https://en.wikipedia.org/wiki/Eating_your_own_dog_food
[prev]: {{< ref "/posts/ecs-outside-of-games.md" >}}
{{% /notice %}}

We don't want our `State`s to be coupled to any particular implementation of
the `Drawing`, instead it just needs to know what can be done with a drawing.
This also makes testing a lot easier because we can insert mocks if necessary.

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

Combined with an `on_cancelled()` method, this gives us a nice starting point
for the `State` trait.

```rust
// demo/src/modes/mod.rs

pub trait State {
    /// The [`State`] has been cancelled and needs to clean up any temporary
    /// objects it created.
    fn on_cancelled(&mut self, _drawing: &mut dyn Drawing) {}

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
just returns `Transition::DoNothing`. This is a convenience thing so states
can ignore events they don't care about without needing to explicitly write a
no-op event handler.
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

We usually refer to the base `State` for an application as *Idle*. This is where
the user isn't in the middle of an interaction and the computer is waiting to
do something.

{{% notice note %}}
As a convention I'll refer to top-level `State`s as *Modes* (i.e. `IdleMode`,
`AddArcMode`, `AddPointMode`, etc.), with any sub-states being referred to as
just states.

This is just something I've noticed when watching people train new users at
work. I'm not sure how widespread the convention is. The top-level `State`
that a user has conscious control over (e.g. by clicking buttons on the
toolbar) normally gets referred to as a *Mode*, and intermediate `State`s
created while performing an action inside a mode aren't normally significant
enough (to an end user) to get a bespoke name.
{{% /notice %}}

First we need to create a type representig the `Idle` state and implement
`State` for it.

```rust
// demo/src/modes/idle.rs

use crate::modes::State;

#[derive(Debug)]
pub struct Idle;

impl State for Idle {}
```

We'll also need to tell Rust that `idle.rs` is part of the `modes` module and
we want the `Idle` mode publicly accessible.

```rust
// demo/src/modes/mod.rs

mod idle;

pub use idle::Idle;
```

Next we need to figure out what we want our `Idle` mode to do. Some normal
responsibilities for an `Idle` mode are,

- Clicking on one or more objects to select them
- Triggering a "drag" action when the user clicks and drags on an object
- Clearing the current selection when the user clicks in the middle of nowhere

In addition to this we can hard-code a couple keyboard shortcuts.

- `A` - transitions to `ArcMode` for drawing arcs
- `L` - transitions to `LineMode` for drawing lines
- `P` - transitions to `PointMode` for drawing points

{{% notice note %}}
This is mainly because I'm lazy and don't want to mess around with giving the
`arcs` demo a toolbar for changing modes just yet, but not having to worry
about external transitions right away should also make it easier for the
reader to follow.
{{% /notice %}}

I'm envisioning something like this for our `Idle` mode.

{{< mermaid >}}
stateDiagram

    state arc: Arc Mode
    state line: Line Mode
    state point: Point Mode

    [*] --> Idle
    Idle --> arc: A
    Idle --> line: L
    Idle --> point: P
    line --> Idle: Cancel
    arc --> Idle: Cancel
    point --> Idle: Cancel

    state Idle {
        state "dragging" as idle_dragging
        idle --> idle_dragging: Mouse Down
        idle_dragging --> idle_dragging: Mouse Move
        idle_dragging --> idle: Mouse Up
    }

{{< /mermaid >}}

### Idle Mode Keyboard Shortcuts

The keyboard shortcuts for changing to `AddArcMode` and friends is easy enough
to implement. We just need to handle the `on_key_pressed()` event and `match`
on the key that was pressed, returning a `Transition::ChangeState` if it's
a button we support.

```rust
// demo/src/modes/idle.rs

impl State for Idle {
    fn on_key_pressed(
        &mut self,
        _drawing: &mut dyn Drawing,
        event_args: &KeyboardEventArgs,
    ) -> Transition {
        match event_args.key {
            Some(VirtualKeyCode::A) => {
                Transition::ChangeState(Box::new(AddArcMode::default()))
            },
            Some(VirtualKeyCode::P) => {
                Transition::ChangeState(Box::new(AddPointMode::default()))
            },
            Some(VirtualKeyCode::L) => {
                Transition::ChangeState(Box::new(AddLineMode::default()))
            },
            _ => Transition::DoNothing,
        }
    }
}
```

We haven't actually created `AddArcMode`, `AddPointMode`, and `AddLineMode` yet,
so let's stub out some code for them.

```rust
// demo/src/modes/add_point_mode.rs

use crate::modes::State;

#[derive(Debug, Default)]
pub struct AddPointMode;

impl State for AddPointMode {}


// demo/src/modes/add_line_mode.rs

use crate::modes::State;

#[derive(Debug, Default)]
pub struct AddLineMode;

impl State for AddLineMode {}


// demo/src/modes/add_arc_mode.rs

use crate::modes::State;

#[derive(Debug, Default)]
pub struct AddArcMode;

impl State for AddArcMode {}


// demo/src/modes/mod.rs

mod add_arc_mode;
mod add_line_mode;
mod add_point_mode;

pub use add_arc_mode::AddArcMode;
pub use add_line_mode::AddLineMode;
pub use add_point_mode::AddPointMode;
```

This code isn't overly interesting. I've just created a couple new types and
done the bare minimum so they can be used as `State`s.

I've also given them default constructors because it makes switching to that
mode easier, this works when there isn't any setup that needs to be done to
enter a state (e.g. no need to create temporary objects).

To make sure we are actually changing state we can write a test.

```rust
// demo/src/modes/idle.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[derive(Debug, Default)]
    struct DummyDrawing;

    impl Drawing for DummyDrawing { }

    #[test]
    fn change_to_arc_mode() {
        let mut idle = Idle::default();
        let mut drawing = DummyDrawing;
        let args = KeyboardEventArgs::pressing(VirtualKeyCode::A);

        let got = idle.on_key_pressed(&mut drawing, &args);

        match got {
            Transition::ChangeState(new_state) => ...,
            Transition::DoNothing => panic!("We expected a state change"),
        }
    }
}
```

(I also decided to extract creating the `KeyboardEventArgs` with
`VirtualKeyCode::A` into its own `KeyboardEventArgs::pressing()` constructor)

```rust
// demo/src/modes/mod.rs

impl KeyboardEventArgs {
    /// Create a new [`KeyboardEventArgs`] which just presses a key.
    pub fn pressing(key: VirtualKeyCode) -> Self {
        KeyboardEventArgs {
            key: Some(key),
            ..Default::default()
        }
    }
}
```

The tricky bit is figuring out how to ensure we actually got the state we
expected (that `...` on the `Transition::ChangeState` branch). Every `State`
must implement `Debug` so in theory we could get the debug representation and
do some sort of `repr.contains("AddArcMode")`, but that's a bit *too* ~~hacky~~
brittle for my liking.

Another option is to use the [`std::any::Any` trait][any] as an escape hatch
intended for testing purposes. This is a bit like the `Object` in Java where
you can have a pointer to *something* and then try to downcast it to a more
specific type.

The best way to implement this is by saying anything implementing `State` needs
to have an `as_any(&self) -> &dyn Any` method. To avoid needing to manually
write this it can be pulled out into a trait which is automatically implemented
by any type that is `Any`.

```rust
// demo/src/modes/mod.rs

use std::any::Any;

/// A helper trait for casting `self` to [`Any`].
pub trait AsAny {
    fn as_any(&self) -> &dyn Any;
}

impl<A: Any> AsAny for A {
    fn as_any(&self) -> &dyn Any { self }
}
```

And then we can add `AsAny` as a pre-requisite for the `State` trait.

```rust
// demo/src/modes/mod.rs

pub trait State: Debug + AsAny {
    ...
}
```

To make the testing code easier I'll also add a method to `Transition` which lets
us check whether it will change to a particular `State`.

```rust
// demo/src/modes/mod.rs

impl Transition {
    /// Checks whether the transition will change to a particular [`State`].
    pub fn changes_to<S>(&self) -> bool
    where S: State + 'static
    {
        match self {
            Transition::ChangeState(new_state) => (**new_state).as_any().is::<S>(),
            _ => false,
        }
    }
}
```

Now we can write tests for our three keyboard shortcuts. Thanks to the helper
functions we made along the way our tests are actually pretty readable.

```rust
// demo/src/modes/idle.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn change_to_arc_mode() {
        let mut idle = Idle::default();
        let mut drawing = DummyDrawing::default();
        let args = KeyboardEventArgs::pressing(VirtualKeyCode::A);

        let got = idle.on_key_pressed(&mut drawing, &args);

        assert!(got.changes_to::<AddArcMode>());
    }

    #[test]
    fn change_to_line_mode() {
        let mut idle = Idle::default();
        let mut drawing = DummyDrawing::default();
        let args = KeyboardEventArgs::pressing(VirtualKeyCode::L);

        let got = idle.on_key_pressed(&mut drawing, &args);

        assert!(got.changes_to::<AddLineMode>());
    }

    #[test]
    fn change_to_point_mode() {
        let mut idle = Idle::default();
        let mut drawing = DummyDrawing::default();
        let args = KeyboardEventArgs::pressing(VirtualKeyCode::P);

        let got = idle.on_key_pressed(&mut drawing, &args);

        assert!(got.changes_to::<AddPointMode>());
    }
}
```

{{% notice note %}}
Some would argue the use of `std::any::Any` in Rust to do downcasting or
dynamic type checking is a bit of a code smell for a strongly typed language,
and I would be inclined to agree with them.

In normal production code, changing logic based on something's type at
runtime can result in brittleness and invisible coupling. It also hints that
maybe there's actually some deeper abstraction trying to get out, and the
need to have dynamic checks is your code's way of telling you this.

That said, we're not trying to change the main program's behaviour using
dynamic typing. This is mainly for testing purposes, and *maybe* also a tool of
last resort if we realise we've engineered ourselves into a corner with this
architecture six months down the track.
{{% /notice %}}

We should also add a test to make sure pressing other keys does nothing.

```rust
// demo/src/modes/idle.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn pressing_any_other_key_does_nothing() {
        let mut idle = Idle::default();
        let mut drawing = DummyDrawing;
        let args = KeyboardEventArgs::pressing(VirtualKeyCode::Q);

        let got = idle.on_key_pressed(&mut drawing, &args);

        assert!(got.does_nothing());
    }
}


// demo/src/modes/mod.rs

impl Transition {
    ...

    /// Is this a no-op [`Transition`]?
    pub fn does_nothing(&self) -> bool {
        match self {
            Transition::DoNothing => true,
            _ => false,
        }
    }
}
```

### Dragging

Dragging is one of those things which just comes naturally for a human.
Because we're used to picking things up and moving them in the real world
without much mental exertion, people don't stop to think how complex your
basic "drag" interaction can be.

The *"Happy Path"* looks something like this... When in idle mode, if the
user presses the left mouse button we'll mark whatever is under the cursor as
"selected". Then if we receive "mouse moved" events, all selected items get
translated by the amount the mouse has moved. When the mouse button is
released, we stop dragging and "commit" the changes to some sort of
`UndoRedoBuffer` so the user can undo or redo the drag.

We also need to consider a bunch of edge cases,

- What do you do if the user clicks in the middle of nowhere?
- How can a user cancel dragging midway through (e.g. if the drag was accidental)
  and what happens to the objects being dragged?
- How do we handle *debouncing*? Often, when a user tries to click something
  the mouse will move by a couple pixels between the "mouse down" and "mouse
  up" events. If we naively interpreted this as a drag then you'll get lots of
  complaints saying *"things jump a bit whenever I try to select them"*

{{% notice note %}}
Interactivity almost always needs to be paired with some sort of Undo/Redo
mechanism. This lets users undo accidental changes or look back in time to see
what the world looked like several changes ago.

I'm not going to talk about Undo/Redo mechanisms too much here (I'm still
trying to think of a nice way to implement it in `arcs`), other than to
mention that having a robust way to apply and revert changes to the world is
important... And like a lot of things, they can be tricky to implement in a
way that will scale and allow you to maintain some semblance of sanity in the
long term.
{{% /notice %}}

At this point we'll need to give `Idle` its own nested state machine.

I'll call the initial state `WaitingToSelect` seeing as that's what it does...
Plus `Idle` is already taken.

```rust
// demo/src/modes/idle.rs

/// [`Idle`]'s base sub-state.
///
/// We are waiting for the user to click so we can change the selection or start
/// dragging.
#[derive(Debug, Default)]
struct WaitingToSelect;

impl State for WaitingToSelect {}
```

We also need to update `Idle` to have a `nested` field and give it a default
constructor that sets `nested` to the `WaitingToSelect` state.

```rust
// demo/src/modes/idle.rs

#[derive(Debug)]
pub struct Idle {
    nested: Box<dyn State>,
}

impl Default for Idle {
    fn default() -> Idle {
        Idle {
            nested: Box::new(WaitingToSelect::default()),
        }
    }
}
```

To implement `WaitingToSelect` we'll need to handle the `on_mouse_down()`
event and ask the `Drawing` for a list of items under the cursor.

That requires `Drawing` to have some sort of `entities_under_point()` method.

```rust
// demo/src/modes/mod.rs

use arcs::{Point, components::DrawingObject};
use specs::Entity;

pub trait Drawing {
    /// Get a list of all the entities which lie "under" a point, for some
    /// definition of "under".
    ///
    /// Typically this will be implemented by the drawing canvas having some
    /// sort of "pick box" where anything within, say, 3 pixels of something is
    /// considered to be "under" it.
    fn entities_under_point(
        &self,
        location: Point,
    ) -> Box<dyn Iterator<Item = Entity>>;

    ...
}
```

A caller asks the `Drawing` an iterator over the entities underneath some
`location` on the drawing. We've decided to use an iterator here instead of
greedily storing the results in a `Vec` because the number of items under the
cursor can be potentially massive (imagine zooming all the way out and clicking,
the *entire* drawing would be "under" the cursor). Additionally a lot of code
will just care about the first object found under the cursor, so we can avoid
unnecessary work by being lazy.

Unfortunately the iterator itself needs to use dynamic dispatch so we can
make `Drawing` object safe. There's no real way to avoid the allocation while
maintaining object safety, but it shouldn't be too bad considering how
expensive these lookups can be.

Now we can stub out the body for `on_mouse_down()`.

```rust
// demo/src/modes/idle.rs

use crate::modes::{Drawing, MouseEventArgs, Transition};

impl State for WaitingToSelect {
    fn on_mouse_down(
        &mut self,
        drawing: &mut dyn Drawing,
        args: &MouseEventArgs,
    ) -> Transition {
        let mut items_under_cursor = drawing.entities_under_point(args.location);

        match items_under_cursor.next() {
            Some(entity) => unimplemented!(),
            _ => unimplemented!(),
        }
    }
}
```

Looking back at the intended behaviour, it seems like we'll need to update
`Drawing` with a way to select a specific object and unselect everything.

```rust
// demo/src/modes/mod.rs

pub trait Drawing {
    ...

    /// Mark an object as being selected.
    fn select(&mut self, target: Entity);

    /// Clear the selection.
    fn unselect_all(&mut self);
}
```

This gives us enough to complete the `on_mouse_down()` method.

```rust
// demo/src/modes/idle.rs

impl State for WaitingToSelect {
    fn on_mouse_down(
        &mut self,
        drawing: &mut dyn Drawing,
        args: &MouseEventArgs,
    ) -> Transition {
        let first_item_under_cursor =
            drawing.entities_under_point(args.location).next();

        match first_item_under_cursor {
            Some(entity) => {
                drawing.select(entity);
                Transition::ChangeState(Box::new(DraggingSelection::default()))
            },
            _ => {
                drawing.unselect_all();
                Transition::DoNothing
            }
        }
    }
}

/// The left mouse button is currently pressed and the user is dragging items
/// around.
#[derive(Debug, Default)]
struct DraggingSelection;

impl State for DraggingSelection {}
```

Now we need to implement `DraggingSelection`, the actual dragging action. The
code for this is pretty simple, when `on_mouse_move()` gets called we ned to
calculate how much the cursor has been moved and translate all selected
entities accordingly.

We aren't worrying about Undo/Redo at this point, so when the mouse button is
released (`on_mouse_up()`) we just switch back to the `WaitingToSelect` state.

```rust
// demo/src/modes/mod.rs

use arcs::Vector;

pub trait Drawing {
    ...

    /// Translate all selected objects by a specific amount.
    fn translate_selection(&mut self, displacement: Vector);
}


// demo/src/modes/idle.rs

#[derive(Debug)]
struct DraggingSelection {
    previous_location: Point,
}

impl State for DraggingSelection {
    fn on_mouse_move(
        &mut self,
        drawing: &mut dyn Drawing,
        args: &MouseEventArgs,
    ) -> Transition {
        drawing.translate_selection(args.location - self.previous_location);
        self.previous_location = args.location;

        Transition::DoNothing
    }

    fn on_mouse_up(
        &mut self,
        drawing: &mut dyn Drawing,
        args: &MouseEventArgs,
    ) -> Transition {
        Transition::ChangeState(Box::new(WaitingToSelect::default()))
    }
}
```

The implementation is deliberately simple for now. We aren't even handling
debounce or cancellation, but you might see how you'd implement them.

## A Brief Intermission For Refactoring

I don't know about you, but we've only written a couple states so far and I'm
already feeling like that `Drawing` trait will turn into a massive interface
pretty quickly. Every time we need to interact with the drawing we need to add
more methods, and as the proverb goes, *"The bigger the interface, the weaker
the abstraction"*.

Our `Drawing` interface (the interface a `State` can use to interact with the
outside world) also seems to have a bit of an identitiy crisis on its hands.
Despite being called a `Drawing`, this interface comes across as something
which gives us access to the ECS's [`specs::World`][specs-world], has a
`Viewport` representing which part of the drawing is being displayed,
contains the `UndoRedoBuffer`, and maybe some knobs and levers for
communicating with the UI (e.g. to request that the canvas gets redrawn).

Using this interpretation, the current `Drawing` trait seems a little...
confused.

Even its name isn't quite correct. We aren't necessarily giving each `State` a
reference to the drawing, they're getting contextual information relevant to
the drawing and application as a whole. Hmm... How about `ApplicationContext`?

```rust
// demo/src/modes/mod.rs

/// Contextual information passed to each [`State`] when it handles events.
pub trait ApplicationContext {
    fn world(&self) -> &World;
    fn world_mut(&mut self) -> &mut World;
    fn viewport(&self) -> Entity;

    /// An optimisation hint that the canvas doesn't need to be redrawn after
    /// this event handler returns.
    fn suppress_redraw(&mut self) {}
}

pub trait State: Debug + AsAny {
    /// The left mouse button was pressed.
    fn on_mouse_down(
        &mut self,
        _ctx: &mut dyn ApplicationContext,
        _event_args: &MouseEventArgs,
    ) -> Transition {
        Transition::DoNothing
    }

    ...
```

Now we have a way to access the `World`, the methods that were previously
required for `Drawing` (i.e. `ApplicationContext`) can be implemented as
provided methods.

But first we need to give `arcs` a way to mark things as *Selected*.

See, I kinda lied to you earlier when we implemented `WaitingToSelect`. At
the time I only ever ran the code under test using a mock `Drawing`, but now
is as good a time as any seeing as we need to give `ApplicationContext` a set
of `select()` and `unselect_all()` methods.

```rust
// arcs/src/components/selected.rs

use specs::prelude::*;
use specs_derive::Component;

/// An empty [`Component`] used to mark an [`Entity`] as selected.
#[derive(Debug, Copy, Clone, Default, PartialEq, Component)]
#[storage(NullStorage)]
pub struct Selected;


// arcs/src/components/mod.rs

mod selected;

pub use selected::Selected;
```

From here we can add `selected()` and `unselect_all()` to `ApplicationContext`.

```rust
// demo/src/modes/mod.rs

pub trait ApplicationContext {
    ...

    /// Mark an object as being selected.
    fn select(&mut self, target: Entity) {
        self.world()
            .write_storage()
            .insert(target, Selected)
            .unwrap();
    }

    /// Clear the selection.
    fn unselect_all(&mut self) {
        self.world().write_storage::<Selected>().clear();
    }
}
```

The [`arcs::algorithms::Translate`][translate] algorithm can be used to make
`translate_selection()` almost trivial. The only hard part is deciphering the
type returned by `system_data()`.

```rust
// demo/src/modes/mod.rs

pub trait ApplicationContext {
    ...

    /// Translate all selected objects by a specific amount.
    fn translate_selection(&mut self, displacement: Vector) {
        let world = self.world();
        let (entities, selected, mut drawing_objects): (
            Entities,
            ReadStorage<Selected>,
            WriteStorage<DrawingObject>,
        ) = world.system_data();

        for (_, _, drawing_object) in
            (&entities, &selected, &mut drawing_objects).join()
        {
            drawing_object.geometry.translate(displacement);
        }
    }
}
```

## Wiring it Up to the UI

We now have a system for letting users interact with the application in a
structured way, let's wire it up to the UI and make sure it actually works!

The browser demo for `arcs` is written using a framework called [seed][seed].
The framework itself is fairly lightweight, with the idea being you provide a
`update()` function which takes some "message" and uses it to update your
`Model`, and a a `view()` method which will create a representation of your
UI ("virtual DOM") and wire up functions to turn a JavaScript event into a
message to be sent to `update()`.

At the moment the UI already kinda handles click events. I was previously using
it to test my math for coordinate transforms (converting from pixel locations
on a canvas to the corresponding point on the drawing) were correct by clicking
on the canvas and making sure it rendered a dot under my cursor.

It's not overly high-tech (essentially the graphical equivalent of debugging
with print statements) but it's a good feeling when you can click on the
canvas and know that under the hood you've implemented all the machinery for
a zoomable, pannable viewport, plus enough rendering to start drawing coloured
dots.

First we need to update the code handling the `Msg::Clicked` message to call
`on_mouse_down()` on our `Model` (we'll implement it in a bit).

```diff
 fn update(msg: Msg, model: &mut Model, orders: &mut impl Orders<Msg>) {
     log::debug!("Handling {:?}", msg);

     match msg {
         Msg::Rendered => { ... },
-        Msg::Clicked(location) => {
-            let clicked = {
-                let viewports = model.world.read_storage();
-                let viewport = model.window.viewport(&viewports);
-                arcs::window::to_drawing_coordinates(
-                    location,
-                    viewport,
-                    model.canvas_size,
-                )
-            };
-            log::debug!("Resolved {:?} => {:?}", location, clicked);
-
-            model
-                .world
-                .create_entity()
-                .with(DrawingObject {
-                    geometry: Geometry::Point(clicked),
-                    layer: model.default_layer,
-                })
-                .build();
+        Msg::Clicked(cursor) => {
+            let location = {
+                let viewports = model.world.read_storage();
+                let viewport = model.window.viewport(&viewports);
+                arcs::window::to_drawing_coordinates(
+                    cursor,
+                    viewport,
+                    model.canvas_size,
+                )
+            };
+            model.on_mouse_down(location, cursor);
         },
         Msg::WindowResized => { ... }
     }
 }
```

We also need to give `Model` a `current_state` field.

```diff
 pub struct Model {
     world: World,
     window: Window,
     default_layer: Entity,
     canvas_size: Size2D<f64, CanvasSpace>,
+    current_state: Box<dyn State>,
 }

 impl Default for Model {
     fn default() -> Model {
         ...

         Model {
             world,
             window,
             default_layer,
             canvas_size: Size2D::new(300.0, 150.0),
+            current_state: Box::new(Idle::default()),
         }
     }
 }
```

To start using `current_state` we'll need something to act as our `State`'s
`ApplicationContext`. I've decided to pull this out into a "view" struct
which borrows some of our `Model`'s fields. We can't use `Model` as the
`ApplicationContext` because it owns our `current_state`, and passing `&mut
self` to `self.current_state` is no bueno.

```rust
// demo/src/lib.rs

/// A temporary struct which presents a "view" of [`Model`] which can be used
/// as a [`ApplicationContext`].
struct Context<'model> {
    world: &'model mut World,
    window: &'model mut Window,
}

impl<'model> ApplicationContext for Context<'model> {
    fn world(&self) -> &World { &self.world }

    fn world_mut(&mut self) -> &mut World { &mut self.world }

    fn viewport(&self) -> Entity { self.window.0 }
}
```

Now we can finally write our `Model::on_mouse_down()` method. All it does is
construct a couple arguments then calls `self.current_state.on_mouse_down()`.

For convenience, I've pulled `Transition` handling into its own function.

```rust
// demo/src/lib.rs

impl Model {
    fn on_mouse_down(
        &mut self,
        location: Point2D<f64, DrawingSpace>,
        cursor: Point2D<f64, CanvasSpace>,
    ) {
        let args = modes::MouseEventArgs {
            location,
            cursor,
            button_state: modes::MouseButtons::LEFT_BUTTON,
        };

        let mut ctx = Context {
            world: &mut self.world,
            window: &mut self.window,
        };
        let trans = self.current_state.on_mouse_down(&mut ctx, &args);
        self.handle_transition(trans);
    }

    fn handle_transition(&mut self, transition: Transition) {
        match transition {
            Transition::ChangeState(new_state) => {
                self.current_state = new_state
            },
            Transition::DoNothing => {},
        }
    }
}
```

Okay, let's spin up the dev server and give it a test run...

<video controls src="it-doesnt-work.webm" type="video/webm" style="width:100%"></video>

Hmm... I clicked around and nothing seems to happen. Are we even calling
`on_mouse_down()`?

```diff
 impl Model {
     fn on_mouse_down(
         &mut self,
         location: Point2D<f64, DrawingSpace>,
         cursor: Point2D<f64, CanvasSpace>,
     ) {
         ...

+        log::debug!("[ON_MOUSE_DOWN] {:?}, {:?}", args, self.current_state);
+
         let trans = self.current_state.on_mouse_down(&mut ctx, &args);
         self.handle_transition(trans);
     }
 }
```

<video controls src="it-kinda-works.webm" type="video/webm" style="width:100%"></video>

Soo... looks like everything is working as intended. The problem is that our
`Idle` mode is in the `WaitingToSelect` state, but there's nothing on our canvas
to select. I'm going to declare that a success and keep going.

Next, let's wire up keyboard presses.

First we need to add a `KeyPressed` variant to `Msg`.

```diff
 #[derive(Debug, Copy, Clone, PartialEq)]
 pub enum Msg {
     Rendered,
     Clicked(Point2D<f64, CanvasSpace>),
     WindowResized,
+    KeyPressed(KeyboardEventArgs),
 }
```

Then we need to register for the key pressed event and make sure it gets turned
into a `Msg::KeyPressed` message.

```diff
 fn view(model: &Model) -> impl View<Msg> {
     div![div![
         attrs![ At::Class => "canvas-container" ],
         style! {
             St::Width => "100%",
             St::Height => "100%",
             St::OverflowY => "hidden",
             St::OverflowX => "hidden",
         },
         canvas![
             attrs![
                 At::Id => CANVAS_ID,
                 At::Width => model.canvas_size.width,
                 At::Height => model.canvas_size.height,
             ],
-            mouse_ev(Ev::MouseDown, Msg::from_click_event)
+            mouse_ev(Ev::MouseDown, Msg::from_click_event),
+            keyboard_ev(Ev::KeyDown, Msg::from_key_press)
         ],
     ]]
 }

 impl Msg {
     pub fn from_click_event(ev: MouseEvent) -> Self {
         let x = ev.offset_x().into();
         let y = ev.offset_y().into();

         Msg::Clicked(Point2D::new(x, y))
     }
+
+    pub fn from_key_press(ev: KeyboardEvent) -> Self {
+        Msg::KeyPressed(KeyboardEventArgs {
+            shift_pressed: ev.shift_key(),
+            control_pressed: ev.ctrl_key(),
+            key: ev.key().parse().ok(),
+        })
+    }
 }
```

We can now implement the `Msg::KeyPressed` handler like we did with
`Msg::Clicked`.

```diff
 fn update(msg: Msg, model: &mut Model, orders: &mut impl Orders<Msg>) {
     log::debug!("Handling {:?}", msg);

     match msg {
         Msg::Rendered => { ... },
         Msg::Clicked(cursor) => { ... },
+        Msg::KeyPressed(args) => model.on_key_pressed(args),
         Msg::WindowResized => { ... },
     }

     ...
 }


 impl Model {
     ...

+    fn on_key_pressed(&mut self, args: KeyboardEventArgs) {
+        let mut ctx = Context {
+            world: &mut self.world,
+            window: &mut self.window,
+        };
+
+        let trans = self.current_state.on_key_pressed(&mut ctx, &args);
+        self.handle_transition(trans);
+    }

     ...
 }
```

I ended up needing to use [this hack][so] because `<canvas>` elements don't
actually support key up/down events, but now we can receive keyboard events and
even change to `AddArcMode` when `VirtualKeyCode::A` is pressed!

<video controls src="keyboard-events.webm" type="video/webm" style="width:100%"></video>

The crazy part is I spent longer troubleshooting the `<canvas>` keyboard event
browser quirk than I did re-working the UI to use proper modes. Sure, it doesn't
actually do anything at the moment, but that's just because there's no mode for
adding points to the drawing.

## Add Point Mode

I didn't want to finish off without at least showing you a dot that we can drag
around the screen sp let's implement `AddPointMode`.

The first thing we need to do is define how `AddPointMode` will react to actions
from the user. Normally I'll use a whiteboard for this and bounce ideas off
coworkers, but you've got to make do with what you've got.

Our `AddPointMode` won't be as simple as *"place a point wherever the user
clicks"*. If you watch how users interact with a CAD program you'll notice they
tend to hold the mouse button down and fine-tune where they want the point to go
before releasing the button and "committing" the change.

Sometimes they'll realise midway through that they didn't want to place a point,
so you need to give the user a way to cancel the interaction. In the wild, I've
seen roughly two ways people try to do this, one is to hit `<ctrl-Z>` ("I want
to undo the point I've started creating") and the other is to press `<esc>`
("I want to **escape** this interaction").

As someone who seeks out the vim keybindings for pretty much every editor or
IDE they use, pressing `<esc>` seems the more natural of the two. That said,
I just admitted I'm biased plus I'm not your "ordinary" user, so it's always
good to get another person's opinion.

The state machine diagram for this is almost trivial.

{{< mermaid >}}
stateDiagram
    state "Add Point Mode" as point

    state point {
        state "Waiting To Place" as idle
        state "Placing Point" as placing

        idle --> placing: Mouse Down
        placing --> idle: Mouse Up/Cancel
    }
{{< /mermaid >}}

The simplicity of our state machine diagram hides a fair amount of detail
though...

First, let's create a `WaitingToPlace` state to act as `AddPointMode`'s base
state.

```rust
// arcs/demo/src/modes/add_point_mode.rs

/// The base sub-state for [`AddPointMode`]. We're waiting for the user to click
/// so we can start adding a point to the canvas.
#[derive(Debug, Default)]
struct WaitingToPlace;
```

It only responds to a single event, `on_mouse_down()`.

```rust
// arcs/demo/src/modes/add_point_mode.rs

impl State for WaitingToPlace {
    fn on_mouse_down(
        &mut self,
        ctx: &mut dyn ApplicationContext,
        args: &MouseEventArgs,
    ) -> Transition {
        // make sure nothing else is selected
        ctx.unselect_all();

        let layer = ctx.default_layer();

        // create a point and automatically mark it as selected
        let temp_point = ctx
            .world_mut()
            .create_entity()
            .with(DrawingObject {
                geometry: Geometry::Point(args.location),
                layer,
            })
            .with(Selected)
            .build();

        Transition::ChangeState(Box::new(PlacingPoint::new(temp_point)))
    }
}
```

Next we need a `PlacingPoint` state which will keep track of our temporary point
and let us drag it around the screen.

```rust
// demo/src/modes/add_point_mode.rs

#[derive(Debug)]
struct PlacingPoint {
    temp_point: Entity,
}

impl PlacingPoint {
    fn new(temp_point: Entity) -> Self { PlacingPoint { temp_point } }
}
```

Next we need to implement the relevant event handlers. For `PlacingPoint` we'll
need to

- Transition back to `WaitingToPlace` when the mouse is released
- Delete the `temp_point` if we get an `on_cancelled()` event
- Move the `temp_point` if the mouse moves

```rust
// demo/src/modes/add_point_mode.rs

impl State for PlacingPoint {
    fn on_mouse_up(
        &mut self,
        _ctx: &mut dyn ApplicationContext,
        _args: &MouseEventArgs,
    ) -> Transition {
        // We "commit" the change by leaving the temporary point where it is
        Transition::ChangeState(Box::new(WaitingToPlace::default()))
    }

    fn on_mouse_move(
        &mut self,
        ctx: &mut dyn ApplicationContext,
        args: &MouseEventArgs,
    ) -> Transition {
        let world = ctx.world();
        let mut drawing_objects: WriteStorage<DrawingObject> =
            world.write_storage();

        let drawing_object = drawing_objects.get_mut(self.temp_point).unwrap();

        // we *know* this is a point. Instead of pattern matching or translating
        // the drawing object, we can just overwrite it with its new position.
        drawing_object.geometry = Geometry::Point(args.location);

        Transition::DoNothing
    }

    fn on_cancelled(&mut self, ctx: &mut dyn ApplicationContext) {
        // make sure we clean up the temporary point.
        let _ = ctx.world_mut().delete_entity(self.temp_point);
    }
}
```

So we've defined the state machine for `AddPointMode`, but if we want anything
to happen we'll need to make sure `AddPointMode` propagates `on_mouse_up()`,
`on_mouse_down()`, and `on_mouse_move()` to them.

```rust
// demo/src/modes/add_point_mode.rs

impl AddPointMode {
    fn handle_transition(&mut self, transition: Transition) {
        match transition {
            Transition::ChangeState(new_state) => {
                log::debug!(
                    "Changing state {:?} -> {:?}",
                    self.nested,
                    new_state
                );
                self.nested = new_state;
            },
            Transition::DoNothing => {},
        }
    }
}

impl State for AddPointMode {
    fn on_mouse_down(
        &mut self,
        ctx: &mut dyn ApplicationContext,
        args: &MouseEventArgs,
    ) -> Transition {
        let trans = self.nested.on_mouse_down(ctx, args);
        self.handle_transition(trans);
        Transition::DoNothing
    }

    fn on_mouse_up(
        &mut self,
        ctx: &mut dyn ApplicationContext,
        args: &MouseEventArgs,
    ) -> Transition {
        let trans = self.nested.on_mouse_up(ctx, args);
        self.handle_transition(trans);
        Transition::DoNothing
    }

    fn on_mouse_move(
        &mut self,
        ctx: &mut dyn ApplicationContext,
        args: &MouseEventArgs,
    ) -> Transition {
        let trans = self.nested.on_mouse_move(ctx, args);
        self.handle_transition(trans);
        Transition::DoNothing
    }
}
```



While we're at it, we should make sure pressing the escape key cancels the
current mode and switches back to the `Idle` state.

```rust
// demo/src/modes/add_point_mode.rs

impl State for AddPointMode {
    ...

    fn on_key_pressed(
        &mut self,
        ctx: &mut dyn ApplicationContext,
        args: &KeyboardEventArgs,
    ) -> Transition {
        if args.key == Some(VirtualKeyCode::Escape) {
            // pressing escape should take us back to idle
            self.nested.on_cancelled(ctx);
            return Transition::ChangeState(Box::new(Idle::default()));
        }

        let trans = self.nested.on_key_pressed(ctx, args);
        self.handle_transition(trans);
        Transition::DoNothing
    }


    fn on_cancelled(&mut self, ctx: &mut dyn ApplicationContext) {
        self.nested.on_cancelled(ctx);
        self.nested = Box::new(WaitingToPlace::default());
    }
}
```

The top-level application is also only handling mouse down events so we'll need
to add event handlers and `Msg` variants for `MouseUp` and `MouseMove`.

```diff

 #[derive(Debug, Copy, Clone, PartialEq)]
 pub enum Msg {
     Rendered,
-    Clicked(Point2D<f64, CanvasSpace>),
+    MouseDown(Point2D<f64, CanvasSpace>),
+    MouseUp(Point2D<f64, CanvasSpace>),
+    MouseMove(Point2D<f64, CanvasSpace>),
     KeyPressed(KeyboardEventArgs),
     WindowResized,
 }

 fn update(msg: Msg, model: &mut Model, orders: &mut impl Orders<Msg>) {
     log::trace!("Handling {:?}", msg);

     match msg {
         Msg::Rendered => { ... },
-        Msg::Clicked(cursor) => {
-            let location = {
-                let viewports = model.world.read_storage();
-                let viewport = model.window.viewport(&viewports);
-                arcs::window::to_drawing_coordinates(
-                    cursor,
-                    viewport,
-                    model.canvas_size,
-                )
-            };
-            model.on_mouse_down(location, cursor);
-        },
+        Msg::MouseDown(cursor) => model.on_mouse_down(cursor),
+        Msg::MouseUp(cursor) => model.on_mouse_up(cursor),
+        Msg::MouseMove(cursor) => model.on_mouse_move(cursor),
         Msg::KeyPressed(args) => model.on_key_pressed(args),
         Msg::WindowResized => { ... },
     }

     ...
 }

 impl Model {
-    fn on_mouse_down(
-        &mut self,
-        location: Point2D<f64, DrawingSpace>,
-        cursor: Point2D<f64, CanvasSpace>,
-    ) {
-        let args = modes::MouseEventArgs {
-            location,
-            cursor,
-            button_state: modes::MouseButtons::LEFT_BUTTON,
-        };
-        log::debug!("[ON_MOUSE_DOWN] {:?}, {:?}", args, self.current_state);
-
-
-        let mut ctx = Context {
-            world: &mut self.world,
-            window: &mut self.window,
-        };
-        let trans = self.current_state.on_mouse_down(&mut ctx, &args);
-        self.handle_transition(trans);
-    }
+    fn on_mouse_down(&mut self, cursor: Point2D<f64, CanvasSpace>) -> bool {
+        let args = self.mouse_event_args(cursor);
+        log::debug!("[ON_MOUSE_DOWN] {:?}, {:?}", args, self.current_state);
+        self.handle_event(|state, ctx| state.on_mouse_down(ctx, &args))
+    }
+
+    fn on_mouse_up(&mut self, cursor: Point2D<f64, CanvasSpace>) -> bool {
+        let args = self.mouse_event_args(cursor);
+        log::debug!("[ON_MOUSE_UP] {:?}, {:?}", args, self.current_state);
+        self.handle_event(|state, ctx| state.on_mouse_up(ctx, &args))
+    }
+
+    fn on_mouse_move(&mut self, cursor: Point2D<f64, CanvasSpace>) -> bool {
+        let args = self.mouse_event_args(cursor);
+        self.handle_event(|state, ctx| state.on_mouse_move(ctx, &args))
+    }
+
+    fn handle_event<F>(&mut self, handler: F) -> bool
+    where
+        F: FnOnce(&mut dyn State, &mut Context<'_>) -> Transition,
+    {
+        let mut suppress_redraw = false;
+        let transition = handler(
+            &mut *self.current_state,
+            &mut Context {
+                world: &mut self.world,
+                window: &mut self.window,
+                default_layer: self.default_layer,
+                suppress_redraw: &mut suppress_redraw,
+            },
+        );
+        self.handle_transition(transition);
+        if suppress_redraw {
+            log::debug!("Redraw suppressed");
+        }
+        !suppress_redraw
+    }

     ...
 }
```

{{% notice note %}}
It's annoying that we need to implement this sort of dragging a second time
instead of just reusing the code from our `Idle` mode, but that's the
trade-off we made back when thinking up a design. I'm also feeling funny
about needing to constantly propagate events down to nested state machines.

If we were using a pushdown automata, dragging the current selection around
would be a simple case of pushing the `DraggingSelection` state onto the stack,
then when the mouse is released it would be popped and return control back to
`AddPointMode`.

Likewise, events would be sent directly to the innermost `State` so there'd be
no need to explicitly propagate them down.

It's all about trade-offs. In this case, dragging is simple enough I'm okay with
writing it twice because it means we know exactly what's going on when
`DraggingSelection` runs. If we were using a pushdown automata
`DraggingSelection` would have no way of knowing which assumptions are being
made by states higher in the stack so it might be easier to introduce bugs, or
at least some form of *"spooky action at a distance"*.

You could even combine pushdown automata with some sort of bubbling mechanism
where a state will explicitly say whether the event is "handled", allowing
events to be sent to the innermost state first and continually bubbled up
until someone handles the event or we reach the top of the stack. This is how
a lot of GUIs do things (e.g. `preventDefault()` in the browser) to allow
components to be composable, but I feel like that'd just make our already
complex mode system even harder to reason about...
{{% /notice %}}

Something I'd also like to draw your attention to is how little code that
required. Sure we needed to duplicate some of the dragging logic, but overall
it was pretty simple to plug new functionality into our app.

## Conclusions

Looking back, I'm not 100% sure we should have gone the *Nested State Machine*
route instead of using a *Pushdown Automata*.

Having to constantly propagate events down to inner state machines is a bit
annoying to do in Rust, and the various tricks we could have employed to make
the process easier would end up making the code less readable. The large
projects I've needed to implement interactivity for in the past have all had
some form of inheritance, and using inheritance this delegation could be solved
quite elegantly.

{{% expand "Example of event delegation in C#" %}}
```cs
abstract class State
{
    public virtual void OnMouseDown(ApplicationContext ctx, MouseEventArgs args) {}

    ...
}

/// <summary>
/// A State which contains a nested state machine.
/// </summary>
abstract class StateWithNestedStateMachine: State // name subject to much bikeshedding
{
    /// <summary>
    /// The current state in a nested state machine.
    /// </summary>
    protected State Inner { get; set; }

    public virtual void OnMouseDown(ApplicationContext ctx, MouseEventArgs args)
    {
        // by default we just want to propagate the event down and handle any
        // resulting transitions
        var transition = Inner.OnMouseDown(ctx, args);
        HandleTransition(transition);
    }

    ...

    protected void HandleTransition(Transition trans)
    {
        if (trans is ChangeStateTransition change)
        {
            Inner = change.NewState;
        }
    }
}
```
{{% /expand %}}

That said, even if it required a bit more code having everything written out
explicitly means our mode system is pretty easy to understand at a glance.
When troubleshooting there's no need for contextual knowledge (i.e. knowing that
a particular branch can only be hit when something a couple levels higher in the
pushdown automata stack is in a particular state) and you can just follow the
code.

I've found that to tackle these sorts of problems outside of toy projects, you
*really* need to make sure your implementation is backed by a formal model or
pattern. Implementing interactivity by attaching intermediate variables to your
top-level `Window` (or `Model` in our case) and throwing more switch-case
statements at the problem is a great way to create a code monster and make your
successors/coworkers/future self hate you.

And yes, if you are curious, we can indeed now draw points on the canvas 🎉

<video controls src="adding-points.webm" type="video/webm" style="width:100%"></video>

(please excuse the poor frame rate from OBS)

[shotgun]: https://refactoring.guru/smells/shotgun-surgery
[state]: https://refactoring.guru/design-patterns/state
[pda]: https://en.wikipedia.org/wiki/Pushdown_automaton
[any]: https://doc.rust-lang.org/std/any/trait.Any.html
[drawing-object]: https://docs.rs/arcs/0.2.0/arcs/components/struct.DrawingObject.html
[specs-world]: https://docs.rs/specs/0.15.1/specs/struct.World.html
[translate]: https://docs.rs/arcs/0.2.0/arcs/algorithms/trait.Approximate.html
[seed]: https://seed-rs.org/
[so]: https://stackoverflow.com/a/16492878/7149940