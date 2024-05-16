---
title: "Reviewing Unsafe Rust"
date: "2020-01-18T20:38:06+08:00"
draft: true
---

There has recently been a bit of a kerfuffle in the Rust community around the
actix-web project. Rather than talking about the public outcry and nasty
things being said on Reddit or the author's fast-and-loose attitude towards
writing `unsafe` code (Steve Klabnik has [already explained it][sad-day] much
better than I could) I would like to discuss some technical aspects of `unsafe`
Rust.

In particular a lot of people say we should be reviewing our dependencies for
possibly unsound code, but nobody seems to explain *how* such a review is done
or how to reason about correctness.

There's also a tendency to understate how much effort is required to review code
in enough detail that the review can be relied on. To that end, the [crev][crev]
project has done a lot of work to help distribute the review effort and build a
*Web of Trust* system.

I'll also be keeping track of the time taken using an app called
[clockify][clockify], that way at the end we can see a rough breakdown of
time spent and get a more realistic understanding of the effort required to
review code.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Introducing the `anyhow` Crate

Over the past couple months the [`anyhow`][anyhow] and [`thiserror`][thiserror]
crates from [*@dtolnay*][dtolnay] have helped simplify error handling in Rust a
lot.

The `thiserror` crate is a procedural macro for automating the implementation of
`std::error::Error` and isn't overly interesting for our purposes (it's still
really cool, just doesn't contain tricky `unsafe` code).

On the other hand, the `anyhow` crate presents a custom `Error` type and uses a
`unsafe` code under the hood to implement nice things like downcasting and
representing an `anyhow::Error` with a thin pointer.

Before we start the review proper, it's worth looking at the top-level docs and
examples so we can get a rough understanding of how things fit together.

Everything in this article will be done using version 1.0.26 of `anyhow`.

First we'll use `cargo-crev` to drop into a directory with the crate's source
code.

```console
$ cargo crev crate goto anyhow 1.0.26
Opening shell in: /home/michael/.cargo/registry/src/github.com-1ecc6299db9ec823/anyhow-1.0.26
Use `exit` or Ctrl-D to return to the original project.
Use `review` and `flag` without any arguments to review this crate.
$ code .
```

Next we can open the API docs in a browser and have a look around. This crate
is really well documented, so that makes things a lot easier!

```console
$ cargo doc --open
   Compiling anyhow v1.0.26 (/home/michael/.cargo/registry/src/github.com-1ecc6299db9ec823/anyhow-1.0.26)
 Documenting anyhow v1.0.26 (/home/michael/.cargo/registry/src/github.com-1ecc6299db9ec823/anyhow-1.0.26)
    Finished dev [unoptimized + debuginfo] target(s) in 4.03s
     Opening /home/michael/.cargo/registry/src/github.com-1ecc6299db9ec823/anyhow-1.0.26/target/doc/anyhow/index.html
```

{{% notice tip %}}
For those of you following along at home you can also [view the docs
online][docs].

Although if you're doing a proper review I would strongly recommend to build
everything from source instead of relying on 3rd parties. I doubt docs.rs is
trying to deceive us, but it's always good to know that everything you are
looking at comes from the same set of code.

[docs]: https://docs.rs/anyhow/1.0.26/anyhow/
{{% /notice %}}

The crate only exports two types, an `Error` and a helper type for iterating
over a chain of errors.

However looking at the files in the project shows a lot more than just two
files...

```console
$
tree -I 'target|tests'
.
├── build.rs
├── Cargo.lock
├── Cargo.toml
├── Cargo.toml.orig
├── LICENSE-APACHE
├── LICENSE-MIT
├── README.md
└── src
    ├── backtrace.rs
    ├── chain.rs
    ├── context.rs
    ├── error.rs
    ├── fmt.rs
    ├── kind.rs
    ├── lib.rs
    ├── macros.rs
    └── wrapper.rs

1 directory, 16 files
$ tokei --exclude target --exclude tests
-------------------------------------------------------------------------------
 Language            Files        Lines         Code     Comments       Blanks
-------------------------------------------------------------------------------
 Markdown                1          163          163            0            0
 Rust                   10         2257         1140          932          185
 TOML                    1           37           21           11            5
-------------------------------------------------------------------------------
 Total                  12         2457         1324          943          190
-------------------------------------------------------------------------------
```

We can also do a quick search for `"unsafe"` to see how much `unsafe` code there
is and how it's being used.

```console
$ rg unsafe --glob '!target'
src/error.rs
90:        unsafe { Error::construct(error, vtable, backtrace) }
111:        unsafe { Error::construct(error, vtable, backtrace) }
132:        unsafe { Error::construct(error, vtable, backtrace) }
154:        unsafe { Error::construct(error, vtable, backtrace) }
176:        unsafe { Error::construct(error, vtable, backtrace) }
184:    unsafe fn construct<E>(
285:        unsafe { Error::construct(error, vtable, backtrace) }
366:        unsafe {
434:        unsafe {
448:        unsafe {
498:        unsafe {
510:    object_drop: unsafe fn(Box<ErrorImpl<()>>),
511:    object_ref: unsafe fn(&ErrorImpl<()>) -> &(dyn StdError + Send + Sync + 'static),
513:    object_mut: unsafe fn(&mut ErrorImpl<()>) -> &mut (dyn StdError + Send + Sync + 'static),
514:    object_boxed: unsafe fn(Box<ErrorImpl<()>>) -> Box<dyn StdError + Send + Sync + 'static>,
515:    object_downcast: unsafe fn(&ErrorImpl<()>, TypeId) -> Option<NonNull<()>>,
516:    object_drop_rest: unsafe fn(Box<ErrorImpl<()>>, TypeId),
520:unsafe fn object_drop<E>(e: Box<ErrorImpl<()>>) {
528:unsafe fn object_drop_front<E>(e: Box<ErrorImpl<()>>, target: TypeId) {
538:unsafe fn object_ref<E>(e: &ErrorImpl<()>) -> &(dyn StdError + Send + Sync + 'static)
548:unsafe fn object_mut<E>(e: &mut ErrorImpl<()>) -> &mut (dyn StdError + Send + Sync + 'static)
557:unsafe fn object_boxed<E>(e: Box<ErrorImpl<()>>) -> Box<dyn StdError + Send + Sync + 'static>
566:unsafe fn object_downcast<E>(e: &ErrorImpl<()>, target: TypeId) -> Option<NonNull<()>>
583:unsafe fn context_downcast<C, E>(e: &ErrorImpl<()>, target: TypeId) -> Option<NonNull<()>>
603:unsafe fn context_drop_rest<C, E>(e: Box<ErrorImpl<()>>, target: TypeId)
626:unsafe fn context_chain_downcast<C>(e: &ErrorImpl<()>, target: TypeId) -> Option<NonNull<()>>
643:unsafe fn context_chain_drop_rest<C>(e: Box<ErrorImpl<()>>, target: TypeId)
693:        unsafe { &*(self as *const ErrorImpl<E> as *const ErrorImpl<()>) }
701:        unsafe { &*(self.vtable.object_ref)(self) }
708:        unsafe { &mut *(self.vtable.object_mut)(self) }
762:        unsafe {
```

