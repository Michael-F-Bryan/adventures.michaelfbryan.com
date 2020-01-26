---
title: "Words Are Hard - An Essay on Communicating With Non-Programmers"
date: "2020-01-26T17:48:24+08:00"
draft: true
---

There's a well-known saying about the hard problems in computer science, of
which I think this is my favourite variant,

{{< tweet 7269997868 >}}

I've been doing this long enough to be burned by all three at some point, but
as someone working in a small business who represents the software side of
our product and is constantly rubbing shoulders with non-programmers, I
believe the ability to correctly communicate an idea or concept in a way that
others can understand (i.e. to name things) is by far the most important.

While I'm not always the best at this, I'd like to think I'm pretty good at
working with people from other fields and would like to share a couple things
I've picked up along the way.

## Techno-Babble

Like all industries, programmers have developed their own jargon to allow
the concise communication of a concept to others.

This jargon is important. If a co-worker and I are trying to choose between
two different algorithms to solve a particular problem we might say that
*"option A is `O(n^2)` with minimal up-front overhead, while option B is
amortised to `O(n log n)` with a large setup cost"*.

This single sentence says a lot about which scenarios an algorithm should be
used for and how they are implemented under the hood,

- Option A is great for situations where the number of inputs is small
- Option B is great when working with really large inputs, where the large
  setup cost will be compensated for by more efficient runtime
- If you're going to be using this algorithm in a loop, you should prefer option
  A to avoid the expensive setup code
- We may be able to amortise option B's setup cost with caching
- Option A probably compares each input with every other input (e.g. `for x
  in inputs { for y in inputs { if some_condition(x, y) { ... }}}`)
- Option B probably constructs a tree at the start then does a linear search
  followed by a lookup into this tree

You can see how we've been able to convey paragraphs of information with a
handful of words just by employing the correct language.

{{% notice info %}}
In this case, the example I had in mind was two algorithms for detecting
whether shapes collide. One checks every possible combination of inputs while
the second might use a [Quad Tree][quad-tree] or [Binary Search
Partitioning][bsp] to only check items that are close to each other.

[quad-tree]: https://en.wikipedia.org/wiki/Quadtree
[bsp]: https://en.wikipedia.org/wiki/Binary_space_partitioning
{{% /notice %}}

However, if you are in a meeting with people outside of the programming world
(e.g. mechanical or electrical engineers, managers, marketing people) using
this technical jargon is a great way to ostracise and confuse people, and adds
almost no value to the conversation.

This is what I'm referring to as techno-babble.

I'm going to be brutal here, a lot of the time these details just aren't
relevant to people from other fields and they really don't care.

For example, say you're explaining an awesome new feature which will find the
shortest path from A to B by generating a [navmesh][navmesh] and applying the
[A* pathfinding algorithm][a-star].

Don't describing it like I did in the last sentence, say something like *"we
figure out a bunch of possible paths then use clever algorithms from game
development to find the best overall route"*.

It doesn't matter that we're using A\* here (as opposed to Dijkstra or a
breadth-first search), or that A\* is used for more than telling an NPC how
to move around the game world. The other person just cares that you can find
a good path from A to B and that we're using reliable tools already in use in
other areas.

{{< figure
    src="/img/navmesh-and-a-star.png"
    caption="It also doesn't hurt to include a picture of what you mean..."
    alt="A picture of the navmesh and pathfinding in action"
>}}

I've also seen more senior programmers employ techno-babble as a power play
to show their incredible intelligence and impose their superiority over
others, and this really rubs me the wrong way.

Now don't get me wrong, sometimes there are situations where people who know
just enough to be dangerous will say *"that's really complex, why can't you
just do X?"* and you *do* need to let them know that you are the expert here
and they don't really know what they're talking about... But there's still a
right way and a wrong way of going about that.

Don't try to use techno-babble to satisfy your ego, it ostracises people and
gives us a bad name.

## Be Respectful

That segues nicely into the next point... Don't forget to be respectful.

A lot of the people I work with are really intelligent and experts in their own
fields, but they don't necessarily have the same knowledge and experience with
building information systems.

It's often necessary to simplify things (e.g. when trying to explain a tricky
problem you're having), but try not to be condescending.

That software engineer I mentioned earlier (power play guy) would often reply
with *"it's...complicated"* when asked by a "normal" person how a particular
feature works, and then leave it there. As if the code was so clever someone
who isn't a programmer with 20 years experience would have no chance of
understanding.

Don't be that guy.

A better response is to say, *"Okay I'm simplifying a bit here, but the idea
is we first do X, then do Y, and finally do Z. There are a dozen subtle edge
cases you need to keep in mind (maybe explain one or two of them) but that's
the general gist"*. The people you're working with are smart, as long as you
don't throw around techno-babble they're more than capable of understanding
you.

