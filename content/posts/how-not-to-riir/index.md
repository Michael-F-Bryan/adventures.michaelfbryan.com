---
title: "How to not RiiR"
date: "2019-10-20T19:45:00+08:00"
tags:
- Rust
- FFI
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

- [Getting Started](#getting-started)
- [Building `chmlib-sys`](#building-chmlib-sys)
- [Writing a Safe Rust Wrapper](#writing-a-safe-rust-wrapper)
  - [Finding an Item by Name](#finding-an-item-by-name)
  - [Enumerating Items in a CHM File](#enumerating-items-in-a-chm-file)
  - [Reading File Contents](#reading-file-contents)
- [Implementing the Examples](#implementing-the-examples)
  - [Enumerating All Items](#enumerating-all-items)
  - [Extracting A CHM File To Disk](#extracting-a-chm-file-to-disk)
- [Where To From Here?](#where-to-from-here)

{{% notice note %}}
This article actually works towards a real-world project, I want to extract
some information from existing CHM files without doing all the hard work
myself. I'm lazy like that.

The [chmlib crate is published on crates.io](https://crate.io/crates/chmlib),
and the source code is [available on GitHub][repo]. If you found this useful
or spotted a bug, let me know on the blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/chmlib
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Getting Started

The first step in interfacing with a native library is to understand how it was
originally intended to work.

{{% notice info %}}
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

```command
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

{{% expand "CHMLib Header File" %}}
```c
/* $Id: chm_lib.h,v 1.10 2002/10/09 01:16:33 jedwin Exp $ */
/***************************************************************************
 *             chm_lib.h - CHM archive manipulation routines               *
 *                           -------------------                           *
 *                                                                         *
 *  author:     Jed Wing <jedwin@ugcs.caltech.edu>                         *
 *  version:    0.3                                                        *
 *  notes:      These routines are meant for the manipulation of microsoft *
 *              .chm (compiled html help) files, but may likely be used    *
 *              for the manipulation of any ITSS archive, if ever ITSS     *
 *              archives are used for any other purpose.                   *
 *                                                                         *
 *              Note also that the section names are statically handled.   *
 *              To be entirely correct, the section names should be read   *
 *              from the section names meta-file, and then the various     *
 *              content sections and the "transforms" to apply to the data *
 *              they contain should be inferred from the section name and  *
 *              the meta-files referenced using that name; however, all of *
 *              the files I've been able to get my hands on appear to have *
 *              only two sections: Uncompressed and MSCompressed.          *
 *              Additionally, the ITSS.DLL file included with Windows does *
 *              not appear to handle any different transforms than the     *
 *              simple LZX-transform.  Furthermore, the list of transforms *
 *              to apply is broken, in that only half the required space   *
 *              is allocated for the list.  (It appears as though the      *
 *              space is allocated for ASCII strings, but the strings are  *
 *              written as unicode.  As a result, only the first half of   *
 *              the string appears.)  So this is probably not too big of   *
 *              a deal, at least until CHM v4 (MS .lit files), which also  *
 *              incorporate encryption, of some description.               *
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU Lesser General Public License as        *
 *   published by the Free Software Foundation; either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 ***************************************************************************/

#ifndef INCLUDED_CHMLIB_H
#define INCLUDED_CHMLIB_H

#ifdef __cplusplus
extern "C" {
#endif

/* RWE 6/12/1002 */
#ifdef PPC_BSTR
#include <wtypes.h>
#endif

#ifdef WIN32
#ifdef __MINGW32__
#define __int64 long long
#endif
typedef unsigned __int64 LONGUINT64;
typedef __int64          LONGINT64;
#else
typedef unsigned long long LONGUINT64;
typedef long long          LONGINT64;
#endif

/* the two available spaces in a CHM file                      */
/* N.B.: The format supports arbitrarily many spaces, but only */
/*       two appear to be used at present.                     */
#define CHM_UNCOMPRESSED (0)
#define CHM_COMPRESSED   (1)

/* structure representing an ITS (CHM) file stream             */
struct chmFile;

/* structure representing an element from an ITS file stream   */
#define CHM_MAX_PATHLEN  (512)
struct chmUnitInfo
{
    LONGUINT64         start;
    LONGUINT64         length;
    int                space;
    int                flags;
    char               path[CHM_MAX_PATHLEN+1];
};

/* open an ITS archive */
#ifdef PPC_BSTR
/* RWE 6/12/2003 */
struct chmFile* chm_open(BSTR filename);
#else
struct chmFile* chm_open(const char *filename);
#endif

/* close an ITS archive */
void chm_close(struct chmFile *h);

/* methods for ssetting tuning parameters for particular file */
#define CHM_PARAM_MAX_BLOCKS_CACHED 0
void chm_set_param(struct chmFile *h,
                   int paramType,
                   int paramVal);

/* resolve a particular object from the archive */
#define CHM_RESOLVE_SUCCESS (0)
#define CHM_RESOLVE_FAILURE (1)
int chm_resolve_object(struct chmFile *h,
                       const char *objPath,
                       struct chmUnitInfo *ui);

/* retrieve part of an object from the archive */
LONGINT64 chm_retrieve_object(struct chmFile *h,
                              struct chmUnitInfo *ui,
                              unsigned char *buf,
                              LONGUINT64 addr,
                              LONGINT64 len);

/* enumerate the objects in the .chm archive */
typedef int (*CHM_ENUMERATOR)(struct chmFile *h,
                              struct chmUnitInfo *ui,
                              void *context);
#define CHM_ENUMERATE_NORMAL    (1)
#define CHM_ENUMERATE_META      (2)
#define CHM_ENUMERATE_SPECIAL   (4)
#define CHM_ENUMERATE_FILES     (8)
#define CHM_ENUMERATE_DIRS      (16)
#define CHM_ENUMERATE_ALL       (31)
#define CHM_ENUMERATOR_FAILURE  (0)
#define CHM_ENUMERATOR_CONTINUE (1)
#define CHM_ENUMERATOR_SUCCESS  (2)
int chm_enumerate(struct chmFile *h,
                  int what,
                  CHM_ENUMERATOR e,
                  void *context);

int chm_enumerate_dir(struct chmFile *h,
                      const char *prefix,
                      int what,
                      CHM_ENUMERATOR e,
                      void *context);

#ifdef __cplusplus
}
#endif

#endif /* INCLUDED_CHMLIB_H */
```
{{% /expand %}}

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

### Finding an Item by Name

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

### Enumerating Items in a CHM File

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

### Reading File Contents

The last function we need to wrap is actually reading the contents of a file
into memory with `chm_retrieve_object()`.

The implementation is almost trivial, and quite similar to the `std::io::Read`
trait except with the addition of a starting `offset`.

```rust
// chmlib/src/lib.rs

impl ChmFile {
    ...

    pub fn read(
        &mut self,
        unit: &UnitInfo,
        offset: u64,
        buffer: &mut [u8],
    ) -> Result<usize, ReadError> {
        let mut unit = unit.0.clone();

        let bytes_written = unsafe {
            chmlib_sys::chm_retrieve_object(
                self.raw.as_ptr(),
                &mut unit,
                buffer.as_mut_ptr(),
                offset,
                buffer.len() as _,
            )
        };

        if bytes_written >= 0 {
            Ok(bytes_written as usize)
        } else {
            Err(ReadError)
        }
    }
}

#[derive(Error, Debug, Copy, Clone, PartialEq)]
#[error("The read failed")]
pub struct ReadError;
```

It would be nice to provide more useful error messages than *"the read failed"*,
but reading through the source code for `chm_retrieve_object()` shows it doesn't
differentiate between:

- Returning `0` when all data is read
- Invalid arguments - null pointers or out of bounds reads return `0`
- failed file reads - `man 2 read` says `read()` may return `-1` and
set `errno`
- decompression failure - not being able to `malloc()` a scratch buffer or
  the decompression algorithm encountering malformed input will return `-1`

We can also test the `ChmFile::read()` function by looking for known input.

```rust
// chmlib/src/lib.rs

#[test]
fn read_an_item() {
    let sample = sample_path();
    let mut chm = ChmFile::open(&sample).unwrap();
    let filename = "/template/packages/core-web/css/index.responsive.css";

    // look for a known file
    let item = chm.find(filename).unwrap();

    // then read it into a buffer
    let mut buffer = vec![0; item.length() as usize];
    let bytes_written = chm.read(&item, 0, &mut buffer).unwrap();

    // we should have read everything
    assert_eq!(bytes_written, item.length() as usize);

    // ... and got what we expected
    let got = String::from_utf8(buffer).unwrap();
    assert!(got.starts_with(
        "html, body, div#i-index-container, div#i-index-body"
    ));
}
```

## Implementing the Examples

We've now covered the vast majority of the CHMLib API and by this point most
people would be happy to call it a day, however it's worth taking the time to
make the crate more approachable for our users. This is primarily accomplished
by adding examples and documentation, two things I've noticed the Rust and Go
communities tend to put a lot of effort into (probably thanks to `rustdoc` and
`godoc` being first-class citizens in the language toolchain).

Luckily the underlying CHMLib came with examples, so we should just be able
to port them to use the `chmlib` crate.

It's also useful as a sanity check to make sure the underlying library and our
wrapper generate the same output.

### Enumerating All Items

This example opens the provided CHM file and generates a table with information
about all items inside.

{{% expand "Original Example" %}}
```c
/* $Id: enum_chmLib.c,v 1.7 2002/10/09 12:38:12 jedwin Exp $ */
/***************************************************************************
 *          enum_chmLib.c - CHM archive test driver                        *
 *                           -------------------                           *
 *                                                                         *
 *  author:     Jed Wing <jedwin@ugcs.caltech.edu>                         *
 *  notes:      This is a quick-and-dirty test driver for the chm lib      *
 *              routines.  The program takes as its input the paths to one *
 *              or more .chm files.  It attempts to open each .chm file in *
 *              turn, and display a listing of all of the files in the     *
 *              archive.                                                   *
 *                                                                         *
 *              It is not included as a particularly useful program, but   *
 *              rather as a sort of "simplest possible" example of how to  *
 *              use the enumerate portion of the API.                      *
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU Lesser General Public License as        *
 *   published by the Free Software Foundation; either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 ***************************************************************************/

#include "chm_lib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 * callback function for enumerate API
 */
int _print_ui(struct chmFile *h,
              struct chmUnitInfo *ui,
              void *context)
{
    static char szBuf[128];
    memset(szBuf, 0, 128);
    if(ui->flags & CHM_ENUMERATE_NORMAL)
        strcpy(szBuf, "normal ");
    else if(ui->flags & CHM_ENUMERATE_SPECIAL)
        strcpy(szBuf, "special ");
    else if(ui->flags & CHM_ENUMERATE_META)
        strcpy(szBuf, "meta ");

    if(ui->flags & CHM_ENUMERATE_DIRS)
        strcat(szBuf, "dir");
    else if(ui->flags & CHM_ENUMERATE_FILES)
        strcat(szBuf, "file");

    printf("   %1d %8d %8d   %s\t\t%s\n",
           (int)ui->space,
           (int)ui->start,
           (int)ui->length,
           szBuf,
           ui->path);
    return CHM_ENUMERATOR_CONTINUE;
}

int main(int c, char **v)
{
    struct chmFile *h;
    int i;

    for (i=1; i<c; i++)
    {
        h = chm_open(v[i]);
        if (h == NULL)
        {
            fprintf(stderr, "failed to open %s\n", v[i]);
            exit(1);
        }

        printf("%s:\n", v[i]);
        printf(" spc    start   length   type\t\t\tname\n");
        printf(" ===    =====   ======   ====\t\t\t====\n");

        if (! chm_enumerate(h,
                            CHM_ENUMERATE_ALL,
                            _print_ui,
                            NULL))
            printf("   *** ERROR ***\n");

        chm_close(h);
    }

    return 0;
}

```
{{% /expand %}}

The `_print_ui()` function can be translated to Rust quite with ease. It's just
creating a description based on the `UnitInfo`'s flags and string concatenation,
then playing around with padding to generate tabulated output.

```rust
// chmlib/examples/enumerate-items.rs

fn describe_item(item: UnitInfo) {
    let mut description = String::new();

    if item.is_normal() {
        description.push_str("normal ");
    } else if item.is_special() {
        description.push_str("special ");
    } else if item.is_meta() {
        description.push_str("meta ");
    }

    if item.is_dir() {
        description.push_str("dir");
    } else if item.is_file() {
        description.push_str("file");
    }

    println!(
        "   {} {:8} {:8}   {}\t\t{}",
        item.space(),
        item.start(),
        item.length(),
        description,
        item.path().unwrap_or(Path::new("")).display()
    );
}
```

Then the `main()` function will do some naive command-line argument parsing before
opening the file and passing `describe()` to `ChmFile::for_each()`.

```rust
// chmlib/examples/enumerate-items.rs

fn main() {
    let filename = env::args()
        .nth(1)
        .unwrap_or_else(|| panic!("Usage: enumerate-items <filename>"));

    let mut file = ChmFile::open(&filename).expect("Unable to open the file");

    println!("{}:", filename);
    println!(" spc    start   length   type\t\t\tname");
    println!(" ===    =====   ======   ====\t\t\t====");

    file.for_each(Filter::all(), |_file, item| {
        describe_item(item);
        Continuation::Continue
    });
}
```

As a sanity check we'll compare the output from our Rust example with the
original.

```console
$ cargo run --example enumerate-items topics.classic.chm > rust-example.txt
$ cd vendor/CHMLib/src
$ clang chm_lib.c enum_chmLib.c lzx.c -o enum_chmLib
$ cd ../../..
$ ./vendor/CHMLib/src/enum_chmLib topics.classic.chm > c-example.txt
$ diff -u rust-example.txt c-example.txt
$ echo $?
0
```

The diff indicates both examples generate identical output, but to make sure
`diff` is actually doing something let's inject some dodgy output and see the
`diff` complain.

```diff
diff --git a/chmlib/examples/enumerate-items.rs b/chmlib/examples/enumerate-items.rs
index e68fa58..ef855ac 100644
--- a/chmlib/examples/enumerate-items.rs
+++ b/chmlib/examples/enumerate-items.rs
@@ -36,6 +36,10 @@ fn describe_item(item: UnitInfo) {
         description.push_str("file");
     }

+    if item.length() % 7 == 0 {
+        description.push_str("🦀");
+    }
+
     println!(
         "   {} {:8} {:8}   {}\t\t{}",
         item.space(),
```

And re-running with the new code:

```console
$ cargo run --example enumerate-items topics.classic.chm > rust-example.txt
$ diff -u rust-example.txt c-example.txt
--- rust-example.txt	2019-10-20 16:51:53.933560892 +0800
+++ c-example.txt	2019-10-20 16:40:42.007053966 +0800
@@ -1,9 +1,9 @@
 topics.classic.chm:
  spc    start   length   type			name
  ===    =====   ======   ====			====
-   0        0        0   normal dir🦀		/
+   0        0        0   normal dir		/
    1  5125797     4096   special file		/#IDXHDR
-   0        0        0   special file🦀		/#ITBITS
+   0        0        0   special file		/#ITBITS
    1  5104520      148   special file		/#IVB
    1  5132009     1227   special file		/#STRINGS
    0     1430     4283   special file		/#SYSTEM
@@ -13,9 +13,9 @@
...
```

Success!

### Extracting A CHM File To Disk

Another example provided with CHMLib is to extract all "normal" files to disk.

{{% expand "Original Example" %}}
```c
/* $Id: extract_chmLib.c,v 1.4 2002/10/10 03:24:51 jedwin Exp $ */
/***************************************************************************
 *          extract_chmLib.c - CHM archive extractor                       *
 *                           -------------------                           *
 *                                                                         *
 *  author:     Jed Wing <jedwin@ugcs.caltech.edu>                         *
 *  notes:      This is a quick-and-dirty chm archive extractor.           *
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU Lesser General Public License as        *
 *   published by the Free Software Foundation; either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 ***************************************************************************/

#include "chm_lib.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef WIN32
#include <windows.h>
#include <direct.h>
#define mkdir(X, Y) _mkdir(X)
#define snprintf _snprintf
#else
#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#endif

struct extract_context
{
    const char *base_path;
};

static int dir_exists(const char *path)
{
#ifdef WIN32
        /* why doesn't this work?!? */
        HANDLE hFile;

        hFile = CreateFileA(path,
                        FILE_LIST_DIRECTORY,
                        0,
                        NULL,
                        OPEN_EXISTING,
                        FILE_ATTRIBUTE_NORMAL,
                        NULL);
        if (hFile != INVALID_HANDLE_VALUE)
        {
        CloseHandle(hFile);
        return 1;
        }
        else
        return 0;
#else
        struct stat statbuf;
        if (stat(path, &statbuf) != -1)
                return 1;
        else
                return 0;
#endif
}

static int rmkdir(char *path)
{
    /*
     * strip off trailing components unless we can stat the directory, or we
     * have run out of components
     */

    char *i = strrchr(path, '/');

    if(path[0] == '\0'  ||  dir_exists(path))
        return 0;

    if (i != NULL)
    {
        *i = '\0';
        rmkdir(path);
        *i = '/';
        mkdir(path, 0777);
    }

#ifdef WIN32
        return 0;
#else
    if (dir_exists(path))
        return 0;
    else
        return -1;
#endif
}

/*
 * callback function for enumerate API
 */
int _extract_callback(struct chmFile *h,
              struct chmUnitInfo *ui,
              void *context)
{
    LONGUINT64 ui_path_len;
    char buffer[32768];
    struct extract_context *ctx = (struct extract_context *)context;
    char *i;

    if (ui->path[0] != '/')
        return CHM_ENUMERATOR_CONTINUE;

    /* quick hack for security hole mentioned by Sven Tantau */
    if (strstr(ui->path, "/../") != NULL)
    {
        /* fprintf(stderr, "Not extracting %s (dangerous path)\n", ui->path); */
        return CHM_ENUMERATOR_CONTINUE;
    }

    if (snprintf(buffer, sizeof(buffer), "%s%s", ctx->base_path, ui->path) > 1024)
        return CHM_ENUMERATOR_FAILURE;

    /* Get the length of the path */
    ui_path_len = strlen(ui->path)-1;

    /* Distinguish between files and dirs */
    if (ui->path[ui_path_len] != '/' )
    {
        FILE *fout;
        LONGINT64 len, remain=ui->length;
        LONGUINT64 offset = 0;

        printf("--> %s\n", ui->path);
        if ((fout = fopen(buffer, "wb")) == NULL)
    {
        /* make sure that it isn't just a missing directory before we abort */
        char newbuf[32768];
        strcpy(newbuf, buffer);
        i = strrchr(newbuf, '/');
        *i = '\0';
        rmkdir(newbuf);
        if ((fout = fopen(buffer, "wb")) == NULL)
              return CHM_ENUMERATOR_FAILURE;
    }

        while (remain != 0)
        {
            len = chm_retrieve_object(h, ui, (unsigned char *)buffer, offset, 32768);
            if (len > 0)
            {
                fwrite(buffer, 1, (size_t)len, fout);
                offset += len;
                remain -= len;
            }
            else
            {
                fprintf(stderr, "incomplete file: %s\n", ui->path);
                break;
            }
        }

        fclose(fout);
    }
    else
    {
        if (rmkdir(buffer) == -1)
            return CHM_ENUMERATOR_FAILURE;
    }

    return CHM_ENUMERATOR_CONTINUE;
}

int main(int c, char **v)
{
    struct chmFile *h;
    struct extract_context ec;

    if (c < 3)
    {
        fprintf(stderr, "usage: %s <chmfile> <outdir>\n", v[0]);
        exit(1);
    }

    h = chm_open(v[1]);
    if (h == NULL)
    {
        fprintf(stderr, "failed to open %s\n", v[1]);
        exit(1);
    }

    printf("%s:\n", v[1]);
    ec.base_path = v[2];
    if (! chm_enumerate(h,
                        CHM_ENUMERATE_ALL,
                        _extract_callback,
                        (void *)&ec))
        printf("   *** ERROR ***\n");

    chm_close(h);

    return 0;
}
```

{{% /expand %}}

The original example is quite verbose due to C's lack of high-level abstractions
and crippled standard library, hopefully our example will be much more readable.

The interesting code lies inside our `extract()` function. The code is rather
self-explanatory, so I'll let you read that instead of describing the process
of extracting items in plain English.

```rust
// chmlib/examples/extract.rs

fn extract(
    root_dir: &Path,
    file: &mut ChmFile,
    item: &UnitInfo,
) -> Result<(), Box<dyn Error>> {
    if !item.is_file() || !item.is_normal() {
        // we only care about normal files
        return Ok(());
    }
    let path = match item.path() {
        Some(p) => p,
        // if we can't get the path, ignore it and continue
        None => return Ok(()),
    };

    let mut dest = root_dir.to_path_buf();
    // Note: by design, the path for a normal file is absolute (starts with "/")
    // so when joining it with the root_dir we need to drop the initial "/".
    dest.extend(path.components().skip(1));

    // make sure the parent directory exists
    if let Some(parent) = dest.parent() {
        fs::create_dir_all(parent)?;
    }

    let mut f = File::create(dest)?;
    let mut start_offset = 0;
    // CHMLib doesn't give us a &[u8] with the file contents directly (e.g.
    // because it may be compressed) so we need to copy chunks to an
    // intermediate buffer
    let mut buffer = vec![0; 1 << 16];

    loop {
        let bytes_read = file.read(item, start_offset, &mut buffer)?;
        if bytes_read == 0 {
            // we've reached the end of the file
            break;
        } else {
            // write this chunk to the file and continue
            start_offset += bytes_read as u64;
            f.write_all(&buffer)?;
        }
    }

    Ok(())
}
```

Compared to `extract()`, our `main()` function is relatively simple, with the
handling of failures during extraction being the only real difference from the
previous example.

```rust
// chmlib/examples/extract.rs

fn main() {
    let args: Vec<_> = env::args().skip(1).collect();
    if args.len() != 2 || args.iter().any(|arg| arg.contains("-h")) {
        println!("Usage: extract <chm-file> <out-dir>");
        return;
    }

    let mut file = ChmFile::open(&args[0]).expect("Unable to open the file");

    let out_dir = PathBuf::from(&args[1]);

    file.for_each(Filter::all(), |file, item| {
        match extract(&out_dir, file, &item) {
            Ok(_) => Continuation::Continue,
            Err(e) => {
                eprintln!("Error: {}", e);
                Continuation::Stop
            },
        }
    });
}
```

Running this example against our sample CHM file gives us a set of files which
can be opened using a normal web browser.

```console
$ cargo run --example extract -- ./topics.classic.chm ./extracted
$ tree ./extracted
./extracted
├── default.html
├── BrowserForward.html
...
├── Images
│   ├── Commands
│   │   └── RealWorld
│   │       ├── BrowserBack.bmp
...
├── script
│   ├── _community
│   │   └── disqus.js
│   ├── hs-common.js
...
└── userinterface.html
$ firefox topics.classic/default.html
(opens default.html in firefox)
```

Some of the JavaScript is broken (I'm assuming implementation quirks with the
Microsoft Help viewer?) and there is no search functionality, but overall the
website is quite usable.

## Where To From Here?

The `chmlib` crate is now essentially feature complete and (with a couple minor
tweaks) ready to be published to crates.io.

There are a couple places I've left as an exercise to the reader, though:

- If the `closure` in `ChmFile::for_each()` or
  `ChmFile::for_each_item_in_dir()` panic, we should resume unwinding after
  returning from C to Rust instead of swallowing the error.

- It'd be nice if the simple case of iterating over every item in a `ChmFile`
  didn't need to return `Continuation::Continue` for the closure passed to
  `ChmFile::for_each()` and friends. This could probably be implemented by
  accepting `F: FnMut(&mut ChmFile, UnitInfo) -> C` where `C: Into<Continuation>`
  and then adding an `impl From<()> for Continuation`.

- Errors encountered during iteration (e.g. like our `extract()` example) should
  also be passed back to the caller of `ChmFile::for_each()` and abort iteration
  early. This could tie in with the previous point by adding an implementation
  of `impl<E> From<Result<(), E>> for Continuation where E: Error + 'static`

- Having to manually copy chunks into an intermediate buffer before writing them
  to a `File` in the `extract()` example is annoying. We may want to add a
  convenience function which will call `ChmFile:read()` in a loop and write the
  entire item into some `std::io::Write`r.

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