It looks like all the `unsafe` code is in `src/error.rs` and the frequent
references to a `vtable` indicate this is probably related to some sort of
hand-coded trait object.

## Beginning the Review

We'll start off the review by checking out `lib.rs`.

After scrolling past almost 200 lines of top-level docs we come across our first
interesting block of code.

```rust
// src/lib.rs

mod alloc {
    #[cfg(not(feature = "std"))]
    extern crate alloc;

    #[cfg(not(feature = "std"))]
    pub use alloc::boxed::Box;

    #[cfg(feature = "std")]
    pub use std::boxed::Box;
}
```

Now the code itself is quite boring, but the fact that it exists says a lot
about this crate. Namely that they're going to great lengths to ensure `anyhow`
is usable without the standard library.

~~This `alloc` module allows code to use `crate::alloc::Box` when boxing things
instead of relying on the `Box` added to the prelude by `std` (which isn't in
the prelude for `#[no_std]` crates).~~

**EDIT: *@dtolnay* has [pointed out][comment] the previous interpretation of the
`alloc` module is incorrect:**

> FYI this isn't the main reason. We could do `extern crate alloc`
> unconditionally and use `alloc::boxed::Box` even in std mode, and get the
> same effect. But that only works on 1.36+. The more verbose setup is
> necessary in order for `anyhow` in std mode to support back to 1.34+.

You can also see they're providing a polyfill for `std::error::Error` when
compiled without the standard library.

```rust
// src/lib.rs

#[cfg(feature = "std")]
use std::error::Error as StdError;

#[cfg(not(feature = "std"))]
trait StdError: Debug + Display {
    fn source(&self) -> Option<&(dyn StdError + 'static)> {
        None
    }
}
```

Next comes the declaration for `Error` itself.

<a name="error-decl"></a>

```rust
// lib.rs

pub struct Error {
    inner: ManuallyDrop<Box<ErrorImpl<()>>>,
}
```

One of the distinctions raised in `Error`'s documentation is that it's
represented using a narrow pointer. It looks like `ErrorImpl<()>` is a concrete
struct which holds all the implementation details for `Error`.

The `ManuallyDrop` is certainly interesting. Straight away this tells me that
`Error` will be explicitly implementing `Drop` and probably doing some `unsafe`
shenanigans to make sure our `ErrorImpl` is destroyed properly.

I'll jump down to around line 540 where things start getting interesting again.

```rust
// lib.rs

pub trait Context<T, E>: context::private::Sealed {
    /// Wrap the error value with additional context.
    fn context<C>(self, context: C) -> Result<T, Error>
    where
        C: Display + Send + Sync + 'static;

    /// Wrap the error value with additional context that is evaluated lazily
    /// only once an error does occur.
    fn with_context<C, F>(self, f: F) -> Result<T, Error>
    where
        C: Display + Send + Sync + 'static,
        F: FnOnce() -> C;
}
```

This is the declaration for the `Context` trait. It's a helper for converting
something like `Result<T, E>` or `Option<T>` into a `Result<T, Error>`.

Notably, the trait uses [the Sealed Pattern][sealed] so it's impossible for
downstream users to implement `Context` on their own types. Presumably this is
to allow `Context` to be extended in the future without breaking backwards
compatibility.

Sealing a trait can also be used to ensure it is only implemented for a specific
set of types or to ensure a particular invariant is upheld, but that's probably
not the case here.

Finally, we get to a peculiar `private` module at the bottom of the file.

```rust
// src/lib.rs

// Not public API. Referenced by macro-generated code.
#[doc(hidden)]
pub mod private {
    use crate::Error;
    use core::fmt::{Debug, Display};

    #[cfg(backtrace)]
    use std::backtrace::Backtrace;

    pub use core::result::Result::Err;

    #[doc(hidden)]
    pub mod kind {
        pub use crate::kind::{AdhocKind, TraitKind};

        #[cfg(feature = "std")]
        pub use crate::kind::BoxedKind;
    }

    pub fn new_adhoc<M>(message: M) -> Error
    where
        M: Display + Debug + Send + Sync + 'static,
    {
        Error::from_adhoc(message, backtrace!())
    }
}
```

It looks like code generated by macros will use the `private` module when
constructing errors (i.e. by calling `$crate::private::new_adhoc()`).

## The Real Meat and Potatoes

Now we've checked out `lib.rs`, the use of `ManuallyDrop` has made me curious
to see how `Error` is implemented under the hood.

It looks like `error.rs` contains the majority of this crate's functionality.
Weighing in at a whopping 794 lines with 30 uses of the `unsafe` keyword, this
may take a while...

So while you were reading through the previous section I decided to be sneaky
and skip ahead to get a brief overview of how `Error` is implemented.

Before we go any further it's worth knowing the `ErrorImpl` type's definition
because we'll be doing some `unsafe` shenanigans which rely on its layout in
subtle ways.

```rust
// src/error.rs line 670

// repr C to ensure that E remains in the final position.
#[repr(C)]
pub(crate) struct ErrorImpl<E> {
    vtable: &'static ErrorVTable,
    backtrace: Option<Backtrace>,
    // NOTE: Don't use directly. Use only through vtable. Erased type may have
    // different alignment.
    _object: E,
}
```

The `#[repr(C)]` attribute is a dead giveaway that the order of fields is
important. From the comments we can assume that `unsafe` code will be relying
on the fact that the first two fields are a vtable and a backtrace.

The leading `_` in `_object` indicates it's even more private than a normal
non-`pub` field. Trying to access it without the right checks will probably
lead to a bad time.

## Constructing an `Error`

The first chunk of code in `error.rs` lets us create an `Error` from a
`std::error::Error`.

