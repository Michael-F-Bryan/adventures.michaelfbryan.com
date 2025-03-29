---
title: "Link Time Dependency Injection"
publishDate: "2024-03-29T12:59:58+08:00"
tags:
- Architecture
- Tips & Tricks
- Rust
- Unsafe Rust
---

Have you ever been in a situation where, because of how the code is structured, it's practically impossible to inject a dependency into the component that needs it? Even global variables - ubiquitously reviled for their ability to do "spooky action at a distance" - weren't spooky enough.

In this article, I'll share a technique I discovered while working on a WebAssembly-based CAD package that allows for dependency injection at link time. This technique is particularly useful when traditional dependency injection methods aren't available or practical.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the blog's [issue tracker][issue]!

Please excuse any outdated comments about `wit-bindgen`. I wrote the bulk of this article back in 2022 but never got around to publishing it.

[repo]: https://github.com/Michael-F-Bryan/fornjot-plugins
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## The Problem

Let's start with a concrete example. Imagine you are designing a CAD package where people can provide custom parts using a DLL that the CAD package will load at runtime. The CAD package expects each DLL to have a function that can be called whenever the part should be generated, with the function signature looking something like this:

```rust
extern "C" fn model(args: &Arguments) -> Shape;
```

Where the `Arguments` and `Shape` types come from some code generator, and the only way you can make them ergonomic to use is if you add your own helper methods and trait implementations.

What you would really like to do is pull the generated code into a common crate that all implementations can import. This lets us hide the code generation step, allows reusing the pre-defined helper methods and trait implementations, and gives us a nice place to write examples and API docs.

This would normally be fine because you can define the types in some common crate and let the model author define the `model()` function (possibly enforcing the function signature via a macro), but there's a twist...

1. Because "reasons", the generated code requires our `model()` function to be defined in its parent module (i.e. somewhere in our common crate), and
2. The CAD package directly calls `model()` with no possibility for the model author to intercept the call or do some setup beforehand

## Why Traditional Solutions Don't Work

Let's look at why our usual dependency injection techniques won't work here:

1. **Direct Injection**: We can't pass the implementation as an argument because the CAD package calls `model()` directly.

2. **Global Variables**: Even if we used a global variable to store the implementation, we have no way to initialize it. This is because our "DLL" is actually a WebAssembly binary, and WebAssembly has no way to make sure a function is called when it is first loaded (i.e. we can't use `__attribute__(ctor)` or [the `ctor` crate][ctor]).

3. **Runtime Registration**: The `log` crate's pattern of having a `static` variable containing a function that gets set on startup won't work either, since we can't guarantee when or if initialization code will run.

## The Solution: Link Time Dependency Injection

The solution comes from an unexpected place - the linker. This technique is actually quite common in C programs and is even used by Rust's standard library for the global allocator.

Let's look at how [Rust's `#[global_allocator]` attribute][global-alloc] works:

```rust
// library/alloc/src/alloc.rs

extern "Rust" {
    #[rustc_allocator]
    #[rustc_allocator_nounwind]
    fn __rust_alloc(size: usize, align: usize) -> *mut u8;
    #[rustc_allocator_nounwind]
    fn __rust_dealloc(ptr: *mut u8, size: usize, align: usize);
    #[rustc_allocator_nounwind]
    fn __rust_realloc(ptr: *mut u8, old_size: usize, align: usize, new_size: usize) -> *mut u8;
    #[rustc_allocator_nounwind]
    fn __rust_alloc_zeroed(size: usize, align: usize) -> *mut u8;
}
```

The `alloc` crate declares a bunch of `extern "Rust"` functions and some downstream crate provides the implementation, with all the nitty-gritty details hidden behind a macro.

{{% notice note %}}
It wasn't until after writing up most of this article that I realised I'd read about this technique before.

In *Working Effectively With Legacy Code* there is a section called *Link Seams*,

> In many language systems, compilation isn't the last step of the build process. The compiler produces an intermediate representation of the code, and that representation contains calls to code in other files. Linkers combine these representations. They resolve each of the calls so that you can have a complete program at runtime.

You can leverage this linking step to provide your own implementation for functions. In the book's case, it is primarily used to provide mocks and spies when trying to get some gnarly code under test, but it works equally well for splitting a dependency cycle.
{{% /notice %}}

## A Real-World Example

Let's look at how this technique is used in practice. At [Hammer of the Gods][hotg], we developed a containerisation technology backed by WebAssembly which lets us compile various operations in a data processing pipeline once, then execute these operations on a variety of platforms (desktop, browser, mobile, etc.)[^1].

A key part of this is [the `wit-bindgen` project][wit-bindgen] which lets us define host and guest interfaces in `*.wit` files, then generate Rust code that satisfies the interfaces. If you are familiar with gRPC and Protocol Buffers, `wit-bindgen` is like `protoc` and `*.wit` files are like `*.proto` files.

