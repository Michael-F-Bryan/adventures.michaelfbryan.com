---
title: "How I Translate Feature Requests into Code"
date: "2020-12-02T16:10:00+08:00"
tags:
- Architecture
---

As part of my previous job I worked on a CAD/CAM package, and a very common
task would be to take a vague feature description, rephrase it as a more
formal software problem, then use computational geometry algorithms to turn
it into code which can be integrated into the overall application.

I eventually got quite good at this, so I'm going to write down the system I
came up with. This process works especially well for larger features which
add new functionality with minimal coupling to existing code.

{{% notice note %}}
If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

<!-- Mention [line simplification][simplification] as prior art -->

## Step 1: Research

While you *can* dive into the code immediately, a lot of the time creating your
own solution from scratch will lead to an implementation with logic/design
flaws.

This is especially the case when you are working on things requiring complex
algorithms or mathematical concepts.

### Understanding the Problem

Often the problem you are given won't be something straightforward like
*"implement A\* path finding"*. Feature descriptions normally come from a
non-programmer and will be something a lot less precise, like

> I want to display a CAD drawing in the background, then when I click points
> on the drawing you should create a path which goes from A to B to C taking the
> shortest path along that drawing without doubling back on itself.

Often important bits will be left out, too.

> Oh, and this background drawing may have points added or removed at any time.

(i.e. we need to deal with mutation)

Unfortunately, that's a bit too vague to turn into code and Googling a
problem statement like that won't be very helpful! What we want is a
description of the problem which can be phrased as computer operations.

When I'm given a vague feature description the first thing I'll do is draw it
out. Seeing something visualised is often enough to summon the correct keywords
to rephrase the problem in a more searchable form.

I don't know about you, but when I see something like this, my first thought is
that we're doing pathfinding. We're also trying to optimise for the shortest
distance while preferring untraversed edges.

{{< figure
    src="/img/link-lines.gif"
    caption="Problem visualised (black lines are the background image, red X means click, red lines are the desired path)"
    alt="Animation of the expected interaction"
    width="75%"
>}}

Don't forget to come up with an unambiguous definition of *"done"*. This lets
you determine when the feature request has been fulfilled, and gives you a way
to ward off [scope creep][scope-creep].

{{% notice info %}}
This example came was one of the feature requests which taught me the
importance of getting the full picture up front and leaving yourself room to
make changes down the track.

In this case, I'd created a component for doing pathfinding by converting the
"background drawing" into a graph and passing it to *A\**, but neglected to
ask whether the background drawing would change.

Only after I'd finished integrating the component into the overall CAD/CAM
package did I find out that we need a way to add a path midway along an edge
of the background drawing (mutating the graph by removing an edge and
replacing it with two smaller edges). I'm a big fan of immutability, so you
can see how this might be a problem.

We ended up needing to rewrite the component because immutability was so
deeply ingrained into its implementation... I'd engineered myself into a
corner!
{{% /notice %}}

If your problem involves a lot of maths (like a lot of my computational
geometry work) it's a good idea to draw sketches and try to work out the
solution by hand. This also lets you derive equations that you'll need later
on.

## Searching for Prior Art

Once you can phrase the problem in computer terms it's time to pull out the
programmer's most powerful tool... The internet.

You're looking anything relevant to the problem at hand. This may take the form
of:

- Wikipedia - usually my first port of call
- Blog posts exploring similar problems
- Academic Papers - tend to be quite information-dense and go into *much* more
  detail than you care about, but a quick skim through will often find pictures
  or algorithms that are useful
- Existing Products or Libraries - why waste weeks reimplementing the wheel?

I'll often end up with 20-40 open tabs with promising items from the first
couple pages of search results, then I'll skim through the content on each
tab, also checking out interesting things *those* pages link to.

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
  report progress or support cancellation?
- Do I need to let the caller update the feature's internal state? (e.g. when
  altering the "background drawing" from the earlier example)
