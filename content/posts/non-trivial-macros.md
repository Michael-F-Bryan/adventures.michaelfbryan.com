---
title: "Non Trivial Rust Macros"
date: "2020-06-18T22:52:32+08:00"
draft: true
tags:
- Rust
---


{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Back-Story

In one of the big projects I work on, we made a design decisions you won't
see in most typical Rust codebases:

> Major systems must be isolated in their own crate with all requirements
> declared via traits, and **where possible these traits should be
> [object-safe][object-safety]**.

The reasoning for this is quite straightforward, the application may need to
reconfigure both its behaviour and hardware bindings at runtime.

This is a soft-realtime motion controller which can control several families
of machines, so imagine it is initially configured to run machine A with
particular assumptions about the world (which inputs things are attached to,
available optional components, etc.) and then the user changes some settings
to make it behave like machine B with its own assumptions about the world.

You have a couple options for how to implement this:

1. Load the machine configuration on startup and jump to the corresponding
   code... This requires a restart for any settings changes to take effect
2. Use enums to encapsulate the different IO layouts or business logic...
   Congratulations, your code now has 10x times more `match` statements
3. Take an object-oriented approach, replacing the conditionals from option 2
   [with polymorphism][replace-conditional] (i.e. dynamic dispatch)... Adds
   constraints on the behaviour you can expect from things, but reduces
   cognitive load and lets you switch between things at runtime by pointing at
   a different object

The last option looks like the least-bad of the 3, but no doubt you'll know
if it doesn't work out. Just look out for the blog post exploring different
architectures for complicated systems 😛

Making allowances for dynamic dispatch where possible adds an interesting
challenge, though...

Imagine you're programming the flashing lights on an operator console and come
up with something like this:

```rust
struct GPIOA { ... }

fn flash_periodically(gpio: &mut GPIOA, pin: usize, interval: Duration) {
    let mut current_state = false;

    loop {
        lamp.set_state(pin, current_state);
        current_state = !current_state;
        sleep(interval);
    }
}
```

Now, being a good developer you pull the hardware-specific logic out into its
own trait.

```rust
trait DigitalInput {
    fn set_state(&mut self, new_state: bool);
}

fn flash_periodically<D>(lamp: &mut D, interval: Duration)
    where D: DigitalInput
{
    let mut current_state = false;

    loop {
        lamp.set_state(current_state);
        current_state = !current_state;
        sleep(interval);
    }
}
```

On the surface this looks quite good, we are only coupling to the functionality
declared by the trait.

We can even make our own `DigitalInput` and verify it compiles as expected.

```rust
struct Pin;

impl DigitalInput for Pin {
    fn set_state(&mut self, new_state: bool) { unimplemented!() }
}

fn main() {
    let mut pin = Pin;
    flash_periodically(&mut pin, Duration::from_millis(100));
}
```

However, the `DigitalInput` trait has a couple quirks that prevent it from doing
dynamic dispatch. The easiest way to see this is by creating an
`assert_is_digital_input()` function.

```rust
fn assert_is_digital_input<D>() where D: DigitalInput + ?Sized {}

fn main() {
    assert_is_digital_input::<dyn DigitalInput>();
    assert_is_digital_input::<Box<dyn DigitalInput>>();
    assert_is_digital_input::<&mut dyn DigitalInput>();
}
```

This fails to compile.

```
error[E0277]: the trait bound `std::boxed::Box<dyn DigitalInput>: DigitalInput` is not satisfied
  --> src/main.rs:23:5
   |
19 | fn assert_is_digital_input<D>() where D: DigitalInput + ?Sized {}
   |                                          ------------ required by this bound in `assert_is_digital_input`
...
23 |     assert_is_digital_input::<Box<dyn DigitalInput>>();
   |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ the trait `DigitalInput` is not implemented for `std::boxed::Box<dyn DigitalInput>`

error[E0277]: the trait bound `&mut dyn DigitalInput: DigitalInput` is not satisfied
  --> src/main.rs:24:5
   |
19 | fn assert_is_digital_input<D>() where D: DigitalInput + ?Sized {}
   |                                          ------------ required by this bound in `assert_is_digital_input`
...
24 |     assert_is_digital_input::<&mut dyn DigitalInput>();
   |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ the trait `DigitalInput` is not implemented for `&mut dyn DigitalInput`

error: aborting due to 2 previous errors
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=d9293c605ba8fd1fc6c656b5155410b0)

The key bits to look out for:

> the trait bound `std::boxed::Box<dyn DigitalInput>: DigitalInput` is not satisfied

> the trait bound `&mut dyn DigitalInput: DigitalInput` is not satisfied

Trait objects don't natively implement their own traits!

The workaround is to manually implement `DigitalInput` for the types you need
(i.e. `Box<dyn DigitalInput>` and `&mut dyn DigitalInput`).

```rust
impl<D: DigitalInput + ?Sized> DigitalInput for Box<D>
{
    fn set_state(&mut self, new_state: bool) { (**self).set_state(new_state) }
}

impl<'d, D: DigitalInput + ?Sized> DigitalInput for &'d mut D
{
    fn set_state(&mut self, new_state: bool) { (**self).set_state(new_state) }
}
```

This works, but it leads to *loads* of copy/paste code. For example, adding a
new method to a trait means you need to fix the trait object impls as well as
any other real downstream implementations. Multiply by half a dozen systems
with 2 or 3 traits each (each with their own set of methods) and this
copy-pasta gets annoying pretty quickly.

My solution is to use a macro (i.e. compile-time codegen) to automatically
generate the necessary impl blocks. This *could* be implemented using
procedural macros, but they can have a negative impact on compile times and
I'd like an excuse to play around with Rust's declarative macros some more.

## Getting Started

The end goal is to write something like this...

```rust
trait_with_dyn_impls! {
    /// An interesting trait.
    pub trait InterestingTrait {
        fn get_x(&self) -> u32;

        /// Do some sort of mutation.
        fn mutate(&mut self, y: String);
    }
}
```

... And have it automatically implement the trait for `&mut dyn InterestingTrait`
and `Box<dyn InterestingTrait>`.

You can think of Rust's declarative (`macro_rules`) macros as a form of
pattern matching which, instead of relying on the type system, uses parsing
machinery from the compiler itself.

For example, when you write `$value:expr` in a macro, that asks the compiler
to try and parse some tokens as an expression, and assign the AST node to
`$value` on success.

Our first step is to write a macro that can match a method signature.

Matching something like `fn get_x(&self) -> u32;` isn't too difficult. The only
bits that will change are `get_x` and `u32`, where `get_x` is some identifier
for the item name and `u32` is our return type.

```rust
// src/lib.rs

macro_rules! visit_members {
    ( fn $name:ident(&self) -> $ret:ty; ) =>  {}
}
```

We can even write a test for it.

```rust
// src/lib.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn visit_simple_getter_method() {
        visit_members! { fn get_x(&self) -> u32; }
    }
}
```

If the code compiles, it works 👍

We can also use repetition to match a function with 0 or more arguments.

```rust
// src/lib.rs

