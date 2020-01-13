---
title: "Experiment: Safe FFI for Rust ↔ C++"
date: "2020-01-13T21:25:45+08:00"
draft: true
tags:
- rust
- unsafe
---

Last week the venerable [@dtolnay][dtolnay] quietly [announced][announcement] a
tool for reducing the amount of boilerplate code when interoperating between
Rust and C++.

Considering FFI is an area of Rust (well, really, programming in general)
that I'm quite familiar with, I thought I'd kick the tyres by wrapping the
`bzip2` library. The [bindgen project][bg] already has [a tutorial][bg-tutorial]
on this so it should be a nice comparison.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/cxx-experiment
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Building the `bzip2` Library

First we'll need to create a new project and enable travis. There's
[a template][template] I use alongside [cargo-generate][cg] to avoid needing to
copy around `LICENSE-*.md` files and tell travis to publish API docs to GitHub
Pages.

```console
$ cargo generate --git https://github.com/Michael-F-Bryan/github-template --name cxx-experiment
 Creating project called `cxx-experiment`...
 Done! New project created /tmp/cxx-experiment
$ cd cxx-experiment
$ travis enable
Detected repository as Michael-F-Bryan/cxx-experiment, is this correct? |yes|
repository not known to Travis CI (or no access?)
triggering sync: ... done
Michael-F-Bryan/cxx-experiment: enabled :)
```

Before we can do anything else we'll need to get a copy of the `bzip2`
library. I've elected to add it as a git submodule and compile from source
instead of relying on the user already having it installed.

```console
$ git submodule init
$ git submodule add git://sourceware.org/git/bzip2.git vendor/bzip2
Cloning into '/home/michael/Documents/cxx-experiment/vendor/bzip2'...
remote: Enumerating objects: 467, done.
remote: Counting objects: 100% (467/467), done.
remote: Compressing objects: 100% (241/241), done.
remote: Total 467 (delta 340), reused 304 (delta 225)0 KiB/s
Receiving objects: 100% (467/467), 593.74 KiB | 289.00 KiB/s, done.
Resolving deltas: 100% (340/340), done.
```

Now we've got the source code, let's see if we can compile it locally. It's
always a good idea to see if a project builds first, otherwise you risk
spending hours trying to figure out why your `build.rs` script isn't
compiling things properly only to realise the project never compiled in the
first place... Don't ask me how I know...

```console
$ cd vendor/bzip2
$ make libbz2.a
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c blocksort.c
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c huffman.c
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c crctable.c
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c randtable.c
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c compress.c
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c decompress.c
gcc -Wall -Winline -O2 -g -D_FILE_OFFSET_BITS=64 -c bzlib.c
rm -f libbz2.a
ar cq libbz2.a blocksort.o huffman.o crctable.o randtable.o compress.o decompress.o bzlib.o
ranlib libbz2.a
```

Seems simple enough, there are half a dozen C files which get compiled and
linked together to generate the final `libbz2.a`. There aren't any 3rd party
dependencies or complicated steps to worry about, so it's the ideal candidate
for the [cc][cc] crate.

First, let's add `cc` as a build dependency using [cargo-edit][ce].

```console
$ cargo add --build cc
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding cc v1.0.50 to build-dependencies
```

Then we can create a `build.rs` file which invokes `cc` and tells it to compile
our `bzip2` code.

```rust
// build.rs

use cc::Build;
use std::{env, path::PathBuf};

fn main() {
    let project_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let bzip2_dir = project_dir.join("vendor").join("bzip2");

    Build::new()
        .file(bzip2_dir.join("blocksort.c"))
        .file(bzip2_dir.join("huffman.c"))
        .file(bzip2_dir.join("crctable.c"))
        .file(bzip2_dir.join("randtable.c"))
        .file(bzip2_dir.join("compress.c"))
        .file(bzip2_dir.join("decompress.c"))
        .file(bzip2_dir.join("bzlib.c"))
        .define("_FILE_OFFSET_BITS", Some("64"))
        .warnings(false)
        .include(&bzip2_dir)
        .compile("bz2");
}
```

If you squint you'll notice that this is actually quite similar to the `gcc`
commands emitted by `make` earlier, just written more verbosely.

I normally have [cargo-watch][cw] running in the background so it'll
automatically recompile my code, run the tests, and generate API docs
whenever anything changes. Jumping over to the console shows the build script
seems to have run without any errors.

```console
$ cargo watch --clear \
    -x "check" \
    -x "test" \
    -x "doc --document-private-items" \
    -x "build --release"
    Finished dev [unoptimized + debuginfo] target(s) in 0.07s
    Finished test [unoptimized + debuginfo] target(s) in 0.07s
     Running target/debug/deps/cxx_experiment-a673c0eef131592e

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

   Doc-tests cxx-experiment

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

    Finished dev [unoptimized + debuginfo] target(s) in 0.09s
    Finished release [optimized] target(s) in 0.07s
```

Before going any further I'd like write a small smoke test to check everything
linked properly... Linker errors are the worst 😒

Conveniently, the library defines a `BZ2_bzlibVersion()` function for getting
the library version as a C string.

```c
// vendor/bzip2/bzlib.h

BZ_EXTERN const char * BZ_API(BZ2_bzlibVersion) (
      void
   );
```

The smoke test can sit at the bottom of `lib.rs` for now.

```rust
// src/lib.rs

#[cfg(test)]
mod tests {
    use super::*;
    use std::{ffi::CStr, os::raw::c_char};

    extern "C" {
        fn BZ2_bzlibVersion() -> *const c_char;
    }

    #[test]
    fn smoke_test() {
        unsafe {
            let got = BZ2_bzlibVersion();

            assert!(!got.is_null());
            let version_number = CStr::from_ptr(got).to_str().unwrap();
            assert_eq!(version_number, "1.0.8, 13-Jul-2019");
        }
    }
}
```

{{% notice note %}}
I cheated and found that `"1.0.8, 13-Jul-2019"` by looking through `bzip2`'s
source code. At this stage we just want to make sure everything works.
{{% /notice %}}

## Declaring the Foreign Function Interface

The `cxx` library takes a slightly different approach to `bindgen`

## Initial Bindings

## A Peek Under The Hood...

## Conclusions

[announcement]: https://www.reddit.com/r/rust/comments/elvfyn/ffi_like_its_2020_announcing_safe_ffi_for_rust_c/
[dtolnay]: https://github.com/dtolnay/
[bg]: https://github.com/rust-lang/bindgen
[bg-tutorial]: https://rust-lang.github.io/rust-bindgen/tutorial-0.html
[template]: https://github.com/Michael-F-Bryan/github-template
[cg]: https://crates.io/crates/cargo-generate
[cc]: https://crates.io/crates/cc
[ce]: https://crates.io/crates/cargo-edit
[cw]: https://crates.io/crates/cargo-watch
