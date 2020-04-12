---
title: "Line Simplification with Ramer–Douglas–Peucker"
date: "2020-02-23T21:56:00+08:00"
tags:
- Rust
- algorithms
---

The other day I needed to do a fairly routine graphical operation, to
"simplify" a polyline with many points into a simpler polyline which has
roughly the same shape plus or minus some `tolerance` factor.

My actual use case was in sending linear movements to a CNC machine. Drawings
are defined using floating point numbers and can be "accurate" to about 7-15
decimal places (depending on if you use floats or doubles) but when you take
the machine's mechanical tolerances and material effects into account the
final cut is only really accurate to about 1 decimal place (0.1 mm). If I
were to simplify the path with a tolerance of, say, 0.05 mm I could massively
reduce the number of points sent to the machine (which reduces the amount of
data sent, buffer sizes, communications overhead, etc.) with minimal effect
on the accuracy.

Other places where this operation can be useful are:

- Cleaning up paths from from "noisy" data sources (imagine getting pixel
  locations from an [edge detection][edge-detection] algorithm)
- When you just need a general shape and more points would have a large
  negative effect on performance for the consumer (e.g. a [nesting
  algorithm][nesting]).

My go-to tool for this sort of operation is the [Ramer–Douglas–Peucker
algorithm][wiki], and I thought this would make a nice addition to the
[arcs][arcs] library I've been working on over the last couple months.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Algorithm

The algorithm itself uses a remarkably simple recursive algorithm,

1. Mark the `first` and `last` points as kept
2. Find the point, `p` that is the farthest from the first-last line segment.
   If there are no points between `first` and `last` we are done (the base case)
3. If `p` is closer than `tolerance` units to the line segment then
   everything between `first` and `last` can be discarded
4. Otherwise, mark `p` as kept and repeat steps 1-4 using the points between
   `first` and `p` and between `p` and `last` (the call to recursion)

This animation from [the Wikipedia article][wiki] can help wrap your head
around how it works.

{{< figure
    src="https://upload.wikimedia.org/wikipedia/commons/3/30/Douglas-Peucker_animated.gif"
    link="https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm"
    caption="Visualisation of the Ramer-Douglas-Peucker algorithm"
    alt="Visualisation of the Ramer-Douglas-Peucker algorithm"
>}}

Like most divide-and-conquer algorithms, in the ideal case this completes in
`O(n log n)` time. However, if you hit an edge case where the "furthest"
point is right next to the endpoints this can blow out to `O(n^2)`.

I don't normally worry about computational complexity too often (computers
are fast), but because it's quite common for my application to work with
drawings containing hundreds of thousands of points it's something to keep an
eye on.

## The Implementation

To start, let's add a `line_simplification` module to `arcs::algorithms`.

```diff
 // arcs/src/algorithms/mod.rs

 mod length;
+mod line_simplification;
 mod scale;

 ...

 pub use length::Length;
+pub use line_simplification::simplify;
 pub use scale::Scale;
```

I've also stubbed out a `simplify` function.

```rust
// arcs/src/algorithms/line_simplification.rs

use euclid::{Length, Point2D};

/// Decimate a curve composed of line segments to a *"simpler"* curve with fewer
/// points.
///
/// The algorithm defines *"simpler"* based on the maximum distance
/// (`tolerance`) between the original curve and the simplified curve.
///
/// You may want to research the [Ramer–Douglas–Peucker algorithm][wiki] for
/// the exact details and assumptions that can be made.
///
/// [wiki]: https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
pub fn simplify<Space>(
    points: &[Point2D<f64, Space>],
    tolerance: Length<f64, Space>,
) -> Vec<Point2D<f64, Space>> {
    unimplemented!()
}
```

{{% notice note %}}
You'll notice that the function signature has this funny `Space` generic type
variable. The `arcs` crate takes advantage of [the `euclid` crate][euclid]'s
ability to "tag" a type with the coordinate space it can be used with, and
because this algorithm isn't specific to any one coordinate space we're
making it generic over *all* coordinate spaces.

You can think of this *"Coordinate Space"* idea as the graphical version of
units. It's really annoying to accidentally mix up locations on a screen
(*Canvas Space*, with the origin at the top-left) with locations in a drawing
(*Drawing Space*, Cartesian coordinates which can go to infinity), so
tagging points and lengths with their intended space lets us
statically prevent the types of conversion problems that destroyed the [Mars
Climate Orbiter][mco].

[euclid]: https://crates.io/crates/euclid
[mco]: https://en.wikipedia.org/wiki/Mars_Climate_Orbiter#Cause_of_failure
{{% /notice %}}

To implement this I'm going to procedurally build up a new `Vec` of points,
passing a `&mut Vec<_>` to the function doing the actual recursion.

