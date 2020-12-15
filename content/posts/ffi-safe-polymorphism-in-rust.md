---
title: "FFI-Safe Polymorphism: Thin Trait Objects"
date: "2020-12-03T14:03:24+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
- FFI
toc: true
---

A while ago someone [posted a question][forum-post] on the Rust User Forums
asking how to achieve polymorphism in a C API and while lots of good
suggestions were made, I'd like to explore my take on things.

As a recap, Rust provides two mechanisms for letting you write code which will
work with multiple types. These are

- **Static Dispatch**, where the compiler will generate multiple copies of the
  function, tailor-made for each type and resolved at compile time, and
- **Dynamic Dispatch**, where we use an extra level of indirection to only
  resolve the actual implementation at runtime

While both mechanisms are extremely powerful and can cover almost all of your
needs in normal Rust code, they both have one drawback... The actual
mechanisms used are (deliberately) unspecified and not safe for FFI.

The concrete use case is looking for a FFI-safe equivalent of C's `FILE*`;
some writeable thing which doesn't care if it is backed by a real file on
disk, a network socket, an OS pipe, or an arbitrary piece of code that
consumes bytes. This `FILE*`-like type could then be instantiated by C and
used to initialise the logger in a Rust library.

Normally you'd just reach for a `Box<dyn std::io::Write>` here, but as we've
already mentioned Rust's trait objects aren't FFI-safe, meaning we need to be
a little more creative.

My solution takes inspiration from something I first discovered while
browsing the source code for [`anyhow::Error`][anyhow]. I wasn't able to find
a proper name for it, so I'm referring to this technique as *Thin Trait
Objects*.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/thin-trait-objects
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Alternate Solutions

Now before we go any further it is important to ask the question, *"do we
actually **need** to come up with a fancy solution here?"* This is especially
important if your solution will require writing `unsafe` code.

9 times out of 10 taking the more complicated option will require you to do
extra work that wasn't needed in the first place.

### Don't Allow Polymorphism

This is probably the simplest option. If you want to avoid complexity,
especially when already writing a Foreign Function Interface, don't do
polymorphism.

This could be as simple as hard-coding a simple implementation (i.e. if on
Linux, accept a file descriptor and write to that).

Another option would be to design your API to be more data-oriented. That way
the caller can write the custom logic in their own code instead of trying to
inject it into someone else's.

After all, the simplest code is no code.

### Pointer to Enum

If you have a finite set of possible implementations you can pass around a
pointer to an enum.

While more complex than the previous option, we're all familiar with the Rust
enum and how it enables a limited form of polymorphism.

### Double Indirection

The problem with passing around a normal trait object (e.g. `Box<dyn Trait>`
or `*mut dyn Trait`) is that you need space for two pointers, one for the
data and one for a vtable that operates on the data.

The problem is that Rust trait objects don't have a stable ABI so we can't pass
`Box<dyn Trait>` by value across the FFI boundary.

However, what about a pointer to a `Box<dyn Trait>`? A `Box<Box<dyn Trait>>` is
the size of a single pointer and can be passed around just fine using
`Box::into_raw()` and `Box::from_raw()`.

The only drawback for this method is that you need to pass through two levels
of indirection every time you want to use the object. Even though it probably
doesn't matter in the grand scheme of things (your performance bottlenecks will
almost certainly be elsewhere), using double indirection feels like a pretty
weak solution.

### Pointer to VTable + Object

Believe it or not, but you can implement inheritance-based polymorphism in
plain C with just a couple function pointers and some casting.

The idea is you create a struct which will act as an *"abstract base class"*,
a type which declares an interface which other types inherit from and implement
methods for.

The trick is works because of this particular clause in the C standard:

> A pointer to a structure object,suitably converted, points to its initial
> member (or if that member is a bit-field, then to the unit in which it
> resides), and vice versa. There may be unnamed padding within a structure
> object, but not at its beginning.
>
> <cite><a href="http://www.open-std.org/jtc1/sc22/wg14/www/docs/n2310.pdf">C17 Standard, §6.7.2.1</a></cite>

In layman's terms, it means I can declare a `Child` type who's first element
is a `Base`.

```c
struct Base
{
    void (*destructor)(Base *);
    const char *(*get_name)(const Base *);
    const char *(*set_name)(Base *, const char *);
};

typedef struct Child
{
    Base base;
    const char *name;
} Child;
```