```rust
// src/lib.rs line 20

impl Error {
    #[cfg(feature = "std")]
    pub fn new<E>(error: E) -> Self
    where
        E: StdError + Send + Sync + 'static,
    {
        let backtrace = backtrace_if_absent!(error);
        Error::from_std(error, backtrace)
    }

    ...
}
```

At first I was confused about the `#[cfg(feature = "std")]`. If `StdError` is
just an alias for `std::error::Error` then this is just equivalent to
`where E: std::error::Error`, isn't it?

Well... not exactly. While `StdError` is an alias to `std::error::Error` when
compiled against the standard library, in `#[no_std]` environments it's a
private adapter trait called `StdError`. If we dropped the conditional
compilation then we'd have a private type in a public interface, which, is
likely to confuse developers and leak implementation details (most people would
look through the source code to find the definition of `StdError`).

The `backtrace_if_absent!()` macro will crate a backtrace if the `backtrace`
feature flag (which unlocks the nightly-only `std::backtrace::Backtrace` type)
is provided.

```rust
// src/backtrace.rs

#[cfg(backtrace)]
macro_rules! backtrace_if_absent {
    ($err:expr) => {
        match $err.backtrace() {
            Some(_) => None,
            None => Some(Backtrace::capture()),
        }
    };
}

#[cfg(all(feature = "std", not(backtrace)))]
macro_rules! backtrace_if_absent {
    ($err:expr) => {
        None
    };
}
```

Next we have a way to create an `Error` using something `Display`-able.

```rust
// src/error.rs line 67

impl Error {
    pub fn msg<M>(message: M) -> Self
    where
        M: Display + Debug + Send + Sync + 'static,
    {
        Error::from_adhoc(message, backtrace!())
    }
}
```

Nothing to see here... Next up is `Error::from_std()`.

```rust
// src/error.rs line 74

impl Error {
    #[cfg(feature = "std")]
    pub(crate) fn from_std<E>(error: E, backtrace: Option<Backtrace>) -> Self
    where
        E: StdError + Send + Sync + 'static,
    {
        let vtable = &ErrorVTable {
            object_drop: object_drop::<E>,
            object_ref: object_ref::<E>,
            #[cfg(feature = "std")]
            object_mut: object_mut::<E>,
            object_boxed: object_boxed::<E>,
            object_downcast: object_downcast::<E>,
            object_drop_rest: object_drop_front::<E>,
        };

        // Safety: passing vtable that operates on the right type E.
        unsafe { Error::construct(error, vtable, backtrace) }
    }
}
```

Well that got complicated fast!

Remember that `vtable` we mentioned earlier? It looks like this code creates a
vtable for working with our `E` type.

Before we delve deeper into what the code is doing, let's have a look at the
`ErrorVTable` struct.

```rust
// src/error.rs line 509

struct ErrorVTable {
    object_drop: unsafe fn(Box<ErrorImpl<()>>),
    object_ref: unsafe fn(&ErrorImpl<()>) -> &(dyn StdError + Send + Sync + 'static),
    #[cfg(feature = "std")]
    object_mut: unsafe fn(&mut ErrorImpl<()>) -> &mut (dyn StdError + Send + Sync + 'static),
    object_boxed: unsafe fn(Box<ErrorImpl<()>>) -> Box<dyn StdError + Send + Sync + 'static>,
    object_downcast: unsafe fn(&ErrorImpl<()>, TypeId) -> Option<NonNull<()>>,
    object_drop_rest: unsafe fn(Box<ErrorImpl<()>>, TypeId),
}
```

This type contains a bunch of function pointers for working with an
`ErrorImpl<()>`. Note that this **isn't** a `ErrorImpl<E>`.

If you look back [at the definition for `Error`](#error-decl), the `Error`
contains a `ManuallyDrop<Box<ErrorImpl<()>>>`. From this we can see the author
is effectively rolling their own trait object system, except instead of using
fat pointers like Rust normally would, we've got a thin pointer to something
with a vtable followed by some common data and then the concrete type... Which
is almost identical to how C++ implements dynamic dispatch.

{{% notice tip %}}
If you want to explore this in more detail you'll probably find [C++ vtables
- Part 1 - Basics][article] interesting. It explores how clang has implemented
classes with virtual methods, even running code under a debugger and inspecting
the layout in memory at runtime.

[article]: https://shaharmike.com/cpp/vtable-part1/
{{% /notice %}}

Populating the `ErrorVTable` is done by "instantiating" some generic functions
to get versions which will work for our `E` type (e.g. `object_drop::<E>`).

{{% notice info %}}
Let me know if you've got a better ELI5 explanation for the phrase
*"instantiation"*, as used here. Preferably without using type theory jargon.

You can think of the name for a generic function (e.g. `fn foo<F>()`) as
something which, when given a type argument using turbofish (`::<F>`) will give
you a copy of `foo` which is tailored precisely for `F`. *"Instantiating"* is
the technical term for this.
{{% /notice %}}

The vtable functions themselves are mostly quite benign. For the most part
they're just shims to help with downcasting or implementing the drop glue
that `rustc` might otherwise provide.

We'll get back to `object_drop_rest()` later.

The `Safety:` note before `Error::from_std()`'s `unsafe` block is important
here. It communicates to readers what they've done to ensure the use of
`unsafe` is sound, mentioning how particular invariants have been upheld (in
this case, that the vtable can be used with `E`).

```rust
// src/error.rs line 93

impl Error {
    ...

    pub(crate) fn from_adhoc<M>(message: M, backtrace: Option<Backtrace>) -> Self
    where
        M: Display + Debug + Send + Sync + 'static,
    {
        use crate::wrapper::MessageError;
        let error: MessageError<M> = MessageError(message);
        let vtable = &ErrorVTable {
            object_drop: object_drop::<MessageError<M>>,
            object_ref: object_ref::<MessageError<M>>,
            #[cfg(feature = "std")]
            object_mut: object_mut::<MessageError<M>>,
            object_boxed: object_boxed::<MessageError<M>>,
            object_downcast: object_downcast::<M>,
            object_drop_rest: object_drop_front::<M>,
        };

        // Safety: MessageError is repr(transparent) so it is okay for the
        // vtable to allow casting the MessageError<M> to M.
        unsafe { Error::construct(error, vtable, backtrace) }
    }

    ...
}
```

The `Error::from_adhoc()` is mostly identical except for the `MessageError`
bit.

