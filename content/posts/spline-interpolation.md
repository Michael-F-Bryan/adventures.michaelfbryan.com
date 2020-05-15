---
title: "An Intro to Polylines - The Interpolated Spline"
date: "2020-05-15T23:53:09+08:00"
draft: true
tags:
- Rust
- Geometry
---

I do a lot of work in the CAD world and one of my tools is the spline, it
essentially gives you a way to tell the computer, *"here's a bunch of points,
please draw a smooth line that passes through them"*.

The term, *"spline"*, originally came from ship builders who would use flexible
strips of wood held using pegs to draw smooth curves, but nowadays the term can
refer to a variety of curves.

In an effort to explore the mathematics behind the various types of spline, I
thought I'd try to implement them myself and add them to [`arcs`][arcs], a
Rust CAD engine I've been playing around with in my spare time.

Here are some of the splines we can choose from:

- [Hermite Spline](https://en.wikipedia.org/wiki/Cubic_Hermite_spline) - the
  mathematical function you get when trying to minimise the "tension" in a
  flexible curve passing
- [B-Spline](https://en.wikipedia.org/wiki/B-spline)
- [NURBS](https://en.wikipedia.org/wiki/Non-uniform_rational_B-spline) - The
  general form of a *B-Spline*, used all over the place in CAM
- [Bézier Curve](https://en.wikipedia.org/wiki/B%C3%A9zier_curve) - sibling of
  the *B-Spline*, often used in fonts
- [Interpolated Cubic/Quadratic Spline][wiki] - what you get after fitting a
  polynomial to the curve

As the easiest for me to wrap my head around, I thought I'd start with the
[*Interpolated Spline*][wiki].

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The General Idea

## Quadratic Spline in Rust

## Generalising To Higher Degrees

## Taking Derivatives

## Conclusions

[arcs]: https://github.com/Michael-F-Bryan/arcs
[wiki]: https://en.wikipedia.org/wiki/Polynomial_interpolation
