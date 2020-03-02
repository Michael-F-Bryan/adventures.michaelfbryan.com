---
title: "Is It Possible to Be Too Generic?"
date: 2020-03-02T19:06:56+08:00
draft: true
tags:
- architecture
- rust
---

A phrase that gets hammered into programmers almost from from day 1 is *"Don't
Repeat Yourself"* and, while it's a bit cliché, the world is definitely a better
place because of it.

There are several techniques to reduce repetition and the amount of boilerplate
code you need to write and arguably one of the most powerful is "generics", a
loosely-defined umbrella term for code that is generic over the concrete type
it is acting on and defined at compile time. This is sometimes referred to as
[Parametric Polymorphism][para-poly] (in languages like C#, Haskell, and Rust)
or [Ad Hoc Polymorphism][ad-hoc] (in the case of C++ templates).

However not everything is sunshine and rainbows. Last week I was experimenting
with [the `legion` ECS library][legion] and encountered a greater-than-usual 
amount of friction while trying to implement some "typical" use cases. It took
a while for me to realise, but the library's decision to use sophisticated 
generics to increase expressiveness when querying and manipulating data brings
to light some of the downsides that comes from this sort of polymorphism.

- Readability
- Cognitive Load
- Discoverability

Languages like C++ and Rust pride themselves on their [zero-cost
abstractions][0-cost] and compile-time generics underpin their ability to
provide these abstractions. I've seen several code monsters born through the
use of generics, and hopefully by pointing out some pain points of compile-time
generics people will be able to create more user-friendly APIs into the future.

{{% notice note %}}
If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Readability

## Cognitive Load

## Discoverability

## Some Best Practices

## Conclusions

[para-poly]: https://en.wikipedia.org/wiki/Parametric_polymorphism
[ad-hoc]: https://en.wikipedia.org/wiki/Ad_hoc_polymorphism
[0-cost]: https://www.quora.com/What-are-zero-cost-abstractions-in-programming-languages