We can then pass the `Child *` pointer around as a `Base *` and, assuming
`get_name` and `set_name` were implemented correctly, we can get and set the
`Child.name` field.

```c
void main()
{
    // Create a Child* and upcast it to a Base*
    Base *child = (Base *)new_child();

    // set the child object's name
    child->set_name(child, "Michael");

    // get the child object's name
    printf("Child's name is \"%s\"\n", child->get_name(child));

    // make sure the destructor is called
    child->destructor(child);
}
```

The `set_name` and `get_name` members are called *virtual methods* in
traditional Object-Oriented parlance.

**This technique is equally valid in Rust when each struct is marked as
`#[repr(C)]`.**

The benefit of using C-style inheritance is that a `Base *` pointer is *just*
a pointer, with the vtable being kept alongside the data being pointed to.

{{% notice note %}}
This isn't a novel technique. It's actually already used by frameworks like
Gnome's [*GObject*][g] and Microsoft's [*COM*][c].

Most C++ implementations use [a slight variation][c++] where the virtual
methods are stored behind another level of indirection. This extra level of
indirection makes different trade-offs with respect to memory use, cache, and
performance, but it's much the same idea.

In code, the C++ implementation might look something like this:

```c
struct VTable {
    void (*destructor)(Base *);
    const char *(*get_name)(const Base *);
    const char *(*set_name)(Base *, const char *);
};

struct CppBase {
    const VTable *vtable;
};

struct CppChild {
    CppBase base;
    ...
}
```

[g]: https://en.wikipedia.org/wiki/GObject
[c]: https://en.wikipedia.org/wiki/Component_Object_Model
[c++]: http://www.vishalchovatiya.com/memory-layout-of-cpp-object/
{{% /notice %}}

## Creating the FileHandle

Returning to our original goal of creating a FFI-safe version of
`Box<dyn std::io::Write>`, let's create a struct representing our base "class".

I'm going to call this a `FileHandle` because that's how it was being used in
the [user forum thread][forum-post] that inspired this article.

```rust
// src/file_handle.rs

use std::{any::TypeId, io::{Error, Write}};

#[repr(C)]
pub struct FileHandle {
    pub(crate) type_id: TypeId,
    pub(crate) destroy: unsafe fn(*mut FileHandle),
    pub(crate) write: unsafe fn(*mut FileHandle, &[u8]) -> Result<usize, Error>,
    pub(crate) flush: unsafe fn(*mut FileHandle) -> Result<(), Error>,
}
```

I've added a couple extra fields alongside the `write()` and `flush()`
methods from [`std::io::Write`][write],

- `type_id` to allow downcasting (more on that later)
- `destroy()`, our object's destructor

I don't particularly want have to create a new type which inherits from
`FileHandle` for every possible `std::io::Write` implementation I need.

Instead it'd be nice to have some generic function like
`FileHandle::for_writer()` which accepts *any* writer and returns a pointer
to an appropriate child class.

```rust
impl FileHandle {
    pub fn for_writer<W>(writer: W) -> *mut FileHandle
    where
        W: Write + 'static,
    {
        ...
    }
}
```

To do this we just need a normal generic struct.

```rust
// src/file_handle.rs

#[repr(C)]
pub(crate) struct Repr<W> {
    // SAFETY: The FileHandle must be the first field so we can cast between
    // *mut Repr<W> and *mut FileHandle
    pub(crate) base: FileHandle,
    pub(crate) writer: W,
}
```

Our `FileHandle::for_writer()` function can then be implemented by creating a
`Repr<W>` on the heap and returning a pointer to it, cast to `*mut FileHandle`.

```rust
// src/file_handle.rs

impl FileHandle {
    pub fn for_writer<W>(writer: W) -> *mut FileHandle
    where
        W: Write + 'static,
    {
        let repr = Repr {
            base: FileHandle::vtable::<W>(),
            writer,
        };

        let boxed = Box::into_raw(Box::new(repr));

        // SAFETY: A pointer to the first field on a #[repr(C)] struct has the
        // same address as the struct itself
        boxed as *mut _
    }

    fn vtable<W: Write + 'static>() -> FileHandle {
        let type_id = TypeId::of::<W>();

        FileHandle {
            type_id,
            destroy: destroy::<W>,
            write: write::<W>,
            flush: flush::<W>,
        }
    }
}
```

For the `destroy`, `write`, and `flush` fields we can use a trick taken from
[*Rust Closures in FFI*][callbacks], using [*turbofish*][fish] to get a
concrete function pointer to a generic function.

