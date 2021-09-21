---
title: "Common Newbie Mistakes and Bad Practices in Rust: Bad Habits"
publishDate: "2021-09-16T23:44:27+08:00"
draft: true
tags:
- Rust
series:
- Rust Best Practices
toc: true
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

Back in the 70's, a naming convention called [*Hungarian Notation*][hungarian]
was developed by programmers writing in languages where variables are untyped or
dynamically typed. It works by adding a mnemonic to the start of a name to
indicate what it represents, for example the boolean `visited` variable might be
called `bVisited` or the string `name` might be called `strName`.

You can still see this naming convention in languages Delphi where classes
(types) start with `T`, fields start with `F`, arguments start with `A`, and
so on.

```delphi
type
 TKeyValue = class
  private
    FKey: integer;
    FValue: TObject;
  public
    property Key: integer read FKey write FKey;
    property Value: TObject read FValue write FValue;
    function Frobnicate(ASomeArg: string): string;
  end;
```

C# also has a convention that all interfaces should start with `I`, meaning
programmers coming to Rust from C# will sometimes prefix their traits with `I`
as well.

```rs
trait IClone {
  fn clone(&self) -> Self;
}
```

In this case, just drop the leading `I`. It's not actually helping anyone and
unlike in C#, every place a trait it's unambiguous what the thing is and
sensible code shouldn't cause situations where you may confuse traits and types
(trait definitions start with `trait`, trait objects start with `dyn`, you can
*only* use traits in generics/where clauses, etc.).

You also see this inside functions where people will come up with new names for
something as they convert it from one form to another. Often these names are
silly and/or contrived, providing negligible additional useful information to
the reader.

```rs
let account_bytes: Vec<u8> = read_some_input();
let account_str = String::from_utf8(account_bytes)?;
let account: Account = account_str.parse()?;
```

I mean, if we're calling `String::from_utf8()` we already know `account_str`
will be a `String` so why add the `_str` suffix?

