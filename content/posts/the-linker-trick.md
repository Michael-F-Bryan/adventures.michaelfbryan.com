---
title: "Link Time Dependency Injection"
publishDate: "2022-07-04T00:07:49+08:00"
draft: true
tags:
- Architecture
- Tips & Tricks
- Rust
- Unsafe Rust
---

Have you ever been in a situation where, because of how the code is structured,
it's practically impossible to inject a dependency into the component that needs
it?

I was recently working on a task where some code depended on functionality
provided by another component, but I had no way to provide my implementation
directly as an input because.

Even global variables - ubiquitously reviled for their ability to do "spooky
action at a distance" - weren't spooky enough.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/fornjot-plugins
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}


## The Scenario

That introduction was a bit on the vague side, so let's give you a real world
example.

Imagine you are designing a CAD package where people can provide custom parts
using a DLL that the CAD package will load at runtime. The CAD package expects
each DLL to have a function that can be called whenever the part should be
generated, with the function signature looking something like this:

```rust
extern "C" fn model(args: &Arguments) -> Shape;
```

Where the `Arguments` and `Shape` types actually come from some code generator,
and the only way you can make them ergonomic to use is if you add your own
helper methods and trait implementations.

Now, what you would really like to do is pull the generated code into a common
crate that all implementations can import. This lets us hide the code generation
step, allows reusing the pre-defined helper methods and trait implementations,
and gives us a nice place to write examples and API docs.

This would normally be fine because you can define the types in some common
crate and let the model author define the `model()` function (possibly enforcing
the function signature via a macro), but there's a twist...

1. Because "reasons", the generated code requires our `model()` function to be
   defined in its parent module (i.e. somewhere in our common crate), and
2. The CAD package directly calls `model()` with no possibility for the model
   author to intercept the call or do some setup beforehand

How do you deal with this?

Ideally, I would set things up so the CAD package calls my model implementation
which then injects the required dependency into the common crate, but that's not
possible here.

An alternative way to do dependency injection is for the common crate to have a
`static` variable containing a function, and then make sure the model
implementation calls some `common:set_model_handler()` function on startup. This
is the pattern Rust's [`log` crate][log] uses, btw.

However, something I neglected to mention earlier is that this "DLL" is actually
a WebAssembly binary, and WebAssembly has no way to make sure a function is
called when it is first loaded (i.e. we can't use `__attribute__(ctor)` or [the
`ctor` crate][ctor]) so this approach won't work either.

## The Solution

### Create An Abstraction Layer

### Breaking Dependencies with the Linker

### Hide The Implementation Details

## When Should I Use This Trick?

- Last resort
- If you have control over how/when your code is called - pass in your
  implementation as an argument
- If you can run some code on startup - set a global (e.g. the `log` crate)
- You can guarantee only one version of your crate will be in the crate graph
  (might be able to use the `links` key in `Cargo.toml`)
- Only if everything is statically linked and compiled together (unstable ABI)

## Conclusions