We've got 30+ different operations and it would be really nice if we could put the generated glue code in one common crate. That way we can add nice things like constructors, helper methods, and trait implementations to the generated types, wire up nicer error handling with the `?` operator, and so on.

Here's how we use link time dependency injection to solve this:

```rust
// support/src/guest/bindings.rs

extern "Rust" {
    fn __proc_block_metadata() -> Metadata;
    fn __proc_block_new(
        args: Vec<Argument>,
    ) -> Result<Box<dyn ProcBlock>, CreateError>;
}

struct ProcBlockV2;

impl proc_block_v2::ProcBlockV2 for ProcBlockV2 {
    fn metadata() -> Metadata {
        crate::guest::ensure_initialized();
        unsafe { __proc_block_metadata() }
    }

    fn create_node(
        args: Vec<Argument>,
    ) -> Result<wit_bindgen_rust::Handle<self::Node>, CreateError> {
        crate::guest::ensure_initialized();
        let proc_block = unsafe { __proc_block_new(args)? };
        Ok(Handle::new(Node(Box::new(proc_block))))
    }
}
```

And a downstream crate provides the implementation:

```rust
// argmax/src/lib.rs

hotg_rune_proc_blocks::export_proc_block! {
  metadata: metadata,
  proc_block: ArgMax,
}

#[derive(Debug, Clone, Default, PartialEq)]
struct ArgMax;

impl From<Vec<Argument>> for ArgMax {
  fn from(_: Vec<Argument>) -> Self { ArgMax }
}

fn metadata() -> Metadata {
  ...
}

impl ProcBlock for ArgMax {
  fn tensor_constraints(&self) -> TensorConstraints { ... }
  fn run(&self, inputs: Vec<Tensor>) -> Result<Vec<Tensor>, RunError> { ... }
}
```

The macro that makes this work is also [part of the support crate][macros]:

```rust
// support/src/guest/macros.rs

/// Tell the runtime that a WebAssembly module contains a proc-block.
#[macro_export]
macro_rules! export_proc_block {
    (metadata: $metadata_func:expr, proc_block: $proc_block:ty $(,)?) => {
        #[doc(hidden)]
        #[no_mangle]
        pub fn __proc_block_metadata() -> $crate::guest::Metadata { $metadata_func() }

        #[doc(hidden)]
        #[no_mangle]
        pub fn __proc_block_new(
            args: Vec<$crate::guest::Argument>,
        ) -> Result<Box<dyn $crate::guest::ProcBlock>, $crate::guest::CreateError> {
            fn assert_impl_proc_block(_: &impl $crate::guest::ProcBlock) {}

            let proc_block = <$proc_block>::try_from(args)?;
            assert_impl_proc_block(&proc_block);

            Ok(Box::new(proc_block) as Box<dyn $crate::guest::ProcBlock>)
        }
    };
}
```

## When Should You Use This Trick?

This technique should be used as a last resort, after considering these alternatives:

1. **Pass Implementation as Arguments**: If you have control over how/when your code is called, this is the cleanest solution.
2. **Runtime Registration**: If you can run some code on startup, use a global variable (like the `log` crate does).
3. **Crate Links**: If you can guarantee only one version of your crate will be in the crate graph, you might be able to use the `links` key in `Cargo.toml`.
4. **Static Linking**: If everything is statically linked and compiled together, you might be able to use unstable ABI features.

## Conclusion

Link time dependency injection is a powerful technique that can help break dependency cycles and provide implementations where traditional dependency injection methods aren't available. While it should be used sparingly and as a last resort, it's a valuable tool to have in your arsenal when dealing with complex architectural challenges.

The technique isn't novel - it's used extensively in C programs and is even employed by Rust's standard library for the global allocator. As mentioned in *Working Effectively with Legacy Code*, this pattern is known as "Link Seams" and is particularly useful when you need to provide alternative implementations without modifying the original code.

[global-alloc]: https://github.com/rust-lang/rust/blob/3a8b0144c82197a70e919ad371d56f82c2282833/library/alloc/src/alloc.rs#L22-L39
[hotg]: https://hotg.ai/
[wit-bindgen]: https://github.com/bytecodealliance/wit-bindgen
[macros]: https://github.com/hotg-ai/proc-blocks/blob/f776393c60d4c53483d2d633bb7f73006598fda4/support/src/guest/macros.rs
[ctor]: https://crates.io/crates/ctor
[log]: https://crates.io/crates/log

[^1]: For example, imagine making a pipeline which takes an audio clip, normalises the volume level, converts the audio samples into a spectrum, then passes the spectrum to a ML model which can recognise particular words. Each of these steps is compiled into its own WebAssembly module and our "runtime" chains them together. We also use the [*WebAssembly Package Manager*][wapm] to distribute WebAssembly modules and manage versions.

[wapm]: https://wapm.io/
