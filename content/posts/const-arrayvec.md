---
title: "Implementing ArrayVec Using Const Generics"
date: "2019-11-12T20:57:53+08:00"
draft: true
tags:
- rust
---

If you've ever done much embedded programming in Rust, you've most probably run
across the [`arrayvec`][arrayvec] crate before. It's awesome. The main purpose
of the crate is to provide the `ArrayVec` type, which is essentially like
`Vec<T>` from the standard library, but backed by an array instead of some
memory on the heap.

One of the problems I ran into while writing the *Motion Planning* chapter of my
[Adventures in Motion Control][aimc] was deciding how far ahead my motion
planner should plan.

The *Adventures in Motion Control* series is targeting a platform without an
allocator, so the number of moves will be determined at compile time. I *could*
pluck a number out of thin air and say *"she'll be right"*, but there's also
this neat feature on *nightly* at the moment called [*"Const Generics"*][cg]...

{{< figure 
    src="https://imgs.xkcd.com/comics/nerd_sniping.png" 
    link="https://xkcd.com/356/" 
    caption="(obligatory XKCD reference)" 
    alt="Nerd Sniping" 
>}}

## Getting Started

Okay, so the first thing we'll need to do is create a crate and enable this 
`const_generics` feature.

When creating a new project I like to use [`cargo generate`][cargo-generate]
and a template repository. It just saves needing to manually copy license info
from another project.

```console
$ cargo generate --git https://github.com/Michael-F-Bryan/github-template --name const-arrayvec
 Creating project called `const-arrayvec`...
 Done! New project created /home/michael/Documents/const-arrayvec
```

And we'll need to update `lib.rs`:

```rust
// src/lib.rs

//! An implementation of the [arrayvec](https://crates.io/crates/arrayvec) crate
//! using *Const Generics*.

#![no_std]
#![feature(const_generics)]
```

It's around this time that I'll start a second terminal and use [`cargo watch`][cw]
to run `cargo build`, `cargo test`, and `cargo doc` in the background.

```console
$ cargo watch --clear 
    -x "check --all" 
    -x "test --all" 
    -x "doc --document-private-items --all" 
    -x "build --release --all"
warning: the feature `const_generics` is incomplete and may cause the compiler to crash
 --> src/lib.rs:2:12
  |
2 | #![feature(const_generics)]
  |            ^^^^^^^^^^^^^^
  |
  = note: `#[warn(incomplete_features)]` on by default

    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
```

Well that's encouraging. You know a feature *must* be unstable when even 
*nightly* warns you it may crash the compiler...

{{% notice tip %}}
You can "fix" this compiler warning by adding a `#![allow(incomplete_features)]`
to the top of `lib.rs`.
{{% /notice %}}

Now we've got a crate, we can start implementing our `ArrayVec` type.

The first decision we need to make is how values will be stored within our
`ArrayVec` the naive implementation would use a simple `[T; N]` array, but that
only works when `T` has a nice default value and no destructor. Instead, what
we're really doing is storing an array of possibly initialized `T`'s... Which
is exactly what [`core::mem::MaybeUninit`][MaybeUninit] is designed for.

```rust
// src/lib.rs

use core::mem::MaybeUninit;

pub struct ArrayVec<T, const N: usize> {
    items: [MaybeUninit<T>; N],
    length: usize,
}
```

Next we'll need to give `ArrayVec` a constructor. This is what I *would* like
to write...

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    pub const fn new() -> ArrayVec<T, { N }> {
        ArrayVec {
            items: [MaybeUninit::uninit(); N],
            length: 0,
        }
    }
}
```

... But unfortunately it doesn't seem to be implemented yet (see 
[this u.rl.o post][forum]).

```
    Checking const-arrayvec v0.1.0 (/home/michael/Documents/const-arrayvec)
error: array lengths can't depend on generic parameters
  --> src/lib.rs:15:44
   |
15 |             items: [MaybeUninit::uninit(); N],
   |                                            ^

error: aborting due to previous error

