---
title: "A Pragmatic Approach To Global State"
date: "2020-02-11T23:00:38+08:00"
draft: true
tags:
- rust
- architecture
---

One of the first things I learned when programming professionally is that
*global variables are bad*. We all take it for granted that it's bad practice
to write code that relies heavily on global state (especially global mutable
state) but the other day I was working with a 3rd party native library, and
it reminded *why* these best practices come about.

There are a couple factors which made this particular library's use of global
mutable state rather ugly to work with,

- Thread safety - mutating something from two concurrent threads of execution
  without proper synchronisation is a [data race][data-race], a common form of
  *Undefined Behaviour*. This means the library can only ever be used from one
  place at a time.
- Brittle code - Relying on global state often means the code expects to be
  run in a very specific order. Failing to invoke functions in the correct
  order can lead to memory issues (e.g. leaks or double-frees) and
  accidentally corrupting the library's state
- Poor testability - when code is mutating global variables there's no way to
  inject mocks (e.g. to `assert!()` specific conditions) or make sure
  individual chunks of functionality work. You are often reduced to writing
  one or two high-level integration tests which execute the "happy path", and
  when an error occurs you have no way of knowing how to fix it

{{% notice info %}}
To be clear, when I refer to *"global state"* I am referring to variables in
a program (typically declared with the keyword `static` in languages like C#,
Java, and Rust) which lives for the lifetime of the program, only ever has
one instance, and all uses of the variable are hard-coded to use that
instance.

These variables don't necessarily need to be publicly accessible. All of
these problems occur when using [static local variables][slv] inside a
function or class. The core problems related to having static lifetime and
code directly referencing the variable are still there.

[slv]: https://en.wikipedia.org/wiki/Local_variable#Static_local_variables
{{% /notice %}}

For my use case it's not really viable to use a different library because the
alternatives don't necessarily have the features we need. We also can't
rewrite the code to not use global mutable state because it's closed-source,
and even then would require tens of man-years of effort.

This necessitates a more pragmatic solution. We needed to find a way to use
this 3rd party library without it polluting the rest of the application too
much.

I'll be implementing this in Rust primarily because it's quite good at
enforcing guarantees via the type system, but the general ideas aren't really
language-specific.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/stateful-native-library
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Getting Acquainted

It would be a bit overwhelming to show you the full code, so I've prepared a
rough example we can play around with.