If you're paying attention, you may have noticed that we use
`MessageError<M>` for things like `object_drop::<MessageError<M>>`, but `M`
in `object_downcast::<M>`. That seems a little... odd... Let's have a peek at
`MessageError`'s definition.

```rust
// src/wrapper.rs

#[repr(transparent)]
pub struct MessageError<M>(pub M);
```

The `#[repr(transparent)]` attribute's raison d'être as mentioned [in the
Nomicon][repr-transparent] is to ensure `M` and `MessageError<M>` are identical
in memory and are interchangeable without breaking things at the ABI level.

> This can only be used on structs with a single non-zero-sized field (there
> may be additional zero-sized fields). The effect is that the layout and ABI
> of the whole struct is guaranteed to be the same as that one field.
>
> The goal is to make it possible to transmute between the single field and the
> struct. An example of that is `UnsafeCell`, which can be transmuted into the
> type it wraps.
>
> Also, passing the struct through FFI where the inner field type is expected
> on the other side is guaranteed to work. In particular, this is necessary for
> struct `Foo(f32)` to always have the same ABI as `f32`.

The `MessageError` type doesn't seem to add any extra invariants or
assumptions on our `E` type so using `object_downcast::<M>` instead of
`object_downcast::<MessageError<M>>` for downcasting should be perfectly fine.

{{% notice note %}}
I originally created [a pull request][anyhow-61] to add extra comments around
this and update `object_drop_front` to use
`object_drop_front::<MessageError<M>>` instead of `object_drop_front::<M>`,
the reasoning being that we're technically dropping the front fields in a
`ErrorImpl<MessageError<M>>>` and not `ErrorImpl<M>>`. Even if the `_object` (a
`MessageError<M>` never gets touched).

That PR was eventually closed because, as *@dtolnay* pointed out, the current
code is still sound and the various `object_drop_front` methods are a sort of
downcast (you can [check out the PR][anyhow-61] for more).

I'd also like to draw attention to an aspect of the open-source community
many people take for granted, or just never notice... Even though my PR was
eventually rejected, the maintainer still took the time to make a review and
explain their reasoning behind the decision in a courteous manner.

[anyhow-61]: https://github.com/dtolnay/anyhow/issues/61
{{% /notice %}}

We can skim past the `Error::from_display()`, `Error::from_context()`, and
`Error::from_boxed()` constructors because their implementations are almost
identical, although use different wrapper types (like `MessageError`) so we
can accept different inputs.

Finally we reach the `Error::construct()` method...

```rust
// src/error.rs line 185

impl Error {
    ...

    unsafe fn construct<E>(
        error: E,
        vtable: &'static ErrorVTable,
        backtrace: Option<Backtrace>,
    ) -> Self
    where
        E: StdError + Send + Sync + 'static,
    {
        let inner = Box::new(ErrorImpl {
            vtable,
            backtrace,
            _object: error,
        });
        // Erase the concrete type of E from the compile-time type system. This
        // is equivalent to the safe unsize coersion from Box<ErrorImpl<E>> to
        // Box<ErrorImpl<dyn StdError + Send + Sync + 'static>> except that the
        // result is a thin pointer. The necessary behavior for manipulating the
        // underlying ErrorImpl<E> is preserved in the vtable provided by the
        // caller rather than a builtin fat pointer vtable.
        let erased = mem::transmute::<Box<ErrorImpl<E>>, Box<ErrorImpl<()>>>(inner);
        let inner = ManuallyDrop::new(erased);
        Error { inner }
    }

    ...
}
```

This is the main constructor for our `Error` type. Its main purpose is to
allocate the vtable, a backtrace, and our error object on the heap and "unsize"
it.

Normally whenever I see people using `mem::transmute()` being used my
knee-jerk reaction is that they're trying to side-step the type system
([obligatory rust koan reference][obstacles]) and, to be fair, that's exactly
what this code is trying to do.

However the difference between `anyhow` and a newbie trying to trick the
borrow checker is we've deliberately chosen to take on the responsibility for
maintaining correctness and designed `Error`'s API and `ErrorImpl` so all
operations are done using vtables for the correct underlying type (who's
construction we have full control over).

Next we come to the `Error::context()` method. It's a decorator method for
wrapping an `Error` with additional contextual information, and almost identical
to `Error::from_adhoc()` and friends.

```rust
// src/error.rs line 263

impl Error {
    ...

    pub fn context<C>(self, context: C) -> Self
    where
        C: Display + Send + Sync + 'static,
    {
        let error: ContextError<C, Error> = ContextError {
            context,
            error: self,
        };

        let vtable = &ErrorVTable {
            object_drop: object_drop::<ContextError<C, Error>>,
            object_ref: object_ref::<ContextError<C, Error>>,
            #[cfg(feature = "std")]
            object_mut: object_mut::<ContextError<C, Error>>,
            object_boxed: object_boxed::<ContextError<C, Error>>,
            object_downcast: context_chain_downcast::<C>,
            object_drop_rest: context_chain_drop_rest::<C>,
        };

        // As the cause is anyhow::Error, we already have a backtrace for it.
        let backtrace = None;

        // Safety: passing vtable that operates on the right type.
        unsafe { Error::construct(error, vtable, backtrace) }
    }

    ...
}
```

The main difference is we use custom `context_chain_downcast()` and
`context_chain_drop_rest()` functions. Presumably that's to allow callers to
access the `context` argument when downcasting, but we can investigate in
more depth when we get to those functions.

The next three methods seem to be fairly unremarkable. `Error::backtrace()` and
`Error::chain()` delegate to their respective methods on `inner` (which we'll
see soon enough) and `Error::root_cause()` is effectively trying to find the
last node in a linked list.

```rust
// src/error.rs line 300

impl Error {
    ...

    #[cfg(backtrace)]
    pub fn backtrace(&self) -> &Backtrace {
        self.inner.backtrace()
    }

    #[cfg(feature = "std")]
    pub fn chain(&self) -> Chain {
        self.inner.chain()
    }

    #[cfg(feature = "std")]
    pub fn root_cause(&self) -> &(dyn StdError + 'static) {
        let mut chain = self.chain();
        let mut root_cause = chain.next().unwrap();
        for cause in chain {
            root_cause = cause;
        }
        root_cause
    }

    ...
}
```

## Downcasting

Finally we've reached the code related to downcasting. While this feature is
one of the most useful tools `anyhow` provides it also has a lot of potential
for unsoundness and security issues because we're giving the caller a way to
reinterpret the data inside our `Error` as something else.

