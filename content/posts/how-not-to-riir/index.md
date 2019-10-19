---
title: "How to not RiiR"
date: "2019-10-19T14:06:47+08:00"
draft: true
tags:
- rust
---

Once you get past the growing pains of the *Borrow Checker* and realise Rust
gives you the power to do things which would be unheard of (or just plain 
dangerous) in other languages, the temptation to [*Rewrite it in Rust*][riir]
can be quite strong. However at best, the temptation to *RiiR* is unproductive
(unnecessary duplication of effort), and at worst it can promote the creation
of buggy software (why would *you* be better equipped to write a library for
some domain-specific purpose than the original author?).

A much better alternative is to reuse the original library and just publish a
safe interface to it.

## Getting Started

The first step in interfacing with a native library is to understand how it was
originally intended to work.

{{% notice tip %}}
Not only does this show us how to use the library, it also acts as a sanity
check to make sure it builds, as well as providing build instructions and
potential tests or examples.

**Do not skip this step!**
{{% /notice %}}

The library we'll be binding to is [CHMLib][chmlib], a C library for reading
*Microsoft HTML Help Files* (`.chm`).

First, we'll make a new project and vendor `CHMLib` using git submodules.

```console
$ git init chmlib && cd chmlib
  Initialized empty Git repository in /home/michael/Documents/chmlib/.git/
$ touch README.md Cargo.toml
$ cargo new --lib chmlib
  Created library `chmlib` package
$ cargo new --lib chmlib-sys
  Created library `chmlib-sys` package
$ cat Cargo.toml 
  [workspace]
  members = ["chmlib", "chmlib-sys"]
$ git submodule add git@github.com:jedwing/CHMLib.git vendor/CHMLib
  Cloning into '/home/michael/Documents/chmlib/vendor/CHMLib'...
  remote: Enumerating objects: 99, done.
  remote: Total 99 (delta 0), reused 0 (delta 0), pack-reused 99
  Receiving objects: 100% (99/99), 375.51 KiB | 430.00 KiB/s, done.
  Resolving deltas: 100% (45/45), done.
```

We can then use the `tree` command to see what files are contained in the 
repository.

```
$ tree vendor/CHMLib
vendor/CHMLib
├── acinclude.m4
├── AUTHORS
├── ChangeLog
├── ChmLib-ce.zip
├── ChmLib-ds6.zip
├── configure.in
├── contrib
│   └── mozilla_helper.sh
├── COPYING
├── Makefile.am
├── NEWS
├── NOTES
├── README
└── src
    ├── chm_http.c
    ├── chm_lib.c
    ├── chm_lib.h
    ├── enum_chmLib.c
    ├── enumdir_chmLib.c
    ├── extract_chmLib.c
    ├── lzx.c
    ├── lzx.h
    ├── Makefile.am
    ├── Makefile.simple
    └── test_chmLib.c

2 directories, 23 files
```

It looks like the original library uses [GNU Autotools][at] as a build system.
This may be problematic because it'll require all users of our `chmlib` crate
(and their users) to have Autotools installed. 

{{% notice note %}}
If possible we'll try to avoid this "viral" need to install a dependency
system-wide by invoking the C compiler manually, but file that thought away
for later.
{{% /notice %}}

Upon further inspection, the `lzx.h` and `lzx.c` files are vendored copies of
code for decompression using the [LZX][lzx] compression algorithm. Normally it'd
be better to link with whatever `lzx` library is installed on the user's
machine so we receive updates, but it'll be a lot easier to compile it into 
`chmlib`.

The `enum_chmLib.c`, `enumdir_chmLib.c`, and `extract_chmLib.c` appear to be
examples displaying the usage of `chm_enumerate()`, `chm_enumerate_dir()`, and
`chm_retrieve_object()` respectively. These should be useful...

The `test_chmLib.c` file appears to be another example, this time showing how
to find a single document from the CHM file and extract it to disk.

`chm_http.c` appears to be a simple HTTP server which serves the contents of a
CHM file online. Let's ignore it for now.

Now we've had a look around the various files under `vendor/CHMLib/src/`, let's
try to build the library.

To be perfectly honest, this library is small enough that I can kinda stumble my
way through until one of the examples runs.

