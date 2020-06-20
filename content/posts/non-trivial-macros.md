---
title: "Writing Non-Trivial Macros in Rust"
date: "2020-06-21T01:15:00+08:00"
tags:
- Rust
---

Macros in Rust tend to have a reputation for being complex and magical, the
likes which only seasoned wizards like [`@dtolnay`][dt] can hope to
understand, let alone master.

Rust's declarative macros provide a mechanism for pattern matching on
arbitrary syntax to generate valid Rust code at compile time. I use them all
the time for simple search/replace style operations like generating tests
that have a lot of boilerplate, or straightforward trait implementations for
a large number of types.

This is copied directly from a DSL parser I wrote many moons ago.

```rust
pub trait AstNode {
    /// The location of this node in its source document.
    fn span(&self) -> ByteSpan;
}

macro_rules! impl_ast_node {
    ($($name:ty,)*) => {
        $(
            impl AstNode for $name {
                fn span(&self) -> ByteSpan { self.span }
            }
        )*
    };
}

// these types all have a `span` field.
impl_ast_node!(
    Literal,
    Assignment,
    Declaration,
    Identifier,
    BinaryExpression,
    IfStatement,
    ...
);
```

Unfortunately once you need to do more than these trivial macros, the
difficulty tends to go through the roof...

I recently encountered a situation at work where a non-trivial technical
problem could be solved by writing an equally non-trivial macro. There are a
number of tricks and techniques I employed along the way that helped keep the
code manageable and easy to implement, so I thought I'd help the next adventurer
by writing them down.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/non-trivial-macros
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## The Back-Story

In one of the big projects I work on, we made a design decisions you won't
see in most typical Rust codebases:

> Major systems must be isolated in their own crate with all requirements
> declared via traits, and **where possible these traits should be
> [object-safe][object-safety]**.

The reasoning for this is quite straightforward, the application may need to
reconfigure both its behaviour and hardware bindings at runtime, and allowing
the possibility of dynamic dispatch makes this a lot easier.

This is a soft-realtime motion controller which can control several related
families of machine using the same electronics and electrical components, but
with different mechanical configurations.

Now, imagine the controller is initially configured to run machine A with
particular assumptions about the world (which inputs things are attached to,
available optional components, etc.) and the user changes some settings to
make it behave like machine B with its own assumptions about the world.

You have a couple options for how to implement this:

1. Load the machine configuration on startup and jump to the corresponding
   code... This requires a restart for any settings changes to take effect
2. Use enums to encapsulate the different IO layouts or business logic...
   Congratulations, your code now has 10x more `match` statements
3. Take an object-oriented approach, replacing the conditionals from option 2
   [with polymorphism][replace-conditional] (i.e. dynamic dispatch)... Adds
   constraints on the behaviour you can expect from dependencies, but reduces
   cognitive load and lets you switch between things at runtime by pointing at
   a different object

The last option looked like the least-bad of the 3, but no doubt you'll find
out if it doesn't work for us... Just look out for the blog post exploring
different architectures for complicated systems 😛

Making allowances for dynamic dispatch where possible adds its own set of
interesting challenge, though.

Imagine you're programming the flashing lights on an operator console and come
up with something like this:

```rust
/// Port A of the on-board General Purpose IOs.
struct GPIOA { ... }

fn flash_periodically(gpio: &mut GPIOA, pin: usize, interval: Duration) {
    let mut current_state = false;

    loop {
        gpio.set_state(pin, current_state);
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

{{% notice tip %}}
This `assert_is_digital_input()` function is a nice little trick you can use
to make sure something implements a particular trait. By using
[turbofish][fish] we can specify *exactly* which type we're trying to check,
avoiding things like auto-defer and coersion.

You can find more gems like this in [the `static_assertions` crate][s],

[fish]: https://turbo.fish/
[s]: https://docs.rs/static_assertions
{{% /notice %}}

The key bits to look out for in thiserror message:

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
generate the necessary impl blocks.

This *could* be implemented using procedural macros, but they can have a
negative impact on compile times and I'd like an excuse to play around with
Rust's declarative macros.

## Getting Started

Now you have a better understanding of the problem we're trying to solve, the
end goal I have in mind is being able to write something like this...

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
machinery from the compiler itself. For example, when you write `$value:expr`
in a macro, that asks the compiler to try and parse some tokens as an
expression, and assign the AST node to `$value` on success.

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

Testing this sort of thing is really simple. If the code compiles, it works 👍

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
macro. Now we're able to match the method signatures you're likely to see in
object-safe traits we can start building on this foundation.

## Incremental TT Munching

One of the most powerful tools in your Rust macro arsenal is the
[Incremental TT Muncher][tt]. This is perfect for when you have a stream of
input and want to apply different logic based on what each item looks like.

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

(note the `\$( $rest:tt )*`)

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
works

Don't you love it when you write something based on theory and it all works
perfectly first time? It doesn't happen often, so I like to cherish these
moments 🎉

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
name. I'm using the name `print`, but the callback doesn't matter for now
because it's not used.

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

To begin with, I just want to swallow the tokens and do nothing. If the code
compiles, we can be pretty sure we're invoking the callback correctly.

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

When passing `my_callback` to the `match_two_getters` test, we get a compile
error like this:

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

        impl_trait_for_ref! {
            $( #[$attr] )*
            $vis trait $name { $( $body )* }
        }
        impl_trait_for_mut_ref! {
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

Do you remember how we deferred dealing with traits that have `&mut self`
methods, claiming there are a couple quirks that make handling `&self` or
`&mut self` awkward?

Now that you've got a couple more tools in your `macro_rules` toolbox, we're
better positioned to talk about these quirks.

So, how do you write a macro that matches both `&self` and `&mut self` and pass
that to a callback?

`&self` looks like a valid expression as far as the language grammar is
concerned, so we could define a macro like this:

```rust
macro_rules! match_self {
    ($callback:ident, fn $name:ident($self:expr)) => {
        $callback!(fn $name($self));
    }
}
```

Then our `$callback` is a macro that attaches a method to some type, `Foo`.

```rust
macro_rules! callback {
    (fn $name:ident($self:expr)) => {
        impl Foo {
            fn $name($self) {}
        }
    };
}

struct Foo;
```

And in theory we should be able to use it like this, right?

```rust
match_self!(callback, fn foo(&self));
```

However `rustc` doesn't agree. Instead, we get the following... less than
optimal... compile error.

```rust
error: expected one of `...`, `..=`, `..`, `:`, or `|`, found `)`
   --> src/lib.rs:215:35
    |
206 | /         macro_rules! match_self {
207 | |             ($callback:ident, fn $name:ident($self:expr)) => {
208 | |                 $callback!(fn $name($self));
    | |                 ---------------------------- in this macro invocation
209 | |             }
210 | |         }
    | |_________- in this expansion of `match_self!`
211 |
212 | /         macro_rules! callback {
213 | |             (fn $name:ident($self:expr)) => {
214 | |                 impl Foo {
215 | |                     fn $name($self) {}
    | |                                   ^
216 | |                 }
217 | |             };
218 | |         }
    | |_________- in this expansion of `callback!`
...
222 |           match_self!(callback, fn foo(&self));
    |           ------------------------------------- in this macro invocation
