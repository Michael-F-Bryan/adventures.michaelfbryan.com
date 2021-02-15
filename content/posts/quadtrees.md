---
title: "Creating a Custom Quad Tree in Rust"
date: "2021-02-14T20:51:45+08:00"
draft: true
tags:
- Rust
- Algorithms
---

Have you ever run into a situation where there's this data structure you'd
really like to use, but none of the implementations you find on the internet
function *exactly* as you want?

I ran into that exact problem the other day while working on the 2D renderer
for my CAD engine, [`arcs`][arcs], and ended up needing to create my own
implementation from scratch.

The data structure in question is a [Quad Tree][wiki]. It's kinda like a
`HashMap` or `BTreeMap` in that you get an efficient map from keys to values,
except instead of the key being a string or an integer, the key is a region
of space.

A quad tree can massively improve the performance of a rendering system
because it lets you ask *"which entities are within view at the moment?"* and
render *just* those entities to the screen, regardless of how big your world
is.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://gitlab.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## What is a Quad Tree

- Paraphrase Wikipedia
- Point vs Region quad trees
- Outline my specific requirements
  - `O(log n)` query time
  - `O(1)` modification and delete (or close to)
  - `O(1)` reverse-lookup from key to region
  - Don't need to modify the key
  - The key will always be some `K: Copy + Eq + Hash` like `legion::Entity`
  - the region should be generic and work for any dimension

```rust
trait Region: Copy {
    const DIMENSION: usize;
    type Bound: Copy + PartialEq;

    fn split(&self) -> [Self::Bound; Self::DIMENSION];
    fn contains(&self, other: &Self) -> bool;
}
```

## Making a Tree

- `Option<Node<K, Bounds>>`

## Insert

## Querying

## Update and Remove

## Conclusions

- Could also be done using raw pointers and `unsafe`
- Haven't done any serious benchmarking
- I just know the rough performance characteristics I want
- Would you use this? And should I upload to crates.io?
- How can I make it generic over region types (2D/3D, euclid, kurbo, etc.)?


[arcs]: https://gitlab.com/Michael-F-Bryan/arcs
[wiki]: https://en.wikipedia.org/wiki/Quadtree