The functions themselves are almost trivial, they just cast a `*mut FileHandle`
to `*mut Repr<W>` then invoke the corresponding method. The destructor uses
`Box::from_raw()` to turn the `*mut Repr<W>` back into a `Box<Repr<W>>` so it
can be destroyed properly.

```rust
// src/file_handle.rs

// SAFETY: The following functions can only be used when `handle` is actually a
// `*mut Repr<W>`.

unsafe fn destroy<W>(handle: *mut FileHandle) {
    let repr = handle as *mut Repr<W>;
    let _ = Box::from_raw(repr);
}

unsafe fn write<W: Write>(handle: *mut FileHandle, data: &[u8]) -> Result<usize, Error> {
    let repr = &mut *(handle as *mut Repr<W>);
    repr.writer.write(data)
}

unsafe fn flush<W: Write>(handle: *mut FileHandle) -> Result<(), Error> {
    let repr = &mut *(handle as *mut Repr<W>);
    repr.writer.flush()
}
```

It only took about 50 lines, but we've

1. Created an abstract base class
2. Created a child class inheriting from the base class
3. Made a `FileHandle::for_writer()` constructor which will create a new child
   and populate the vtable in the base class with child-specific methods

## Using the FileHandle from C

Now, to actually be usable from C code we'll need to define `extern "C"`
functions for interacting with our `*mut FileHandle`.

Let's start with a couple common constructors.

```rust
// src/ffi.rs

use crate::FileHandle;

/// Create a new [`FileHandle`] which throws away all data written to it.
#[no_mangle]
pub unsafe extern "C" fn new_null_file_handle() -> *mut FileHandle {
    FileHandle::for_writer(std::io::sink())
}

/// Create a new [`FileHandle`] which writes directly to stdout.
#[no_mangle]
pub unsafe extern "C" fn new_stdout_file_handle() -> *mut FileHandle {
    FileHandle::for_writer(std::io::stdout())
}
```

It'd be nice to construct a `FileHandle` which actually writes to a file, so
let's create a `new_file_handle_from_path()` constructor which takes a
`*const c_char` containing the path.

This constructor is a bit more complex than the previous two in that we need
to use `CStr` to turn the `*const c_char` into a Rust `&str` that can be
passed to `File::create()`. Both `CStr::to_str()` and `File::create()` can
fail, in which case we'll let the caller know by returning a null pointer.

```rust
// src/ffi.rs

use std::{os::raw::c_char, ffi::CStr, fs::File};

/// Create a new [`FileHandle`] which will write to a file on disk.
#[no_mangle]
pub unsafe extern "C" fn new_file_handle_from_path(path: *const c_char) -> *mut FileHandle {
    let path = match CStr::from_ptr(path).to_str() {
        Ok(p) => p,
        Err(_) => return ptr::null_mut(),
    };

    let f = match File::create(path) {
        Ok(f) => f,
        Err(_) => return ptr::null_mut(),
    };

    FileHandle::for_writer(f)
}
```

Now callers can create a `*mut FileHandle`, let's give them a way to destroy it.

The implementation is pretty simple in this case, load the destructor from our
vtable then call it with the `*mut FileHandle`.

```rust
// src/ffi.rs

#[no_mangle]
pub unsafe extern "C" fn file_handle_destroy(handle: *mut FileHandle) {
    let destructor = (*handle).destroy;
    destructor(handle);
}
```

Next we need a way to call the `write()` and `flush()` methods. This gets a bit
trickier because we need to translate arguments from C types to Rust types and
follow C conventions for notifying the caller of failure.

In this case the convention we use is to return a negative error code on
failure, which aligns with `errno` on most *nix platforms.

```rust
// src/ffi.rs

/// Write some data to the file handle, returning the number of bytes written.
///
/// The return value is negative when writing fails.
#[no_mangle]
pub unsafe extern "C" fn file_handle_write(
    handle: *mut FileHandle,
    data: *const c_char,
    len: c_int,
) -> c_int {
    let write = (*handle).write;
    let data = std::slice::from_raw_parts(data as *const u8, len as usize);

    match write(handle, data) {
        Ok(bytes_written) => bytes_written as c_int,
        Err(e) => -e.raw_os_error().unwrap_or(1),
    }
}

/// Flush this output stream, ensuring that all intermediately buffered contents
/// reach their destination.
///
/// Returns `0` on success or a negative value on failure.
#[no_mangle]
pub unsafe extern "C" fn file_handle_flush(handle: *mut FileHandle) -> c_int {
    let flush = (*handle).flush;

    match flush(handle) {
        Ok(_) => 0,
        Err(e) => -e.raw_os_error().unwrap_or(1),
    }
}
```