```rust
// arcs/src/algorithms/line_simplification.rs

pub fn simplify<Space>(
    points: &[Point2D<f64, Space>],
    tolerance: Length<f64, Space>,
) -> Vec<Point2D<f64, Space>> {
    if points.len() <= 2 {
        return points.to_vec();
    }

    let mut buffer = Vec::new();

    // push the first point
    buffer.push(points[0]);
    // then simplify every point in between the start and end
    simplify_points(&points[..], tolerance, &mut buffer);
    // and finally the last one
    buffer.push(*points.last().unwrap());

    buffer
}
```

Next we need to implement this `simplify_points()` function.

We can use `if let` and the really handy [slice pattern][slice-patterns]
feature (stabilised in Rust 1.42) to extract the `first`, `last`, and `rest`.
This gives us everything we need to create a `Line` from `first` and `last`.

```rust
// arcs/src/algorithms/line_simplification.rs

fn simplify_points<Space>(
    points: &[Point2D<f64, Space>],
    tolerance: Length<f64, Space>,
    buffer: &mut Vec<Point2D<f64, Space>>,
) {
    if let [first, rest @ .., last] = points {
        let line_segment = Line::new(*first, *last);

        ...
    }
}
```

Next we can try to find the point whose perpendicular distance is furthest from
`line_segment`.

Ideally I'd like to use the [`Iterator::max_by_key()`][max-by-key] method to
find the index of the furthest point where our "key" function uses
`Line::perpendicular_distance_to()`, but that returns a reference to the item
and not its index... So to make the code cleaner I ended up rolling my own
`max_by_key()` function.

```rust
// arcs/src/algorithms/line_simplification.rs

fn simplify_points<Space>(
    points: &[Point2D<f64, Space>],
    tolerance: Length<f64, Space>,
    buffer: &mut Vec<Point2D<f64, Space>>,
) {
    if let [first, rest @ .., last] = points {
        let line_segment = Line::new(*first, *last);

        if let Some((ix, distance)) =
            max_by_key(rest, |p| line_segment.perpendicular_distance_to(*p))
        {
            ...
        }
    }
}

fn max_by_key<T, F, K>(items: &[T], mut key_func: F) -> Option<(usize, K)>
where
    F: FnMut(&T) -> K,
    K: PartialOrd,
{
    let mut best_so_far = None;

    for (i, item) in items.iter().enumerate() {
        let key = key_func(item);

        let is_better = match best_so_far {
            Some((_, ref best_key)) => key > *best_key,
            None => true,
        };

        if is_better {
            best_so_far = Some((i, key));
        }
    }

    best_so_far
}
```

