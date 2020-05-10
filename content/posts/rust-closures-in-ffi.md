---
title: "Rust Closures in FFI"
date: "2020-05-10T16:47:27+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
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

[strategy]: https://sourcemaking.com/design_patterns/strategy
