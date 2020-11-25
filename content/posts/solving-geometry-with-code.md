---
title: "How I Translate Feature Requests into Code"
date: "2020-11-23T01:36:05+08:00"
draft: true
---

As part of my previous job I worked on a CAD/CAM package, and a very common
task would be to take a vague feature description, rephrase it as a more
formal software problem, then use computational geometry algorithms to turn
it into code.

I eventually got quite good at this, so I'm going to write down the system I
came up with. Hopefully others can gain insight from my experience.

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

I'd engineered myself into a corner 😞
{{% /notice %}}

## Searching for Prior Art

Once you can phrase the problem in searchable terms it's time to pull out the
programmer's most powerful tool... The internet.

You're looking anything relevant to the problem at hand. This may take the form
of:

- Wikipedia - usually my first port of call
- Blog posts exploring similar problems
- Academic Papers - tend to be quite information-dense and go into *much* more
  detail than you care about, but a quick skim through will often find pictures
  or algorithms that are useful
- Existing Products or Libraries - why waste weeks reimplementing the wheel?

I'll often end up with 20-40 open tabs because I've opened most of the
promising items on the first couple pages of search results, then I'll skim
through and open interesting things those pages link to.

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

If your problem involves a lot of maths (like a lot of my computational
geometry work) it's a good idea to draw sketches and try to work out the
solution by hand. This also lets you derive equations that you'll need later
on.

## Step 2: Thinking About the Public API

No code exists in a vacuum, so knowing how the outside world will use your
feature has a big effect on how it will be integrated into the rest of the
application.

In this stage you develop a big picture view of the feature and how it will
expose its functionality to the outside world.

{{% notice note %}}
The feature's public API also acts as a natural seam that you can use for
testing (e.g. mocking out the component when testing the application) and to
allow you to restructure the feature's implementation (or swap it out
entirely) without breaking the rest of the application.
{{% /notice %}}

Every feature will be used differently so it's hard to provide concrete
examples, but here some questions to ask yourself:

- Is this a well-contained batch process or is the feature interactive?
- What are my inputs and outputs?
- Are there any hard constraints imposed by the implementation?
- If the process will take a long time (i.e. more than 100ms), does it need to
  report process or support cancellation?
- Do I need to let the caller update the feature's internal state? (e.g. when
  altering the "background drawing" from the earlier example)
- How are we going to report failure?
- Is there information the caller will need to provide? (see [*Dependency
  Injection*][d-i] and the [Strategy Pattern][strategy])
- Is this a thin interface, or will I need to leak a lot of implementation
  details to the caller? (see [*The Law of Leaky Abstractions*][leaky])
- Would I reasonably want to reuse this component elsewhere?
- Does my language promote patterns or abstractions that would make this
  feature more ergonomic to use? (C# has events as first-class citizens,
  Go's goroutines and channels are great for creating streams of events, etc.)

Answering these questions should give you an idea of how your feature will
interact with the rest of the application, and from there you can start
thinking in more concrete terms like interfaces and data types.

{{% notice tip %}}
You actually don't need to write code for this step.

My normal approach was to turn away from my computer and stare at a random
patch of wall on the other side of the office. This lets me think about how I
want to interact with the feature without being bogged down with the precise
details you get when writing code.
{{% /notice %}}

If your research indicated the feature's implementation will be quite
complex, there are a couple tools at your disposal for limiting how much of
that complexity leaks into the wider application. Namely, by encapsulating
the problem you can paper over the complexity (see the [*Facade
Pattern*][facade]) and adding another level of [*Indirection*][indirection].

## Step 3: Initial Implementation

Now you've done some background research and thought about the feature's API,
it's time to actually start implementing it. Depending on how your research
went, this stage can be either very easy or very hard.

### The Easy Case

If you are lucky, you may have stumbled upon a similar solution during your
research that you can reuse or adapt to fit your purposes. This was the case
with our from earlier, by analysing the feature request we were able to
reduce it to a pathfinding issue; a solved problem in computer science.

It's really nice when this happens. Often implementation is just a case of
going to the Wikipedia page, scrolling down to [the pseudocode section][wiki],
and adapting it fit the API you developed earlier.

Just remember sprinkle in enough tests to make sure the implementation is
correct and edge cases are handled gracefully. There's not much more to be
said here.

### The Not-So-Easy Case

Unfortunately, most "interesting" feature requests won't have libraries or
tutorials you can use directly, requiring you to do a bit of original work.

A lot of the work I do has a visual or mathematical element to it, so you can
simulate the feature using pen and paper.

I'll often start with the top-most level first, stubbing out the public API
with code that just blows up (i.e. `throw new NotImplementedException()` in C#
or `todo!()` in Rust).

From there you can start decomposing each of the functions into
sub-functions, recursively decomposing the problem into smaller problems
until you eventually reach a problem you know the solution to.

Whenever you get stuck, look back over the resources you found while
researching. You may have missed some gem of knowledge which will make
everything *click*.

An alternative to this top-down approach is attacking the problem bottom-up.
You'll often take this approach when you know how something deep down is done,
but aren't quite sure how to connect that with the public API.

When taking the bottom-up approach I'll first implement the thing I know and
make sure to develop a solid foundation. Then you add higher and higher level
layers, slowly working your way towards that public API you want to expose.

In practice you'll often use a hybrid approach, doing a little work from the
top down, then a bit more from the bottom up, until eventually you meet in
the middle and everything fits together.

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
[d-i]: https://www.freecodecamp.org/news/a-quick-intro-to-dependency-injection-what-it-is-and-when-to-use-it-7578c84fa88f/
[strategy]: https://refactoring.guru/design-patterns/strategy
[seam]: https://softwareengineering.stackexchange.com/questions/132563/problem-with-understanding-seam-word
[indirection]: https://wiki.c2.com/?OneMoreLevelOfIndirection
[facade]: https://refactoring.guru/design-patterns/facade
[wiki]:https://en.wikipedia.org/wiki/A*_search_algorithm#Pseudocode
[leaky]: https://www.joelonsoftware.com/2002/11/11/the-law-of-leaky-abstractions/
