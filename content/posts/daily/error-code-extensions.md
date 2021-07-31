---
title: "Using Extension Traits to Make Error Codes More Ergonomic"
publishDate: "2021-08-08T00:46:59+08:00"
tags:
- Daily Rust
- Rust
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

## Real World Example

I [recently reviewed some code][post] on the Rust user forums where the author
was interacting with the Windows API and this part of their comment popped out
at me:

> You will also notice that I have little to no error handling. If it were me I
> would do an if statement after every Windows API call but that seems
> unnecessary for some reason. My question is - how should my thought process
> be, should I handle every potential pitfall or skip over some functions like
> `GetWindowThreadProcessId` that I know will, for most of the time, work just
> fine?

Even the author admits that they should be checking the result of each call into
the Windows API, but adding `if result == S_OK` checks after every single
operation is a massive pain and it is tempting to skip the error checking when
you "know" the operation won't fail.

{{% notice note %}}
The Windows API uses something called [`HRESULT`][hresult] as the return value
of fallible functions. This is just an integer where zero (normally named
`S_OK`) signals success and non-zero values indicate failure.
{{% /notice %}}

This isn't an ideal situation, especially in `unsafe` code where ignoring an
error may trigger a crash or *Undefined Behaviour* due to using uninitialized
values, so let's see if we can help improve the ergonomics a bit.

## Our `ErrorCodeExt` Trait

{{% notice note %}}
If you are coming from a language like C++ or Python this is similar to [mixin
classes][mixin-classes], however it is strictly more powerful because

1. You can attach new behaviour in a downstream crate *after* a type has been
   defined
2. You don't need an instance of the type in order to use the extended
   functionality

[mixin-classes]: https://stackoverflow.com/questions/533631/what-is-a-mixin-and-why-are-they-useful
{{% / notice %}}

## Conclusions

[post]: https://users.rust-lang.org/t/code-review-on-windows-api-usage/62921
[hresult]: https://docs.microsoft.com/en-us/windows/win32/com/error-handling-in-com
[xion]: http://xion.io/post/code/rust-extension-traits.html
[rfc]: https://rust-lang.github.io/rfcs/0445-extension-trait-conventions.html