```rust
// src/error.rs line 354

impl Error {
    ...

    pub fn is<E>(&self) -> bool
    where
        E: Display + Debug + Send + Sync + 'static,
    {
        self.downcast_ref::<E>().is_some()
    }

    pub fn downcast<E>(self) -> Result<E, Self>
    where
        E: Display + Debug + Send + Sync + 'static,
    {
        let target = TypeId::of::<E>();
        unsafe {
            // Use vtable to find NonNull<()> which points to a value of type E
            // somewhere inside the data structure.
            let addr = match (self.inner.vtable.object_downcast)(&self.inner, target) {
                Some(addr) => addr,
                None => return Err(self),
            };

            // Prepare to read E out of the data structure. We'll drop the rest
            // of the data structure separately so that E is not dropped.
            let outer = ManuallyDrop::new(self);

            // Read E from where the vtable found it.
            let error = ptr::read(addr.cast::<E>().as_ptr());

            // Read Box<ErrorImpl<()>> from self. Can't move it out because
            // Error has a Drop impl which we want to not run.
            let inner = ptr::read(&outer.inner);
            let erased = ManuallyDrop::into_inner(inner);

            // Drop rest of the data structure outside of E.
            (erased.vtable.object_drop_rest)(erased, target);

            Ok(error)
        }
    }

    ...
}
```

Something I really like is how the author took the time to explain each step
of the downcasting code, as well as the assumptions they're making.

The purpose of downcasting is to extract the underlying error if it is an
instance of `E`, dropping the other metadata that `ErrorImpl` adds. If the type
check fails then the original `Error` is returned.

The first step is to get a pointer to our `E`, if it's the correct type.

```rust
// Use vtable to find NonNull<()> which points to a value of type E
// somewhere inside the data structure.
let addr = match (self.inner.vtable.object_downcast)(&self.inner, target) {
    Some(addr) => addr,
    None => return Err(self),
};
```

The `object_downcast` method will return a `NonNull<()>` pointer if `_object`
has the same `TypeId` as `target`, allowing us to do the type checking and
retrieve a pointer to the inner data in one step.

Keep in mind `addr` is still a pointer to *something* (`NonNull<()>`, or
`void *` in C parlance).

Next we put `self` inside a `ManuallyDrop` because it's about to be manually
*destructured*. This also helps to ensure that `Error`'s destructor will never
be run... After all, if you're extracting bits and pieces from a type and the
destructor would normally free those bits and pieces, if the destructor runs
you're gonna have a bad time.

```rust
// Prepare to read E out of the data structure. We'll drop the rest
// of the data structure separately so that E is not dropped.
let outer = ManuallyDrop::new(self);
```

We now get to the actual destructuring of the `Error`'s inner field into a
`E` and `ManuallyDrop<Box<ErrorImpl<()>>>`. As already mentioned, this needs
to be done using raw pointer operations.

```rust
// Read E from where the vtable found it.
let error = ptr::read(addr.cast::<E>().as_ptr());

// Read Box<ErrorImpl<()>> from self. Can't move it out because
// Error has a Drop impl which we want to not run.
let inner = ptr::read(&outer.inner);
let erased = ManuallyDrop::into_inner(inner);
```

If you remember the `ErrorImpl` type's definition there were three fields;
`vtable`, `backtrace`, and `_object`. We've already extracted `_object` and will
be returning that to the caller so there's nothing more we need to do about it,
however the `vtable` and `backtrace` fields will need to be destroyed somehow.

We can't just call the destructor for `ErrorImpl` because that would also
destroy our `_object` (which would be bad), instead we need to use the special
`object_drop_rest()` function from the `vtable`.

```rust
// Drop rest of the data structure outside of E.
(erased.vtable.object_drop_rest)(erased, target);
```

And finally we've cleaned everything up and can return the downcasted `error`.

```rust
    ...
    Ok(error)
}
```

Phew 😓

Compared to `Error::downcast()` which needed to manage memory and manually
implement destructuring, `Error::downcast_ref()` and `Error::downcast_mut()`
*"just"* need to do a type check and return a pointer to the underlying
*`_object`.

```rust
// src/error.rs line 430

impl Error {
    ...

    pub fn downcast_ref<E>(&self) -> Option<&E>
    where
        E: Display + Debug + Send + Sync + 'static,
    {
        let target = TypeId::of::<E>();
        unsafe {
            // Use vtable to find NonNull<()> which points to a value of type E
            // somewhere inside the data structure.
            let addr = (self.inner.vtable.object_downcast)(&self.inner, target)?;
            Some(&*addr.cast::<E>().as_ptr())
        }
    }

    pub fn downcast_mut<E>(&mut self) -> Option<&mut E>
    where
        E: Display + Debug + Send + Sync + 'static,
    {
        let target = TypeId::of::<E>();
        unsafe {
            // Use vtable to find NonNull<()> which points to a value of type E
            // somewhere inside the data structure.
            let addr = (self.inner.vtable.object_downcast)(&self.inner, target)?;
            Some(&mut *addr.cast::<E>().as_ptr())
        }
    }
}
```

The first thing to note is our vtable's `object_downcast()` function is in
charge of the type checking. It looks like this is implemented to allow
extracting the context object passed to `Error::context()` and other wrapper
functions, as well as the underlying error type.

When you think about it, this is pretty clever. It means you can ask for
*something* of the desired and if the underlying error has a field with that
type, you'll get a pointer to it.

There's a lot of pointer casting going on at the end, so I'll spread it out
over multiple lines for demonstration purposes.

```rust
let addr: NonNull<()> = /* get a pointer to some E field or bail if None */;
let e_addr: NonNull<E> = addr.cast();
let e_ptr: *mut E = e_addr.as_ptr();
let e_ref: &E = &*e_ptr;
return Some(e_ref);
```

LGTM 👍

## Giving Error a Destructor

All these shenanigans with vtables and unsized types mean we need to make sure
`Error`'s `inner` field (`ManuallyDrop<ErrorImpl<()>>`) is destroyed properly
when `Error` is dropped.

```rust
// src/error.rs line 497

impl Drop for Error {
    fn drop(&mut self) {
        unsafe {
            // Read Box<ErrorImpl<()>> from self.
            let inner = ptr::read(&self.inner);
            let erased = ManuallyDrop::into_inner(inner);

            // Invoke the vtable's drop behavior.
            (erased.vtable.object_drop)(erased);
        }
    }
}
```

