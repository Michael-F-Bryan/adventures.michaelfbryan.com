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

Another important point to emphasize is this 3rd party library is native code
(I think it's written in C++?). The reason this is important is because it
uses pointers and a bug doesn't just mean an exception gets thrown, we could
segfault and tear down the entire process.

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

Finally, we get a couple functions for inspecting the output. Something to
keep in mind is they can only be called from inside our `result_cb` callback.

```c
// Try to get the number of outputs in the result.
int stateful_get_num_outputs(int *value);
// Tries to retrieve a particular output.
int stateful_get_output_by_index(int index, int *value);
```

## Our High-Level Approach

## The Bottom Layer

## Idiomatic Rust

## Conclusions

[data-race]: https://doc.rust-lang.org/nomicon/races.html