If you're keeping track we've completed step 2 from [the algorithm
section](#the-algorithm).

Now if the `distance` is greater than our `tolerance` we need to recurse and
add the furthest point to our `buffer`.

The only real difficulty here is that the `ix` returned by `max_by_key()` is
an index into `rest`, not `points`... I originally forgot this bit and had an
off-by-one error that resulted in infinite recursion and blowing the stack 😊

```rust
// arcs/src/algorithms/line_simplification.rs

fn simplify_points<Space>(
    points: &[Point2D<f64, Space>],
    tolerance: Length<f64, Space>,
    buffer: &mut Vec<Point2D<f64, Space>>,
) {
    if let [first, rest @ .., last] = points {
        let line_segment = Line::new(*first, *last);

        if let Some((ix, distance)) =
            max_by_key(rest, |p| line_segment.perpendicular_distance_to(*p))
        {
            if distance > tolerance {
                // note: index is the index into `rest`, but we want it relative
                // to `point`
                let ix = ix + 1;

                simplify_points(&points[..=ix], tolerance, buffer);
                buffer.push(points[ix]);
                simplify_points(&points[ix..], tolerance, buffer);
            }
        }
    }
}
```

... And that's pretty much it. We've implemented the full
*Ramer-Douglas-Peucker algorithm* in about 50 lines or Rust.

{{% notice tip %}}
When you're doing recursion it's always nice to do a sanity check and make sure
you've implemented the reduction and base cases properly, otherwise you risk
infinite recursion...

For our base case, the `if let [first, .., last]` slice pattern means we'll stop
recursing when there are less than 2 points.

Also, because `rest` gets smaller and smaller every time we recurse we're
constantly dividing the problem into smaller and smaller pieces.
{{% /notice %}}

## Writing Tests

At this point we know our code compiles, but is it actually correct?

We can start off with lines of 0, 1, or 2 points, because they're already as
simple as they're going to get.

```rust
// arcs/src/algorithms/line_simplification.rs

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Point;

    #[test]
    fn empty_line() {
        let points: Vec<Point> = Vec::new();

        let got = simplify(&points, Length::new(1.0));

        assert!(got.is_empty());
    }

    #[test]
    fn line_with_one_point() {
        let points = vec![Point::new(0.0, 0.0)];

        let got = simplify(&points, Length::new(1.0));

        assert_eq!(got, points);
    }

    #[test]
    fn line_with_two_points() {
        let points = vec![Point::new(0.0, 0.0), Point::new(10.0, 2.0)];

        let got = simplify(&points, Length::new(1.0));

        assert_eq!(got, points);
    }
}
```

What about a perfectly straight line containing 100 points? The simplified
version should only contain the start and end points.

```rust
// arcs/src/algorithms/line_simplification.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn simplify_a_straight_line_to_two_points() {
        let points: Vec<Point> =
            (0..100).map(|i| Point::new(i as f64, 0.0)).collect();
        let should_be = &[points[0], points[99]];

        let got = simplify(&points, Length::new(0.1));

        assert_eq!(got, should_be);
    }
}
```

Next, let's add a bit of movement to the various points in this line. I'm going
to use `sin` to add a bit of "randomness" to each point's vertical component.
As long as the vertical movement is within our threshold all points between the
start and end should be simplified out.

```rust
// arcs/src/algorithms/line_simplification.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn simplify_a_horizontal_line_with_small_amounts_of_vertical_jitter() {
        let max_jitter = 0.1;

        let points: Vec<Point> = (0..100)
            .map(|i| {
                let jitter = max_jitter * (i as f64 / 100.0 * PI).sin();
                Point::new(i as f64, jitter)
            })
            .collect();

        let should_be = &[points[0], points[99]];

        let got = simplify(&points, Length::new(max_jitter * 2.0));

        assert_eq!(got, should_be);
    }
}
```

As a fun fact, if you were to graph this you'd see a sine wave between 0 and 99
with a period of 50 and amplitude of `0.1`.

Finally I thought I'd try a more realistic curve to make sure the tests so far
haven't added some bias due to their contrived nature.

For this, I needed to pull out the most sophisticated tool in my mathematical
toolbox.

![A hand-drawn sketch of several points with annotations showing how the path would be simplified](/img/line-simplification-sketch.png)

... Pen and paper.

I've drawn a series of points on a set of cartesian coordinates, and circled the
points (blue) that would be kept. By tracing around my ruler (red) I can emulate
the tolerance area, with anything inside the ruler boundary being discarded.

By measuring the location of each point we can write one last test.

```rust
// arcs/src/algorithms/line_simplification.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn simplify_more_realistic_line() {
        // Found by drawing it out on paper and using a ruler to determine
        // point coordinates
        let line = vec![
            Point::new(-43.0, 8.0),
            Point::new(-24.0, 19.0),
            Point::new(-13.0, 23.0),
            Point::new(-8.0, 36.0),
            Point::new(7.0, 40.0),
            Point::new(24.0, 12.0),
            Point::new(44.0, -6.0),
            Point::new(57.0, 2.0),
            Point::new(70.0, 7.0),
        ];
        let should_be = vec![line[0], line[4], line[6], line[8]];
        let ruler_width = Length::new(20.0);

        let got = simplify(&line, ruler_width / 2.0);

        assert_eq!(got, should_be);
    }
}
```

## Conclusions

This was a lot shorter than my [usual][1] [deep][2] [dives][3] into complex
programming topics (I think the average read time for articles on my blog is
around 25 minutes?), but I hope it'll be useful if you ever need to
implement line simplification.

Even if you aren't going to implement line simplification any time soon the
algorithm itself is also quite elegant, so you might appreciate it for its
aesthetic qualities.

In the meantime I think I'll keep adding bits and pieces to [arcs][arcs] and
[experimenting with motion control][rustmatic] when I have time. Let me know
if either of those topics interest you and I'll do some more write-ups as
various things get implemented.

[nesting]: https://en.wikipedia.org/wiki/Nesting_(process)
[wiki]: https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
[arcs]: https://github.com/Michael-F-Bryan/arcs
[edge-detection]: https://en.wikipedia.org/wiki/Edge_detection
[slice-patterns]: https://doc.rust-lang.org/edition-guide/rust-2018/slice-patterns.html
[max-by-key]: https://doc.rust-lang.org/std/iter/trait.Iterator.html#method.max_by_key
[1]: {{< ref "/posts/pragmatic-global-state.md" >}}
[2]: {{< ref "/posts/ecs-outside-of-games.md" >}}
[3]: {{< ref "/posts/wasm-as-a-platform-for-abstraction.md" >}}
[rustmatic]: https://github.com/Michael-F-Bryan/rustmatic
