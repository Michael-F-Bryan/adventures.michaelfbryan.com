---
title: "Common Newbie Mistakes and Bad Practices in Rust: Bad Habits"
publishDate: "2021-09-16T23:44:27+08:00"
draft: true
tags:
- Rust
series:
- Rust Best Practices
---

When you are coming to Rust from another language you bring all your previous
experiences with you.

Often this is awesome because it means you aren't learning programming from
scratch! However, you can also bring along bad habits or solutions which may
have been fine in the original language but end up being unidiomatic Rust.

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## Using Sentinel Values

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

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=ed6d6b8ebdd7581a95b0098258b4f371)

## Hungarian Notation

- Traits prefixed with `I`
- Types and traits shouldn't be easily confused in sensible code; they don't
  need a marked naming convention.

## An Abundance of `Rc<RefCell<T>>`

- People try to reuse patterns from GC'd (typically OO) languages

## Using the Wrong Integer Type

- Another hang-over from writing a lot of C is using the wrong integer type and
  getting frustrated because you need to cast to/from `usize` all the time
  because those integers were actually used as indices.
- Just use `usize` for anywhere you might be doing indexing or memory operations

## Unsafe - I Know What I'm Doing

- Using `unsafe` to just do what you would have in C because you "know it works"
- Transmute
- Trying to "work around" the borrow checker or privacy system

## Not Using Namespaces

- Manually uniquefying all identifiers (`lib_module_struct_method`) instead of
  just using built-in namespaces (`lib::module::Struct::method`). It's what
  they're there for!

## Overusing Slice Indexing

- Overusing slice indexing when iterators would be cleaner/faster, or the
  converse, overusing iterators where indexing would be easier on borrowck.

## Not Leveraging Pattern Matching

- Unnecessary `unwrap()`: `if opt.is_some() { opt.unwrap() }`

[post]: https://users.rust-lang.org/t/common-newbie-mistakes-or-bad-practices/64821
[index-of]: https://docs.microsoft.com/en-us/dotnet/api/system.string.indexof?view=net-5.0