### Tests

Now we have some code for interacting with `FileHandle`, let's make sure it
actually works and is sound.

The first thing I want to test is that destructors are called by
`file_handle_destroy()`.

To do this let's create a dummy type which implements `Write` and will set a
flag when it gets destroyed.

```rust
// src/ffi.rs

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::{Arc, atomic::{AtomicBool, Ordering}};

    struct NotifyOnDrop(Arc<AtomicBool>);

    impl Drop for NotifyOnDrop {
        fn drop(&mut self) {
            self.0.store(true, Ordering::SeqCst);
        }
    }

    impl Write for NotifyOnDrop {
        fn write(&mut self, _buf: &[u8]) -> std::io::Result<usize> {
            todo!()
        }

        fn flush(&mut self) -> std::io::Result<()> {
            todo!()
        }
    }
}
```

Now we can use `FileHandle::for_writer()` to create a new `*mut FileHandle`,
then immediately call `file_handle_destroy()` to destroy it.

```rust
// src/ffi.rs

mod tests {
    ...

    #[test]
    fn writer_destructor_is_always_called() {
        let was_dropped = Arc::new(AtomicBool::new(false));
        let file_handle = FileHandle::for_writer(NotifyOnDrop(Arc::clone(&was_dropped)));
        assert!(!file_handle.is_null());

        unsafe {
            file_handle_destroy(file_handle);
        }

        assert!(was_dropped.load(Ordering::SeqCst));
    }
}
```

Normally you can run this test with `cargo test` but when working with
`unsafe` code it's a good idea to run tests with [Miri][miri], a Rust
interpreter which executes code and will detect instances of *Undefined
Behaviour* and memory leaks.

```console
$ cargo miri test
    Finished test [unoptimized + debuginfo] target(s) in 0.00s
     Running target/x86_64-unknown-linux-gnu/debug/deps/thin_trait_objects-3a5d6200958baa20

running 1 test
test ffi::tests::writer_destructor_is_always_called ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

The test passed and Miri seems happy with our code so that gives me a lot of
confidence 🙂

{{% notice tip %}}
If our test did something wrong like forgetting to call `file_handle_destroy()`
we'd be greeted with a message like this:

```console
$ cargo miri test
    Finished test [unoptimized + debuginfo] target(s) in 0.00s
     Running target/x86_64-unknown-linux-gnu/debug/deps/thin_trait_objects-3a5d6200958baa20

running 1 test
test ffi::tests::writer_destructor_is_always_called ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 7 filtered out

The following memory was leaked: alloc77819 (Rust heap, size: 24, align: 8) {
    0x00 │ 01 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 │ ................
    0x10 │ 00 __ __ __ __ __ __ __                         │ .░░░░░░░
}
alloc77918 (Rust heap, size: 58, align: 8) {
    0x00 │ 1d 71 55 22 f5 a8 92 81 ╾alloc77896[<191016>]─╼ │ .qU"....╾──────╼
    0x10 │ ╾alloc77897[<191017>]─╼ ╾alloc77898[<191018>]─╼ │ ╾──────╼╾──────╼
    0x20 │ ╾─a77819[<untagged>]──╼                         │ ╾──────╼
}
alloc77896 (fn: file_handle::destroy::<ffi::tests::NotifyOnDrop>)
alloc77897 (fn: file_handle::write::<ffi::tests::NotifyOnDrop>)
alloc77898 (fn: file_handle::flush::<ffi::tests::NotifyOnDrop>)
```

In this case you can see two items were leaked, the first is a block of 24
bytes for the `Arc<AtomicBool>`. If you look carefully, you'll see the
allocation contains 2x `1_usize` values followed by a single `0` and a bunch
of padding (the underscores). They are the strong count, the weak count, and
the `false`, respectively.

In the second allocation you can see 8 bytes followed by a bunch of items
like `alloc77896`, which we see further down is actually a pointer to the
`file_handle::destroy::<ffi::tests::NotifyOnDrop>` function.

That indicates we've leaked the `Repr<NotifyOnDrop>` behind our `*mut
FileHandle`, which would hopefully be enough information to start tracking down
a memory leak.
{{% /notice %}}

Most of the other `ffi` module tests look the same, create a dummy type which
will behave in a particular way (e.g. by returning an error from `write()` or
writing to a buffer that can be inspected later) then exercise the code,
running tests with `cargo miri test`.

## An Owned Wrapper

Now our hypothetical C caller has the ability to create a `*mut FileHandle`,
but we don't want to be using `unsafe` and raw pointers when the file handle
gets passed to normal Rust code.

We need a safe smart pointer.

```rust
// src/owned.rs

