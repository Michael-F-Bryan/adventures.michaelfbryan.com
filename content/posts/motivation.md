---
title: "A Reflection on What Motivates a Person"
date: "2020-04-04T16:34:44+08:00"
draft: true
tags:
- People Skills
---

Motivation is a funny thing.

I'm someone who's productivity levels change wildly depending on my
motivation levels. When I work on something which I'm passionate about or
which interests me on an intellectual level (e.g. computational geometry or
systems programming), I'm routinely 5-10x more productive than my peers.

However, if I'm working on something which is less personally interesting
(e.g. tracking down GUI bugs or creating yet another CRUD app) I'll tend to
drag my feet and not work as hard.

This revelation isn't overly profound, most people's productivity will ebb
and flow with their motivation levels, after all. It's just that the amount
of variation will change from person to person, with society typically
labelling the flatter, more consistent people as being more "disciplined",
while those with more volatile productivity levels being considered "lazy
geniuses".

With most people working remotely due to the recent pandemic, I've had an
opportunity to do some introspection and realised that for the last month or
so (late February 2020 onwards) I've been in one of those low motivation
periods.

The engineer in me wants to find out why.

{{% notice info %}}
While I'm using the term *"productivity"*, this doesn't necessarily mean the
amount of work done at my day job.

Yes, that plays a big part in productivity (because it's where I spend most
of my daylight hours through the week), but I'm also referring to the things
I do in my spare time like toy projects, [thought experiments][ecs], and
personal development.

[ecs]: http://localhost:1313/posts/ecs-outside-of-games/
[ecs]: {{< ref "ecs-outside-of-games/" >}}
{{% /notice %}}

## Inspiration

A lot of the projects or writing I do in my spare time can be traced back to
problems or observations I've encountered at my day job.

For example, I might notice some unnecessary manual work in our release
process and [create a Rust library which could make this easier][markedit],
or I may have needed to add a feature for line simplification to our product
and decide to [also implement it in a side project][line-simplification].

I'm always very careful to stick with openly available information (e.g. the
[*Line Simplification*][line-simplification] article mainly draws from
Wikipedia) and not expose sensitive intellectual property, but that doesn't
mean you can't use the problems you encounter at work as inspiration for
original research.

Now that the major project I've been working on for the last year is entering
its final phases, I feel like a lot of those initial sources of inspiration
have started to dry up. Sure, this product will be in the wild for quite a
while and we'll be continuing to develop it, but I can't foresee many game
changing new challenges or features.

This means I'll need to find a new source of inspiration, potentially
something not related to work, or maybe by transitioning to a different area
within my company/industry.

## The Learning Curve

## Passion

## Obligations

## Sturgeon's Law

[Sturgeon's Law][sturgeon] is an observation about the world, often paraphrased
as

> Ninety percent of everything is crap.
>
> <cite>[Wikipedia][sturgeon]</cite>

This phenomena can have a pretty big impact on your motivation. For example, a
*lot* of the code I've seen (written by others, of course) falls into that 90%.

It feels like a lot of people learn the basics of programming and decide to
commercialise it without really learning how to design large projects properly,
so they end up flailing about until they've added enough global variables and
if-statements that the thing *kinda* works.

I normally wouldn't care less if your code is a pile of 💩 under the hood,
you're doing something you enjoy and trying to create a product which will
give others value so more power to you.

However, when you inflict that 💩 on me that can really impact my motivation
levels (e.g. I inherit your codebase and it's the second month of debugging
in production trying to track down a spurious, mission-critical bug which is
actively costing customers money because you designed a communication
protocol without knowing how to design a communication protocol).

And the thing about motivation is that once lost, it doesn't tend to come
back. Not even when the original problem goes away.

It's also quite humbling in a way.

When I look at the list of repositories I've created on [GitHub][gh-repos] or
[GitLab][gl-repos] I see a large number of half-baked ideas and failed
projects. Although I've learned a lot from each of them and enjoyed the creation
process, I'm sure quite a lot of it *is* crap. I'd like to think it's not as
much as 90% (maybe only 50%?) but that can probably be attributed to the
[Dunning–Kruger effect][dk] 😜

## Conclusions

[markedit]: {{< ref "markedit.md" >}}
[line-simplification]: {{< ref "line-simplification.md" >}}
[sturgeon]: https://en.wikipedia.org/wiki/Sturgeon%27s_law
[gh-repos]: https://github.com/Michael-F-Bryan?tab=repositories
[gh-profile]: https://github.com/Michael-F-Bryan
[gl-repos]: https://gitlab.com/users/Michael-F-Bryan/projects
[dk]: https://en.wikipedia.org/wiki/Dunning%E2%80%93Kruger_effect
[posts]: {{< ref "." >}}