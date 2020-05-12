---
title: "Rust Closures in FFI"
date: "2020-05-10T16:47:27+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
- FFI
---

Every now and then when using native libraries from Rust you'll be asked to
pass a callback across the FFI boundary. Often this might be done to notify
the caller when "interesting" things happen, for injecting logic (see the
[Strategy Pattern][strategy]), or to handle the result of an asynchronous
operation.

If this were normal Rust, we'd just accept a closure (e.g. a `Box<dyn Fn(...)>`
or by being generic over any function-like type) and be done with it. However,
the C language (or more specifically, the ABI and machine code in general) don't
understand generics or Rust's "fat" pointers, meaning we need to be a little...
creative.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/rust-closures-and-ffi
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## A Simple Example

Let's look at a simple C function which adds two numbers and will let the caller
know the result by invoking a callback.

```c
// native/simple.c

typedef void (*AddCallback)(int result);

void simple_add_two_numbers(int a, int b, AddCallback cb)
{
    int result = a + b;
    cb(result);
}
```

The straightforward way to use the `simple_add_two_numbers()` is to define a
function with the correct signature...

```rust
// src/simple.rs

pub unsafe extern "C" fn on_two_numbers_added(result: c_int) {
    println!("Got {}!", result);
}
```

... And pass it to the native function.

```rust
// examples/straightforward_simple.rs

use rust_closures_and_ffi::simple::{
    on_two_numbers_added, simple_add_two_numbers,
};

fn main() {
    let a = 1;
    let b = 2;

    println!("Adding {} and {}", a, b);

    unsafe {
        simple_add_two_numbers(1, 2, on_two_numbers_added);
    }
}
```

{{% notice note %}}
To make the C function callable from Rust, we need to add the corresponding
function declarations.

```rust
// src/simple.rs

use std::os::raw::c_int;

pub type AddCallback = unsafe extern "C" fn(c_int);

extern "C" {
    pub fn simple_add_two_numbers(a: c_int, b: c_int, cb: AddCallback);
}
```

We also need to use `unsafe` here because the `simple_add_two_numbers()`
function was written in another language and Rust has no way of knowing that
it's safe to use.
{{% /notice %}}

We can even run this code and see what it generates.

```console
 cargo run --example straightforward_simple
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/examples/straightforward_simple`
Adding 1 and 2
Got 3!
```

Okay, that's awesome, but what if you want to do something with the result? Say
I need to go through a list of items and add them up.

Our problem is that the callback function only accepts a single integer and
doesn't return anything. That means there's no way to pass in a reference to
some `total` counter so we can add the `result` to it.

If you aren't able to access any state from the calling function, the only real
way to pass information around is via a `static` mutable global variable.

Here's one possible way to write it:

```rust
// examples/simple_with_global_variable.rs

use rust_closures_and_ffi::simple::simple_add_two_numbers;
use std::os::raw::c_int;

static mut TOTAL: c_int = 0;

fn main() {
    let numbers = [1, 2, 3, 4, 5, 6, 7];

    for i in 0..numbers.len() {
        for j in i..numbers.len() {
            let a = numbers[i];
            let b = numbers[j];

            unsafe {
                simple_add_two_numbers(a, b, add_result_to_total);
            }
        }
    }

    println!("The sum is {}", TOTAL);
}

unsafe extern "C" fn add_result_to_total(result: c_int) { TOTAL += result; }
```

Compiling and running:

```console
$ cargo run --example simple_with_global_variable
   Compiling rust-closures-and-ffi v0.1.0 (/home/michael/Documents/rust-closures-and-ffi)
error[E0133]: use of mutable static is unsafe and requires unsafe function or block
  --> examples/simple_with_global_variable.rs:20:31
   |
20 |     println!("The sum is {}", TOTAL);
   |                               ^^^^^
   |
   = note: mutable statics can be mutated by multiple threads: aliasing violations or data races will cause undefined behavior

error: aborting due to previous error

For more information about this error, try `rustc --explain E0133`.
error: could not compile `rust-closures-and-ffi`.

To learn more, run the command again with --verbose.
```

Oops, we forgot that reading from a global requires `unsafe`.

```diff
// examples/simple_with_global_variable.rs

 fn main() {
     ...

-    println!("The sum is {}", TOTAL);
+    unsafe {
+        println!("The sum is {}", TOTAL);
+    }
 }
```

Let's try again...

```console
$ cargo run --example simple_with_global_variable
    Blocking waiting for file lock on build directory
    Finished dev [unoptimized + debuginfo] target(s) in 0.37s
     Running `target/debug/examples/simple_with_global_variable`