Compared to what we needed to do while downcasting, implementing `Drop` seems
rather simple.

The `inner` field is a `ManuallyDrop` type so we need to extract the underlying
`ErrorImpl<()>`. The problem is you can't use normal destructuring
(`let Error { inner } = self`) because that would move `inner` and call
`Error`'s destructor, so we fall back to raw pointer operations.

Once we've extracted the erased `ErrorImpl<()>` we can use a vtable method we
prepared earlier to do the appropriate cleanup.

{{% notice info %}}
As a bit of trivia, you may have noticed that `ErrorImpl<()>` variables tend
to be called `erased`. This is because the underlying error type has been
"erased" at compile time (and is only known at runtime).
{{% /notice %}}

## Deconstructing the vtable

The largest source of `unsafe` code in `anyhow` is related to `ErrorImpl<E>`,
with the library heavily relying on a correctly implemented `ErrorVTable` to be
sound.

```rust
// src/error.rs line 510

struct ErrorVTable {
    object_drop: unsafe fn(Box<ErrorImpl<()>>),
    object_ref: unsafe fn(&ErrorImpl<()>) -> &(dyn StdError + Send + Sync + 'static),
    #[cfg(feature = "std")]
    object_mut: unsafe fn(&mut ErrorImpl<()>) -> &mut (dyn StdError + Send + Sync + 'static),
    object_boxed: unsafe fn(Box<ErrorImpl<()>>) -> Box<dyn StdError + Send + Sync + 'static>,
    object_downcast: unsafe fn(&ErrorImpl<()>, TypeId) -> Option<NonNull<()>>,
    object_drop_rest: unsafe fn(Box<ErrorImpl<()>>, TypeId),
}
```

The `ErrorVTable` type contains function pointers for each operation that
involves the `ErrorImpl`'s `_object` field.

As we've seen from the various comments the author made when calling
`Error::construct()`, these functions are all `unsafe` because they rely on
being passed some sort of pointer to `ErrorImpl<E>` masquerading as a
`ErrorImpl<()>`.

To change things up a bit, instead of scrolling through the file from top to
bottom I'll review the next several `unsafe` functions grouped by the vtable
method they belong to.

```rust
// src/error.rs

struct ErrorVTable {
    object_drop: unsafe fn(Box<ErrorImpl<()>>),
    ...
}

// (line 520)
// Safety: requires layout of *e to match ErrorImpl<E>.
unsafe fn object_drop<E>(e: Box<ErrorImpl<()>>) {
    // Cast back to ErrorImpl<E> so that the allocator receives the correct
    // Layout to deallocate the Box's memory.
    let unerased = mem::transmute::<Box<ErrorImpl<()>>, Box<ErrorImpl<E>>>(e);
    drop(unerased);
}
```

There is only one function used for `ErrorVTable::object_drop`, unsurprisingly
called `object_drop()`. This just transmutes the `Box<ErrorImpl<()>>` back to
its actual type (reversing the original *"unsizing"* operation) and explicitly
destroys the value.

The method relies on our `e` parameter actually pointing to a `ErrorImpl<E>`,
but that invariant should be upheld by whoever is constructing the vtable.

```rust
// src/error.rs

struct ErrorVTable {
    ...
    object_ref: unsafe fn(&ErrorImpl<()>) -> &(dyn StdError + Send + Sync + 'static),
    ...
}

// (line 538)
// Safety: requires layout of *e to match ErrorImpl<E>.
unsafe fn object_ref<E>(e: &ErrorImpl<()>) -> &(dyn StdError + Send + Sync + 'static)
where
    E: StdError + Send + Sync + 'static,
{
    // Attach E's native StdError vtable onto a pointer to self._object.
    &(*(e as *const ErrorImpl<()> as *const ErrorImpl<E>))._object
}
```

The `ErrorVTable::object_ref` method is in charge of converting a
`&ErrorImpl<()>` to a `&ErrorImpl<E>`, and then accessing the `_object` as a
`&dyn StdError` trait object.

Again, assuming the `e` actually points to a `&ErrorImpl<E>` and `E` implements
`StdError` (which it does), this is perfectly safe.

```rust
// src/error.rs

struct ErrorVTable {
    ...
    #[cfg(feature = "std")]
    object_mut: unsafe fn(&mut ErrorImpl<()>) -> &mut (dyn StdError + Send + Sync + 'static),
    ...
}

// (line 547)
// Safety: requires layout of *e to match ErrorImpl<E>.
#[cfg(feature = "std")]
unsafe fn object_mut<E>(e: &mut ErrorImpl<()>) -> &mut (dyn StdError + Send + Sync + 'static)
where
    E: StdError + Send + Sync + 'static,
{
    // Attach E's native StdError vtable onto a pointer to self._object.
    &mut (*(e as *mut ErrorImpl<()> as *mut ErrorImpl<E>))._object
}
```

The `object_mut` method is the same as `object_ref`, except returning a mutable
reference.

I'm not 100% sure why this method needs a `#[cfg(feature = "std")]` feature
gate, possible reasons are:

- The `StdError` polyfill on `#[no_std]` platforms doesn't support downcasting
  but the `std::error::Error` version does
- To prevent exposing the `StdError` polyfill as part of the public API for
  `#[no_std]` users (the `StdError` trait is actually a private type)

I'd be keen to hear from someone who knows the reasoning behind this design
decision.

```rust
// src/error.rs

struct ErrorVTable {
    ...
    object_boxed: unsafe fn(Box<ErrorImpl<()>>) -> Box<dyn StdError + Send + Sync + 'static>,
    ...
}

// (line 557)
// Safety: requires layout of *e to match ErrorImpl<E>.
unsafe fn object_boxed<E>(e: Box<ErrorImpl<()>>) -> Box<dyn StdError + Send + Sync + 'static>
where
    E: StdError + Send + Sync + 'static,
{
    // Attach ErrorImpl<E>'s native StdError vtable. The StdError impl is below.
    mem::transmute::<Box<ErrorImpl<()>>, Box<ErrorImpl<E>>>(e)
}
```

The `ErrorVtable::object_boxed` method is pretty subtle. Unlike `object_ref` and
`object_mut` which were just extracting references to the `_object` field as
trait methods, `object_boxed` involves ownership and misusing it could result
in memory leaks or double-frees (as well as the usual problems related to
`unsafe` casting).

To review this properly we'll need to see how it's used.

As far as I can tell, `object_boxed` exists purely so we can convert a `Error`
into a `Box<dyn std::error::Error>` (e.g. for use with `?`).

