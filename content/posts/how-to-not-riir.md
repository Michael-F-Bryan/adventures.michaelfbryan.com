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

[riir]: https://transitiontech.ca/random/RIIR
[chmlib]: https://github.com/jedwing/CHMLib
[at]: https://en.wikipedia.org/wiki/GNU_Autotools
[lzx]: https://en.wikipedia.org/wiki/LZX