macro_rules! visit_members {
    ( fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) -> $ret:ty; ) => {};
}

#[test]
fn visit_method_with_multiple_parameters() {
    visit_members! { fn get_x(&self, foo: usize) -> u32; }
    visit_members! { fn get_x(&self, bar: &str, baz: impl FnOnce()) -> u32; }
}
```

In the same way you can use `$( ... )*` for zero or more repeats, you can use
`$( ... )?` to match exactly zero or one items. This gives us a nice way to handle
functions which don't return anything (i.e. the implicit `-> ()`).

```rust
// src/lib.rs

macro_rules! visit_members {
    ( fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?; ) => {};
}

#[test]
fn visit_method_without_return_type() {
    visit_members! { fn get_x(&self); }
}
```

We can also use the `meta` specifier to handle an arbitrary number of
attributes or docs-comment attached to a function.

```rust
// src/lib.rs

macro_rules! visit_members {
    (
        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;
    ) => {};
}

#[test]
fn visit_method_with_attributes() {
    visit_members! {
        /// Get `x`.
        #[allow(bad_style)]
        fn get_x(&self) -> u32;
    }
}
```

{{% notice note %}}
You'll notice that I introduced a couple line breaks to help make the pattern
expression look similar to the code we're trying to match. Something you'll
learn in this article is that readability is super important.

Rust's declarative macros are similar to [APL][apl] in that they're really
powerful and let you accomplish a lot with not much code... but it's also the
kind of code that will only be written once. Then when a bug shows up you
throw it away and start again instead of trying to understand the mess of
punctuation, words, and symbols.

[apl]: https://en.wikipedia.org/wiki/APL_(programming_language)
{{% /notice %}}

{{% notice info %}}
I'm going to skip the problem of handling `&self` versus `&mut self` for the
time being. The macro system has a couple... quirks... which make dealing
with `self` kinda awkward.
{{% /notice %}}

This `visit_members!()` forms the core part of our `trait_with_dyn_impls!()`
macro.

## Incremental TT Munching

When you have a stream of input where you want to apply different logic based
on what each item looks like, one of the most powerful tools in your Rust
macro arsenal is the [Incremental TT Muncher][tt].

*The Little Book of Rust Macros* does a pretty good job of explaining how it
works:

> A "TT muncher" is a recursive macro that works by incrementally processing
> its input one step at a time. At each step, it matches and removes (munches)
> some sequence of tokens from the start of its input, generates some
> intermediate output, then recurses on the input tail.

We're going to use a TT muncher to match multiple function signatures. The idea
is that we'll adapt our existing `visit_members!()` macro to match the function
signature at the start of our input stream, then recurse on the rest.

The first step is to add something which will match any tokens after our
signature.

```rust
// src/lib.rs