Another important point to emphasize is the 3rd party library which initially
inspired this experiment is native code (I think it's written in C++?). The
reason this is important is because it uses pointers and a bug doesn't just
mean an exception gets thrown, we could segfault and tear down the entire
process. My decision to write use it from Rust also means we'll need to write
some `unsafe` code when crossing the language boundary.

It's actually pretty painful to write code in Rust which relies on global
mutable state (it's almost like the code is trying to tell us something 🤔)
so our example will be written in C. Plus, in the real world all we have
access to is a compiled DLL and corresponding header file, so it seems
fitting for our Rust code to only see the library as a black box.

Without further ado, here's a header file:

```c
// native/stateful.h

#if !defined(STATEFUL_H)
#define STATEFUL_H

#include <stdbool.h>

// The various possible return codes.
enum
{
    // The function completed successfully.
    RESULT_OK,
    // A function was called out of order.
    RESULT_BAD_STATE,
    // One of the provided arguments is invalid.
    RESULT_INVALID_ARGUMENT,
};

// Initialize the library. MUST be run before any other function.
int stateful_open();

// Clean up any state associated with this library.
int stateful_close();

// Begin setting parameters. MUST be run before any parameters can be set.
int stateful_start_setting_parameters();
int stateful_set_bool_var(const char *name, bool value);
int stateful_set_int_var(const char *name, int value);
// Finish setting parameters.
int stateful_end_setting_parameters();

// Start adding input items.
int stateful_start_adding_items();
// Add a single item as an input.
int stateful_add_item(const char *name, int value);
// Start adding a group of items.
int stateful_start_adding_group(const char *name);
// Add an item to the current group. stateful_start_adding_group MUST be called
// beforehand.
int stateful_add_group_item(const char *name, int value);
// Finish adding items to the current group, adding the overall group to the
// list of inputs.
int stateful_end_adding_group();
// Finish setting up the list of inputs.
int stateful_end_adding_items();

// A callback used to notify the caller when progress is made.
typedef int (*progress_cb)(int percent);
// A callback used to let the user retrieve results.
typedef int (*result_cb)(int number_of_results);

// Run the code.
int stateful_execute(progress_cb progress, result_cb result);

// Try to get the number of outputs in the result.
int stateful_get_num_outputs(int *value);
// Tries to retrieve a particular output.
int stateful_get_output_by_index(int index, int *value);

#endif // STATEFUL_H
```

{{% notice note %}}
The difficulty with trying to explain complex architecture is to find the
sweet spot between simplifying so much that people miss the point or the
example feels contrived, and providing so much detail that the reader loses
track of what's going on amongst the various moving parts.

Hopefully I'm somewhere near that sweet spot.
{{% /notice %}}

There's quite a lot going on here, so let's unpack it a bit.

Fortunately, this library does a pretty decent job of handling errors and most
of the time functions will give you some sort of return code.

```c
// The various possible return codes.
enum
{
    // The function completed successfully.
    RESULT_OK,
    // A function was called out of order.
    RESULT_BAD_STATE,
    // One of the provided arguments is invalid.
    RESULT_INVALID_ARGUMENT,
};
```

In reality there are going to be a lot more error cases, but you get the gist.

The library needs to initialize some global state before first use and do
cleanup at the end, so our `stateful` library has `open()` and `close()`
functions.

```c
// Initialize the library. MUST be run before any other function.
int stateful_open();

// Clean up any state associated with this library.
int stateful_close();
```

(I don't know about you, but usually when I this sort of pattern the first
thing I think of is RAII)

After initializing the library we need to set some global parameters. These are
various knobs and levers that are used to alter how the input is processed.

```c
// Begin setting parameters. MUST be run before any parameters can be set.
int stateful_start_setting_parameters();
int stateful_set_bool_var(const char *name, bool value);
int stateful_set_int_var(const char *name, int value);
// Finish setting parameters.
int stateful_end_setting_parameters();
```

You can see that we need to explicitly start and stop setting parameters. The
functions themselves take no arguments, which is a big give-away that the code
mutates global variables under the hood.

Next we've got functions for setting up the input.

```c
// Start adding input items.
int stateful_start_adding_items();
// Add a single item as an input.
int stateful_add_item(const char *name, int value);
// Start adding a group of items.
int stateful_start_adding_group(const char *name);
// Add an item to the current group. stateful_start_adding_group MUST be called
// beforehand.
int stateful_add_group_item(const char *name, int value);
// Finish adding items to the current group, adding the overall group to the
// list of inputs.
int stateful_end_adding_group();
// Finish setting up the list of inputs.
int stateful_end_adding_items();
```

If you squint, you'll see that the input is a list of individual named items
or groups of items. The `Input` that we're building procedurally might look
something like this (if written in Rust):

```rust
enum Item {
  Single(i32),
  Group(HashMap<String, i32>),
}

type Input = HashMap<String, Item>;
```

Now we've set the algorithm's parameters and created our input, we can execute
the code.

```c
// A callback used to notify the caller when progress is made.
typedef int (*progress_cb)(int percent);
// A callback used to let the user retrieve results.
typedef int (*result_cb)(int number_of_results);

// Run the code.
int stateful_execute(progress_cb progress, result_cb result);
```

You'll notice this uses callback functions to notify the caller of progress and
when the results are ready. This wouldn't normally be a problem, except the
code doesn't let us provide some sort of `void *` pointer to user-provided data.
That means the only way our callbacks will be able to pass information to the
caller is by itself using global variables.

Finally, we get a couple functions for inspecting the output.

```c
// Try to get the number of outputs in the result.
int stateful_get_num_outputs(int *value);
// Tries to retrieve a particular output.
int stateful_get_output_by_index(int index, int *value);
```

Something to keep in mind is they can only be called from inside our
`result_cb` callback. Other than that, the functions are pretty ordinary.

{{% notice info %}}
I'm going to be deliberately vague about what `stateful_execute()` actually
does. For our purposes the computation isn't actually relevant, we're mainly
concerned about *how* you can make use of such a "stateful" library while
maintaining nice things like,

- thread-safety
- memory-safety
- using a strong type system to statically ensure it is impossible to do
  things out of order

If it helps, think of `stateful_execute()` as something like this:

```rust
fn stateful_execute(
    parameters: &HashMap<String, Value>,
    items: Vec<Input>,
) -> Vec<c_int> {
    // magic
}
```
{{% /notice %}}

## Our High-Level Approach

We have two main goals for this exercise,

- Create a safe wrapper which lets us use this library while maintaining memory
  and thread-safety
- Use the type system to *make illegal states unrepresentable*

The first goal can be fulfilled fairly easily, because this library can only be
used by one bit of code at a time (`static` variables aren't thread-safe) we
can make a type which represents a "handle" to the library.

We can then write our code in such a way that calling a function from our
`stateful` library *needs* you to have a valid handle.

```rust
// src/lib.rs

use std::marker::PhantomData;

/// A handle to the `stateful` library.
pub struct Library {
    _not_send: PhantomData<*const ()>,
}
```

Something to note is the use of `PhantomData<*const ()>` here. This makes sure
`Library` is `!Send` and `!Sync` (i.e. it can't be used from another thread).

We can double-check that `Library` can't be used from other threads by adding
the [`static_assertions` crate][static-assert] as a dev-dependency...

```console
$ cargo add --dev static_assertions
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding static_assertions v1.1.0 to dev-dependencies
```

... And then writing a new test.

```rust
// src/lib.rs

#[cfg(test)]
mod tests {
    use super::*;

    static_assertions::assert_not_impl_any!(Library: Send, Sync);
}
```

If this test failed we would get a build failure from `cargo test`.

```diff
 /// A handle to the `stateful` library.
 pub struct Library {
     _not_send: PhantomData<*const ()>,
 }

+unsafe impl Send for Library {}
```

The error message leaves a lot to be desired, but this is what you'd see if
`Library` were `Send`.

```console
$ cargo test
   Compiling stateful-native-library v0.1.0 (/home/michael/Documents/stateful-native-library)
error[E0282]: type annotations needed for `fn() {<Library as tests::_::{{closure}}#0::AmbiguousIfImpl<_>>::some_item}`
  --> src/lib.rs:14:5
   |
14 |     static_assertions::assert_not_impl_any!(Library: Send, Sync);
   |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
   |     |
   |     consider giving this pattern the explicit type `fn() {<Library as tests::_::{{closure}}#0::AmbiguousIfImpl<_>>::some_item}`, with the type parameters specified
   |     cannot infer type
   |
   = note: this error originates in a macro outside of the current crate (in Nightly builds, run with -Z external-macro-backtrace for more info)

error: aborting due to previous error
```

Now we have a thread-safe `Library` type, we also need to make sure it's not
possible to create more than one `Library` at a time. This can be done easily
enough using a flag (`AtomicBool`) which is set to `true` when `Library` is
created and `false` when it is destroyed.

```rust
// src/lib.rs

use sync::atomic::{AtomicBool, Ordering};

static LIBRARY_IN_USE: AtomicBool = AtomicBool::new(false);

impl Library {
    pub fn new() -> Result<Library, AlreadyInUse> {
        if LIBRARY_IN_USE.compare_and_swap(false, true, Ordering::SeqCst)
            == false
        {
            Ok(Library {
                _not_send: PhantomData,
            })
        } else {
            Err(AlreadyInUse)
        }
    }
}

impl Drop for Library {
    fn drop(&mut self) { LIBRARY_IN_USE.store(false, Ordering::SeqCst); }
}

/// An error indicating the `Library` can't be accessed again until the existing
/// session is over.
#[derive(Debug, Copy, Clone, PartialEq, thiserror::Error)]
#[error("The library is already in use")]
pub struct AlreadyInUse;
```

Yes, I know the irony in using a `static` variable to workaround another
library's zealous use of `static` variables. Sometimes you've got to break a
couple eggs to make an omelette 🤷‍

To make sure we've implemented this correctly, let's write a test which
deliberately tries to create multiple `Library` handles at the same time.

```rust
// lib/src.rs

#[cfg(test)]
mod tests {
    use super::*;

    ...

    #[test]
    fn cant_create_multiple_library_handles_at_the_same_time() {
        let first_library = Library::new().unwrap();

        // make sure the flag is set
        assert!(LIBRARY_IN_USE.load(Ordering::SeqCst));

        // then try to create another handle
        assert!(Library::new().is_err());

        // explicitly drop the first library so we know it clears the flag
        drop(first_library);

        assert!(!LIBRARY_IN_USE.load(Ordering::SeqCst));

        // now the old handle is destroyed, we can create another
        let _another = Library::new().unwrap();
    }
}
```

Next, to ensure functions aren't called out of order we can create some sort of
type-level state machine. This idea was originally taken from [a thread on the
Rust users forum][u.rl.o]. You'll notice the approach we're taking is uncannily
similar to the solution proposed by [@Yandros][yandros],

> I would wrap the library using a type-level state machine to make misusage
> simply not compile; If necessary, you can even use the singleton pattern to
> enforce no concurrency problems (which would be the only part checked at
> runtime).

When setting parameters it should be impossible to use any non-parameter-setting
functionality.

This is where lifetimes really show their power, using a `&mut Library` reference
the compiler can statically ensure some `SettingParameters` type (which we're
about to create) has unique access to our `Library`.

```rust
// src/lib.rs

impl Library {
    ...

    pub fn set_parameters(&mut self) -> SettingParameters<'_> {
        SettingParameters { _library: self }
    }
}

pub struct SettingParameters<'lib> {
    _library: &'lib mut Library,
}

impl<'lib> SettingParameters<'lib> {
    pub fn boolean(&mut self, _name: &str, _value: bool) -> &mut Self {
        unimplemented!()
    }

    pub fn integer(&mut self, _name: &str, _value: i32) -> &mut Self {
        unimplemented!()
    }
}
```

You'll notice I'm deliberately leaving the body for `boolean()` and
`integer()` as `unimplemented!()`. We're just setting up the infrastructure
for this "type-level state machine" for now and will execute the actual FFI
calls in a bit.

Once we've set the various parameters we need to start constructing our inputs.
This can be done using some sort of `RecipeBuilder` which leverages the
`&mut Library` trick from `SettingParameters`.

```rust
// src/lib.rs

impl Library {
    ...

    pub fn create_recipe(&mut self) -> RecipeBuilder<'_> {
        RecipeBuilder { _library: self }
    }
}

pub struct RecipeBuilder<'lib> {
    _library: &'lib mut Library,
}

impl<'lib> RecipeBuilder<'lib> {
    pub fn add_item(&mut self, _name: &str, _value: i32) -> &mut Self {
        unimplemented!()
    }
}
```

Now we've got a problem, how can you add a group of items to the "recipe" (the
term I'm using for our set of inputs)? We need to make sure it's not possible
to call `RecipeBuilder::add_item()` while in the middle of constructing a group.

If you think for a moment, that's the same problem we had with `Library` when
we wanted to make sure you can *either* be creating a recipe using the
`RecipeBuilder`, or setting parameters with `SettingParameters`. We just need to
add another layer of `&mut`s!

```rust
// src/lib.rs

impl<'lib> RecipeBuilder<'lib> {
    ...

    pub fn add_group<'r>(&'r mut self, _name: &str) -> GroupBuilder<'r, 'lib> {
        GroupBuilder {
            _recipe_builder: self,
        }
    }
}

