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
fn path_to_cstring(path: &Path) -> Result<CString, InvalidPath> {
    use std::os::unix::ffi::OsStrExt;
    let bytes = path.as_os_str().as_bytes();
    CString::new(bytes).map_err(|_| InvalidPath)
}

#[cfg(not(unix))]
fn path_to_cstring(path: &Path) -> Result<CString, InvalidPath> {
    // Unfortunately, on Windows CHMLib uses CreateFileA() which means all
    // paths will need to be ascii. This can get quite messy, so let's just
    // cross our fingers and hope for the best?
    let rust_str = path.as_os_str().as_str().ok_or(InvalidPath)?;
    CString::new(rust_str).map_err(|_| InvalidPath)
}

#[derive(Error, Debug, Copy, Clone, PartialEq)]
#[error("Invalid Path")]
pub struct InvalidPath;
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

/// The error returned when we are unable to open a [`ChmFile`].
#[derive(Error, Debug, Copy, Clone, PartialEq)]
pub enum OpenError {
    #[error("Invalid path")]
    InvalidPath(#[from] InvalidPath),
    #[error("Unable to open the ChmFile")]
    Other,
}
```

To make sure we're not leaking memory, we can use `valgrind` to run a test that
constructs a `ChmFile` then immediately drops it.

The test:

```rust
// chmlib/src/lib.rs

#[test]
fn open_valid_chm_file() {
    let sample = sample_path();

    // open the file
    let chm_file = ChmFile::open(&sample).unwrap();
    // then immediately close it
    drop(chm_file);
}

fn sample_path() -> PathBuf {
    let project_dir = Path::new(env!("CARGO_MANIFEST_DIR"));
    let sample = project_dir.parent().unwrap().join("topics.classic.chm");
    assert!(sample.exists());

    sample
}
```

And the output from `valgrind` shows nothing is amiss.

```console
$ valgrind ../target/debug/deps/chmlib-8d8c740d57832498 open_valid_chm_file
==8953== Memcheck, a memory error detector
==8953== Copyright (C) 2002-2017, and GNU GPL'd, by Julian Seward et al.
==8953== Using Valgrind-3.14.0 and LibVEX; rerun with -h for copyright info
==8953== Command: /home/michael/Documents/chmlib/target/debug/deps/chmlib-8d8c740d57832498 open_valid_chm_file
==8953== 

running 1 test
test tests::open_valid_chm_file ... ok

test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out

==8953== 
==8953== HEAP SUMMARY:
==8953==     in use at exit: 0 bytes in 0 blocks
==8953==   total heap usage: 249 allocs, 249 frees, 43,273 bytes allocated
==8953== 
==8953== All heap blocks were freed -- no leaks are possible
==8953== 
==8953== For counts of detected and suppressed errors, rerun with: -v
==8953== ERROR SUMMARY: 0 errors from 0 contexts (suppressed: 0 from 0)
```

Next, we'll implement the `chm_resolve_object()` function.

```rust
pub const CHM_RESOLVE_SUCCESS : u32 = 0;
pub const CHM_RESOLVE_FAILURE: u32 = 1;
/* resolve a particular object from the archive */
pub unsafe extern "C" fn chm_resolve_object(
    h: *mut chmFile, 
    objPath: *const c_char, 
    ui: *mut chmUnitInfo
) -> c_int;
```

This is a fallible operation, so the `chm_resolve_object()` function returns a
status code indicating success or failure and a pointer to some `chmUnitInfo`
object which will be populated if something was found.

The [`std::mem::MaybeUninit`][uninit] type was create for the exact purpose of
representing the `ui` "out pointer".

For now we'll create an empty `UnitInfo` struct to be the Rust equivalent of
`chmUnitInfo`. It will be populated when we start reading items out of the
`ChmFile`.

```rust
// chmlib/src/lib.rs

impl ChmFile {
    ...

    /// Find a particular object in the archive.
    pub fn find<P: AsRef<Path>>(&mut self, path: P) -> Option<UnitInfo> {
        let path = path_to_cstring(path.as_ref()).ok()?;

        unsafe {
            // put an uninitialized chmUnitInfo on the stack
            let mut resolved = MaybeUninit::<chmlib_sys::chmUnitInfo>::uninit();

            // then try to resolve the unit info
            let ret = chmlib_sys::chm_resolve_object(
                self.raw.as_ptr(),
                path.as_ptr(),
                resolved.as_mut_ptr(),
            );

            if ret == chmlib_sys::CHM_RESOLVE_SUCCESS {
                // if successful, "resolved" would have been initialized by C
                Some(UnitInfo::from_raw(resolved.assume_init()))
            } else {
                None
            }
        }
    }
}

#[derive(Debug)]
pub struct UnitInfo;

impl UnitInfo {
    fn from_raw(ui: chmlib_sys::chmUnitInfo) -> UnitInfo { UnitInfo }
}
```

{{% notice info %}}
Note that `ChmFile::find()` takes `&mut self`, even though none of our Rust code
seems to do any mutation. This is because under the hood it uses things like 
`fseek()` to move back and forth around a file... which mutates internal state.
{{% /notice %}}

We can test that `ChmFile::find()` works using the sample CHM file from before.

```rust
// chmlib/src/lib.rs

#[test]
fn find_an_item_in_the_sample() {
    let sample = sample_path();
    let chm = ChmFile::open(&sample).unwrap();

    assert!(chm.find("/BrowserView.html").is_some());
    assert!(chm.find("doesn't exist.txt").is_none());
}
```

CHMLib exposes an API for inspecting items in the CHM file filtering the items
to inspect based on a bitmask. 

We'll be using the `bitflags` crate.

```console
$ cargo add bitflags
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding bitflags v1.2.1 to dependencies
```

The `Filter` flags are defined straight from the `#define`s in `chm_lib.h`.

```rust
// chmlib/src/lib.rs

bitflags::bitflags! {
    pub struct Filter: c_int {
        /// A normal file.
        const NORMAL = chmlib_sys::CHM_ENUMERATE_NORMAL as c_int;
        /// A meta file (typically used by the CHM system).
        const META = chmlib_sys::CHM_ENUMERATE_META as c_int;
        /// A special file (starts with `#` or `$`).
        const SPECIAL = chmlib_sys::CHM_ENUMERATE_SPECIAL as c_int;
        /// It's a file.
        const FILES = chmlib_sys::CHM_ENUMERATE_FILES as c_int;
        /// It's a directory.
        const DIRS = chmlib_sys::CHM_ENUMERATE_DIRS as c_int;
    }
}
```

We also need an `extern "C"` adaptor to use a Rust closure as a normal
function pointer.

```rust
// chmlib/src/lib.rs