The sum is 224
```

You can see that this works but using a global variable isn't great, and as
the compiler reminded us, it's prone to data races and other foot-guns.

If this were pure Rust, we'd just declare a `total` variable on the stack and
use a closure to update the variable with the result.

```rust
fn main() {
    let mut total = 0;

    ...

    simple_add_two_numbers(a, b, |result| total += result);
}
```

The problem here isn't actually related to Rust. Whoever wrote the
`simple_add_two_numbers()` function included a big design flaw... It's
impossible for the callback to update state!

## A Better Adding Function

Now we know the original native function was flawed, let's go about fixing it.

If the original flaw is that our callback can't use any non-global state, we
should give it a way to access state passed in by the caller.

Normally this state would be passed around as a pointer, but what type should
we be using? In theory the caller may want to use their own custom struct as
state (imagine we need to update a text field on a GUI program), so hard-coding
a pointer to an integer won't really cut it.

Luckily, that's where C's `void *` pointer comes in. This says *"I've got a
pointer to... something"* and to make that pointer usable downstream code will
need to cast it to the desired type.

Here is the amended function for adding numbers:

```c
// native/better.c

typedef void (*AddCallback)(int result, void *user_data);

void better_add_two_numbers(int a, int b, AddCallback cb, void *user_data)
{
    int result = a + b;
    cb(result, user_data);
}
```

I've also taken the liberty of providing Rust declarations for
`better_add_two_numbers()`.

```rust
// src/better.rs

use std::os::raw::{c_int, c_void};

pub type AddCallback = unsafe extern "C" fn(c_int, *mut c_void);

extern "C" {
    pub fn better_add_two_numbers(
        a: c_int,
        b: c_int,
        cb: AddCallback,
        user_data: *mut c_void,
    );
}
```

It's actually pretty straightforward to use this `void *` user data argument
for our counter.  Here's the equivalent of our `simple_with_global_variable`
example.

```rust
// examples/better_with_counter_pointer.rs

use rust_closures_and_ffi::better::better_add_two_numbers;
use std::os::raw::{c_int, c_void};

fn main() {
    let numbers = [1, 2, 3, 4, 5, 6, 7];
    let mut total = 0;

    for i in 0..numbers.len() {
        for j in i..numbers.len() {
            let a = numbers[i];
            let b = numbers[j];

            unsafe {
                better_add_two_numbers(
                    a,
                    b,
                    add_result_to_total,
                    &mut total as *mut c_int as *mut c_void,
                );
            }
        }
    }

    println!("The sum is {}", total);
}

unsafe extern "C" fn add_result_to_total(
    result: c_int,
    user_data: *mut c_void,
) {
    let total = &mut *(user_data as *mut c_int);
    *total += result;
}
```

If you squint, you'll notice that we didn't need to change much from the
global variable version. The only extra work we needed to do was casting
`total` to a `void *` when calling `better_add_two_numbers()` and then cast
it back at the top of `add_result_to_total()`.

Of course, there's no reason why we can only use a `c_int` for our
`user_data`. For more complex scenarios you'll often need to use a custom
type and update multiple members at a time.

For example, imagine we wanted to count the number of times the callback is
invoked as well as the final total.

First we create a new `Counter` type.

```rust
// examples/better_with_counter_struct.rs

#[derive(Debug, Default, Clone, PartialEq)]
struct Counter {
    total: c_int,
    calls: usize,
}
```

And then we can tweak the code to update our `Counter` struct.

```diff
  // examples/better_with_counter_struct.rs

  fn main() {
      let numbers = [1, 2, 3, 4, 5, 6, 7];
+     let mut counter = Counter::default();
-     let mut total = 0;

      for i in 0..numbers.len() {
          for j in i..numbers.len() {
              let a = numbers[i];
              let b = numbers[j];

              unsafe {
                  better_add_two_numbers(
                      a,
                      b,
                      add_result_to_total,
-                     &mut total as *mut c_int as *mut c_void,
+                     &mut counter as *mut Counter as *mut c_void,
                  );
              }
          }
      }

-     println!("The sum is {}", total);
+     println!("The result is {:?}", counter);
  }

  unsafe extern "C" fn add_result_to_total(
      result: c_int,
      user_data: *mut c_void,
  ) {
-     let total = &mut *(user_data as *mut c_int);
-     *total += result;
+     let mut counter = &mut *(user_data as *mut Counter);
+     counter.total += result;
+     counter.calls += 1;
  }
```

And of course, we can compile and run this code.

```console
$ cargo run --example better_with_counter_struct
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/examples/better_with_counter_struct`
The result is Counter { total: 224, calls: 28 }
```

## Introducing Closures

In Rust, a closure is just syntactic sugar for defining a new type with some
sort of `call()` method. So in theory, we should be able to pass a closure to
native code by "splitting" it into its data (instance of the anonymous type)
and function (the `call()` method) parts.

The easiest way to do this is by creating a "shim" function which is generic
over one of the `Fn*()` traits and will invoke the closure with the provided
arguments. Then we can get the data bit by taking a reference to the closure
variable and casting that to a `void *` pointer.

Using the last section's example, here is a function which satisfies the
`AddCallback` signature and will treat the provided `user_data` as a closure.