```rust
// src/error.rs line 760

impl From<Error> for Box<dyn StdError + Send + Sync + 'static> {
    fn from(error: Error) -> Self {
        let outer = ManuallyDrop::new(error);
        unsafe {
            // Read Box<ErrorImpl<()>> from error. Can't move it out because
            // Error has a Drop impl which we want to not run.
            let inner = ptr::read(&outer.inner);
            let erased = ManuallyDrop::into_inner(inner);

            // Use vtable to attach ErrorImpl<E>'s native StdError vtable for
            // the right original type E.
            (erased.vtable.object_boxed)(erased)
        }
    }
}
```

We've seen code like this before. It's manually destructuring an `Error` to
retrieve the `inner` field, making sure not to drop the original `Error` (which
would destroy `inner`).

From there, it looks like `object_boxed` takes the `Box<ErrorImpl<()>>` and casts
it back to a `Box<ErrorImpl<E>>`, then if `ErrorImpl<E>` implements `StdError`
(spoiler: it does) the compiler will automatically cast our `Box<ErrorImpl<E>>`
to the `Box<dyn StdError>` trait object.

There's a lot of casting going on, but by looking at the implementation of
`object_boxed` and how it gets used we're able to confirm there's nothing fishy
going on... Well there's a lot of clever `unsafe` shenanigans going on, but to
the best of my knowledge it all seems correct.

Finally we're getting to the pointy end of `ErrorVTable`. This crate's
downcasting support deserves a bit of extra scrutiny because it lets callers
reinterpret `_object` as an arbitrary type, with `anyhow` taking on the burden
of type checking.

Sure you could use `object_ref` and the `downcast()` methods on
`std::error::Error` for downcasting, but that was implemented by the folks
behind the Rust standard library (with a much higher standard for reviews and
code quality!), and even that [took a couple tries][error-type-id] to get
right...

```rust
// src/error.rs

struct ErrorVTable {
    ...
    object_downcast: unsafe fn(&ErrorImpl<()>, TypeId) -> Option<NonNull<()>>,
    ...
}

// (line 566)
// Safety: requires layout of *e to match ErrorImpl<E>.
unsafe fn object_downcast<E>(e: &ErrorImpl<()>, target: TypeId) -> Option<NonNull<()>>
where
    E: 'static,
{
    if TypeId::of::<E>() == target {
        // Caller is looking for an E pointer and e is ErrorImpl<E>, take a
        // pointer to its E field.
        let unerased = e as *const ErrorImpl<()> as *const ErrorImpl<E>;
        let addr = &(*unerased)._object as *const E as *mut ();
        Some(NonNull::new_unchecked(addr))
    } else {
        None
    }
}

// (line 582)
// Safety: requires layout of *e to match ErrorImpl<ContextError<C, E>>.
#[cfg(feature = "std")]
unsafe fn context_downcast<C, E>(e: &ErrorImpl<()>, target: TypeId) -> Option<NonNull<()>>
where
    C: 'static,
    E: 'static,
{
    if TypeId::of::<C>() == target {
        let unerased = e as *const ErrorImpl<()> as *const ErrorImpl<ContextError<C, E>>;
        let addr = &(*unerased)._object.context as *const C as *mut ();
        Some(NonNull::new_unchecked(addr))
    } else if TypeId::of::<E>() == target {
        let unerased = e as *const ErrorImpl<()> as *const ErrorImpl<ContextError<C, E>>;
        let addr = &(*unerased)._object.error as *const E as *mut ();
        Some(NonNull::new_unchecked(addr))
    } else {
        None
    }
}

// (line 626)
// Safety: requires layout of *e to match ErrorImpl<ContextError<C, Error>>.
unsafe fn context_chain_downcast<C>(e: &ErrorImpl<()>, target: TypeId) -> Option<NonNull<()>>
where
    C: 'static,
{
    if TypeId::of::<C>() == target {
        let unerased = e as *const ErrorImpl<()> as *const ErrorImpl<ContextError<C, Error>>;
        let addr = &(*unerased)._object.context as *const C as *mut ();
        Some(NonNull::new_unchecked(addr))
    } else {
        // Recurse down the context chain per the inner error's vtable.
        let unerased = e as *const ErrorImpl<()> as *const ErrorImpl<ContextError<C, Error>>;
        let source = &(*unerased)._object.error;
        (source.inner.vtable.object_downcast)(&source.inner, target)
    }
}
```

The basic `object_downcast()` function seems fairly reasonable, if the type
we're trying to downcast to (`target`) matches the type this vtable was created
for (`E`), the type check passes and we can return a pointer to `_object`.

I also really appreciate this comment:

> ```rust
> // Caller is looking for an E pointer and e is ErrorImpl<E>, take a
> // pointer to its E field.
> ```

While it's nothing we don't already know after having read through most of
the `error.rs` file in great detail, it's really useful to reiterate your
assumptions for someone who doesn't have that background knowledge.

Something that jumped out at me was this line:

```rust
let unerased = e as *const ErrorImpl<()> as *const ErrorImpl<E>;
let addr = &(*unerased)._object as *const E as *mut ();
```

We're starting off with an immutable reference (`&ErrorImpl<E>`) then borrowing
the `_object` field (immutably) and using pointer casts to get rid of the
`const`.

This sort of behaviour tends to raise the eyebrow of most seasoned
rustaceans, after all turning an `&T` into a `&mut T` is pure
*Undefined Behaviour* in Rust. [The Nomicon][nomicon-transmute] puts this
*really
well:

> - Transmuting an `&` to `&mut` is UB
>   - Transmuting an `&` to `&mut` is *always* UB
>   - No you can't do it
>   - No you're not special

However if you look carefully, we aren't actually turning a `&T` into a
`&mut T`, we're "only" turning it into a `*mut ()` and then the caller
(`Error::downcast()`) reads from the pointer. At no point do we turn the pointer
into a reference, and as [this StackOverflow question][so-question] points out,
the compiler makes absolutely no assumptions about a `*mut` pointer. Meaning
this use of pointer casting is perfectly fine **as long as we never convert the
`*mut T` to a `&mut T`**.

{{% notice note %}}
This pattern of retrieving a `*mut ()` pointer from a `&T` is fairly common
when `ErrorImpl<()>` is concerned, and we can employ the same reasoning at each
cast site.
{{% /notice %}}

