---
title: "Line Simplification"
date: "2020-02-23T17:31:35+08:00"
draft: true
tags:
- rust
- algorithms
---

The other day I needed to do a fairly routine graphical operation, to
"simplify" a polyline with many points into a simpler polyline which has
roughly the same shape plus or minus some `tolerance` factor.

My actual use case was in sending linear movements to a CNC machine. Drawings
are defined using floating point numbers and can be "accurate" to about 7-15
decimal places (depending on if you use floats or doubles) but when you take
the machine's mechanical tolerances and material effects into account, the
final cut is only really accurate to about 1 decimal place (0.1 mm). If I
were to simplify the path with a tolerance of, say, 0.05 mm I could massively
reduce the number of points sent to the machine (which reduces data rates,
memory usage, communications overhead, etc.) with minimal effect on the
accuracy.

Other places where this operation can be useful are,

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

For the visually minded among you, the animation from the Wikipedia article may
be more approachable.

{{< figure
    src="https://upload.wikimedia.org/wikipedia/commons/3/30/Douglas-Peucker_animated.gif"
    link="https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm"
    caption="Visualisation of the Ramer-Douglas-Peucker algorithm"
    alt="Visualisation of the Ramer-Douglas-Peucker algorithm"
>}}

## The Implementation

## Conclusions

[nesting]: https://en.wikipedia.org/wiki/Nesting_(process)
[wiki]: https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm
[arcs]: https://github.com/Michael-F-Bryan/arcs
[edge-detection]: https://en.wikipedia.org/wiki/Edge_detection