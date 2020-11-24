---
title: "Solving Math Problems With Code"
date: "2020-11-23T01:36:05+08:00"
draft: true
---

I created a CAD/CAM package at my previous job and a very common task would
be to take a vague feature description, rephrase it as a more formal software
problem, then use computational geometry algorithms to turn it into code.

I eventually got quite good at this, so I'm going to write down the system I
came up with in the hope that others can gain insight.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

<!-- Mention [line simplification][simplification] as prior art -->

## Step 1: Research

While you *can* dive into the code immediately, 9 times out of 10 trying to
make up your own solution for a mathematical problem will lead to a buggy
implementation with logic flaws.

### Understanding the Problem

Often the problem you are given won't be something straightforward like
*"implement A\* path finding"*. Feature descriptions normally come from a
non-programmer and will be something a lot less precise, like

> I want to display a CAD drawing in the background, then when I click points
> on the drawing you should create a path which goes from A to B to C taking the
> shortest path along that drawing.

Often important bits will be left out, too.

> Oh, and this background drawing may have points added or removed at any time.

(i.e. we need to deal with updates and mutation)

Unfortunately, that's a bit too vague to turn into code. What we want is a
description of the problem which can be phrased as computer operations.
Unfortunately Googling a problem statement like that won't be very helpful!

When I'm given a vague feature description the first thing I'll do is draw it
out. Seeing something visualised is often enough to summon the correct keywords
to rephrase the problem in a more searchable form.

I don't know about you, but when I see something like this, my first thought is
that we're doing pathfinding where untraversed edges are preferred.

{{< figure
    src="/img/link-lines.gif"
    caption="Problem visualised (black lines are the background image, red X means click, red lines are the desired path)"
    alt="Animation of the expected interaction"
    width="75%"
>}}

{{% notice tip %}}
If you haven't noticed by how oddly specific this example is, I've been
burned by this one before... I created a component for doing pathfinding by
converting the "background drawing" into a graph and throwing it at *A\**,
but neglected to ask whether the background drawing would change.

Only after I'd finished integrating the component into the overall CAD/CAM
package did I find out that we need a way to add a path midway along an edge
of the background drawing (logically equivalent to removing an edge from the
graph and replacing it with two smaller edges).

We ended up needing to rewrite the component because immutability was so
deeply ingrained into its implementation (direct references to edges, no way
to tell the component about updates or propagate changes, etc.).

I'd engineered myself into a corner.
{{% /notice %}}

## Searching for Prior Art

Once you can phrase the problem in searchable terms it's time to pull out the
programmer's most powerful tool... The internet.

You're looking anything relevant to the problem at hand. I'll often end up with
20-40 open tabs because I've opened most of the promising items on the first
couple pages of search results, then I'll skim through and open interesting
things those pages link to.

Continuing with our example from before where we're wanting to find the path
from one point to another preferring to use unvisited edges, I might search
for things like:

- Pathfinding
- Pathfinding preferred
- Pathfinding algorithm
- Incremental pathfinding (because it'll happen over multiple user interactions)
- Undirected weighted graph traversal

My definition of "interesting" is anything which seems to mention keywords from
my problem. Algorithm names are particularly useful.

This [*Introduction to the A\* Algorithm*][intro-to-a-star] link ticks a lot
of those boxes. Plus it seems to be a tutorial with lots of code snippets and
pictures, which will be handy when it gets to the implementation.

![Search result showing "Introduction to the A\* Algorithm" with certain words highlighted](/img/pathfinding-search-results.png)

Other things you should be looking for

- Wikipedia - usually my first port of call
- Academic Papers - tend to be quite information-dense and go into *much* more
  detail than you care about, but a quick skim through will often find pictures
  or algorithms that are useful
- Existing Products or Libraries - why waste weeks reimplementing the wheel?

If your problem involves a lot of maths (like a lot of my computational
geometry work) it's a good idea to draw sketches and try to work out the
solution by hand.

## Step 2: Thinking About the Public API

<!-- - No code exists in a vacuum
- What seams do I want to provide?
- What parts of the algorithm need to be controlled by the caller? (strategy
  pattern or dependency injection)
- Allow for flexibility and change later on (up to and including ripping out
  the existing implementation) -->

## Step 3: Initial Implementation

## Step 4: Integration

## Step 5: Review and Integration Testing

<!-- - Now you've integrated it in, was your original design correct? If not, how
  should it be changed?
- Make sure the happy path works
- Try a bunch of things a normie would do and start looking for edge cases
- Is this implementation intuitive?
- Do we need a v2? -->

## Conclusions

[simplification]: {{< ref "/posts/line-simplification.md" >}}
[law]: https://meta.wikimedia.org/wiki/Cunningham%27s_Law
[intro-to-a-star]: https://www.redblobgames.com/pathfinding/a-star/introduction.html
