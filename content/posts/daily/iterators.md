---
title: "Daily Rust: Iterators"
publishDate: "2021-08-17T01:45:41+08:00"
draft: true
tags:
- Daily Rust
- Rust
---

Iterators are one of the core abstractions you'll use in Rust. They drive the
language's for-loop and the various combinator methods provide a very ergonomic,
functional way to reason about data.

That said, they can also feel a bit intimidating because they often touch on
more "advanced" topics like generics, associated types, and often lifetimes.

{{% notice info %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## The Iterator Trait

At its most simplest, an iterator is just something with a `next()` method that
may return some `Item` or `None`.

This is all encapsulated in the [`std::iter::Iterator`][std-iter] trait, with
the definition looking something like this:

```rust
trait Iterator {
    type Item;

    fn next(&mut self) -> Option<Self::Item>;
}
```

Now you may be wondering why most Rust code isn't scattered with calls to
`next()`, and that's where the [*Syntactic Sugar*][syntactic-sugar] comes in.
This is where the compiler will see certain high level constructs in your code
and transform them into a lower level form.

The humble for-loop is probably the most familiar place where Rust uses
syntactic sugar to let programmers write high-level code.

For example, when the compiler sees this...

```rust
for item in 0..5 {
    println!("{}", item);
}
```

... the code will be transformed into this...

```rust
let mut iterator = (0..5).into_iter();

while let Some(item) = iterator.next() {
    println!("{}", item);
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=9c2994be6caac61c54698b2e5adf9f94)

What this does is turn the range expression, `0..5`, into an iterator and then
keep calling its `next()` method until we get `None`.

{{% notice note %}}

This `into_iter()` method (backed by the [`std::iter::IntoIterator`][into-iter]
trait) is a way to transform something into an iterator. Some common types that
implement `IntoIterator` are [`Vec<T>`][vec-into-iter],
[`Option<T>`][option-into-iter], and most importantly, [anything implementing
the `Iterator` trait][iter-into-iter] (which will just return itself).

[vec-into-iter]: https://github.com/rust-lang/rust/blob/73d96b090bb68065cd3a469b27cbd568e39bf0e7/library/alloc/src/vec/mod.rs#L2489-L2529
[option-into-iter]: https://github.com/rust-lang/rust/blob/73d96b090bb68065cd3a469b27cbd568e39bf0e7/library/core/src/option.rs#L1660-L1682
[iter-into-iter]: https://github.com/rust-lang/rust/blob/73d96b090bb68065cd3a469b27cbd568e39bf0e7/library/core/src/iter/traits/collect.rs#L237-L246
[into-iter]: https://doc.rust-lang.org/std/iter/trait.IntoIterator.html
{{% /notice %}}

## Fibonacci

Now we have some basic familiarity with iterators, let's create our own iterator
over all the Fibonacci numbers that fit into a `u32`.

First we'll create a new `Fibonacci` type.

```rust
struct Fibonacci {
    a: u32,
    b: u32,
}
```

Then we implement the `Iterator` trait. The idea is that each call to `next()`
will do just enough work to generate the next number in the sequence.

```rust
impl Iterator for Fibonacci {
    type Item = u32;

    fn next(&mut self) -> Option<u32> {
        // Try to add "a" and "b", returning None if the addition would
        // overflow to signal that we've reached the end of the sequence.
        let next_term = self.a.checked_add(self.b)?;

        self.a = self.b;
        self.b = next_term;

        Some(next_term)
    }
}
```

{{% notice note %}}
You'll notice we use the [`checked_add()`][checked-add] method here instead of
the normal `+` operator. This is important because we need a stopping
condition.

Without it we would reach `2_971_215_073` and either panic (in debug mode)
overflow (in release mode) - Rust's way of telling us that we if we are creating
bigger and bigger numbers we should handle the situation when our numbers get
too big for the integer type we are using.

We actually miss the top two Fibonacci numbers this way, but adding extra logic
to handle them would complicate the example and you wouldn't actually learn
anything new about iterators.

[checked-add]: https://doc.rust-lang.org/std/primitive.u32.html#method.checked_add
{{% /notice %}}

Now all we need is a helper function to create a `Fibonacci` object with our
initial conditions  and a `main()` function that uses it in a loop and we're
good to go.

```rust
fn fibonacci_numbers() -> Fibonacci {
    Fibonacci { a: 1, b: 0 }
}

fn main() {
    for number in fibonacci_numbers() {
        println!("{}", number);
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=5ecf8f52253983fabe7b24edc2ed6c8d)

Strictly speaking the helper function wasn't really necessary, but it helps
make the code cleaner and means readers won't see the `a: 1, b: 0` and wonder
where we pulled those magic numbers from.

## Iterating Over a Slice

```rust
struct SliceIter<'a, T> {
    slice: &'a [T],
    index: usize,
}
```

```rust
impl<'a, T> Iterator for SliceIter<'a, T> {
    type Item = &'a T;

    fn next(&mut self) -> Option<Self::Item> {
        let item = self.slice.get(self.index)?;
        self.index += 1;

        Some(item)
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=release&edition=2018&gist=ab2183b26e3a10c63e2b4c60a7843cb2)

{{% notice info %}}
For the curious, I've also implemented [an `unsafe` version][unsafe]. I'll leave
comparing the two for performance as an exercise for the reader, but gut feel
says they'll be identical.

I'd love you to prove me wrong and explain why on Reddit or the user forums,
though 😉

[unsafe]: https://play.rust-lang.org/?version=stable&mode=release&edition=2018&gist=420278dbeec26f0c560f9b1b13612922
{{% /notice %}}

## Filter

One of the most commonly used iterator combinators is [`filter()`][filter], a
combinator which takes an iterator and a predicate and only yields items where
that predicate returns `true`.

You often see it used like this:

```rust
fn main() {
    let even_numbers = (0..10).filter(|n| n % 2 == 0);

    for number in even_numbers {
        println!("{}", number);
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=add1a5b92871b9162b4de061976393b3)

We get the following output, as expected:

```
0
2
4
6
8
```

Now, let's write our own implementation!

First we'll need a `Filter` type and some way of constructing it. For ergonomics,
you would normally create an extension trait with a `fn filter()` method that
returns `Filter` and implement that for all iterators, but we'll be lazy and
just write a function.

```rust
struct Filter<I, F> {
    iter: I,
    predicate: F,
}

fn filter<I, F>(iter: I, predicate: F) -> impl Iterator<Item = I::Item>
{
    Filter { iter, predicate }
}
```

{{% notice tip %}}
In this situation we've chosen to use `impl Trait` for the return value instead
of providing an explicit type.

The `Filter` struct is just an implementation detail, and not necessarily one we
want people to code against or make public, so we make the concrete type
unnameable.
{{% /notice %}}

Now we obviously need to implement the `Iterator` trait on `Filter`.

The naive implementation would look something like this:

```rust
impl<I, F> Iterator for Filter<I, F>
where
    I: Iterator,
    F: FnMut(&I::Item) -> bool,
{
    type Item = I::Item;

    fn next(&mut self) -> Option<Self::Item> {
        let item = self.iter.next()?;

        if (self.predicate)(&item) {
            Some(item)
        } else {
            None
        }
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=518ed8c15e89a1807ac1c8881211e7a1)

{{% notice tip %}}
You might have noticed we chose to accept a `FnMut` closure for our predicate
instead of a plain `Fn`. By allowing the closure to have mutable state, it means
the caller could mutate external state (e.g. some sort of `count` variable from
the calling function) to determine whether the predicate is satisfied or not.

Similarly, we choose to pass in an `&I::Item` because we want to give the
predicate access to the item, but it shouldn't be given ownership (because then
our iterator has nothing to yield) or allowed to mutate the item.
{{% /notice %}}

You can see we pull the next item out of the inner iterator (using `?` to return
`None` if there are no more items), then we call the predicate function provided
by the user to check whether we should yield the item.

However, there is a small issue... Check out the output:

```
0
```

We're stopping after the first `false` item!

What we actually need to do is write a loop which keeps pulling items out of
the iterator until the predicate is satisfied.


```rust
impl<I, F> Iterator for Filter<I, F>
where
    I: Iterator,
    F: FnMut(&I::Item) -> bool,
{
    type Item = I::Item;

    fn next(&mut self) -> Option<Self::Item> {
        while let Some(item) = self.iter.next() {
            if (self.predicate)(&item) {
                return Some(item);
            }
        }

        None
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=3b8b02131aa32684e23c048ec07cd92d)


## Conclusions

[syntactic-sugar]: https://en.wikipedia.org/wiki/Syntactic_sugar
[std-iter]: https://github.com/rust-lang/rust/blob/73d96b090bb68065cd3a469b27cbd568e39bf0e7/library/core/src/iter/traits/iterator.rs#L55-L92
[filter]: https://doc.rust-lang.org/std/iter/trait.Iterator.html#method.filter
