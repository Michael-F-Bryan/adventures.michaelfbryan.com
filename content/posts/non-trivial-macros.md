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

[object-safety]: https://doc.rust-lang.org/book/ch17-02-trait-objects.html#object-safety-is-required-for-trait-objects
[replace-conditional]: https://refactoring.guru/replace-conditional-with-polymorphism
