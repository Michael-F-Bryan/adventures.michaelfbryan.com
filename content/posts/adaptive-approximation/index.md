---
title: "An Algorithm for Adaptively Sampling Polynomials"
date: "2020-06-07T10:49:55+08:00"
draft: true
tags:
- Rust
- algorithms
---

I've [started working on][splines-pr] adding *Interpolated Splines* to the
[`arcs`][arcs] crate and a feature I'd really like is being able to
approximate the spline as a bunch of points. This is useful when you want to
draw the polyline on a screen because you can draw lines through each point
and get a pretty good approximation of the polyline's shape.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Polyline

At its most basic, an *Interpolated Polyline* is composed of a series of
segments, where each segment is a polynomial function (usually cubic)
defining that section of the spline.

Polylines can double back on themselves and fail [the vertical line
test][vertical-test], so we can't define each segment using something like $y
= f(x)$. Instead we [introduce another parameter][parameter], $t$ (I usually
think of it as the % distance along the polyline, or the fractional segment
number), and define each component in terms of $t$. Parameterising an
equation is the math equivalent of adding [another level of
indirection][indirection].

In Rust parlance, we might write this like so:

```rust
struct Polyline {
    x_segments: Vec<CubicSegment>,
    y_segments: Vec<CubicSegment>,
}

struct CubicSegment {
    a: f64,
    b: f64,
    c: f64,
    d: f64,
}

impl CubicSegment {
    fn evaluate(&self, t: f64) -> f64 {
        // f(t) = a + bt + ct^2 + dt^3
        self.a + self.b * t.powi(1) + self.c * t.powi(2) + self.d * t.powi(3)
    }
}
```

{{% notice note %}}
How we actually derive the coefficients (`a`, `b`, `c`, and `d`) for each
`CubicSegment` will be explored in another article, but for now we can just
assume they exist.
{{% /notice %}}

Based on this definition we can create a function that evaluates the
`Polyline` at some fraction, `t`, along its length.

```rust
impl Polyline {
    pub fn point_at(&self, t: f64) -> (f64, f64) {
        debug_assert!(
            0.0 <= t && t <= 1.0,
            "{} should be a fraction between 0 and 1, inclusive",
            t,
        );

        let segment_number = t * self.len() as f64;
        let ix = segment_number.floor() as usize;
        let t = segment_number.fract();

        let x = self.x_segments[ix].evaluate(t);
        let y = self.y_segments[ix].evaluate(t);

        (x, y)
    }

    pub fn len(&self) -> usize {
        self.x_segments.len()
    }
}
```

## The Implementation

## Conclusions

[splines-pr]: https://github.com/Michael-F-Bryan/arcs/pull/27
[arcs]: https://github.com/Michael-F-Bryan/arcs
[vertical-test]: https://en.wikipedia.org/wiki/Vertical_line_test
[parameter]: https://en.wikipedia.org/wiki/Parametric_equation
[indirection]: https://en.wikipedia.org/wiki/Fundamental_theorem_of_software_engineering
