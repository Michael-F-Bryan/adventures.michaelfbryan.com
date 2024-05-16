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
place because of that mentality.

There are several techniques to reduce repetition and the amount of boilerplate
code you need to write and arguably one of the most powerful is "generics", a
loosely-defined umbrella term for code that is generic over the concrete type
it is acting on and defined at compile time. This is sometimes referred to as
[Parametric Polymorphism][para-poly] (in languages like C#, Haskell, and Rust)
or [Ad Hoc Polymorphism][ad-hoc] (in the case of C++ templates).

Not everything is sunshine and rainbows, though. For example, last week I was
experimenting with [the `legion` ECS library][legion] and encountered a
greater-than-usual amount of friction while trying to do some typical
operations. It took a while for me to realise this, but the library's decision
increase expressiveness when querying and manipulating data by using advanced
generics brings to light some of the downsides that comes from this form of
polymorphism.

- Readability
- Cognitive Load
- Discoverability

You'll notice that these don't affect an application directly (e.g. by impacting
performance or functionality), instead they impair the *Developer Experience*.

In my books, making a library easy to just as important as performance or
adding functionality. After all, it doesn't matter how fast your library is or
how many things it can do if it's so hard to use that I throw it away after a
week of banging my head against a wall and write my own version.

{{% notice note %}}
If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Readability of Code and Error Messages

I'm not sure if it's just me, but when a programmer has been a little
"enthusiastic" with their generics it can make the code nigh unreadable.

It's a bit hard to find examples of this without being accused of making a
straw man argument, but I'll try.

## Cognitive Load

## Discoverability

## Some Best Practices

## Conclusions

I've seen several code monsters born through the
use of generics, and hopefully by pointing out some pain points of compile-time
generics people will be able to create more user-friendly APIs into the future.

This is important because languages like C++ and Rust pride themselves on their
[zero-cost abstractions][0-cost], and compile-time generics underpin their
ability to provide these abstractions. If you can't create zero-cost
abstractions that are easy to use, people are going to do things the long way
with lots of boilerplate and error-prone code, and that would be a shame.


[para-poly]: https://en.wikipedia.org/wiki/Parametric_polymorphism
[ad-hoc]: https://en.wikipedia.org/wiki/Ad_hoc_polymorphism
[0-cost]: https://www.quora.com/What-are-zero-cost-abstractions-in-programming-languages
[legion]: https://crates.io/crates/legion