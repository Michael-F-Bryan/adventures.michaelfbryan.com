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
that I'm quite familiar with, I thought I'd kick the tyres by wrapping part of
[the `libtorrent` library][upstream].

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/cxx-experiment
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Building the `libtorrent` Library

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

Before we can do anything else we'll need to get a copy of the `libtorrent`
library. I've elected to add it as a git submodule and compile from source
instead of relying on the user already having it installed.

```console
$ git submodule init
$ git submodule add https://github.com/arvidn/libtorrent vendor/libtorrent
Cloning into '/home/michael/Documents/cxx-experiment/vendor/libtorrent'...
remote: Enumerating objects: 149, done.
remote: Counting objects: 100% (149/149), done.
remote: Compressing objects: 100% (83/83), done.
remote: Total 120217 (delta 82), reused 86 (delta 59), pack-reused 120068
Receiving objects: 100% (120217/120217), 72.43 MiB | 1.09 MiB/s, done.
Resolving deltas: 100% (93988/93988), done.
```

Now we've got the source code, let's see if we can compile it locally. It's
always a good idea to see if a project builds first, otherwise you risk
spending hours trying to figure out why your `build.rs` script isn't
compiling things properly only to realise the project never compiled in the
first place... Don't ask me how I know...

First we'll `cd` into the `libtorrent` directory and have a look around. Maybe
there'll be instructions on how to compile everything.

```console
$ cd vendor/libtorrent
$ git rev-parse HEAD
ab07eceead59da9a85d60d406f1a99ad86dbb2d5
$ ls
appveyor.yml    configure.ac      libtorrent-rasterbar.pc.in          src
AUTHORS         CONTRIBUTING.rst  LibtorrentRasterbarConfig.cmake.in  test
autotool.sh     COPYING           LICENSE                             tools
bindings        docs              m4
bootstrap.sh    ed25519           Makefile.am
build_dist.sh   examples          NEWS
ChangeLog       fuzzers           README.rst
clang_tidy.jam  include           setup.py
cmake           Jamfile           simulation
CMakeLists.txt  Jamroot.jam       sonar-project.properties
```

Well this is interesting, it seems like there's half a dozen different build
systems at work here. I'm guessing instead of choosing a single build system and
making everyone use it, as new developers have come along they've brought their
favourite build system with them...

{{% notice info %}}
I can spot at least 3 build systems at work here...

The `CMakeLists.txt` file and `cmake` directory mark this as the root of a
`cmake` project.

Things like `configure.ac`, the various `*.in` files, and the `m4/` directory
stick out like a sore thumb. They indicate you can use [autotools][autotools]
to build `libtorrent`.

The `Jamfile` and `Jamroot.jam` belong to [boost-build][b2]. I can't say I've
ever used it before.

[autotools]: https://en.wikipedia.org/wiki/GNU_Autotools
[b2]: https://boostorg.github.io/build/
{{% /notice %}}

We want to make sure users of our crate don't have to mess around with
dependencies or compiling code themselves, so it's important to write
[a build script][build-script] to this for them. Having a robust and
cross-platform way of building the project is a really important part of this!

It looks like `cmake` will be our best option. The `autotools` suite isn't
really used much outside of GNU projects on Linux, and it's especially painful
to use on Windows. Boost-build seems a bit more obscure, so it's probably not
going to be as well-supported or easy to install.

Something else to remember is someone's already published [a cmake
crate][cmake-crate], which will make our lives easier.

Before we rush into writing our `build.rs` script we should see if everything
builds normally.

