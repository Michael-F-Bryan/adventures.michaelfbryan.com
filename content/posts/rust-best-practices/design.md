---
title: "Common Newbie Mistakes and Bad Practices in Rust: Design"
publishDate: "2021-09-16T23:44:27+08:00"
draft: true
tags:
- Rust
series:
- Rust Best Practices
---

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## Don't Assume Where Data Comes From

- use `fn parse(reader: impl std::io::Read)` instead of `fn parse(filename: &str)`

## Useful by Construction

- Initialise your object with useful values instead of populating it afterwards

## Optimise For Compile Times

- being able to keep compile time for most crates at < 2s; < 2s vs > 10s is the
  difference between staying in flow vs reading reddit
- Generic bloat
  ```rs
  pub fn do_something(path: impl AsRef<Path>) {
      // 200 line function to monomorphise in every crate
  }
  ```

## Getters and Setters

- Don't need to use getters and setters within the same crate
- You probably don't need setters at all, tbh

## Public Trait Private Impl Class

- Matched trait-struct "pairs".
- Often combined with [the above](#hungarian-notation) - `impl IFoo for Foo`.
- It won't work out the way you want
- Common in Java and C++

## Using `#[path]`

- Only useful in niche situations (e.g. switching between different
  implementations based on OS)
- Mainly a workaround because you don't understand how modules work

## Overusing Traits

- Often you don't *need* to be super generic
- Hiding implementations isn't as important as in OO because you can't inherit
  from another implementation and tamper with it
- I get the sense that newcomers to Rust tend to overuse traits in general, when
  you can get by most of the time defining only ADTs (and using other people's
  traits). Maybe this is the imprint of object-oriented languages where classes
  can be both containers for data and abstract interfaces? (Makes me a little
  apprehensive about the "field in trait" proposals you sometimes see floated.)
- Trait over-use: implementing `From` for something which could have been a
  *named* factory function; introducing a trait where a bunch of inherent
  methods would do.
- [Concrete Abstraction](https://matklad.github.io/2020/08/15/concrete-abstraction.html)

## Putting IO Resources Inside a Mutex

- Putting IO resources inside mutexes.

## Self-Referential Structs

## Lifetimes in Long-Lived Objects

## Separate IO from Domain Logic

- In a CLI program, intermingling I/O, argument parsing, etc. with actual domain
  logic. Domain logic should have its own module or even crate for clean
  re-usability.

## Error Handling is an Afterthought

- Thinking of error handling as an "afterthought" or as some additional
  annoyance instead of designing with `Result` and `?`-bubbling upfront.
- Rust has the tools to implement the best possible error management of any
  language, but there's no pit of success there. One stable state is a giant
  enum which combines errors from different subsystems, has an `Other(String)`
  variant just in case, and which is used for basically anything.

## Cyclic Crate Dependencies

- Cyclic dependencies between crates (when a leaf crate have a dev-dependency on
  the root crate)

## Too Generic for your Own Good

- Related to [Overusing Traits](#overusing-traits)
- Complex `where` clauses are hard to read
- Lifetimes and HRTBs and bounds on associated types can get pretty complex
  pretty quickly

[post]: https://users.rust-lang.org/t/common-newbie-mistakes-or-bad-practices/64821