error: could not compile `const-arrayvec`.
```

Instead we'll need to drop the `const fn` for now and find a different way of
creating our array of uninitialized data.

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    pub fn new() -> ArrayVec<T, { N }> {
        unsafe {
            ArrayVec {
                // this is safe because we've asked for a big block of
                // uninitialized memory which will be treated as
                // an array of uninitialized items,
                // which perfectly valid for [MaybeUninit<_>; N]
                items: MaybeUninit::uninit().assume_init(),
                length: 0,
            }
        }
    }
}
```

While we're at it, because we're implementing a collection we should add `len()`
and friends.

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    pub const fn len(&self) -> usize { self.length }

    pub const fn is_empty(&self) -> bool { self.len() == 0 }

    pub const fn capacity(&self) -> usize { N }

    pub const fn is_full(&self) -> bool { self.len() == self.capacity() }
}
```

We also want a way to get a raw pointer to the first element in the underlying
buffer. This will be important when we actually need to read data.

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    pub fn as_ptr(&self) -> *const T { self.items.as_ptr() as *const T }

    pub fn as_mut_ptr(&mut self) -> *mut T { self.items.as_mut_ptr() as *mut T }
}
```

## The Basic Operations

About the most basic operation for a `Vec`-like container to support is adding
and removing items, so that's what we'll be implementing next.

As you may have guessed, this crate will do a lot of work with possibly
initialized memory so there'll be a decent chunk of `unsafe` code. 

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    /// Add an item to the end of the array without checking the capacity.
    /// 
    /// # Safety
    /// 
    /// It is up to the caller to ensure the vector's capacity is suitably 
    /// large.
    /// 
    /// This method uses *debug assertions* to detect overflows in debug builds.
    pub unsafe fn push_unchecked(&mut self, item: T) {
        debug_assert!(!self.is_full());
        let len = self.len();

        // index into the underlying array using pointer arithmetic and write
        // the item to the correct spot
        self.as_mut_ptr().add(len).write(item);

        // only now can we update the length
        self.set_len(len + 1);
    }

    /// Set the vector's length without dropping or moving out elements.
    /// 
    /// # Safety
    /// 
    /// This method is `unsafe` because it changes the number of "valid"
    /// elements the vector thinks it contains, without adding or removing any
    /// elements. Use with care.
    pub unsafe fn set_len(&mut self, new_length: usize) {
        debug_assert!(new_length < self.capacity());
        self.length = new_length;
    }
}
```

The `push_unchecked()` and `set_len()` methods should be fairly descriptive,
so I'll just let you read the code. Something to note 

{{% notice note %}}
You would have noticed that the `unsafe` functions have a `# Safety` section in
their doc-comments specifying various assumptions and invariants that must be
upheld. 

This is quite common when writing `unsafe` code, and is actually
[part of the Rust API guidelines][guidelines]. I would recommend giving that
document a quick read if you haven't already.

[guidelines]: https://rust-lang.github.io/api-guidelines/documentation.html#c-failure
{{% /notice %}}

We also need to expose a safe `push()` method. Preferably one which will return
the original item when there is no more space.

```rust
// src/lib.rs

use core::fmt::{self, Display, Formatter};

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    /// Add an item to the end of the vector.
    ///
    /// # Examples
    ///
    /// ```rust
    /// # use const_arrayvec::ArrayVec;
    /// let mut vector: ArrayVec<u32, 5> = ArrayVec::new();
    ///
    /// assert!(vector.is_empty());
    ///
    /// vector.push(42);
    ///
    /// assert_eq!(vector.len(), 1);
    /// assert_eq!(vector[0], 42);
    /// ```
    pub fn push(&mut self, item: T) -> Result<(), CapacityError<T>> {
        if self.is_full() {
            Err(CapacityError(item))
        } else {
            unsafe {
                self.push_unchecked(item);
                Ok(())
            }
        }
    }
}

#[derive(Debug, Copy, Clone, PartialEq, Eq, Hash)]
pub struct CapacityError<T>(pub T);

impl<T> Display for CapacityError<T> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(f, "Insufficient capacity")
    }
}
```

While we're at it, we should add a `pop()` method. This one is quite similar,
except implemented in reverse (i.e. the length is decremented and we read from
the array).

```rust
// src/lib.rs