pub struct GroupBuilder<'r, 'lib> {
    _recipe_builder: &'r mut RecipeBuilder<'lib>,
}

impl<'r, 'lib> GroupBuilder<'r, 'lib> {
    pub fn add_item(&mut self, _name: &str, _value: i32) -> &mut Self { unimplemented!() }

    pub fn finish(self) -> &'r mut RecipeBuilder<'lib> { self._recipe_builder }
}
```

Next, I'm going to continue with this builder pattern theme and give
`RecipeBuilder` a `build()` method which returns a `Recipe`. A `Recipe` will
just be an empty type indicating we've fully assembled the inputs. Signifying
the transition to the *"inputs assembled and ready for use"* state.

```rust
// src/lib.rs

impl<'lib> RecipeBuilder<'lib> {
    ...

    pub fn build(self) -> Recipe<'lib> {
        Recipe {
            _library: self._library,
        }
    }
}

pub struct Recipe<'lib> {
    _library: &'lib mut Library,
}
```

If you've been keeping up, we're now at the point where everything is
initialized and we're ready to consume this `Recipe` and get the output.

It seems odd for a `Recipe` to know how to execute itself, so we'll create
some sort of top-level `execute()` function instead.

```rust
// src/lib.rs

pub fn execute<P>(_recipe: Recipe<'_>, _progress: P) -> Result<Output, Error>
where
    P: FnMut(i32),
{
    unimplemented!()
}

pub enum Error {}

pub struct Output {
    pub items: Vec<i32>,
}
```

To make sure the code we've written prevents invalid uses of `Library`, let's
use Rustdoc's `compile_fail` feature to document our functions with examples
we expect `rustc` to reject.

```rust
// src/lib.rs

impl Library {
    ...

    /// Start creating the inputs for [`execute()`].
    ///
    /// The [`RecipeBuilder`] uses lifetimes to make sure you can't do anything
    /// else while creating a [`Recipe`].
    ///
    /// ```rust,compile_fail
    /// # use stateful_native_library::Library;
    /// let mut library = Library::new().unwrap();
    ///
    /// // start creating the recipe
    /// let mut recipe_builder = library.create_recipe();
    ///
    /// // trying to set parameters while recipe_builder is alive is an error
    /// library.set_parameters();
    ///
    /// // recipe_builder is still alive until here
    /// drop(recipe_builder);
    /// ```
    pub fn create_recipe(&mut self) -> RecipeBuilder<'_> {
        ...
    }
}
```

You can see that fulfilling the `!Send` and `!Sync` goal was quite easy to
do. By making sure `Library: !Send`, anything referencing `Library` is also
`!Send`.

On the other hand, ensuring functions can only be called in the correct order
is a lot more invasive. We needed to restructure our entire API using complex
concepts like lifetimes and RAII to encode the logical equivalent of a
type-level state machine.

## Creating FFI Bindings

## Writing a Safe Interface to LibStateful

## Conclusions

[data-race]: https://doc.rust-lang.org/nomicon/races.html
[static-assert]: https://crates.io/crates/static_assertions
[u.rl.o]: https://users.rust-lang.org/t/common-strategies-for-wrapping-a-library-that-uses-globals-everywhere/37944
[yandros]: https://users.rust-lang.org/u/yandros/summary