unsafe extern "C" fn function_wrapper<F>(
    file: *mut chmlib_sys::chmFile,
    unit: *mut chmlib_sys::chmUnitInfo,
    state: *mut c_void,
) -> c_int
where
    F: FnMut(&mut ChmFile, UnitInfo) -> Continuation,
{
    // we need to make sure panics can't escape across the FFI boundary.
    let result = panic::catch_unwind(|| {
        // Use ManuallyDrop because we want to give the caller a `&mut ChmFile`
        // but want to make sure the destructor is never called (to
        // prevent double-frees).
        let mut file = ManuallyDrop::new(ChmFile {
            raw: NonNull::new_unchecked(file),
        });
        let unit = UnitInfo::from_raw(unit.read());
        // the opaque state pointer is guaranteed to point to an instance of our
        // closure
        let closure = &mut *(state as *mut F);
        closure(&mut file, unit)
    });

    match result {
        Ok(Continuation::Continue) => {
            chmlib_sys::CHM_ENUMERATOR_CONTINUE as c_int
        },
        Ok(Continuation::Stop) => chmlib_sys::CHM_ENUMERATOR_SUCCESS as c_int,
        Err(_) => chmlib_sys::CHM_ENUMERATOR_FAILURE as c_int,
    }
}
```

{{% notice warning %}}
This `function_wrapper` is a fairly tricky bit of `unsafe` code and there are
a couple things to keep in mind:

- The `state` pointer **must** point to an instance of our `F` closure
- Unwinding the stack from Rust to C is Undefined behaviour, and our `closure`
  may trigger a panic. We need to use `std::panic::catch_unwind()` to prevent
  panics from escaping the `function_wrapper`.
- The `chmlib_sys::chmFile` passed to `function_wrapper` is also pointed to by
  the calling `ChmFile`. We need to make sure `closure` is the only thing able
  to mutate the `chmlib_sys::chmFile` otherwise we'll open ourselves up to
  race conditions
- We want to pass a `&mut ChmFile` to the closure which means we'll need to 
  construct a temporary one on the stack using the `file` pointer. However if
  it gets dropped then the `chmlib_sys::chmFile` will be freed prematurely. This
  can be prevented using `std::mem::ManuallyDrop`.
{{% /notice %}}

We can now use `function_wrapper` to implement `ChmFile::for_each()`.

```rust
// chmlib/src/lib.rs

impl ChmFile {
    ...

    /// Inspect each item within the [`ChmFile`].
    pub fn for_each<F>(&mut self, filter: Filter, mut cb: F)
    where
        F: FnMut(&mut ChmFile, UnitInfo) -> Continuation,
    {
        unsafe {
            chmlib_sys::chm_enumerate(
                self.raw.as_ptr(),
                filter.bits(),
                Some(function_wrapper::<F>),
                &mut cb as *mut _ as *mut c_void,
            );
        }
    }

    /// Inspect each item within the [`ChmFile`] inside a specified directory.
    pub fn for_each_item_in_dir<F, P>(
        &mut self,
        filter: Filter,
        prefix: P,
        mut cb: F,
    ) where
        P: AsRef<Path>,
        F: FnMut(&mut ChmFile, UnitInfo) -> Continuation,
    {
        let path = match path_to_cstring(prefix.as_ref()) {
            Ok(p) => p,
            Err(_) => return,
        };

        unsafe {
            chmlib_sys::chm_enumerate_dir(
                self.raw.as_ptr(),
                path.as_ptr(),
                filter.bits(),
                Some(function_wrapper::<F>),
                &mut cb as *mut _ as *mut c_void,
            );
        }
    }
}
```

{{% notice info %}}
This trick works by using the `F` type parameter to instantiate
`function_wrapper` for our closure type. This is a trick that comes up often
when wanting to pass a Rust closure across the FFI barrier.
{{% /notice %}}

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
[uninit]: https://doc.rust-lang.org/std/mem/union.MaybeUninit.html#out-pointers