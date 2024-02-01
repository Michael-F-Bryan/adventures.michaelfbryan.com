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

Normally you'll define a polyline as some sort of mathematical function which
spits out X-Y coordinates, so the simplest approximation strategy is to split
the curve's length into `n` equally spaced segments. It might look something
like this:

```rust
fn approximate(num_pieces: usize, poly: &Polyline) -> impl Iterator<Item = Point> {
    let step_size = 1.0 / num_pieces as f64;

    (0..num_pieces)
        .map(|step| step_size * step)
        .map(|t| poly.evaluate(t))
}
```

This works but has a couple problems...

For example, what step size (the reciprocal of `n`) should I use split the
curve into? Too few and our connect-the-dots approximation will look blocky
or miss features, however too many pieces can massively hurt performance
because we may be processing 10-10,000x more line segments than we need to
(and need to copy all those bytes around).

points at corners (which is great, because that's where the curve is changing
quickly) and just as many points along the straight stretches (which isn't as
great, because we could have approximated it as a single line segment).

It also doesn't feel very elegant. Usually you'll be able to use
domain-specific knowledge to estimate how many pieces to split a curve into
(e.g. you know the drawing will be consumed by a machine with 0.1 mm
tolerances) and that's file, but it still feels naive and taking the
conservative approach leaves a lot of performance on the table.

I feel like we can improve on this approach by taking a smarter approach.

Often polylines will be composed of tight corners connected by long
straight-ish sections, so instead of using a uniform step size what if we
adjusted the step so we increase the point density when things change
rapidly? Conversely, we could space them out when the curve is fairly
straight to reduce the overall number of points in the approximation.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Polyline

At its most basic, an *Interpolated Spline* is a polyline composed of a
series of segments, where each segment is a polynomial function (usually
cubic) defining that section of the spline.

Polylines can double back on themselves and fail [the vertical line
test][vertical-test], so we can't define each segment using something like $y
= f(x)$. Instead we [introduce another parameter][parameter], $t$ (I usually
think of it as the % distance along the polyline, or the fractional segment
number), and define each component in terms of $t$. Parameterising an
equation is the mathematical equivalent of adding [another level of
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

## Sprinkling in a Bit of Calculus

## Conclusions

[splines-pr]: https://github.com/Michael-F-Bryan/arcs/pull/27
[arcs]: https://github.com/Michael-F-Bryan/arcs
[vertical-test]: https://en.wikipedia.org/wiki/Vertical_line_test
[parameter]: https://en.wikipedia.org/wiki/Parametric_equation
[indirection]: https://en.wikipedia.org/wiki/Fundamental_theorem_of_software_engineering