{{% notice warning %}}
I was going to apply the same logic to `Error::downcast_mut()`, reasoning
that even though we return a `&mut E` it's still sound because we started off
with `self: &mut Error`. But `Error::downcast_mut()` passes a `&self.inner`
to the `object_downcast` method. The overall result is like taking an `&mut
Error` and getting a `&mut` reference to one of its fields, but we access the
field via `&self.inner`.

(here's the original code for reference)

```rust
impl Error {
    pub fn downcast_mut<E>(&mut self) -> Option<&mut E>
    where
        E: Display + Debug + Send + Sync + 'static,
    {
        let target = TypeId::of::<E>();
        unsafe {
            // Use vtable to find NonNull<()> which points to a value of type E
            // somewhere inside the data structure.
            let addr = (self.inner.vtable.object_downcast)(&self.inner, target)?;
            Some(&mut *addr.cast::<E>().as_ptr())
        }
    }
}
```

If you look at it in isolation and ignore the fact that `self` is borrowed
mutably, it looks like `Error::downcast_mut()` is passing an immutable
reference to `&self.inner` to the `object_downcast` function then casting the
returned pointer to `&mut E`... Is that sound?

I've created [a bug ticket][anyhow-62] for now and hopefully *@dtolnay* will
be able to shine more light on the situation. I also tried to create a
minimal reproducible example [on the playground][repro] but running it under
`miri` fails with an execution error:

```
   Compiling playground v0.0.1 (/playground)
error: Miri evaluation error: trying to reborrow for Unique, but parent tag <untagged> does not have an appropriate item in the borrow stack
  --> src/main.rs:15:13
   |
15 |             &mut *ptr.cast().as_ptr()
   |             ^^^^^^^^^^^^^^^^^^^^^^^^^ trying to reborrow for Unique, but parent tag <untagged> does not have an appropriate item in the borrow stack
   |
note: inside call to `TopLevel::get_field` at src/main.rs:32:20
  --> src/main.rs:32:20
   |
32 |     println!("{}", top_level.get_field());
   |                    ^^^^^^^^^^^^^^^^^^^^^
   = note: inside call to `main` at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/rt.rs:67:34
   = note: inside call to closure at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/rt.rs:52:73
   = note: inside call to closure at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/sys_common/backtrace.rs:129:5
   = note: inside call to `std::sys_common::backtrace::__rust_begin_short_backtrace::<[closure@DefId(1:6019 ~ std[8be3]::rt[0]::lang_start_internal[0]::{{closure}}[0]::{{closure}}[0]) 0:&dyn std::ops::Fn() -> i32 + std::marker::Sync + std::panic::RefUnwindSafe], i32>` at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/rt.rs:52:13
   = note: inside call to closure at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/panicking.rs:305:40
   = note: inside call to `std::panicking::r#try::do_call::<[closure@DefId(1:6018 ~ std[8be3]::rt[0]::lang_start_internal[0]::{{closure}}[0]) 0:&&dyn std::ops::Fn() -> i32 + std::marker::Sync + std::panic::RefUnwindSafe], i32>` at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/panicking.rs:281:13
   = note: inside call to `std::panicking::r#try::<i32, [closure@DefId(1:6018 ~ std[8be3]::rt[0]::lang_start_internal[0]::{{closure}}[0]) 0:&&dyn std::ops::Fn() -> i32 + std::marker::Sync + std::panic::RefUnwindSafe]>` at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/panic.rs:394:14
   = note: inside call to `std::panic::catch_unwind::<[closure@DefId(1:6018 ~ std[8be3]::rt[0]::lang_start_internal[0]::{{closure}}[0]) 0:&&dyn std::ops::Fn() -> i32 + std::marker::Sync + std::panic::RefUnwindSafe], i32>` at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/rt.rs:51:25
   = note: inside call to `std::rt::lang_start_internal` at /playground/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/src/rust/src/libstd/rt.rs:67:5
   = note: inside call to `std::rt::lang_start::<()>`

error: aborting due to previous error

error: could not compile `playground`.

To learn more, run the command again with --verbose.
```

The error message isn't the most intuitive, but I *think* this is saying we're
trying to borrow something mutably when we aren't allowed to? I don't know
enough about `miri` to say whether it's detected *Undefined Behaviour* or if
I've encountered a bug in `miri`'s evaluator.

[anyhow-62]: https://github.com/dtolnay/anyhow/issues/62
[repro]: https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=e328faa721f7a1ed3f9820712f2e7097
{{% /notice %}}

To analyse the `context_downcast()` function we'll want to remind ourselves of
the definition for `ContextError`.

```rust
// src/error.rs line 681

// repr C to ensure that ContextError<C, E> has the same layout as
// ContextError<ManuallyDrop<C>, E> and ContextError<C, ManuallyDrop<E>>.
#[repr(C)]
pub(crate) struct ContextError<C, E> {
    pub context: C,
    pub error: E,
}
```

We can see that a `ContextError` contains both a `context` and an `error`,
so when downcasting there are actually two types we can access.

If you think about it for a bit, this makes sense. Most users of `anyhow`
I've seen will use a `&'static str` or a `String` for the context, but it
seems quite reasonable to use something more complex. For example, imagine a
service attaching a summary of the request so developers can see what input
caused a particular error.

To that end, `context_downcast()` needs to do two type checks and return
a pointer to the appropriate field.

## Time Taken

## Conclusions

[sad-day]: https://words.steveklabnik.com/a-sad-day-for-rust
[crev]: https://github.com/crev-dev/crev
[clockify]: https://clockify.me/
[anyhow]: https://github.com/dtolnay/anyhow
[thiserror]: https://github.com/dtolnay/thiserror
[dtolnay]: https://github.com/dtolnay
[sealed]: https://rust-lang.github.io/api-guidelines/future-proofing.html#sealed-traits-protect-against-downstream-implementations-c-sealed
[unsize]: https://doc.rust-lang.org/std/marker/trait.Unsize.html
[repr-transparent]: https://doc.rust-lang.org/nomicon/other-reprs.html#reprtransparent
[obstacles]: https://users.rust-lang.org/t/rust-koans/2408
[comment]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/pull/8#pullrequestreview-345588595
[error-type-id]: https://blog.rust-lang.org/2019/05/13/Security-advisory.html
[nomicon-transmute]: https://doc.rust-lang.org/nomicon/transmutes.html
[so-question]: https://stackoverflow.com/questions/57364654/do-aliasing-mutable-raw-pointers-mut-t-cause-undefined-behaviour