Another really useful technique is to use a non-programmer as a sounding
board, kinda like a human rubber ducky. If you're trying to come up with a
solution to something, explain the rough problem to them and how you'd like
to solve it, then ask if they can think of a better way of doing things.

Our company works in the CNC industry and for things that have some
connection to the real world (e.g. say you're trying to implement [cut width
compensation][kerf]) engineers are really good at analysing problems based in
physics or geometry.

## Personify, Exaggerate, and Use Analogies

People are social creatures. We're hard-wired to understand relationships
between people and love to use analogies to relate foreign concepts to
something we already understand. When you're talking to someone you can take
advantage of this to make complex topics easier to understand.

Say your company has an online purchasing system and a marketing person wants
to know how we go from the online checkout to getting a parcel at the door so
they can answer customer questions better. I might say something like this:

> Pretend there's a customer named Charlie who wants to buy a dozen fidget
> spinners. He goes to www.example.com, adds the fidget spinners to his cart
> then hits "checkout" (most people have used online shopping before so you
> can gloss over *how* a cart and checkout work).
>
> From there, Charlie's computer sends the order to Sam (the web server) who
> checks with Debbie (the database) to make sure there's enough stock to fulfil
> the order. Once Debbie gives the okay, Sam lets Charlie know the purchase was
> successful and gives him a receipt (possibly also sending an invoice via
> email).
>
> There's also a guy out the back (let's call him Fred) who's constantly
> asking Debbie if there have been any new orders. If so, Fred lets a real
> human know so they can grab the items from their shelf and hand them to Mary
> in the mail room (Mary is a real person, computers can't hold fidget spinners
> silly) to be sent to Charlie via snail mail.
>
> Sam and Rebecca (the recommendation engine) are in cahoots, so whenever an
> order is made Sam will let Rebecca know so she can use *Artificial
> Intelligence* and black magic to recommend other products to Charlie.

This all sounds rather comical and the example is more than a bit contrived,
but I can guarantee it's going to be more approachable than drawing up a big
network diagram and using opaque words like "web server", "Event-Driven
Architecture", or "Apache Kafka" (see the section on
[techno-babble](#techno-babble)).

As another example, if you're trying to describe how a pathfinding algorithm
works to a layperson, you don't say *"lines we've already visited are
weighted higher"*, you say *"the algorithm really doesn't want to go over
lines it's already visited"*.

It's subtle, but personifying the pathfinding algorithm by saying it *"really
wants to do X"* and will *"try really hard to avoid Y"* often helps people to
just *Get It*.

Anecdotes (when relevant) are helpful too. You've probably already noticed
that this article is chock full of examples, and instead of talking about
things in the abstract I've provided a concrete story which helps explain my
point. This is no accident.

## Draw Pretty Pictures

It sounds cliché, but sometimes a picture really does paint a thousand words.

A couple months back I was doing a radio course and a lady next to me was
having trouble remembering which buttons to press to navigate around the menus
on this little 16x2 LCD display.

I asked if she'd like me to draw a map.

She thought I was being a smart ass and making fun of her.

I wasn't.

Instead, I found a bit of scrap paper and together we drew up something like
this:

{{< mermaid >}}
graph TD;

    Idle;
    advanced[Advanced Menu];
    dual_receive[Single/Dual Receive];
    main[Main Menu];
    select_channel[Select Channel Using Keypad];

    Idle-- A -->dual_receive -->Idle;
    Idle-- left eyebrow -->main;
    main-- cancel -->Idle;
    main-- "advanced" -->advanced;
    advanced-- cancel -->Idle;
    Idle-- select -->select_channel;
    select_channel-- number keys -->select_channel;
    select_channel-- enter -->Idle;
{{< /mermaid >}}

A programmer would immediately recognise this "map" for what it is, a *State
Machine Diagram*. Unbenounced to them, I had just explained a fundamental
technique in computer science and how this radio's UI was coded under the
hood.

But the lady (and the rest of the group by this stage) didn't care. This was a
map that they could use to navigate the UI.

There's something oddly satisfying about finding a way to make a tricky concept
approachable to someone from another field. Especially when they're able to
identify that the map actually has a bug in it and you need to press and hold
*cancel* to get back to the *Idle* state, because pressing *cancel* normally
takes you back to the *Main Menu*.

On my desk I have a book of un-lined paper. Normally it's used for my weekly
to-do list or scratch paper when I'm trying to work something out, but it
frequently doubles as an explanation aid. Being able to sketch things out as
you are talking with someone helps make sure everyone is on the same page
(pun intended) and that you are both meaning the same thing when you use a
particular name.

## "Done" and "Fixed"

## I Made *$FEATURE* 10x Faster

## It's Okay to Say *"I Don't Know"*

## Conclusions

[navmesh]: https://en.wikipedia.org/wiki/Navigation_mesh
[a-star]: https://en.wikipedia.org/wiki/A*_search_algorithm
[kerf]: https://www.esabna.com/us/en/education/blog/what-is-cutting-kerf.cfm