```console
$ mkdir build
$ cd build
$ cmake ..
-- The C compiler identification is GNU 9.2.1
-- The CXX compiler identification is GNU 9.2.1
-- Check for working C compiler: /usr/bin/cc
-- Check for working C compiler: /usr/bin/cc -- works
...
CMake Error at /usr/share/cmake-3.13/Modules/FindBoost.cmake:2100 (message):
  Unable to find the requested Boost libraries.

  Boost version: 1.67.0

  Boost include path: /usr/include

  Could not find the following Boost libraries:

          boost_system

  No Boost libraries were found.  You may need to set BOOST_LIBRARYDIR to the
  directory containing Boost libraries or BOOST_ROOT to the location of
  Boost.
...
-- The following REQUIRED packages have not been found:

 * Boost

-- Configuring incomplete, errors occurred!
```

Hmm... Looks like we need to install the full boost library.

```console
$ sudo apt install libboost-all-dev
[sudo] password for michael:
Reading package lists... Done
Building dependency tree
Reading state information... Done
The following additional packages will be installed:
  libboost-chrono1.67-dev libboost-chrono1.67.0 libboost-container-dev libboost-container1.67-dev libboost-container1.67.0
  libboost-context-dev libboost-context1.67-dev libboost-context1.67.0 libboost-coroutine-dev libboost-coroutine1.67-dev
  libboost-coroutine1.67.0 libboost-date-time-dev libboost-date-time1.67-dev libboost-exception-dev libboost-exception1.67-dev
  ...
  mpi-default-dev ocl-icd-libopencl1 openmpi-bin openmpi-common
0 to upgrade, 118 to newly install, 0 to remove and 1 not to upgrade.
Need to get 34.5 MB of archives.
After this operation, 238 MB of additional disk space will be used.
Do you want to continue? [Y/n] y
Get:1 http://au.archive.ubuntu.com/ubuntu eoan/main amd64 libgfortran-9-dev amd64 9.2.1-9ubuntu2 [684 kB]
...
```

After installing half the internet let's give it another shot.

```console
$ cmake ..
-- Compiler default is C++14
-- Building in C++14 mode
-- Boost version: 1.67.0
...

-- Configuring done
-- Generating done
-- Build files have been written to: /home/michael/Documents/cxx-experiment/vendor/libtorrent/build
$ ls
bindings  cmake_install.cmake  CMakeCache.txt  CMakeFiles  LibtorrentRasterbar
Makefile  torrent-rasterbar-pkgconfig
$ make -j8
```

`cmake` isn't normally known for its concise output, but at least everything
builds!

{{% notice tip %}}
Something to keep in mind is how long it takes to compile `libtorrent`. On my
laptop (8 cores, 12GB RAM) a full build with 1 core (the default when running
`make`) took so long (28 minutes!) I ended up leaving it running overnight.

In comparison, building with all 8 cores (`make -j8`) only took about 5 minutes.
Hopefully the `cmake` crate is smart enough to enable parallelism where
possible, otherwise our users aren't going to be happy...
{{% /notice %}}












I normally have [cargo-watch][cw] running in the background so it'll
automatically recompile my code, run the tests, and generate API docs
whenever anything changes. Jumping over to the console shows our build script
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

{{% notice warning %}}
TODO: Write a simple smoke test
{{% /notice %}}














## Declaring the Foreign Function Interface

## Initial Bindings

## A Peek Under The Hood...

## Conclusions

[announcement]: https://www.reddit.com/r/rust/comments/elvfyn/ffi_like_its_2020_announcing_safe_ffi_for_rust_c/
[dtolnay]: https://github.com/dtolnay/
[upstream]: https://github.com/arvidn/libtorrent
[bg]: https://github.com/rust-lang/bindgen
[bg-tutorial]: https://rust-lang.github.io/rust-bindgen/tutorial-0.html
[template]: https://github.com/Michael-F-Bryan/github-template
[cg]: https://crates.io/crates/cargo-generate
[cc]: https://crates.io/crates/cc
[ce]: https://crates.io/crates/cargo-edit
[cw]: https://crates.io/crates/cargo-watch
[build-script]: https://doc.rust-lang.org/cargo/reference/build-scripts.html
[cmake-crate]: https://crates.io/crates/cmake