macro_rules! visit_members {
    (
        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;

        $( $rest:tt )*
    ) => {};
}
```

At this point all our existing tests still pass because they don't have any
trailing tokens.

While we're at it let's actually add in the recursion call, otherwise we'd be
matching everything after our first method signature and silently throwing it
away.

```rust
// src/lib.rs

macro_rules! visit_members {
    (
        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;

        $( $rest:tt )*
    ) => {
        // TODO: do something with the signature we just matched

        visit_members! { $($rest)* }
    };
}
```

I have [`cargo watch`][cargo-watch] running on a background terminal to
automatically recompile whenever something changes, and immediately after
hitting save I started seeing lots of red...

```
    Finished dev [unoptimized + debuginfo] target(s) in 0.00s
   Compiling non-trivial-macros v0.1.0 (/home/michael/Documents/non-trivial-macros)
error: unexpected end of macro invocation
  --> src/lib.rs:11:9
   |
2  | macro_rules! visit_members {
   | -------------------------- when calling this macro
...
11 |         visit_members! { $($rest)* }
   |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
...
21 |         visit_members! { fn get_x(&self) -> u32; }
   |         ------------------------------------------ in this macro invocation
   |
   = note: this error originates in a macro (in Nightly builds, run with -Z macro-backtrace for more info)

...
```

The important bit is that *"unexpected end of macro invocation"* message. It's
saying the macro ran out of tokens when it was expecting to match something.

Just like with normal programming, when you do recursion you need to add a
base case so you can stop recursing. The error message is telling us that it
matched the function signature, then when trying to match the rest of the
input (of which there is none) it didn't have enough tokens.

The solution is easy enough, just add a base case which matches exactly nothing.

```rust
// src/lib.rs

macro_rules! visit_members {
    (
        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;

        $( $rest:tt )*
    ) => {
        visit_members! { $($rest)* }
    };
    () => {}
}
```

Now that's solved, let's add a test with two signatures and see what happens.

```rust
// src/lib.rs

#[test]
fn match_two_getters() {
    visit_members! {
        fn get_x(&self) -> u32;
        fn get_y(&self) -> u32;
    }
}
```

Looking back at the output from my terminal, it seems like it all just
works... Don't you love it when you write something based on theory and it
all works perfectly first time?

It doesn't happen often, so I like to cherish these moments 😉

## Callbacks

*The Little Book of Rust Macros* also includes a couple techniques for
generating code. Most notable among them for our purposes is the
[Callback][callback].

This lets us pass the name of a macro into a macro so it can be invoked later
with the results of our pattern matching.

Passing in the callback's name is easy enough. Just add it to the start of the
macro input.

```rust
// src/lib.rs

macro_rules! visit_members {
    (
        $callback:ident;

        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;

        $( $rest:tt )*
    ) => {
        visit_members! { $callback; $($rest)* }
    };
    ($callback:ident;) => {}
}
```

{{% notice note %}}
Make sure you update the base case now we're always passing a `$callback;` at
the start of recursive call.
{{% /notice %}}

At this point we'll need to update all our tests to start with the callback
name. I'm using the name `print`, which we'll actually declare in the next
step. The callback doesn't matter for now because it's never actually used.

```rust
// src/lib.rs

#[test]
fn visit_simple_getter_method() {
    visit_members! { print; fn get_x(&self) -> u32; }
}

#[test]
fn match_two_getters() {
    visit_members! {
        print;

        fn get_x(&self) -> u32;
        fn get_y(&self) -> u32;
    }
}
```

Now we can make the macro invoke our callback with the matched signature.

For now I just want to swallow the tokens and do nothing. If the code compiles,
we can be pretty sure we're invoking the callback correctly.

```rust
// src/lib.rs

macro_rules! visit_members {
    (
        $callback:ident;

        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;

        $( $rest:tt )*
    ) => {
        $callback!(
            $( #[$attr] )*
            fn $name(&self $(, $arg_name : $arg_ty )*) $(-> $ret)?
        );

        visit_members! { $callback; $($rest)* }
    };
    ($callback:ident;) => {};
}

macro_rules! my_callback {
    ( $($whatever:tt)* ) => {}
}
```

{{% notice tip %}}
If you ever get stuck and are wanting some sort of "print statement" to see what
a macro is doing, have a look at the `compile_error!()` macro.

By combining `compile_error!()` with `stringify!()` and `concat!()` you can
concatenate the stringified form of arbitrary tokens to create an error message
containing the tokens you've matched.

```rust
macro_rules! my_callback {
    ( $($tokens:tt)* ) => {
        compile_error!(
            concat!(
                $(
                    stringify!($tokens), " "
                ),*
            )
        );
    };
}
```

When used on our existing tests, we get errors like this:

```
error: fn get_x (& self) -> u32
  --> src/lib.rs:27:13
   |
27 | /             compile_error!(
28 | |                 concat!(
29 | |                     $(
30 | |                         stringify!($tokens), " "
31 | |                     ),*
32 | |                 )
33 | |             );
   |
...
39 |           visit_members! { echo; fn get_x(&self) -> u32; }
   |           ------------------------------------------------ in this macro invocation
   |
   = note: this error originates in a macro (in Nightly builds, run with -Z macro-backtrace for more info)

```

It's not particularly elegant, but this (ab)use of the `compile_error!()`
macro lets us see that `fn get_x (& self) -> u32` was passed to the callback.
{{% /notice %}}

## Generating Our Impl Blocks

Now we've got a way to invoke a macro on each method we can actually start
generating some code!

If you look back towards the beginning, we're trying to take something like
this...

```rust
fn get_x(&self) -> u32;
```

... and expand it to some code that dereferences `&self` twice (once to get
past `&self` and a second time to dereference the pointer that is `self`) then
invokes the method.

```rust
fn get_x(&self) -> u32 {
    (**self).get_x()
}
```

First off, I'm going to create a new macro to use as our callback. We know
ahead of time that we'll be passed a valid method signature, so we can steal the
matching code from `visit_members!()`.

```rust
// src/lib.rs

macro_rules! call_via_deref {
    (
        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?
    ) => { };
}
```

(note the lack of a trailing semicolon)

Now we can generate the method body.

```rust
// src/lib.rs

macro_rules! call_via_deref {
    (
        $( #[$attr:meta] )*
        fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?
    ) => {
        fn $name(&self $(, $arg_name : $arg_ty )*) $(-> $ret)? {
            (**self).$name( $($arg_name),* )
        }
    };
}
```

We can test this by using it in the same place it's intended for.

```rust
// src/lib.rs

#[test]
fn defer_impl_to_item_behind_pointer() {
    trait GetX {
        fn get_x(&self) -> u32;
    }

    impl GetX for u32 {
        fn get_x(&self) -> u32 { *self }
    }

    impl GetX for Box<u32> {
        call_via_deref!( fn get_x(&self) -> u32 );
    }

    fn assert_is_get_x<G: GetX>() {}

    assert_is_get_x::<u32>();
    assert_is_get_x::<Box<u32>>();
}
```

We're on the home stretch now. We just need to tie together our callback and
TT muncher to generate `GetX` impls for `Box<dyn GetX>`.

Here's the macro for working with boxed trait objects. All it really does is
wrap everything in an `impl Trait for Box<dyn Trait>` block then defer to
`visit_members!()` and `call_via_deref!()` for the hard work.

```rust
// src/lib.rs

macro_rules! impl_trait_for_boxed {
    (
        $( #[$attr:meta] )*
        $vis:vis trait $name:ident {
            $( $body:tt )*
        }
    ) => {
        impl<F: $name + ?Sized> $name for Box<F> {
            visit_members!( call_via_deref; $($body)* );
        }
    };
}
```

We can also test this by creating a trait, implementing it for one type, then
copy/pasting the trait definition into an `impl_trait_for_boxed!()` call and
making sure it generates the desired impls.

```rust
// src/lib.rs

#[test]
fn impl_trait_for_boxed() {
    trait Foo {
        fn get_x(&self) -> u32;
        fn execute(&self, expression: &str);
    }

    impl Foo for u32 {
        fn get_x(&self) -> u32 { unimplemented!() }

        fn execute(&self, _expression: &str) { unimplemented!() }
    }

    impl_trait_for_boxed! {
        trait Foo {
            fn get_x(&self) -> u32;
            fn execute(&self, expression: &str);
        }
    }

    fn assert_is_foo<F: Foo>() {}

    assert_is_foo::<u32>();
    assert_is_foo::<Box<u32>>();
    assert_is_foo::<Box<dyn Foo>>();
}
```

Once you've got your head around the `Box` version, you'll notice it's almost
identical to the macro for references.

```rust
// src/lib.rs

#[macro_export]
macro_rules! impl_trait_for_ref {
    (
        $( #[$attr:meta] )*
        $vis:vis trait $name:ident {
            $( $body:tt )*
        }
    ) => {
        impl<'f, F: $name + ?Sized> $name for &'f F {
            visit_members!( call_via_deref; $($body)* );
        }
    };
}

#[macro_export]
macro_rules! impl_trait_for_mut_ref {
    (
        $( #[$attr:meta] )*
        $vis:vis trait $name:ident {
            $( $body:tt )*
        }
    ) => {
        impl<'f, F: $name + ?Sized> $name for &'f mut F {
            visit_members!( call_via_deref; $($body)* );
        }
    };
}
```

From here the full `trait_with_dyn_impls!()` macro just falls out. We make sure
the trait gets declared, then pass it to `impl_trait_for_boxed!()` and friends
to generate the appropriate impls.

```rust
// src/lib.rs

#[macro_export]
macro_rules! trait_with_dyn_impls {
    (
        $( #[$attr:meta] )*
        $vis:vis trait $name:ident { $( $body:tt )* }
    ) => {
        // emit the trait declaration
        $( #[$attr] )*
        $vis trait $name { $( $body )* }

        // then implement it for Box and references
        impl_trait_for_ref! {
            $( #[$attr] )*
            $vis trait $name { $( $body )* }
        }
        impl_trait_for_boxed! {
            $( #[$attr] )*
            $vis trait $name { $( $body )* }
        }
    };
}
```

## Non-Identifier Identifiers

{{% notice warning %}}
TODO: Talk about handling `&self` and `&mut self`.
{{% /notice %}}

## Conclusions


[object-safety]: https://doc.rust-lang.org/book/ch17-02-trait-objects.html#object-safety-is-required-for-trait-objects
[replace-conditional]: https://refactoring.guru/replace-conditional-with-polymorphism
[tt]: https://danielkeep.github.io/tlborm/book/pat-incremental-tt-munchers.html
[cargo-watch]: https://crates.io/crates/cargo-watch
[callback]: https://danielkeep.github.io/tlborm/book/pat-callbacks.html
