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

I have seen such code monsters in the wild. They are not fun to maintain or
debug. Please don't do this.

A much better solution is to use the [*State Pattern*][state].

{{% notice tip %}}
It may sound weird for someone who is both a Functional Programming fan and
diehard Rust coder to be promoting a stereotypically object-oriented pattern,
but bear with me.

There is method to this madness.
{{% /notice %}}

The idea is actually pretty simple, encapsulate everything about a particular
"state" into an object which can transition to other states in response to
certain events.

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

Another very important aspect of this pattern is how it is completely
decoupled from the `Window` (as far as each `State` is concerned, it doesn't
even know the `Window` exists).

When your `State` doesn't know anything about the rest of the world and can
only interact with data passed to it as parameters it becomes almost trivial
to test. Create a dummy drawing in memory, instantiate the `State`, then call
an event handler and make sure it behaves as expected.

## A Note On Optimising and Dynamic Dispatch

## The Infrastructure

## Idle Mode

## Add Point Mode

## Conclusions

[shotgun]: https://refactoring.guru/smells/shotgun-surgery
[state]: https://refactoring.guru/design-patterns/state