```console
$ clang chm_lib.c enum_chmLib.c -o enum_chmLib
  /usr/bin/ld: /tmp/chm_lib-537dfe.o: in function `chm_close':
  chm_lib.c:(.text+0x8fa): undefined reference to `LZXteardown'
  /usr/bin/ld: /tmp/chm_lib-537dfe.o: in function `_chm_decompress_region':
  chm_lib.c:(.text+0x18ca): undefined reference to `LZXinit'
  /usr/bin/ld: /tmp/chm_lib-537dfe.o: in function `_chm_decompress_block':
  chm_lib.c:(.text+0x2900): undefined reference to `LZXreset'
  /usr/bin/ld: chm_lib.c:(.text+0x2a4b): undefined reference to `LZXdecompress'
  /usr/bin/ld: chm_lib.c:(.text+0x2abe): undefined reference to `LZXreset'
  /usr/bin/ld: chm_lib.c:(.text+0x2bf4): undefined reference to `LZXdecompress'
  clang: error: linker command failed with exit code 1 (use -v to see invocation)
```

Okay, the linker can't find some `LZX*` routines...

```console
$ clang chm_lib.c enum_chmLib.c lzx.c -o enum_chmLib
```

Well... that worked?

To make sure it works I've downloaded a sample help file from the internet.

```console
$ curl http://www.innovasys.com/static/hs/samples/topics.classic.chm.zip -o topics.classic.chm.zip
$ unzip topics.classic.chm.zip 
Archive:  topics.classic.chm.zip
  inflating: output/compiled/topics.classic.chm
$ file output/compiled/topics.classic.chm 
output/compiled/topics.classic.chm: MS Windows HtmlHelp Data
```

Let's see what `enum_chLib` makes of it.

```console
$ ./enum_chmLib output/compiled/topics.classic.chm 
output/compiled/topics.classic.chm:
 spc    start   length   type			name
 ===    =====   ======   ====			====
   0        0        0   normal dir		/
   1  5125797     4096   special file		/#IDXHDR
   ...
   1  4944434    11234   normal file		/BrowserView.html
   ...
   0        0        0   normal dir		/flash/
   1   532689      727   normal file		/flash/expressinstall.swf
   0        0        0   normal dir		/Images/Commands/RealWorld/
   1    24363     1254   normal file		/Images/Commands/RealWorld/BrowserBack.bmp
   ...
   1    35672     1021   normal file		/Images/Employees24.gif
   ...
   1  3630715   200143   normal file		/template/packages/jquery-mobile/script/jquery.mobile-1.4.5.min.js
   ...
   0      134     1296   meta file		::DataSpace/Storage/MSCompressed/Transform/{7FC28940-9D31-11D0-9B27-00A0C91E9C7C}/InstanceData/ResetTable
```

Hmm, looks like even help files pull in jQuery ¯\\\_(ツ)\_/¯

## Building `chmlib-sys`

Now we can kinda use CHMLib we need to write a `chmlib-sys` crate which will
manage building the native library so it can be linked by `rustc`, and declare 
the various functions it exposes.

To build the library we'll need to write a `build.rs` file. This will invoke the
C compiler using the [`cc`][cc] crate and send various messages to `rust` to 
make sure everything links properly.

{{% notice info %}}
For our purposes we can pass all the hard work off to the [`cc`][cc] crate, but
normally it's not that simple. Check out the [docs on build scripts][build-rs]
for more detailed information.

[build-rs]: https://doc.rust-lang.org/cargo/reference/build-scripts.html
[cc]: https://docs.rs/cc
{{% /notice %}}

First, add the `cc` crate as a build dependency for `chmlib-sys`.

```console
$ cd chmlib-sys
$ cargo add --build cc
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding cc v1.0.46 to build-dependencies
```

Then add a `build.rs` file.

```rust
// chmlib-sys/build.rs

use cc::Build;
use std::{env, path::PathBuf};