use core::ptr;

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    /// Remove an item from the end of the vector.
    ///
    /// # Examples
    ///
    /// ```rust
    /// # use const_arrayvec::ArrayVec;
    /// let mut vector: ArrayVec<u32, 5> = ArrayVec::new();
    ///
    /// vector.push(12);
    /// vector.push(34);
    ///
    /// assert_eq!(vector.len(), 2);
    ///
    /// let got = vector.pop();
    ///
    /// assert_eq!(got, Some(34));
    /// assert_eq!(vector.len(), 1);
    /// ```
    pub fn pop(&mut self) -> Option<T> {
        if self.is_empty() {
            return None;
        }

        unsafe {
            let new_length = self.len() - 1;
            self.set_len(new_length);
            Some(ptr::read(self.as_ptr().add(new_length)))
        }
    }
}
```

Some more relatively straightforward methods are `clear()` and `truncate()` for 
shortening the vector and dropping any items after the new end.

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    /// Shorten the vector, keeping the first `new_length` elements and dropping
    /// the rest.
    pub fn truncate(&mut self, new_length: usize) {
        unsafe {
            if new_length < self.len() {
                let start = self.as_mut_ptr().add(new_length);
                let num_elements_to_remove = self.len() - new_length;
                let tail: *mut [T] =
                    slice::from_raw_parts_mut(start, num_elements_to_remove);

                self.set_len(new_length);
                ptr::drop_in_place(tail);
            }
        }
    }

    /// Remove all items from the vector.
    pub fn clear(&mut self) { self.truncate(0); }
}
```

{{% notice note %}}
Note the use of `core::ptr::drop_in_place()`, this will call the destructor of
every item in the `tail` and leave them in a logically uninitialized state.
{{% /notice %}}