- Not a novel technique
- Point to how [Rust's `#[global_allocator] works`][global-alloc]
- Used all the time in C programs
- Titbit, mentioned in *Working Effectively with Legacy Code* under the name
  *"Link Seams"*








---







- Couple months back
- Ran into a cyclic dependency problem at work
- Unable to restructure the code because the core was maintained by a 3rd party
- Couldn't afford to spend a week restructuring the upstream code and making a
  PR
- Take inspiration from how [Rust's `#[global_allocator] works`][global-alloc]
- Used all the time in C programs
- Titbit, mentioned in *Working Effectively with Legacy Code* under the name
  *"Link Seams"*
- Forward declare `extern "Rust"` functions and make the linker figure it out

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

## Some Context

The background for this problem isn't really relevant to the solution, but it
might help to provide examples for where this trick is useful.

At [Hammer of the Gods][hotg], we have developed a containerisation technology
backed by WebAssembly which lets us compile various operations in a data
processing pipeline once, then execute these operations on a variety of
platforms (desktop, browser, mobile, etc.)[^1].

A key part of this is [the `wit-bindgen` project][wit-bindgen] which lets us
define host and guest interfaces in `*.wit` files, then generate Rust code that
satisfies the interfaces. If you are familiar with gRPC and Protocol Buffers,
`wit-bindgen` is like `protoc` and `*.wit` files are like `*.proto` files.

Now, we've got 30+ different operations and it would be really nice if we could
put the generated glue code in one common crate. That way we can add nice things
like constructors, helper methods, and trait implementations to the generated
types, wire up nicer error handling with the `?` operator, and so on.

This has a massive benefit for developer ergonomics, but turned out to be very
difficult because of the way `wit-bindgen`'s glue code works.

- The `wit_bindgen_rust::import!("path/to/guest-interface.wit")` macro takes
  the path to a WIT file and figures out which structs and traits to generate
- When exporting functionality from the guest to the host, it needs to define
  `extern "C"` functions
- These functions look for a type implementing a particular trait in the parent
  namespace
- This type must exist at compile time and be a part of the crate generating
  the glue code

In code, our problem looks something like this:

```rust
// shared-crate/src/lib.rs

wit_bindgen_rust::import!("path/to/guest.wit");

// expands to

mod guest {
  pub struct SomeStruct { ... }

  pub trait Guest {
    fn create_some_struct() -> SomeStruct;
  }

  #[export_name = "guest::create-some-struct"]
  pub extern "C" fn create_some_struct() -> i32 {
    let s: SomeStruct = <super::Guest as self::Guest>::create_some_struct();

    /* magic */
  }
}
```

And we would like the downstream crate to do something like this:

```rust
// downstream-crate/src/lib.rs

struct Guest;

impl shared_crate::guest::Guest for Guest {
  fn create_some_struct() -> SomeStruct { todo!() }
}
```

The problem is that `super::Guest as self::Guest` bit. It means we must define
a `shared_crate::Guest` type which implements the `shared_crate::guest::Guest`
trait.

However, if this is a shared crate where downstream users are meant to
implement `shared_crate::guest::Guest`, we've got a bit of a problem... There
*is* no `shared_crate::Guest` type, and it's not possible for a downstream crate
to inject a type into an upstream crate's namespace.

There are also no "seams" for traditional methods of dependency injection.

We've got a dependency cycle where `shared_crate` requires functionality from
downstream to be available at compile time, while a downstream crate uses traits
from upstream to implement that functionality.  Our normal tools for introducing
seams via indirection (e.g. storing a concrete implementation in a field or
`static` variable that gets provided at runtime) won't work here[^2].

## The Solution

While our normal tools won't work, not all hope is lost. The Rust standard
library has a very similar problem where the `alloc` crate defines data types
which require an allocator (e.g. `Vec` and `String`) with the expectation that
either `std` or another downstream crate will set the global allocator.

Let's take a look at how [Rust's `#[global_allocator]` attribute][global-alloc]
works.

```rust
// library/alloc/src/alloc.rs

extern "Rust" {
    // These are the magic symbols to call the global allocator.  rustc generates
    // them to call `__rg_alloc` etc. if there is a `#[global_allocator]` attribute
    // (the code expanding that attribute macro generates those functions), or to call
    // the default implementations in libstd (`__rdl_alloc` etc. in `library/std/src/alloc.rs`)
    // otherwise.
    // The rustc fork of LLVM also special-cases these function names to be able to optimize them
    // like `malloc`, `realloc`, and `free`, respectively.
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

So the `alloc` crate declares a bunch of `extern "Rust"` functions and some
downstream crate provides the implementation, with all the nitty-gritty details
hidden behind a macro.

{{% notice note %}}
It wasn't until after writing up most of this article that I realised I'd read
about this technique before.

In *Working Effectively With Legacy Code* there is a section called *Link Seams*,

> In many language systems, compilation isn't the last step of the build
> process. The compiler produces an intermediate representation of the code, and
> that representation contains calls to code in other files. Linkers combine
> these representations. They resolve each of the calls so that you can have a
> complete program at runtime.

You can leverage this linking step to provide your own implementation for
functions. In the book's case, it is primarily used to provide mocks and spies
when trying to get some gnarly code under test, but it works equally well for
splitting a dependency cycle.
{{% /notice %}}

As an aside, I'm not sure how they wire up the *"fallback to `libstd`"* bit
(maybe it uses weak symbols or is special cased in the compiler?) but that's
not really relevant here.


{{% expand "Click to see an example from the real world." %}}
For a concrete example, [here][bindings] we define the `extern "Rust"` functions
and provide an implementation.

```rust
// support/src/guest/bindings.rs

pub use self::{proc_block_v2::*, runtime_v2::*};

use crate::guest::ProcBlock;
use wit_bindgen_rust::Handle;

wit_bindgen_rust::import!("../wit-files/rune/runtime-v2.wit");
wit_bindgen_rust::export!("../wit-files/rune/proc-block-v2.wit");

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

pub struct Node(Box<dyn ProcBlock>);

impl proc_block_v2::Node for Node {
    fn tensor_constraints(&self) -> TensorConstraints {
        self.0.tensor_constraints()
    }

    fn run(&self, inputs: Vec<Tensor>) -> Result<Vec<Tensor>, RunError> {
        self.0.run(inputs)
    }
}
```

The macro is also [part of the support crate][macros]:

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

And a downstream crate provides [the implementation][argmax] like so:

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
```

[bindings]: https://github.com/hotg-ai/proc-blocks/blob/f776393c60d4c53483d2d633bb7f73006598fda4/support/src/guest/bindings.rs
[macros]: https://github.com/hotg-ai/proc-blocks/blob/f776393c60d4c53483d2d633bb7f73006598fda4/support/src/guest/macros.rs
[argmax]: https://github.com/hotg-ai/proc-blocks/blob/f776393c60d4c53483d2d633bb7f73006598fda4/argmax/src/lib.rs#L10-L13
{{% /expand %}}

[^1]: For example, imagine making a pipeline which takes an audio clip,
normalises the volume level, converts the audio samples into a spectrum, then
passes the spectrum to a ML model which can recognise particular words.

    Each of these steps is compiled into its own WebAssembly module and our
    "runtime" chains them together.

    We also use the [*WebAssembly Package Manager*][wapm] to distribute
    WebAssembly modules and manage versions.

[^2]: For example, the `Guest` trait's methods don't take a `&self`, so creating
      a `shared_crate::Guest` struct that delegates to a concrete implementation
      won't work.

    Even if it was possible, the downstream implementation would still have no
    way to initialise the `shared_crate::Guest` because WebAssembly doesn't
    provide a way to automatically run code on startup (this also precludes
    using a `static` variable that gets initialised like what the `log` crate
    does).


[global-alloc]: https://github.com/rust-lang/rust/blob/3a8b0144c82197a70e919ad371d56f82c2282833/library/alloc/src/alloc.rs#L22-L39
[hotg]: https://hotg.ai/
[wapm]: https://wapm.io/
[wit-bindgen]: https://github.com/bytecodealliance/wit-bindgen
[ctor]: https://crates.io/crates/ctor
[log]: https://crates.io/crates/log