```

It looks like the callback is expecting some sort of pattern (e.g.
`self ..= other`) when it tries to use `$self` as the method's `self` parameter.

So what if we try matching on `$self:pat` instead of `$self:expr`?

```diff
 macro_rules! match_self {
-    ($callback:ident, fn $name:ident($self:expr)) => {
+    ($callback:ident, fn $name:ident($self:pat)) => {
         $callback!(fn $name($self));
     }
 }

 macro_rules! callback {
-    (fn $name:ident($self:expr)) => {
+    (fn $name:ident($self:pat)) => {
         impl Foo {
             fn $name($self) {}
         }
     };
 }
```

We get the same error, except the list of expected tokens has shortened a bit.

```text
error: expected one of `:` or `|`, found `)`
   --> src/lib.rs:215:35
    |
206 | /         macro_rules! match_self {
207 | |             ($callback:ident, fn $name:ident($self:pat)) => {
208 | |                 $callback!(fn $name($self));
    | |                 ---------------------------- in this macro invocation
209 | |             }
210 | |         }
    | |_________- in this expansion of `match_self!`
211 |
212 | /         macro_rules! callback {
213 | |             (fn $name:ident($self:pat)) => {
214 | |                 impl Foo {
215 | |                     fn $name($self) {}
    | |                                   ^
216 | |                 }
217 | |             };
218 | |         }
    | |_________- in this expansion of `callback!`
...
222 |           match_self!(callback, fn foo(&self));
    |           ------------------------------------- in this macro invocation
```

Another option is to combine the `$(...)?` syntax for matching something zero or
one times with the fact that `self` is a valid Rust identifier.

```diff
 macro_rules! match_self {
-    ($callback:ident, fn $name:ident($self:pat)) => {
+    ($callback:ident, fn $name:ident(& $(mut)? $self:ident)) => {
         $callback!(fn $name(& $self));
     }
 }

 macro_rules! callback {
-    (fn $name:ident($self:pat)) => {
+    (fn $name:ident(& $(mut)? $self:ident)) => {
         impl Foo {
             fn $name($self) {}
         }
     };
 }
```

Our `match_self!(callback, fn foo(&self))` example even compiles and will
define a `foo` method on `Foo`. However, if you look carefully you'll see the
new `foo()` method silently drops the leading `&` or `&mut` and takes `self`
by value.

You can verify this by trying to store `Foo::foo` in a variable expecting
`fn(&Foo)`.

```rust
let _: fn(&Foo) = Foo::foo;
```

The compiler throws up a *"mismatched types"* compile error upon seeing this.

```text
error[E0308]: mismatched types
   --> src/lib.rs:224:27
    |
224 |         let _: fn(&Foo) = Foo::foo;
    |                --------   ^^^^^^^^
    |                |
    |                expected due to this
    |
    = note: expected fn pointer `for<'r> fn(&'r tests::match_on_self::Foo)`
                  found fn item `fn(tests::match_on_self::Foo) {tests::match_on_self::Foo::foo}`

error: aborting due to previous error
```

Even if we *did* write our callback to not drop the leading `&`, we'd run
into issues trying to pass the optional `mut` through to the callback.
Because we can't store `mut` in a macro variable (you can't bind to literal
tokens and using something like `$mut:ident` would match the `self` token
when `mut` isn't present) we don't really have a way to refer to it or pass
the token around any more.

{{% notice tip %}}
[Non-Identifier Identifiers][id] from *The Little Book of Rust Macros*
explains in a lot more detail what we're seeing here, so I'd recommend
checking out that page if you want to know more.

[id]: https://danielkeep.github.io/tlborm/book/mbe-min-non-identifier-identifiers.html
{{% /notice %}}

After banging my head against a wall for half an hour or so I gave up on
trying to match both `&self` and `&mut self` methods in a single pattern and
decided to take advantage of another tool that I have at my disposal... My
editor's ability to copy and paste 🙃

My solution to making `visit_members` and its `callback` handle both `&self`
and `&mut self` is to just copy the entire pattern and make the second version
handle the `mut` token.

That way, when the TT muncher tries to match the next function signature
it'll be able to take one branch for `&self` methods and another for `&mut
self`. The callback will also need to use the same trick because it needs to
somehow emit `&self` or `&mut self` as the receiver for each generated
method.

```diff
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
+    (
+        $callback:ident;

+        $( #[$attr:meta] )*
+        fn $name:ident(&mut self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?;

+        $( $rest:tt )*
+    ) => {
+        $callback!(
+            $( #[$attr] )*
+            fn $name(&mut self $(, $arg_name : $arg_ty )*) $(-> $ret)?
+        );

+        visit_members! { $callback; $($rest)* }
+    };
     ($callback:ident;) => {};
 }

 macro_rules! call_via_deref {
     (
         $( #[$attr:meta] )*
         fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?
     ) => {
         fn $name(&self $(, $arg_name : $arg_ty )*) $(-> $ret)? {
             (**self).$name( $($arg_name),* )
         }
     };
+    (
+        $( #[$attr:meta] )*
+        fn $name:ident(&mut self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?
+    ) => {
+        fn $name(&mut self $(, $arg_name : $arg_ty )*) $(-> $ret)? {
+            (**self).$name( $($arg_name),* )
+        }
+    };
 }
```

Amongst all that copy-pasta, you *might* even be able to spot the three
letter change that was made to the second copy (`mut`).

{{% notice info %}}
If you know of an easy way to match both `&self` and `&mut self` methods,
*please* let me know!

The solution I've proposed here (i.e. copy/paste) far from elegant and you
can already tell that someone will be cursing your name 6 months from now
when they need to come in and make a minor change.
{{% /notice %}}

As ugly as it is... our tests show that it works.

```rust
#[test]
fn handle_mutable_and_immutable_self() {
    trait Foo {
        fn get_x(&self) -> u32;
        fn execute(&mut self, expression: &str);
    }

    impl_trait_for_boxed! {
        trait Foo {
            fn get_x(&self) -> u32;
            fn execute(&mut self, expression: &str);
        }
    }
}
```

## Deciding Which Impl Blocks to Generate

Now we're able to handle both mutable and immutable methods we run into an
interesting problem.

Let's create a variant of the `full_implementation` test which has a `&mut self`
method.

```rust
#[test]
fn full_implementation_with_mut_methods() {
    trait_with_dyn_impls! {
        trait Foo {
            fn get_x(&self) -> u32;
            fn execute(&mut self, expression: &str);
        }
    }

    fn assert_is_foo<F: Foo>() {}

    assert_is_foo::<&dyn Foo>();
    assert_is_foo::<Box<dyn Foo>>();
}
```

It's identical to `full_implementation`, except `execute()` takes `&mut self`...
and it fails to compile:

```text
error[E0596]: cannot borrow `**self` as mutable, as it is behind a `&` reference
   --> src/lib.rs:51:13
    |
2   |  / macro_rules! visit_members {
3   |  |     (
4   |  |         $callback:ident;
5   |  |
...    |
16  |  |         visit_members! { $callback; $($rest)* }
    |  |         --------------------------------------- in this macro invocation (#4)
...    |
26  | /|         $callback!(
27  | ||             $( #[$attr] )*
28  | ||             fn $name(&mut self $(, $arg_name : $arg_ty )*) $(-> $ret)?
29  | ||         );
    | ||__________- in this macro invocation (#5)
...    |
33  |  |     ($callback:ident;) => {};
34  |  | }
    |  | -
    |  | |
    |  |_in this expansion of `visit_members!` (#3)
    |    in this expansion of `visit_members!` (#4)
...
37  | /  macro_rules! call_via_deref {
38  | |      (
39  | |          $( #[$attr:meta] )*
40  | |          fn $name:ident(&self $(, $arg_name:ident : $arg_ty:ty )*) $(-> $ret:ty)?
...   |
51  | |              (**self).$name( $($arg_name),* )
    | |              ^^^^^^^^
52  | |          }
53  | |      };
54  | |  }
    | |__- in this expansion of `call_via_deref!` (#5)
```

It's a little hard to see, but if you look at the error text we get a
familiar message: *"cannot borrow `**self` as mutable, as it is behind a `&`
reference"*.

This isn't a macro problem, the borrow checker is complaining about one of our
generated methods!

Other than the error text, the rest of this compile error is kinda useless.
There's a problem with our generated code, and because generated code doesn't
actually exist in the source file (i.e. `src/lib.rs`), `rustc` can't point at
a specific line to tell the programmer where the problem is.

The [`cargo expand`][cargo-expand] tool is designed for just these occasions.
Its entire purpose is to ask the compiler to expand all macros and display the
expanded source code to the user.

Here's what `full_implementation_with_mut_methods` expands to:

```rust
fn full_implementation_with_mut_methods() {
    trait Foo {
        fn get_x(&self) -> u32;
        fn execute(&mut self, expression: &str);
    }
    impl<'f, F: Foo + ?Sized> Foo for &'f F {
        fn get_x(&self) -> u32 {
            (**self).get_x()
        }
        fn execute(&mut self, expression: &str) {
            (**self).execute(expression)
        }
    }
    impl<'f, F: Foo + ?Sized> Foo for &'f mut F {
        fn get_x(&self) -> u32 {
            (**self).get_x()
        }
        fn execute(&mut self, expression: &str) {
            (**self).execute(expression)
        }
    }
    impl<F: Foo + ?Sized> Foo for Box<F> {
        fn get_x(&self) -> u32 {
            (**self).get_x()
        }
        fn execute(&mut self, expression: &str) {
            (**self).execute(expression)
        }
    }
    fn assert_is_foo<F: Foo>() {}
    assert_is_foo::<&dyn Foo>();
    assert_is_foo::<Box<dyn Foo>>();
}
```

The output is a little dense, but look at the `&'f F` impl. We've got an
immutable reference to some `F: Foo` and are invoking a method which takes
`&mut self`.

This is a pretty trivial borrowing error and indicates there's a bug in our
`trait_with_dyn_impls!()` macro. We shouldn't be emitting the `&'f F` impl if
*any* trait method takes `&mut self`... but how do you make these sorts of
decisions, its not like `macro_rules` macros let you use `if`-statements!

The answer has been under our noses this entire time. Pattern matching is just
a fancy chain of `if-else` statements, and we can use callbacks to invoke
caller-defined behaviour depending on which branch matches, and a TT muncher to
scan through the input tokens one at a time until we find `&mut self`.

If you are familiar with functional programming, this is sometimes called
[*Continuation Passing Style*][cps] (CPS).

Here's my attempt.

```rust
// src/lib.rs

/// Scans through a stream of tokens looking for `&mut self`. If nothing is
/// found a callback is invoked.
macro_rules! search_for_mut_self {
    // if we see `&mut self`, stop and don't invoke the callback
    ($callback:ident!($($callback_args:tt)*); &mut self $($rest:tt)*) => { };
    ($callback:ident!($($callback_args:tt)*); (&mut self $($other_args:tt)*) $($rest:tt)*) => { };

    // haven't found it yet, drop the first item and keep searching
    ($callback:ident!($($callback_args:tt)*); $_head:tt $($tokens:tt)*) => {
        search_for_mut_self!($callback!( $($callback_args)* ); $($tokens)*);

    };
    // we completed without hitting `&mut self`, invoke the callback and exit
    ($callback:ident!($($callback_args:tt)*);) => {
        $callback!( $($callback_args)* )
    }
}
```

I also wrote up a couple tests.

```rust
// src/lib.rs

#[test]
fn dont_invoke_the_callback_when_mut_self_found() {
    search_for_mut_self! {
        compile_error!("This callback shouldn't have been invoked");

        &mut self asdf
    }
}

#[test]
fn handle_mut_self_inside_parens() {
    search_for_mut_self! {
        compile_error!("This callback shouldn't have been invoked");

        fn foo(&mut self);
    }
}

#[test]
fn invoke_the_callback_if_search_for_mut_self_found() {
    macro_rules! declare_struct {
        ($name:ident) => {
            struct $name;
        };
    }

    search_for_mut_self! {
        declare_struct!(Foo);

        blah blah ... blah
    }

    // we should have declared Foo as a unit struct
    let _: Foo;
}
```

This gives us what we need to conditionally call `impl_trait_for_ref!()`. By
letting the caller provide arguments for the callback, we can copy the old
`impl_trait_for_ref!()` invocation across verbatim.

```diff
 macro_rules! trait_with_dyn_impls {
     (
         $( #[$attr:meta] )*
         $vis:vis trait $name:ident { $( $body:tt )* }
     ) => {
         // emit the trait declaration
         $( #[$attr] )*
         $vis trait $name { $( $body )* }

-        impl_trait_for_ref! {
-            $( #[$attr] )*
-            $vis trait $name { $( $body )* }
-        }
         impl_trait_for_mut_ref! {
             $( #[$attr] )*
             $vis trait $name { $( $body )* }
         }
         impl_trait_for_boxed! {
             $( #[$attr] )*
             $vis trait $name { $( $body )* }
         }

+        // we can only implement the trait for `&T` if there are NO `&mut self`
+        // methods
+        search_for_mut_self! {
+            impl_trait_for_ref!( $( #[$attr] )* $vis trait $name { $( $body )* } );

+            $( $body )*
+        }
+    };
 }
```

## Conclusions

It's been a long journey but this crate now lets us do everything I wanted so
I think we can finally call it done 🙂

Some tips:

- Tests are great for iterating and providing examples later on
- Start as simple as possible and take tiny steps
- Make an effort to keep things simple and not fit all the logic into a single
  macro
- Sometimes you'll need to think outside the box or use concepts from different
  paradigms/languages (e.g. CPS)

As a bonus, unlike a lot of complex macros I've written in the past, I have a
fairly high degree of confidence in its implementation because of the
comprehensive test suite we built along the way. It really makes a difference
in demystifying how the macro works.

[object-safety]: https://doc.rust-lang.org/book/ch17-02-trait-objects.html#object-safety-is-required-for-trait-objects
[replace-conditional]: https://refactoring.guru/replace-conditional-with-polymorphism
[tt]: https://danielkeep.github.io/tlborm/book/pat-incremental-tt-munchers.html
[cargo-watch]: https://crates.io/crates/cargo-watch
[callback]: https://danielkeep.github.io/tlborm/book/pat-callbacks.html
[dt]: https://github.com/dtolnay
[cargo-expand]: https://crates.io/crates/cargo-expand
[cps]: https://en.wikipedia.org/wiki/Continuation-passing_style