Next comes one of the trickier methods for our collection, `try_insert()`. When
inserting, after doing a couple bounds checks we'll need to move everything
after the insertion point over one space. Because the memory we're copying 
*from* overlaps with the memory we're copying *to*, we need to use the less
performant `core::ptr::copy()` (the Rust version of C's `memmove()`) instead of
`core::ptr::copy_non_overlapping()` (equivalent of C's `memcpy()`).

Most of this code is lifted straight from [`alloc::vec::Vec::insert()`][vec].

```rust
// src/lib.rs

macro_rules! out_of_bounds {
    ($method:expr, $index:expr, $len:expr) => {
        panic!(
            concat!(
                "ArrayVec::",
                $method,
                "(): index {} is out of bounds in vector of length {}"
            ),
            $index, $len
        );
    };
}

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    pub fn try_insert(
        &mut self,
        index: usize,
        item: T,
    ) -> Result<(), CapacityError<T>> {
        let len = self.len();

        // bounds checks
        if index > self.len() {
            out_of_bounds!("try_insert", index, len);
        }
        if self.is_full() {
            return Err(CapacityError(item));
        }

        unsafe {
            // The spot to put the new value
            let p = self.as_mut_ptr().add(index);
            // Shift everything over to make space. (Duplicating the
            // `index`th element into two consecutive places.)
            ptr::copy(p, p.offset(1), len - index);
            // Write it in, overwriting the first copy of the `index`th
            // element.
            ptr::write(p, item);
            // update the length
            self.set_len(len + 1);
        }

        Ok(())
    }

    pub fn insert(&mut self, index: usize, item: T) {
        match self.try_insert(index, item) {
            Ok(_) => {},
            Err(e) => panic!("Insert failed: {}", e),
        }
    }
}
```

Something we haven't done up until now is make sure destructors are called for
the items in our collection. Leaking memory is bad, so we need to add a `Drop`
impl.

This is easier than you'd think because we can just use the `clear()` method.

```rust
// src/lib.rs

impl<T, const N: usize> Drop for ArrayVec<T, { N }> {
    fn drop(&mut self) {
        // Makes sure the destructors for all items are run.
        self.clear();
    }
}
```

## Implementing Useful Traits

We're now at the point where should start making our `ArrayVec` easier to use.

The implementation itself is quite boring (we just call
`core::slice::from_raw_parts()`), but this is the first step on the way to being
a first class vec-like container.

```rust
// src/lib.rs

use core::ops::{Deref, DerefMut};

impl<T, const N: usize> Deref for ArrayVec<T, { N }> {
    type Target = [T];

    fn deref(&self) -> &Self::Target {
        unsafe { slice::from_raw_parts(self.as_ptr(), self.len()) }
    }
}

impl<T, const N: usize> DerefMut for ArrayVec<T, { N }> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        unsafe { slice::from_raw_parts_mut(self.as_mut_ptr(), self.len()) }
    }
}
```

From here we get things like `as_slice()` and `AsRef<[T]>` for free.

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    pub fn as_slice(&self) -> &[T] { self.deref() }

    pub fn as_slice_mut(&mut self) -> &mut [T] { self.deref_mut() }
}

impl<T, const N: usize> AsRef<[T]> for ArrayVec<T, { N }> {
    fn as_ref(&self) -> &[T] { self.as_slice() }
}

impl<T, const N: usize> AsMut<[T]> for ArrayVec<T, { N }> {
    fn as_mut(&mut self) -> &mut [T] { self.as_slice_mut() }
}
```

You may have noticed that we didn't use any custom derives when declaring
`ArrayVec`. Now we can use `as_slice()` it's easy enough to defer the 
implementation of traits you'd normally `#[derive]` to their `&[T]` 
implementation.

The traits we're going to implement manually:

- Debug
- PartialEq/Eq
- PartialOrd/Ord
- Hash
- Clone
- Default (just calls `ArrayVec::new()`)

We'll leave `Copy` and `Clone` for later.

```rust
// src/lib.rs

use core::{
    hash::Hasher,
    fmt::{self, Debug, Formatter},
    cmp::Ordering,
};

impl<T: Debug, const N: usize> Debug for ArrayVec<T, { N }> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        f.debug_list().entries(self.as_slice()).finish()
    }
}

impl<T: PartialEq, const N: usize> PartialEq<[T]> for ArrayVec<T, { N }> {
    fn eq(&self, other: &[T]) -> bool { self.as_slice() == other }
}

impl<T: PartialEq, const N: usize, const M: usize> PartialEq<ArrayVec<T, { M }>>
    for ArrayVec<T, { N }>
{
    fn eq(&self, other: &ArrayVec<T, { M }>) -> bool {
        self.as_slice() == other.as_slice()
    }
}

impl<T: Eq, const N: usize> Eq for ArrayVec<T, { N }> {}

impl<T: PartialOrd, const N: usize> PartialOrd for ArrayVec<T, { N }> {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        self.as_slice().partial_cmp(other.as_slice())
    }
}

impl<T: Ord, const N: usize> Ord for ArrayVec<T, { N }> {
    fn cmp(&self, other: &Self) -> Ordering {
        self.as_slice().cmp(other.as_slice())
    }
}

impl<T: Hash, const N: usize> Hash for ArrayVec<T, { N }> {
    fn hash<H: Hasher>(&self, hasher: &mut H) { self.as_slice().hash(hasher); }
}

impl<T, const N: usize> Default for ArrayVec<T, { N }> {
    fn default() -> Self { ArrayVec::new() }
}

impl<T: Clone, const N: usize> Clone for ArrayVec<T, { N }> {
    fn clone(&self) -> ArrayVec<T, { N }> {
        let mut other: ArrayVec<T, { N }> = ArrayVec::new();

        for item in self.as_slice() {
            unsafe {
                // if it fit into the original, it'll fit into the clone
                other.push_unchecked(item.clone());
            }
        }

        other
    }
}
```

{{% notice tip %}}
I imagine we could use [specialization][spec] to convert the `Clone` impl to
a simple `memcpy()` when `T: Copy` to give us a nice speed boost, but there's
a good chance LLVM will figure out what we're doing and apply that
optimisation anyway.

[spec]: https://github.com/rust-lang/rust/issues/31844
{{% /notice %}}

That's a pretty big wall of code, but you may have noticed instead of 
implementing `PartialEq`, we instead implemented `PartialEq<ArrayVec<T, { M }>>`
for `ArrayVec<T, { N }>`. This makes things more flexible by allowing vectors
of different sizes can be compared for equality.

Users will want to index into our vector (i.e. `some_vector[i]`), but if you
look at the docs [implementing `Index` for `[T]`][slice-index] you'll see it
uses the unstable [`core::slice::SliceIndex`][SliceIndex] trait. We *could*
enable another feature flag, but a smarter way would be to say *"`ArrayVec` can
be indexed using whatever can index into a `[T]`"*.

```rust
// src/lib.rs

use core::ops::{Index, IndexMut};

impl<Ix, T, const N: usize> Index<Ix> for ArrayVec<T, { N }>
where
    [T]: Index<Ix>,
{
    type Output = <[T] as Index<Ix>>::Output;

    fn index(&self, ix: Ix) -> &Self::Output { self.as_slice().index(ix) }
}

impl<Ix, T, const N: usize> IndexMut<Ix> for ArrayVec<T, { N }>
where
    [T]: IndexMut<Ix>,
{
    fn index_mut(&mut self, ix: Ix) -> &mut Self::Output {
        self.as_slice_mut().index_mut(ix)
    }
}
```

## Bulk Copies and Insertion

Another useful operation is to copy items directly from another slice.

```rust
// src/lib.rs

impl<T, const N: usize> ArrayVec<T, { N }> {
    ...

    pub const fn remaining_capacity(&self) -> usize { N - self.len() }

    pub fn try_extend_from_slice(
        &mut self,
        other: &[T],
    ) -> Result<(), CapacityError<()>>
    where
        T: Copy,
    {
        if self.remaining_capacity() < other.len() {
            return Err(CapacityError(()));
        }

        let self_len = self.len();
        let other_len = other.len();

        unsafe {
            let dst = self.as_mut_ptr().offset(self_len as isize);
            // Note: we have a mutable reference to self, so it's not possible
            // for the two arrays to overlap
            ptr::copy_nonoverlapping(other.as_ptr(), dst, other_len);
            self.set_len(self_len + other_len);
        }
        Ok(())
    }
}
```

It's also useful to add a `From` to allow construction of a vector from an
array. 

This is can be tricky to do correctly because you can't iterate over the items
(`T`, not `&T`) in an array `[T; N]` due to the lack of an `IntoIterator` impl
for arrays. Instead we'll need to use `unsafe` to directly copy bytes into our
buffer.

```rust
// src/lib.rs

impl<T, const N: usize> From<[T; N]> for ArrayVec<T, { N }> {
    fn from(other: [T; N]) -> ArrayVec<T, { N }> {
        let mut vec = ArrayVec::<T, { N }>::new();

        unsafe {
            // Copy the items from the array directly to the backing buffer

            // Note: Safe because a [T; N] is identical to [MaybeUninit<T>; N]
            ptr::copy_nonoverlapping(
                other.as_ptr(),
                vec.as_mut_ptr(),
                other.len(),
            );
            // ownership has been transferred to the backing buffer, make sure
            // the original array's destructors aren't called prematurely
            mem::forget(other);
            // the memory has now been initialized so it's safe to set the
            // length
            vec.set_len(N);
        }

        vec
    }
}
```

## Implementing Drain

Most collections have a so-called *Draining Iterator* that removes a specified 
range from the vector and yields the removed items.

Implementing this pattern *correctly* can be a non-trivial task however, as
Alexis Beingessner's insightful [Pre-Pooping Your Pants With Rust][ppyp] 
demonstrates.

{{% notice info %}}
TODO: Implement drain...
{{% /notice %}}

[arrayvec]: https://crates.io/crates/arrayvec
[aimc]: http://adventures.michaelfbryan.com/tags/aimc
[cg]: https://github.com/rust-lang/rust/issues/44580
[cargo-generate]: https://crates.io/crates/cargo-generate
[cw]: https://crates.io/crates/cargo-watch
[MaybeUninit]: https://doc.rust-lang.org/core/mem/union.MaybeUninit.html
[forum]: https://doc.rust-lang.org/core/mem/union.MaybeUninit.html
[vec]: https://github.com/rust-lang/rust/blob/a19f93410d4315408f8775e1be29536302adc223/src/liballoc/vec.rs#L993-L1016
[slice-index]: https://doc.rust-lang.org/std/primitive.slice.html#impl-Index%3CI%3E
[SliceIndex]: https://doc.rust-lang.org/std/slice/trait.SliceIndex.html
[ppyp]: http://cglab.ca/~abeinges/blah/everyone-poops/