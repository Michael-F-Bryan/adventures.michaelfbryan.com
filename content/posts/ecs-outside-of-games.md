---
title: "A Thought Experiment: Using an ECS Outside of Game Engines"
date: "2019-12-23T23:25:03+08:00"
draft: true
tags:
- rust
- ecs
---

It's been about 6 months since I watched Catherine West's excellent [Using
Rust for Game Development][youtube] sent me down the *Entity-Component-System*
(ECS) rabbit hole, and I thought I'd share some of my findings.

Something that shocked me the most is how an ECS architecture is suited for more
than just games. In general, it seems to be suited well when:

- Your application is data-oriented
- Your application needs to deal with lots of little bits of data
- Each entity in your system (e.g. a monster in a game, or function in a
  compiler) can have lots of different data attached to it
- independent entities may have the attached data (e.g. both monsters and fire
  can deal damage)
- You need to temporarily associate some data with a particular entity while
  doing a particular thing (e.g. expressions are associated with type variables
  during type inference)

## What Is An Entity-Component-System?

I hope you'll forgive a little copy-paste, but the [Wikipedia definition][wiki]
gives a fairly decent summary of the topic:

> ECS follows the *composition over inheritance* principle that allows greater
> flexibility in defining entities where every object in a game's scene is an
> entity (e.g. enemies, bullets, vehicles, etc.). Every entity consists of one
> or more components which add behavior or functionality. Therefore, the
> behavior of an entity can be changed at runtime by adding or removing
> components.
>
> ...
>
> - **Entity:** The entity is a general purpose object. Usually, it only
>   consists of a unique id. They "tag every coarse gameobject as a separate
>   item". Implementations typically use a plain integer for this.
> - **Component:** The raw data for one aspect of the object, and how it
>   interacts with the world. "Labels the Entity as possessing this particular
>   aspect". Implementations typically use structs, classes, or associative
>   arrays.
> - **System:** "Each System runs continuously (as though each System had its
>   own private thread) and performs global actions on every Entity that
>   possesses a Component of the same aspect as that System."

There are several high-quality ECS implementations, but [specs][specs] crate
is widely accepted as one of the best ECS libraries in Rust.

## Compilers

## CAD Systems

## Conclusion

See Also:

- [ECS design outside gaming systems?](https://www.reddit.com/r/rust/comments/9dw26w/ecs_design_outside_gaming_systems/?utm_source=share&utm_medium=web2x)

[youtube]: https://www.youtube.com/watch?v=aKLntZcp27M
[wiki]: https://en.wikipedia.org/wiki/Entity_component_system#Characteristics
[specs]: https://crates.io/crates/specs