fn main() {
    let project_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap())
        .canonicalize()
        .unwrap();
    let root_dir = project_dir.parent().unwrap();
    let src = root_dir.join("vendor").join("CHMLib").join("src");

    Build::new()
        .file(src.join("chm_lib.c"))
        .file(src.join("lzx.c"))
        .include(&src)
        .warnings(false)
        .compile("chmlib");
}
```

We also need to tell `cargo` that `chmlib-sys` links to the `chmlib` native 
library. Cargo will make sure only one crate in a dependency graph can link to
a particular native library, this helps prevent undecipherable linker errors
due to duplicate symbols or accidentally using incompatible C libraries.

```diff
--- a/chmlib-sys/Cargo.toml
+++ b/chmlib-sys/Cargo.toml
@@ -3,7 +3,13 @@ name = "chmlib-sys"
 version = "0.1.0"
 authors = ["Michael Bryan <michaelfbryan@gmail.com>"]
 edition = "2018"
 description = "Raw bindings to the CHMLib C library"
 license = "LGPL"
 repository = "https://github.com/Michael-F-Bryan/chmlib"
+links = "chmlib"
+build = "build.rs"
 
 [dependencies]
 
 [build-dependencies]
 cc = { version = "1.0" }
```

Next we need to declare the various functions exposed by the `chmlib` C library
so they can be called from Rust.

There's a project called [bindgen][bg] which does exactly this. You give it a
header file and it'll automatically generate FFI bindings.

```console
$ cargo install bindgen
$ bindgen ../vendor/CHMLib/src/chm_lib.h \
    -o src/lib.rs \
    --raw-line '#![allow(non_snake_case, non_camel_case_types)]'
$ head src/lib.rs 
  /* automatically generated by rust-bindgen */
  
  #![allow(non_snake_case, non_camel_case_types)]
  
  pub const CHM_UNCOMPRESSED: u32 = 0;
  pub const CHM_COMPRESSED: u32 = 1;
  pub const CHM_MAX_PATHLEN: u32 = 512;
  pub const CHM_PARAM_MAX_BLOCKS_CACHED: u32 = 0;
  pub const CHM_RESOLVE_SUCCESS: u32 = 0;
  pub const CHM_RESOLVE_FAILURE: u32 = 1;
$ tail src/lib.rs
  extern "C" {
      pub fn chm_enumerate_dir(
          h: *mut chmFile,
          prefix: *const ::std::os::raw::c_char,
          what: ::std::os::raw::c_int,
          e: CHM_ENUMERATOR,
          context: *mut ::std::os::raw::c_void,
      ) -> ::std::os::raw::c_int;
  }
```

{{% notice tip %}}
I would highly recommend browsing the [Bindgen User
Guide](https://rust-lang.github.io/rust-bindgen/) If you want to know how to
tweak the output.
{{% /notice %}}

At this point it's worth writing a small [*Smoke Test*][st] to make sure things
link properly and we can call functions from the C library.

```rust
// chmlib-sys/tests/smoke_test.rs

// we need to convert the Path to a char* with trailing NULL. Unfortunately on
// Windows OsStr (and therefore Path) is a [u16] under the hood and can't be
// properly passed in as a char* string.
#![cfg(unix)]

use std::{ffi::CString, os::unix::ffi::OsStrExt, path::Path};

#[test]
fn open_example_file() {
    let project_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let sample_chm = project_dir.parent().unwrap().join("topics.classic.chm");
    let c_str = CString::new(sample_chm.as_os_str().as_bytes()).unwrap();

    unsafe {
        let handle = chmlib_sys::chm_open(c_str.as_ptr());
        assert!(!handle.is_null());
        chmlib_sys::chm_close(handle);
    }
}
```

Running `cargo test` shows that everything seems to be working okay.

```console
$ cargo test
    Finished test [unoptimized + debuginfo] target(s) in 0.03s
     Running /home/michael/Documents/chmlib/target/debug/deps/chmlib_sys-2ffd7b11a9fd8437

running 1 test
test bindgen_test_layout_chmUnitInfo ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

     Running /home/michael/Documents/chmlib/target/debug/deps/smoke_test-f7be9810412559dc

running 1 test
test open_example_file ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

   Doc-tests chmlib-sys

running 0 tests

test result: ok. 0 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

## Writing a Safe Rust Wrapper

We can now *technically* use the CHMLib from Rust, but it requires a lot of 
`unsafe` to call library functions. That's okay for a quick'n'dirty
implementation, but if this is going to be published to crates.io it's worth
writing a safe wrapper around the `unsafe` code.