Unlike a lot of other languages, Rust encourages shadowing variables when you
are transforming them from one form to another, especially when the previous
variable is no longer accessible (e.g. because it's been moved).

```rs
let account Vec<u8> = read_some_input();
let account = String::from_utf8(account)?;
let account: Account = account.parse()?;
```

This is arguably superior because we can use the same name for the same concept.

Other languages [frown on shadowing][shadowing] because it can be easy to lose track of what
type a variable contains (e.g. in a dynamically typed language like JavaScript)
or you can introduce bugs where the programmer thinks a variable has one type
but it actually contains something separate. Neither issue is relevant with a
strongly typed language like Rust

## An Abundance of `Rc<RefCell<T>>`

- People try to reuse patterns from GC'd (typically OO) languages

## Using the Wrong Integer Type

- Another hang-over from writing a lot of C is using the wrong integer type and
  getting frustrated because you need to cast to/from `usize` all the time
  because those integers were actually used as indices.
- Just use `usize` for anywhere you might be doing indexing or memory operations

## Unsafe - I Know What I'm Doing

There's an old Rust koan on the *User Forums* by Daniel Keep that comes to mind
every time I see a grizzled C++ programmer reach for raw pointers or
`std::mem::transmute()` because the borrow checker keeps rejecting their code:
[*Obstacles*](https://users.rust-lang.org/t/rust-koans/2408?u=michael-f-bryan).

Too often you see people wanting to hack around privacy, create
self-referencing structs, or create global mutable variables using `unsafe`.
Frequently this will be accompanied by comments like *"but I know this program
will only use a single thread so accessing the `static mut` is fine"* or *"but
this works perfectly fine in C"*.

The reality is that `unsafe` code is nuanced and you need to have a good
intuition for Rust's borrow checking rules and memory model. I hate to be a gate
keeper and say *"you must be this tall to write ~~multi-threaded~~ `unsafe`
code"* [^must-be-this-tall], but there's a good chance that if you are new to
the language you won't have this intuition and are opening yourself and your
colleagues up to a lot of pain.

It's fine to play around with `unsafe` if you are trying to learn more about
Rust or you know what you are doing and are using it legitimately, but `unsafe`
is **not** a magical escape hatch which will make the compiler stop complaining.

## Not Using Namespaces

- Manually uniquefying all identifiers (`lib_module_struct_method`) instead of
  just using built-in namespaces (`lib::module::Struct::method`). It's what
  they're there for!

## Overusing Slice Indexing

The for-loop and indexing is the bread and butter for most C-based languages.

```rs
let points: Vec<Coordinate> = ...;
let differences = Vec::new();

for i in 1..points.len() [
  let current = points[i];
  let previous = points[i-1];
  differences.push(current - previous);
]
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=62d33c91cf741e9f89b84054cf6a827d)

However, it's easy to accidentally introduce an off-by-one error when using
indexing (e.g. I needed to remember to start looping from `1` and subtract `1`
to get the `previous` point) and even seasoned programmers aren't immune from
crashing due to an index-out-of-bounds error.

In situations like these, Rust encourages you to reach for iterators instead.
The slice type even comes with high-level tools like the `windows()` and
`array_windows()` methods to let you iterate over adjacent pairs of elements.

```rs
let points: Vec<Coordinate> = ...;
let mut differences = Vec::new();

for [previous, current] in points.array_windows().copied() {
  differences.push(current - previous);
}
```

[(playground)](https://play.rust-lang.org/?version=nightly&mode=debug&edition=2018&gist=e647c18bfec0b8d629e5bcbb7b6a66f1)

You could even remove the for-loop and mutation of `differences` altogether.

```rs
let differences: Vec<_> = points
  .array_windows()
  .copied()
  .map(|[previous, current]| current - previous)
  .collect();
```

[(playground)](https://play.rust-lang.org/?version=nightly&mode=debug&edition=2018&gist=030d0b491a2bc8204499f65b38f2aefd)

Some would argue the version with `map()` and `collect()` is cleaner or more
"functional", but I'll let you be the judge there.

## Overusing Iterators

Once you start drinking the koolaid that is Rust's iterators you can run into
the opposite problem - *when all you have is a hammer everything looks like a
nail*.

This can result in your code being filled with long chains of `map()`,
`filter()`, and `and_then()` calls. Especially when intermingled with the
analogous methods on `Option` and `Result`.

```rs
let stars = github_client.get_starred_repos()
  .and_then(|response| parse_json(response.body))
  .map(|payload: StarredRepoResponse| payload.starred_repos.iter()
    .map(|repo| repo.author))
```

In other domains, this pattern is sometimes referred to as a ["train
wreck"][train-wreck].

## Not Leveraging Pattern Matching

In most other mainstream languages it is quite common to see the programmer
write a check before they do an operation which may throw an exception. Our
C# `IndexOf()` snippet from earlier is a good example of this:

```cs
int index = sentence.IndexOf("fox");

if (index != -1)
{
  string wordsAfterFox = sentence.SubString(index);
  Console.WriteLine(wordsAfterFox);
}
```

Closer to home, you might see code like this:

```rs
let opt: Option<_> = ...;

if opt.is_some() {
  let value = opt.unwrap();
  ...
}
```

or this:

```rs
let list: &[f32] = ...;

if !list.is_empty() {
  let first = list[0];
  ...
}
```

Now both snippets are perfectly valid pieces of code and will never fail, but
similar to [sentinel values](#using-sentinel-values) you are making it easy
for future refactoring to introduce a bug.

Using things like pattern matching and `Option` help you avoid this situation
by making sure the *only* way you can access a value is if it is valid.

```rs
if let Some(value) = opt {
  ...
}

if let [first, ..] = list {
  ...
}
```

Depending on where it is used and how smart LLVM or your CPU's branch predictor
are, this may also generate slower code because the fallible operation
(`opt.unwrap()` or `list[index]` in that example) needs to do unnecessary checks
[^benchmark-it].

[post]: https://users.rust-lang.org/t/common-newbie-mistakes-or-bad-practices/64821
[index-of]: https://docs.microsoft.com/en-us/dotnet/api/system.string.indexof?view=net-5.0
[hungarian]: https://en.wikipedia.org/wiki/Hungarian_notation
[shadowing]: https://rules.sonarsource.com/cpp/RSPEC-1117
[train-wreck]: https://wiki.c2.com/?TrainWreck

[^must-be-this-tall]: [*Must be This Tall to Write Multi-Threaded Code* - Bobby Holley](https://bholley.net/blog/2015/must-be-this-tall-to-write-multi-threaded-code.html)

[^benchmark-it]: Don't just listen to some random guy on the internet. If you
  care about performance then write a benchmark.