```rust
// src/better.rs

unsafe extern "C" fn trampoline<F>(result: c_int, user_data: *mut c_void)
where
    F: FnMut(c_int),
{
    let user_data = &mut *(user_data as *mut F);
    user_data(result);
}
```

Now let's see how this `trampoline()` might be used in practice. Here I've
created a simple integer variable, `got`, and a `closure` closure which will
set `got` to the `result` given to us by `better_add_two_numbers()`.

You can see that we've taken a reference to the `closure` variable (which is
an instance of the anonymous struct `rustc` generated, and is currently
sitting on the stack) and done a couple pointer casts to turn it into
something we can use as our `user_data`.

```rust
// src/better.rs

#[test]
fn use_the_trampoline_function() {
    let mut got = 0;

    {
        let mut closure = |result: c_int| got = result;

        unsafe {
            better_add_two_numbers(
                1,
                2,
                trampoline,
                &mut closure as *mut _ as *mut c_void,
            );
        }
    }

    assert_eq!(got, 1 + 2);
}
```

Unfortunately, `rustc` will complain if you try to use this `trampoline()`
function by itself because it can't infer the `F` type variable. This is
because the type variable is completely unrelated to any of the functions
inputs or outputs, so there isn't any information available to type
inference.

```console
$ cargo test
    Finished dev [unoptimized + debuginfo] target(s) in 0.01s
   Compiling rust-closures-and-ffi v0.1.0 (/home/michael/Documents/rust-closures-and-ffi)
error[E0282]: type annotations needed
  --> src/better.rs:44:21
   |
44 |                     trampoline,
   |                     ^^^^^^^^^^

error: aborting due to previous error

For more information about this error, try `rustc --explain E0282`.
error: could not compile `rust-closures-and-ffi`.
```

To help things along, we can define a getter function which accepts a
reference to the closure as an argument (allowing type inference to figure
out what `F` is) and using [turbofish][turbofish] to return a version of
`trampoline()` specialised for `F` (the technical terminology is to
*"instantiate"* a the `trampoline` function for the type, `F`).

```rust
// src/better.rs

pub fn get_trampoline<F>(_closure: &F) -> AddCallback
where
    F: FnMut(c_int),
{
    trampoline::<F>
}
```

And everything compiles with the new getter.

```diff
  // src/better.rs

  #[test]
  fn use_the_trampoline_function() {
      let mut got = 0;

      {
          let mut closure = |result: c_int| got = result;
+         let trampoline = get_trampoline(&closure);

          unsafe {
              better_add_two_numbers(
                  1,
                  2,
                  trampoline,
                  &mut closure as *mut _ as *mut c_void,
              );
          }
      }

      assert_eq!(got, 3);
  }
```

You can see I've written this as a test, so now we can be confident that
`1 + 2` does in fact equal `3`.

To tie everything together, if I were trying to provide a safe interface to
`better_add_two_numbers()` it might be written like this:

```rust
// better.rs

/// Add two numbers, passing the result to the provided closure for further
/// processing.
pub fn add_two_numbers<F>(a: i32, b: i32, on_result_calculated: F)
where
    F: FnMut(i32),
{
    unsafe {
        let mut closure = on_result_calculated;
        let cb = get_trampoline(&closure);

        better_add_two_numbers(a, b, cb, &mut closure as *mut _ as *mut c_void);
    }
}
```

{{% notice warning %}}
A very important thing to note is the function pointer returned by
`get_trampoline()` can **only** be used on the same closure that was passed in.

This is because our specialised `trampoline()` function will blindly cast
`user_data` to a pointer to that closure type without doing any type checks,
so if you try to use it on anything else you're gonna have a bad time...

This means it's important to make sure the callback is always an `unsafe`
function, making it the caller's responsibility to ensure the correct
`user_data` is used.
{{% /notice %}}

## Conclusions

While it may seem like a niche problem, and it is, when trying to write
idiomatic bindings for a native library it's not uncommon to deal with
callbacks.

In the past I used to use a slightly different version of `get_trampoline()`
which would return *both* the `trampoline` function pointer and `user_data`,
and it even [became part][split_closure] of my `ffi_helpers` crate. However,
after [some lengthy discussion][ffi_helpers_3] with
[`@danielhenrymantilla`][dhm], I've decided the above version is safer and
helps prevent callers from accidentally creating aliased mutable pointers.

{{% expand "(Original trampoline getter)" %}}

```rust
pub fn get_trampoline<F>(closure: &mut F) -> (*mut c_void, AddCallback)
where
    F: FnMut(c_int),
{
    (closure as *mut F as *mut c_void, trampoline::<F>)
}
```

{{% /expand %}}

[strategy]: https://sourcemaking.com/design_patterns/strategy
[turbofish]: https://turbo.fish/
[split_closure]: https://docs.rs/ffi_helpers/0.2.0/ffi_helpers/fn.split_closure.html
[ffi_helpers_3]: https://github.com/Michael-F-Bryan/ffi_helpers/pull/3/
[dhm]: https://github.com/danielhenrymantilla