Looking at the `chmlib-sys` crate with `cargo doc --open` shows it exposes half
a dozen functions, most of which accept a `*mut ChmFile` as the first parameter.
This maps quite nicely to object methods.

Let's start off by creating a type that uses `chm_open()` in its constructor and
calls `chm_close()` in its destructor.

```rust
pub unsafe extern "C" fn chm_open(filename: *const c_char) -> *mut chmFile;
pub unsafe extern "C" fn chm_close(h: *mut chmFile);
```

To make error handling easier we'll pull in the [`thiserror`][te] crate to 
automatically derive `std::error::Error`.

```console
$ cd chmlib
$ cargo add thiserror
```

We now need some way to convert from a `std::path::Path` to a `*const c_char`.
Unfortunately, due to various OS-specific quirks [this][1] [isn't][2] 
[simple][3].

```rust
// chmlib/src/lib.rs

use thiserror::Error;
use std::{ffi::CString, path::Path};

#[cfg(unix)]
fn path_to_cstring(path: &Path) -> Result<CString, OpenError> {
    use std::os::unix::ffi::OsStrExt;
    let bytes = path.as_os_str().as_bytes();
    CString::new(bytes).map_err(|_| OpenError::InvalidPath)
}

#[cfg(not(unix))]
fn path_to_cstring(path: &Path) -> Result<CString, OpenError> {
    // Unfortunately, on Windows CHMLib uses CreateFileA() which means all
    // paths will need to be ascii. This can get quite messy, so let's just
    // cross our fingers and hope for the best?
    let rust_str = path.as_os_str().as_str().ok_or(OpenError::InvalidPath)?;
    CString::new(rust_str).map_err(|_| OpenError::InvalidPath)
}

/// The error returned when we are unable to open a [`ChmFile`].
#[derive(Error, Debug, Copy, Clone, PartialEq)]
pub enum OpenError {
    #[error("Invalid path")]
    InvalidPath,
    #[error("Unable to open the ChmFile")]
    Other,
}
```

Next we'll create a `ChmFile` which contains a non-null pointer to a 
`chmlib_sys::chmFile`. If `chm_open()` returns a null pointer we'll know that
opening the file failed and some sort of error occurred.

```rust
// chmlib/src/lib.rs

use std::{ffi::CString, path::Path, ptr::NonNull};

#[derive(Debug)]
pub struct ChmFile {
    raw: NonNull<chmlib_sys::chmFile>,
}

impl ChmFile {
    pub fn open<P: AsRef<Path>>(path: P) -> Result<ChmFile, OpenError> {
        let c_path = path_to_cstring(path.as_ref())?;

        // safe because we know c_path is valid
        unsafe {
            let raw = chmlib_sys::chm_open(c_path.as_ptr());

            match NonNull::new(raw) {
                Some(raw) => Ok(ChmFile { raw }),
                None => Err(OpenError::Other),
            }
        }
    }
}

impl Drop for ChmFile {
    fn drop(&mut self) {
        unsafe {
            chmlib_sys::chm_close(self.raw.as_ptr());
        }
    }
}
```

[riir]: https://transitiontech.ca/random/RIIR
[chmlib]: https://github.com/jedwing/CHMLib
[at]: https://en.wikipedia.org/wiki/GNU_Autotools
[lzx]: https://en.wikipedia.org/wiki/LZX
[cc]: https://docs.rs/cc
[bg]: https://github.com/rust-lang/rust-bindgen
[st]: http://softwaretestingfundamentals.com/smoke-testing/
[te]: https://github.com/dtolnay/thiserror
[1]: https://stackoverflow.com/questions/38948669/whats-the-most-direct-way-to-convert-a-path-to-a-c-char "Whats the most direct way to convert a Path to a *c_char?"
[2]: https://stackoverflow.com/questions/29590943/how-to-convert-a-path-into-a-const-char-for-ffi "How to convert a Path into a const char* for FFI?"
[3]: https://stackoverflow.com/questions/46342644/how-can-i-get-a-path-from-a-raw-c-string-cstr-or-const-u8 "How can I get a Path from a raw C string (CStr or *const u8)?"