use std::ptr::NonNull;

#[repr(transparent)]
pub struct OwnedFileHandle(NonNull<FileHandle>);
```

{{% notice note %}}
We use a `std::ptr::NonNull` instead of a normal raw pointer (`*mut FileHandle`)
because it guarantees the pointer can never be `null`.

A nice side-effect is that the Rust compiler knows `NonNull` can never be
`null`. This means if it ever needs to store a `OwnedFileHandle` alongside a
single bit of information (e.g. an enum's tag), `null` can be used to
represent this information.

This *Null Pointer Optimisation* means types like `Option<OwnedFileHandle>`
are guaranteed to be the same size as `OwnedFileHandle`, which in turn is
guaranteed to be the same size as a pointer.
{{% /notice %}}

As you would have guessed by the name, our `OwnedFileHandle` needs to run the
destructor from its `Drop` impl.

```rust
// src/owned.rs

impl Drop for OwnedFileHandle {
    fn drop(&mut self) {
        unsafe {
            let ptr = self.0.as_ptr();
            let destroy = (*ptr).destroy;
            (destroy)(ptr)
        }
    }
}
```


This smart pointer also needs functions for converting to/from its raw pointer
form or constructing it with `FileHandle::for_writer()` directly.

```rust
// src/owned.rs

impl OwnedFileHandle {
    /// Create a new [`OwnedFileHandle`] which wraps some [`Write`]r.
    pub fn new<W: Write + 'static>(writer: W) -> Self {
        unsafe {
            let handle = FileHandle::for_writer(writer);
            assert!(!handle.is_null());
            OwnedFileHandle::from_raw(handle)
        }
    }

    /// Create an [`OwnedFileHandle`] from a `*mut FileHandle`, taking
    /// ownership of the [`FileHandle`].
    ///
    /// # Safety
    ///
    /// Ownership of the `handle` is given to the [`OwnedFileHandle`] and the
    /// original pointer may no longer be used.
    ///
    /// The `handle` must be a non-null pointer which points to a valid
    /// `FileHandle`.
    pub unsafe fn from_raw(handle: *mut FileHandle) -> Self {
        debug_assert!(!handle.is_null());
        OwnedFileHandle(NonNull::new_unchecked(handle))
    }

    /// Consume the [`OwnedFileHandle`] and get a `*mut FileHandle` that can be
    /// used from native code.
    pub fn into_raw(self) -> *mut FileHandle {
        let ptr = self.0.as_ptr();
        std::mem::forget(self);
        ptr
    }
}
```

We can also implement `std::io::Write` by directly calling the vtable methods.

```rust
// src/owned.rs

impl Write for OwnedFileHandle {
    fn write(&mut self, buf: &[u8]) -> std::io::Result<usize> {
        unsafe {
            let ptr = self.0.as_ptr();
            let write = (*ptr).write;
            (write)(ptr, buf)
        }
    }

    fn flush(&mut self) -> std::io::Result<()> {
        unsafe {
            let ptr = self.0.as_ptr();
            let flush = (*ptr).flush;
            (flush)(ptr)
        }
    }
}
```

### Downcasting

A useful feature of Object Oriented languages is *downcasting*, the ability
to convert from a parent class back to a child class; in this case we want a
way to access the `W` from our `Repr<W>` when we know what type it is.

Rust provides a mechanism called [`std::any::TypeId`][type-id] for uniquely
identifying different types. It's deliberately basic, providing nothing more
than equality, but that's perfectly fine for our cases.

First we need a way to check if the item inside an `OwnedFileHandle` has a
particular type. We'll use the `TypeId` added to the `FileHandle` vtable earlier.

```rust
// src/owned.rs

