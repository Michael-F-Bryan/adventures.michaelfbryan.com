---
title: "Common Newbie Mistakes and Bad Practices in Rust: Conceptual Misunderstandings"
publishDate: "2021-09-16T23:44:27+08:00"
draft: true
tags:
- Rust
series:
- Rust Best Practices
---

{{% notice note %}}
The code written in this article is available on the Rust Playground using the
various [(playground)][playground] links dotted throughout. Feel free to browse
through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
[playground]: https://play.rust-lang.org/
{{% /notice %}}

### Strings are not Paths

- use `&Path` instead of `&str`
- `join()`, not `format!("{}/{}", dir, filename)`
- Non-UTF8 paths
- Self-documenting

### Unnecessary Indirection

- `fn foo(title: &String)`

### Copy Followed By A Borrow

- `function_taking_str(&"blah".to_string())`

### Compile Time vs Run Time

- Trying to use `include_str!()` instead of `std::fs::read_to_string()`

### Dyn Trait Isn't Like `Object`

- Expecting `dyn Trait` to sub-type or be dynamically typed

### Strings Aren't Arrays of Characters

- Using byte indexing into UTF-8 strings without awareness of char boundaries
  etc. and the resulting panics.
- You can often just use iterators

### Measuring Performance of Debug Builds

- It's a complete waste of time
- Makes people think "Rust is slower than Python"

### Passing Empty Buffers to `read()`

- The `Read` trait writes into an existing buffer
- It won't allocate

### You Need to Read/Write Everything

- Calling `Read::read()` or `Write::write()` when `read_exact()` or
  `write_all()` is needed

[post]: https://users.rust-lang.org/t/common-newbie-mistakes-or-bad-practices/64821