- How are we going to report failure?
- Is there information the caller will need to provide? (see [*Dependency
  Injection*][d-i] and the [Strategy Pattern][strategy])
- Is this a thin interface, or will I need to leak a lot of implementation
  details to the caller? (see [*The Law of Leaky Abstractions*][leaky])
- Would I reasonably want to reuse this component elsewhere?
- Does my language promote patterns or abstractions that would make the code
  more ergonomic to use if written in a certain way? (C# has events as
  first-class citizens, Go's goroutines and channels are great for creating
  streams of events, etc.)
- Does the larger application provide natural mechanisms or extension points
  that we can use?

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
Pattern*][facade]) or adding another level of [*Indirection*][indirection]
(e.g. introduce a middle-man).

Try to avoid creating a "chatty" API, if possible. Making the caller go back
and forth into your code to do complex operations leads to increased coupling
and more bugs down the track.

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

Just remember to sprinkle in enough tests to make sure the implementation is
correct and edge cases are handled gracefully.

There's not much more to be said here.

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

Integration is the process of merging new functionality into an existing
application. This is the point where new code meets old and tests how
suitable your public API from step 2 is.

Again, it's a bit tricky to provide examples when everyone's scenarios are
different, but we can still discuss integration in the abstract.

If you are lucky, your application will already provide places new
functionality can naturally be added to. For example, most CAD applications
are modal (e.g. you might be in the *"add arc"* mode, then switch to *"select
mode"*) and adding a new mode is often just a case of creating a button which
calls some `SetCurrentMode()` function with an instance of your new mode.

Other times you'll be adding to existing functionality and need to be a bit
more careful.

Either way, this step tends to be rather straightforward. You've got some
existing code and some new code, and you need to wire up the existing code to
use the new code. You may need to rewrite/restructure pieces so they fit
together more nicely, but that's the general gist.

{{% notice tip %}}
Don't forget that you have a variety of tools at your disposal for connecting
two pieces of code while keeping the overall codebase maintainable.

*The Refactoring Guru*'s section on [*Design Patterns*][design-patterns] may be
helpful here. These patterns aren't restricted to Object Oriented languages,
with a bit of ingenuity they can be adapted to more procedural or functional
languages too.

[Objects are a poor man's closure, after all][closures].

[design-patterns]: https://refactoring.guru/design-patterns
[closures]: https://wiki.c2.com/?ClosuresAndObjectsAreEquivalent
{{% /notice %}}

The integration stage is also where you need to think about how users will
interact with this new functionality (the buzz word is [*"User
Experience"*][user-experience]). While the feature's public API determines how
code interacts, the integration code is usually the part which takes input
from users and triggers the feature's functionality.

You'll want to think of the intended workflow (your feature's *"happy path"*)
and make sure that is intuitive for users. Some questions to ask yourself are,

- How many knobs and levers do we want to expose to the user?
- Can we use some sort of [*Progressive Disclosure*][disclosure] mechanism to
  simplify the process?
- What norms and conventions can we build on to lower the barrier-to-entry?
- Can users get "stuck" in confusing or unintuitive situations when they go
  off the beaten path?

Something that goes hand-in-hand with user experience is testing. While I'm
sure you've been writing integration tests as you go (*\*hint, hint\**), the
best way to make sure a feature has been properly integrated into your
application is still to use a regular human tester.

{{% notice tip %}}
It's a good idea to make sure your testers *aren't* the same people that
develop a feature.

On more than one occasion, I've been showing a newly implemented feature to
someone and we'll have an exchange like this:

- **Michael:** (draws something in a non-intuitive way)
- **Co-Worker:** Why did you draw it like that instead of doing X?
- **Michael:** Oh, because if I drew it that way the maths would make my arc's
  radius blow out to infinity, and that'll mess up my drawing.

What just happened is the software developer unconsciously avoided a known
edge case (AKA buggy behaviour) because they wanted the demonstration to go
smoothly. This scenario sounds ridiculous, but I've been called out for
unconsciously avoiding "problem" areas by non-technical co-workers several
times *even when I'm aware of it*.

A lot of people (particularly management!) see the bug tester role as an
unnecessary overhead or laziness on the part of the developer, especially in
this era of CI and suites of unit tests. I believe bug testers are a crucial
part of creating anything user-facing, a good bug tester will hold developers
accountable and help to make the user experience as smooth as possible.
{{% /notice %}}

## Step 5: Review

So now you've implemented a feature and rolled it out to production. For most
features you are done and can move on to other things, but it's worth setting
up a paper trail for anything that's taken more than a couple days to
implement.

When merging in the PR which "activates" a new feature (e.g. adds a new item
to the UI which lets users access it) I'll write up a brief summary containing:

- What has been implemented
- Design decisions and constraints
- Possible areas of concern (*"I feel like this area isn't overly robust and we
  may find bugs later on"*)
- Ways you could extend the feature to give the user more value
- Should we come back later on and re-implement the feature? (e.g. we came up
  with a better design later on or a minor design flaw was found)

There's a good chance you didn't achieve perfection and there are points that
could be improved, or extensions that could be made to make the feature even
more useful.

It's important to note down all those thoughts now while they're still fresh in
your mind!

You can also create tickets for new features which extend this one, possibly
adding thoughts on how you would attack the problem and links to significant
parts of the codebase.

Tasks like *"add a checkbox to the window which will make the feature do X
slightly differently"* are great for on-boarding new developers, giving them
a chance to learn the codebase without the pressure of fixing bugs in
production or working to a hard deadline.

{{% notice tip %}}
Issue labels work great for this sort of triage. We used GitLab's [scoped
labels][scoped] to help prioritise how urgent a ticket is.

- `priority::on-demand` - Waiting for some external prompt before allocating
  time to it (e.g. a customer asks about it or requests from the product development
  team)
- `priority::low` - This low priority and can be safely left on the back burner
- `priority::normal` - Normal priority
- `priority::urgent` - This needed to be done yesterday and customers are
  demonstrably impacted (e.g. lost revenue due to downtime)

We used to have `priority::high`, but found it got abused. When people run
into a bug or missing feature that impacts their workflow, the knee-jerk
reaction is to give it a high priority (*"it's breaking my workflow and needs
to be fixed right now, damn-it!"*).

The end result was that 3/4 of open issues were marked as `priority::high`
(man-years worth of effort) with the rest marked as `priority::low`... Which
makes it extremely difficult to find out which items were *actually*
important.

[scoped]: https://docs.gitlab.com/ee/user/project/labels.html#scoped-labels
{{% /notice %}}

While it sounds like a bunch of useless paperwork, your future self will
thank you for it. It's a real pleasure when you go to work on an issue and
see someone has already done some research and planning.

If you are crafty, you could also use this to gain brownie points with your
manager. Being able say *"I've got some ideas for how we can make X better"*
and pointing to some initial research or plans shows initiative and that you
care about giving the customer value.

## Conclusions

There are definitely other approaches which you might take depending on the
feature scope and how much it interacts with other components, but the
workflow I've outlined works quite well for self-contained, mid-sized
features (e.g. 5-10 man-days of effort).

Most of the examples I've provided are from a professional environment where
customers will directly interact with the product you are working on, because
that's what I've got experience with, but there's no reason why it wouldn't
apply to micro-service architectures or a large library. Just replace the
word *"customer"* with *"fellow developer"*.

I love hearing war stories from other people who create software for a
living. If you've got a different approach or want to share your own
experiences, please let me know via [the accompanying Reddit thread][reddit].

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
[scope-creep]: https://www.wrike.com/project-management-guide/faq/what-is-scope-creep-in-project-management/
[disclosure]: https://www.shopify.com.au/partners/blog/progressive-disclosure
[user-experience]: https://www.interaction-design.org/literature/topics/ux-design
[reddit]: https://www.reddit.com/r/programming/comments/k55l1j/how_i_translate_feature_requests_into_code/?utm_source=share&utm_medium=web2x&context=3