impl OwnedFileHandle {
    /// Check if the object pointed to by a [`OwnedFileHandle`] has type `W`.
    pub fn is<W: 'static>(&self) -> bool {
        unsafe {
            let ptr = self.0.as_ptr();
            (*ptr).type_id == TypeId::of::<W>()
        }
    }
}
```

Using this new `is()` method we can now provide access to the `W` by doing a
type check followed by an `unsafe` pointer cast.

```rust
// src/owned.rs

impl OwnedFileHandle {
    /// Returns a reference to the boxed value if it is of type `T`, or
    /// `None` if it isn't.
    pub fn downcast_ref<W: 'static>(&self) -> Option<&W> {
        if self.is::<W>() {
            unsafe {
                // SAFETY: We just did a type check
                let repr = self.0.as_ptr() as *const Repr<W>;
                Some(&(*repr).writer)
            }
        } else {
            None
        }
    }

    /// Returns a mutable reference to the boxed value if it is of type `T`, or
    /// `None` if it isn't.
    pub fn downcast_mut<W: 'static>(&mut self) -> Option<&mut W> {
        if self.is::<W>() {
            unsafe {
                // SAFETY: We just did a type check
                let repr = self.0.as_ptr() as *mut Repr<W>;
                Some(&mut (*repr).writer)
            }
        } else {
            None
        }
    }
}
```

We also need a method which consumes `self`, unboxes the `Repr<W>`, and gives
the original `W` back to the caller.

However, what happens if the type check fails? If we follow `downcast_ref()`
and return an `Option<W>` we'd be throwing the `OwnedFileHandle` away with no
way to try again or fall back to something else. Most APIs in the standard
library will return a `Result<W, OwnedFileHandle>` here, returning ownership
of the file handle in the error case.

```rust
// src/owned.rs

impl OwnedFileHandle {
    /// Attempt to downcast the [`OwnedFileHandle`] to a concrete type and
    /// extract it.
    pub fn downcast<W: 'static>(self) -> Result<W, Self> {
        if self.is::<W>() {
            unsafe {
                let ptr = self.into_raw();
                // SAFETY: We just did a type check
                let repr: *mut Repr<W> = ptr.cast();

                let unboxed = Box::from_raw(repr);
                Ok(unboxed.writer)
            }
        } else {
            Err(self)
        }
    }
}
```

With the addition of downcasting our `OwnedFileHandle` has pretty much reached
feature parity with most `Box<dyn Write>` solutions.

## Conclusions

While it's not something you'll be using every day, *Thin Trait Objects* are
a technique that you may find a use for some day. If nothing else,
understanding them should give you a better appreciation for how much work
our compilers do to implement nice things like Polymorphism and inheritance.

It also reinforces the idea that all Turing-complete languages are
equivalent. Just because you start with a non-OO language doesn't mean you
can't have inheritance, it just requires a bit more work.

Another nice thing is that, apart from the `ffi` module, this code is just a
mechanical transformation based on a trait definition. I'm sure a suitably
motivated person could create a procedural macro which lets you add a
`#[thin_trait_object]` attribute on top of a trait definition and
automatically generate the corresponding `FileHandle`, `OwnedFileHandle`, and
`Repr<W>` types.

If you noticed anything unsound (or just plain incorrect) in my code, please
[get in contact][email] because I want to hear from you! I'm also curious to
hear if from people who create Rust products which use FFI, and if you've had
to do something similar in production.

[forum-post]: https://users.rust-lang.org/t/ffi-c-file-and-good-rust-wrapper-equivalent-type/52050
[poly]: https://blog.rcook.org/blog/2020/traits-and-polymorphism-rust/
[generics]: https://doc.rust-lang.org/book/ch10-01-syntax.html#in-function-definitions
[trait-objects]: https://doc.rust-lang.org/reference/types/trait-object.html
[vtable]: https://en.wikipedia.org/wiki/Virtual_method_table
[c99-first-element]: http://www.coding-guidelines.com/C99/html/6.7.2.1.html#1413
[write]: https://doc.rust-lang.org/std/io/trait.Write.html
[callbacks]: {{< ref "/posts/rust-closures-in-ffi.md#introducing-closures" >}}
[fish]: https://turbo.fish/
[miri]: https://github.com/rust-lang/miri
[type-id]: https://doc.rust-lang.org/std/any/struct.TypeId.html
[email]: mailto:michaelfbryan@gmail.com
[anyhow]: https://github.com/dtolnay/anyhow/blob/2a82468b07751485552a7c1123007ad90e842b24/src/error.rs
