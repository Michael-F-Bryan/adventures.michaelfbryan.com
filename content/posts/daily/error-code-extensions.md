---
title: "Using Extension Traits to Make Error Codes More Ergonomic"
publishDate: "2021-08-08T00:46:59+08:00"
draft: true
tags:
- Daily Rust
- Rust
series:
- Daily Rust
---

Due to the way the Rust trait system works you can use a pattern commonly called
*Extension Traits* to extend the functionality of a type after it has been
defined.

The [original RFC][rfc] for the *Extension Trait* convention and Karol
Kuczmarski's [*Extension traits in Rust*][xion] article both do a better job of
explaining this pattern than I could. Instead, I'd like to focus on a single
example of where a simple extension trait can have a massive effect on your
code's ergonomics.

{{% notice note %}}
The code written in this article is available in the various playground links
dotted throughout. Feel free to browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## The Real World Use Case

I [recently reviewed some code][post] on the Rust user forums where the author
was interacting with the Windows API and this part of their comment popped out
at me:

> You will also notice that I have little to no error handling. If it were me I
> would do an if statement after every Windows API call but that seems
> unnecessary for some reason. My question is - how should my thought process
> be, should I handle every potential pitfall or skip over some functions like
> `GetWindowThreadProcessId` that I know will, for most of the time, work just
> fine?

This sounds like they are wondering whether it's okay to skip error checking
because the extra `if` statements will be cumbersome and they "know" the call
should never fail anyway.

As someone who has written a fair amount of Go code I can definitely understand
how annoying it is to write `if result != S_OK { ... }` after every operation.
You can easily double a function's size and lose the "actual" logic amongst
code for propagating errors to the caller so it'd be nice to cut corners,
especially when you "know" the operation won't fail anyway.

{{% notice note %}}
The Windows API uses something called [`HRESULT`][hresult] as the return value
of fallible functions. This is just an integer where zero (normally named
`S_OK`) signals success and non-zero values indicate failure.

[hresult]: https://docs.microsoft.com/en-us/windows/win32/com/error-handling-in-com
{{% /notice %}}

This isn't an ideal situation, especially in `unsafe` code where ignoring an
error may trigger a crash or *Undefined Behaviour* due to using uninitialised
values, so let's see if we can help improve the ergonomics a bit.

## Our `ErrorCodeExt` Extension Trait

The way you typically deal with boring, routine tasks in programming is via
abstraction and (when supported by the language), syntactic sugar.

In this case, the key piece of syntactic sugar we want to use is [the `?`
operator][question-mark] to let us propagate errors to the caller. However,
we have a problem... Windows API calls return a `HRESULT` (an integer) but we
can only use `?` with a `Result` or `Option`.

Sure, we could write a `match` statement after the Windows API call to convert
the `HRESULT` to a `Result`, but that's no better than `if result != S_OK`.

This is where our extension trait comes in - we can use the extension trait
pattern to give the `HRESULT` type a `to_result()` method.

{{% notice note %}}
If you are coming from a language like C++ or Python this is similar to [mixin
classes][mixin-classes], however it is strictly more powerful because

1. You can attach new behaviour in a downstream crate *after* a type has been
   defined
2. You don't necessarily need an instance of the type in order to use the
   extended functionality

[mixin-classes]: https://stackoverflow.com/questions/533631/what-is-a-mixin-and-why-are-they-useful
{{% / notice %}}

By convention, extension traits will have a `Ext` suffix and this is for working
with error codes, so let's call this extension trait `ErrorCodeExt`.
Programmers aren't known for their originality, after all.

The definition itself is almost trivial.

```rust
trait ErrorCodeExt {
    fn to_result(self) -> Result<(), std::io::Error>;
}
```

We've made the decision to use `std::io::Error` as our error type because it is
used by the standard library to represent all OS errors and has a convenient
[`Error::from_raw_os_error()`][from-os] constructor.

```rust
impl ErrorCodeExt for HRESULT {
    fn to_result(self) -> Result<(), std::io::Error> {
        if self == S_OK {
            Ok(())
        } else {
            Err(std::io::Error::from_raw_os_error(self))
        }
    }
}

// (already defined in the winapi crate)
mod winapi {
    mod shared {
        mod winerror {
            type c_long = i32;
            type HRESULT = c_long;
            const S_OK: HRESULT = 0;
        }
    }
}
```

## Conclusions

[post]: https://users.rust-lang.org/t/code-review-on-windows-api-usage/62921
[xion]: http://xion.io/post/code/rust-extension-traits.html
[rfc]: https://rust-lang.github.io/rfcs/0445-extension-trait-conventions.html
[question-mark]: https://doc.rust-lang.org/book/ch09-02-recoverable-errors-with-result.html#a-shortcut-for-propagating-errors-the--operator
[from-os]: https://doc.rust-lang.org/std/io/struct.Error.html#method.from_raw_os_error
