---
title: "Extension Traits"
date: "2021-03-22T03:42:27+08:00"
draft: true
tags:
- Rust
---

A nice consequence of the way Rust's type system works is a pattern called
the *Extension Trait*. This

{{% notice note %}}
Most of the examples developed in this article are also linked to on the
*Rust Playground*. Feel free to browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Motivation

- Add helper methods to an existing type
    - Like monkey-patching, but only the code that explicitly imports a
      extension will be affected
- Create an interface for additional functionality which is only sometimes
  available

## The General Mechanism

- Create a trait then implement it for each of the types
- Often uses macros for repetitive impls
- Touch on the orphan rule

## Unwrap or Trap

## Other Examples in the Wild

- the `itertools` crate
- `std::os::windows::ffi::OsStrExt`

## Conclusion

See also:

- [RFC - 445 Extension Trait Conventions](https://rust-lang.github.io/rfcs/0445-extension-trait-conventions.html)
- [Extension traits in Rust](http://xion.io/post/code/rust-extension-traits.html)
