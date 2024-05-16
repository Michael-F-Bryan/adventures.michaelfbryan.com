---
title: "Using Rust's Type System to Verify Your Maths"
date: "2021-02-02T16:27:17+08:00"
draft: true
tags:
- Rust
- Architecture
---

Audience: Software engineers wanting to use Rust in the real world.

Introduction:

- One of the most powerful tools in my CAD/CAM toolbelt
- How can I write code with less logic errors or stupid bugs?
- Use the Mars Lunar Orbiter as an example

Motivation:

- Code involving maths is often hard to read
- Primitive obsessions/stringly-typed APIs
- Often comes up in physics
  - CAM and simulation
- Improves readability and makes code self-documenting

The `CanvasSpace`/`DrawingSpace` dichotomy in CAD:

- Mention experience with `arcs`
- Using a common `Vector2D` type can lead to confusion
- The only link between the two is the `Viewport` and its transformation matrix

War Stories:

- Angles and modular arithmetic in Profiler 9
  - Is that `double` in radians or degrees?
  - Soooo many bugs where an arc would be around the wrong way. For example,
    instead of having a nice rounded corner it might be inverted or rotated by
    90 degrees
  - Would split it into `Angle` (`0 <= Angle < 2π`) and `AngularDifference`
    (`-2π <= Angle <= 2π`) to represent the different domains and operations

Conclusion:

- Use the type system where you can!
- Crates like `euclid` and `uom` are amazing

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}


