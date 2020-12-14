---
title: "Thin Trait Objects in Rust"
date: "2020-12-03T14:03:24+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
- FFI
---

- two native mechanisms for polymorphism
  - Compile time
  - Runtime
- Neither are FFI-safe
- Trait objects take up 2x `usize` on the stack
  - Use niche optimisation so things like `Result<(), Error>` are only the size
    of a pointer
- My primary focus is enabling FFI-safe polymorphism

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/thin-trait-objects
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

# Possible Solutions

Now before we go any further it is important to ask the question, *"do we
actually **need** to come up with a fancy, `unsafe` solution here?"*

9 times out of 10 taking the more complicated option will require you to do
extra work that wasn't needed in the first place.

## Don't Allow Polymorphism

This is probably the simplest option. If you want to avoid complexity,
especially when already writing a Foreign Function Interface, don't do
polymorphism.

This could be as simple as hard-coding a simple implementation (i.e. if on
Linux, accept a file descriptor and write to that).

Another option would be to design your API to be more data-oriented. That way
the caller can write the custom logic in their own code instead of trying to
inject it into someone else's.

After all, no code is simpler than no code.

## Pointer to Enum

If you have a finite set of possible implementations you can pass around a
pointer to an enum.

While more complex than the previous option, we're all familiar with the Rust
enum and how it enables a limited form of polymorphism.

## Double Indirection

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

## Pointer to VTable + Object

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

This technique is equally valid in Rust as long as each struct is marked as
`#[repr(C)]`.

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

# Creating the FileHandle

# An Owned Wrapper

# Using the FileHandle from C

# Conclusions

[forum-post]: https://users.rust-lang.org/t/ffi-c-file-and-good-rust-wrapper-equivalent-type/52050
[poly]: https://blog.rcook.org/blog/2020/traits-and-polymorphism-rust/
[generics]: https://doc.rust-lang.org/book/ch10-01-syntax.html#in-function-definitions
[trait-objects]: https://doc.rust-lang.org/reference/types/trait-object.html
[vtable]: https://en.wikipedia.org/wiki/Virtual_method_table
[c99-first-element]: http://www.coding-guidelines.com/C99/html/6.7.2.1.html#1413
