---
title: "Common Newbie Mistakes and Bad Practices"
publishDate: "2021-09-16T23:44:27+08:00"
draft: true
tags:
- Rust
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

## Bad Habits

When you are coming to Rust from another language you bring all your previous
experiences with you.

Often this is awesome because it means you aren't learning programming from
scratch! However, you can also bring along bad habits or solutions which may
have been fine in the original language but end up being unidiomatic Rust.

### Using Sentinel Values

This one is a pet peeve of mine.

In most C-based languages (C, C#, Java, etc.), the way you indicate whether
something failed or couldn't be found is by returning a "special" value.  For
example, C#'s [`String.IndexOf()`][index-of] method will scan an array for a
particular element and return its index. Returning `-1` if nothing is found.

That leads to code like this:

```cs
string sentence = "The fox jumps over the dog";

int index = sentence.IndexOf("fox");

if (index != -1)
{
  string wordsAfterFox = sentence.SubString(index);
  Console.WriteLine(wordsAfterFox);
}
```

You see this sort of *"use a sentinel value to indicate something special"*
practice all the time. Other sentinel values you might find in the wild are
`""`, or `null` (someone once referred to this as their *"billion-dollar
mistake"*).

The general reason why this is a bad idea is that there is absolutely nothing to
stop you from forgetting that check. That means you can accidentally crash your
application with one misplaced assumption or when the code generating the
sentinel is far away from the code using it.

We can do a lot better in Rust, though. Just use `Option`!

By design, there is no way to get the underlying value without dealing with
the possibility that your `Option` may be `None`. This is enforced by the
compiler at compile time, meaning code that forgets to check won't even compile.

```rs
let sentence = "The fox jumps over the dog";
let index = sentence.find("fox");

// let words_after_fox = &sentence[index..]; // Error: Can't index str with Option<usize>

if let Some(fox) = index {
  let words_after_fox = &sentence[fox..];
  println!("{}", words_after_fox);
}
```

This way the compiler can help you write better code.

### An Abundance of `Rc<RefCell<T>>`

- People try to reuse patterns from GC'd (typically OO) languages

### Using the Wrong Integer Type

- Another hang-over from writing a lot of C is using the wrong integer type and
  getting frustrated because you need to cast to/from `usize` all the time
  because those integers were actually used as indices.
- Just use `usize` for anywhere you might be doing indexing or memory operations

### Unsafe - I Know What I'm Doing

- Using `unsafe` to just do what you would have in C because you "know it works"
- Transmute
- Trying to "work around" the borrow checker or privacy system

### Hungarian Notation

- Traits prefixed with `I`
- Types and traits shouldn't be easily confused in sensible code; they don't
  need a marked naming convention.

### Not Using Namespaces

- Manually uniquefying all identifiers (`lib_module_struct_method`) instead of
  just using built-in namespaces (`lib::module::Struct::method`). It's what
  they're there for!

### Overusing Slice Indexing

- Overusing slice indexing when iterators would be cleaner/faster, or the
  converse, overusing iterators where indexing would be easier on borrowck.

### Not Leveraging Pattern Matching

- Unnecessary `unwrap()`: `if opt.is_some() { opt.unwrap() }`

---

## Know Your Ecosystem

### Implement The Conversion Traits

- `From`
- `FromStr`
- `TryFrom`
- Trait miss-use: implementing `TryFrom<&str>` instead of `FromStr`.

### Clippy Is Your Friend

- When you review newbie code and 99% of things you’ll tell them would’ve been
  suggested by `clippy` as well.

### Manual Argument Parsing

- w.r.t. CLI, parsing arguments manually, or even trying to configure
  `clap` manually, instead of using `structopt` to create a strongly-typed
  input/config struct.

---

## Design

### Don't Assume Where Data Comes From

- use `fn parse(reader: impl std::io::Read)` instead of `fn parse(filename: &str)`

### Useful by Construction

- Initialise your object with useful values instead of populating it afterwards

### Optimise For Compile Times

- being able to keep compile time for most crates at < 2s; < 2s vs > 10s is the
  difference between staying in flow vs reading reddit
- Generic bloat
  ```rs
  pub fn do_something(path: impl AsRef<Path>) {
      // 200 line function to monomorphise in every crate
  }
  ```

### Getters and Setters

- Don't need to use getters and setters within the same crate
- You probably don't need setters at all, tbh

### Public Trait Private Impl Class

- Matched trait-struct "pairs".
- Often combined with [the above](#hungarian-notation) - `impl IFoo for Foo`.
- It won't work out the way you want
- Common in Java and C++

### Using `#[path]`

- Only useful in niche situations (e.g. switching between different
  implementations based on OS)
- Mainly a workaround because you don't understand how modules work

### Overusing Traits

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

### Putting IO Resources Inside a Mutex

- Putting IO resources inside mutexes.

### Self-Referential Structs

### Lifetimes in Long-Lived Objects

### Separate IO from Domain Logic

- In a CLI program, intermingling I/O, argument parsing, etc. with actual domain
  logic. Domain logic should have its own module or even crate for clean
  re-usability.

### Error Handling is an Afterthought

- Thinking of error handling as an "afterthought" or as some additional
  annoyance instead of designing with `Result` and `?`-bubbling upfront.
- Rust has the tools to implement the best possible error management of any
  language, but there's no pit of success there. One stable state is a giant
  enum which combines errors from different subsystems, has an `Other(String)`
  variant just in case, and which is used for basically anything.

### Cyclic Crate Dependencies

- Cyclic dependencies between crates (when a leaf crate have a dev-dependency on
  the root crate)

### Too Generic for your Own Good

- Related to [Overusing Traits](#overusing-traits)
- Complex `where` clauses are hard to read
- Lifetimes and HRTBs and bounds on associated types can get pretty complex
  pretty quickly

---

## Conceptual Misunderstandings

### Strings are not Paths

- use `&Path` instead of `&str`
- `join()`, not `format!("{}/{}", dir, filename)`
- Non-UTF8 paths
- Self-documenting

### Unnecessary Indirection

- `fn foo(title: &String)`

### Copy Followed By A Borrow

- `function_taking_str(&"blah".to_string())`

### Compile Time vs Run Time

- Trying to use `include_str!()` instead of `std::fs::read_to_string()`

### Dyn Trait Isn't Like `Object`

- Expecting `dyn Trait` to sub-type or be dynamically typed

### Strings Aren't Arrays of Characters

- Using byte indexing into UTF-8 strings without awareness of char boundaries
  etc. and the resulting panics.
- You can often just use iterators

### Measuring Performance of Debug Builds

- It's a complete waste of time
- Makes people think "Rust is slower than Python"

### Passing Empty Buffers to `read()`

- The `Read` trait writes into an existing buffer
- It won't allocate

### You Need to Read/Write Everything

- Calling `Read::read()` or `Write::write()` when `read_exact()` or
  `write_all()` is needed

[post]: https://users.rust-lang.org/t/common-newbie-mistakes-or-bad-practices/64821
[index-of]: https://docs.microsoft.com/en-us/dotnet/api/system.string.indexof?view=net-5.0
