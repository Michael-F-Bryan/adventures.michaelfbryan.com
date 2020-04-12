---
title: "How to RiiR"
date: "2019-12-02T01:00:00+08:00"
tags:
- Rust
---

In [a previous article][previous-riir] we've talked about how you can avoid
rewriting a library in Rust when you don't need to. But what about the times
when you really *do* need to?

In most languages you'd need to rewrite the entire library from the ground
up, waiting until the port is almost finished before you can start seeing
results. These sorts of ports tend to be quite expensive and error-prone, and
often they'll fail midway and you'll have nothing to show for your effort.
*Joel Spolsky* does a much better job of explaining this than I ever could, see
[his article on why full rewrites are a bad idea][rewrites] for more.

However, Rust has a killer feature when it comes to this sort of thing. It
can call into C code with no overhead (i.e. the runtime doesn't need to
inject automatic marshalling like [C#'s P/Invoke][p-invoke]) and it can
expose functions which can be consumed by C just like any other C function.
This opens the door for an alternative approach:

Port the library to Rust one function at a time.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/tinyvm-rs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Getting Started

Before we do anything else, we're going to need to make a new project. I've got
[a template][template] project that sets up some nice things like CI and
licenses that I'll use with [`cargo-generate`][cg].

```console
$ cargo generate --git https://github.com/Michael-F-Bryan/github-template --name tinyvm-rs
$ cd tinyvm-rs && tree
tree -I 'vendor|target'
.
├── Cargo.toml
├── LICENSE_APACHE.md
├── LICENSE_MIT.md
├── README.md
├── .travis.yml
└── src
    └── lib.rs

1 directory, 6 files
```

Now that's out of the way our first real task will be to build the library we
want to port, and get to know it a bit better.

In this case we're porting [jakogut/tinyvm][tinyvm],

> TinyVM is a small, fast, lightweight virtual machine written in pure ANSI C.

To make referencing it easier in the future we'll add the repository as a
submodule to our project.

```console
$ git submodule add https://github.com/jakogut/tinyvm vendor/tinyvm
```

Now we've got a copy of the source code, let's have a look at the `README.md`
for build instructions.

> TinyVM is a virtual machine with the goal of having a small footprint.
> Low memory usage, a small amount of code, and a small binary.
>
> Building can be accomplished on UNIX-like systems with make and GCC.
>
> There are no external dependencies, save the C standard library.
>
> **Building can be accomplished using "make," or "make rebuild".**
>
> To build a debug version, add "DEBUG=yes" after "make". To build a binary with
> profiling enabled, add "PROFILE=yes" after "make".
>
> I can be reached at "joseph.kogut(at)gmail.com"

(emphasis added)

Okay, let's `cd` into the `tinyvm` directory and see if the build will *Just
Work*.

```console
$ cd vendor/tinyvm
$ make
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_program.c -o libtvm/tvm_program.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_lexer.c -o libtvm/tvm_lexer.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm.c -o libtvm/tvm.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_htab.c -o libtvm/tvm_htab.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_memory.c -o libtvm/tvm_memory.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_preprocessor.c -o libtvm/tvm_preprocessor.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_parser.c -o libtvm/tvm_parser.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_file.c -o libtvm/tvm_file.o
ar rcs lib/libtvm.a libtvm/tvm_program.o libtvm/tvm_lexer.o libtvm/tvm.o libtvm/tvm_htab.o libtvm/tvm_memory.o libtvm/tvm_preprocessor.o libtvm/tvm_parser.o libtvm/tvm_file.o
clang src/tvmi.c -ltvm -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -Llib/ -o bin/tvmi
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c tdb/main.c -o tdb/main.o
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c tdb/tdb.c -o tdb/tdb.o
clang tdb/main.o tdb/tdb.o -ltvm -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -Llib/ -o bin/tdb
```

I really like it when C libraries will compile straight out of the box without
needing to install random `*-dev` packages or mess with the build system 🎉

Unfortunately the library doesn't contain any tests so we won't be able to
(initially) make sure individual functions have been translated correctly,
but it *does* contain an example interpreter that we can use to explore the
high-level functionality.

So we know we can build it from the command-line without much hassle, now
we need to make sure our `tinyvm` crate can build everything programmatically.

This is where build scripts come in. Our strategy will be for the Rust crate to
use a `build.rs` build script and the [`cc`][cc] crate to invoke the equivalent
commands to our `make` invocation. From there we can link to `libtvm` from Rust
just like any other native library.

We'll need to add the `cc` crate as a dependency.

```console
$ cargo add --build cc
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding cc v1.0.47 to build-dependencies
```

And also make sure `build.rs` compiles the `libtvm` source code.

```rust
// build.rs

use cc::Build;
use std::path::Path;

fn main() {
    let tinyvm = Path::new("vendor/tinyvm");
    let include = tinyvm.join("include");
    let src = tinyvm.join("libtvm");

    Build::new()
        .warnings(false)
        .file(src.join("tvm_file.c"))
        .file(src.join("tvm_htab.c"))
        .file(src.join("tvm_lexer.c"))
        .file(src.join("tvm_memory.c"))
        .file(src.join("tvm_parser.c"))
        .file(src.join("tvm_preprocessor.c"))
        .file(src.join("tvm_program.c"))
        .file(src.join("tvm.c"))
        .include(&include)
        .compile("tvm");
}
```

{{% notice note %}}
If you've looked at the `cc` crate's documentation you may have noticed there's
a [`Build::files()`][files] method which accepts an iterator of paths. We
*could* have programmatically detected all the `*.c` files inside
`vendor/tinyvm/libtvm`, but because we're porting code one function at a time
it'll be much easier to delete individual `.file()` calls as bits are ported.

[files]: https://docs.rs/cc/1.0.47/cc/struct.Build.html#method.files
{{% /notice %}}

We also need a way to let Rust know which functions it can call from `libtvm`.
This is typically done by writing definitions for each function in an
[`extern` block][extern], but luckily a tool called [`bindgen`][bg] exists which
can read in a C-style header file and generate the definitions for us.

Let's generate bindings from `vendor/tinyvm/include/tvm/tvm.h`.

```console
$ cargo install bindgen
$ bindgen vendor/tinyvm/include/tvm/tvm.h -o src/ffi.rs
$ wc --lines src/ffi.rs
992 src/ffi.rs
```

We'll need to add the `ffi` module to our crate.

```rust
// src/lib.rs

#[allow(non_camel_case_types, non_snake_case)]
pub mod ffi;
```

Looking at `tinyvm`'s `src/` directory, we find the source code for a `tinyvm`
interpreter.

```c
// vendor/tinyvm/src/tvmi.c

#include <stdlib.h>
#include <stdio.h>

#include <tvm/tvm.h>

int main(int argc, char **argv)
{
	struct tvm_ctx *vm = tvm_vm_create();

	if (vm != NULL && tvm_vm_interpret(vm, argv[1]) == 0)
		tvm_vm_run(vm);

	tvm_vm_destroy(vm);

	return 0;
}
```

It's incredibly simple. Which is nice considering we'll be using this
interpreter as one of our examples.

For now, let's translate it directly to Rust and stick it in the `examples/`
directory.

```rust
// examples/tvmi.rs

use std::{env, ffi::CString};
use tinyvm::ffi;

fn main() {
    let filename = CString::new(env::args().nth(1).unwrap()).unwrap();
    // cast away the `const` because that's what libtvm expects
    let filename = filename.as_ptr() as *mut _;

    unsafe {
        let vm = ffi::tvm_vm_create();

        if !vm.is_null() && ffi::tvm_vm_interpret(vm, filename) == 0 {
            ffi::tvm_vm_run(vm);
        }

        ffi::tvm_vm_destroy(vm);
    }
}
```

As a sanity check, we can also run the virtual machine and make sure it all
works.

```console
$ cargo run --example tvmi -- vendor/tinyvm/programs/tinyvm/fact.vm
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/examples/tvmi vendor/tinyvm/programs/tinyvm/fact.vm`
1
2
6
24
120
720
5040
40320
362880
3628800
```

LGTM 👍

## Low Hanging Fruit

When you start out with something like this it's tempting to dive into the most
important functions and port those first. Try to resist this urge. It can be
easy to bite off more than you can chew and end up either wasting time or
becoming demoralized and give up.

Instead, let's look for the easiest item.

```console
$ ls libtvm
tvm.c  tvm_file.c  tvm_htab.c  tvm_lexer.c  tvm_memory.c  tvm_parser.c
tvm_preprocessor.c  tvm_program.c
```

That `tvm_htab.c` file looks promising. I'm pretty sure `htab` stands for
*"Hash Table"*, and Rust's standard library already contains a high-quality
implementation. We should be able to swap that in easily enough.

Let's look at the `tvm_htab.h` header file and see what we're dealing with.

```c
// vendor/tinyvm/include/tvm/tvm_htab.h

#ifndef TVM_HTAB_H_
#define TVM_HTAB_H_

#define KEY_LENGTH 64
#define HTAB_SIZE 4096

struct tvm_htab_node {
	char *key;
	int value;
	void *valptr;
	struct tvm_htab_node *next;
};

struct tvm_htab_ctx {
	unsigned int num_nodes;
	unsigned int size;
	struct tvm_htab_node **nodes;
};

struct tvm_htab_ctx *tvm_htab_create();
void tvm_htab_destroy(struct tvm_htab_ctx *htab);

int tvm_htab_add(struct tvm_htab_ctx *htab, const char *key, int value);
int tvm_htab_add_ref(struct tvm_htab_ctx *htab,
	const char *key, const void *valptr, int len);
int tvm_htab_find(struct tvm_htab_ctx *htab, const char *key);
char *tvm_htab_find_ref(struct tvm_htab_ctx *htab, const char *key);

#endif
```

Looks easy enough to implement. Our only problem is the definition for
`tvm_htab_ctx` and `tvm_htab_node` are included in the header file, meaning it's
possible that some code accesses the hash table's internals directly instead of
going through the published interface.

We can check whether anything accesses hash table internals by temporarily
moving the struct definitions into `tvm_htab.c` and see if everything still
compiles.

```diff
diff --git a/include/tvm/tvm_htab.h b/include/tvm/tvm_htab.h
index 9feb7a9..e7346b7 100644
--- a/include/tvm/tvm_htab.h
+++ b/include/tvm/tvm_htab.h
@@ -4,18 +4,8 @@
 #define KEY_LENGTH 64
 #define HTAB_SIZE 4096

-struct tvm_htab_node {
-       char *key;
-       int value;
-       void *valptr;
-       struct tvm_htab_node *next;
-};
-
-struct tvm_htab_ctx {
-       unsigned int num_nodes;
-       unsigned int size;
-       struct tvm_htab_node **nodes;
-};
+struct tvm_htab_node;
+struct tvm_htab_ctx;

 struct tvm_htab_ctx *tvm_htab_create();
 void tvm_htab_destroy(struct tvm_htab_ctx *htab);
```

And after running `make` again:

```console
$ make
make
clang -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -c libtvm/tvm_htab.c -o libtvm/tvm_htab.o
ar rcs lib/libtvm.a libtvm/tvm_program.o libtvm/tvm_lexer.o libtvm/tvm.o libtvm/tvm_htab.o libtvm/tvm_memory.o libtvm/tvm_preprocessor.o libtvm/tvm_parser.o libtvm/tvm_file.o
clang src/tvmi.c -ltvm -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -Llib/ -o bin/tvmi
clang tdb/main.o tdb/tdb.o -ltvm -Wall -pipe -Iinclude/ -std=gnu11 -Werror -pedantic -pedantic-errors -O3 -Llib/ -o bin/tdb
```

Looks like it all still works, now onto phase B; Create an identical set of
functions which use a `HashMap<K, V>` under the hood.

Stubbing out the bare minimum, we get:

```rust
// src/htab.rs

use std::{
    collections::HashMap,
    ffi::CString,
    os::raw::{c_char, c_int, c_void},
};

#[derive(Debug, Default, Clone, PartialEq)]
pub struct HashTable(pub(crate) HashMap<CString, Item>);

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct Item {
    // not sure what to put here yet
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_create() -> *mut HashTable {
    unimplemented!()
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_destroy(htab: *mut HashTable) {
    unimplemented!()
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_add(
    htab: *mut HashTable,
    key: *const c_char,
    value: c_int,
) -> c_int {
    unimplemented!()
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_add_ref(
    htab: *mut HashTable,
    key: *const c_char,
    value_ptr: *mut c_void,
    length: c_int,
) -> c_int {
    unimplemented!()
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_find(
    htab: *mut HashTable,
    key: *const c_char,
) -> c_int {
    unimplemented!()
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_find_ref(
    htab: *mut HashTable,
    key: *const c_char,
) -> *mut c_char {
    unimplemented!()
}
```

We also need to declare the `htab` module and re-export its functions from
`lib.rs`.

```rust
// src/lib.rs

mod htab;
pub use htab::*;
```

Now we need to make sure the original `tvm_htab.c` doesn't get compiled and
linked into the final library, otherwise we'll be greeted with a wall of
duplicate symbol errors by the linker.

{{% expand "A wall of duplicate symbol errors" %}}
```
error: linking with `/usr/bin/clang` failed: exit code: 1
  |
  = note: "/usr/bin/clang" "-Wl,--as-needed" "-Wl,-z,noexecstack" "-m64" "-L" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.17q5thi94e1eoj5i.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.19e8sqirbm56nu8g.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.1g6ljku8dwzpfvhi.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.1h5e5mxmiptpb7iz.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.1herotdop66zv9ot.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.1qbfxpvgd885u6o.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.21psdg8ni4vgdrzk.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.2albhpxlxxvc0ccu.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.2btm2dc9rhjhhna1.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.2kct5ftnkrqqr0mf.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.2lwgg3uosup4mkh0.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.2xduj46e9sw5vuan.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.35h8y7f23ua1qnz0.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.3cgfdtku63ltd8oc.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.3ot768hzkzzy7r76.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.3u2xnetcch8f2o02.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.4ldrdjvfzk58myrv.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.4omnum6bdjqsrq8b.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.4s8ch4ccmewulj22.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.4syl3x2rb8328h8x.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.532awiysf0h9r50f.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.dfjs079cp9si4o5.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.qxp6yb2gjpj0v6n.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.xz7ld20yvprst1r.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.z35ukhvchmmby1c.rcgu.o" "-o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.1d7wvlwdjap8p3g4.rcgu.o" "-Wl,--gc-sections" "-pie" "-Wl,-zrelro" "-Wl,-znow" "-nodefaultlibs" "-L" "/home/michael/Documents/tinyvm-rs/target/debug/deps" "-L" "/home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out" "-L" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib" "-Wl,-Bstatic" "-Wl,--whole-archive" "-ltvm" "-Wl,--no-whole-archive" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libtest-a39a3e9a77b17f55.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libterm-97a69cd310ff0925.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libgetopts-66a42b1d94e3e6f9.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libunicode_width-dd7761d848144e0d.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_std_workspace_std-f722acdb78755ba0.rlib" "-Wl,--start-group" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libstd-974c3c08f6def4b3.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libpanic_unwind-eb49676f33a2c8a6.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libhashbrown-7ae0446feecc60f2.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_std_workspace_alloc-2de299b65d7f5721.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libbacktrace-64514775bc06309a.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libbacktrace_sys-1ed8aa185c63b9a5.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_demangle-a839df87f563fba5.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libunwind-8e726bdc2018d836.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libcfg_if-5285f42cbadf207d.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/liblibc-b0362d20f8aa58fa.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/liballoc-f3dd7051708453a4.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_std_workspace_core-83744846c43307ce.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libcore-d5565a3a0f4cfe21.rlib" "-Wl,--end-group" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libcompiler_builtins-ea790e85415e3bbf.rlib" "-Wl,-Bdynamic" "-ldl" "-lrt" "-lpthread" "-lgcc_s" "-lc" "-lm" "-lrt" "-lpthread" "-lutil" "-lutil" "-fuse-ld=lld"
  = note: ld.lld: error: duplicate symbol: tvm_htab_create
          >>> defined at htab.rs:14 (src/htab.rs:14)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o:(tvm_htab_create)
          >>> defined at tvm_htab.c:23 (vendor/tinyvm/libtvm/tvm_htab.c:23)
          >>>            tvm_htab.o:(.text.tvm_htab_create+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a

          ld.lld: error: duplicate symbol: tvm_htab_destroy
          >>> defined at htab.rs:17 (src/htab.rs:17)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o:(tvm_htab_destroy)
          >>> defined at tvm_htab.c:35 (vendor/tinyvm/libtvm/tvm_htab.c:35)
          >>>            tvm_htab.o:(.text.tvm_htab_destroy+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a

          ld.lld: error: duplicate symbol: tvm_htab_add_ref
          >>> defined at htab.rs:29 (src/htab.rs:29)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o:(tvm_htab_add_ref)
          >>> defined at tvm_htab.c:160 (vendor/tinyvm/libtvm/tvm_htab.c:160)
          >>>            tvm_htab.o:(.text.tvm_htab_add_ref+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a

          ld.lld: error: duplicate symbol: tvm_htab_add
          >>> defined at htab.rs:20 (src/htab.rs:20)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o:(tvm_htab_add)
          >>> defined at tvm_htab.c:147 (vendor/tinyvm/libtvm/tvm_htab.c:147)
          >>>            tvm_htab.o:(.text.tvm_htab_add+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a

          ld.lld: error: duplicate symbol: tvm_htab_find
          >>> defined at htab.rs:39 (src/htab.rs:39)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o:(tvm_htab_find)
          >>> defined at tvm_htab.c:189 (vendor/tinyvm/libtvm/tvm_htab.c:189)
          >>>            tvm_htab.o:(.text.tvm_htab_find+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a

          ld.lld: error: duplicate symbol: tvm_htab_find_ref
          >>> defined at htab.rs:47 (src/htab.rs:47)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-599d57f523fdb1a4.5b2qwmmtc5pvnbh.rcgu.o:(tvm_htab_find_ref)
          >>> defined at tvm_htab.c:199 (vendor/tinyvm/libtvm/tvm_htab.c:199)
          >>>            tvm_htab.o:(.text.tvm_htab_find_ref+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a
          clang: error: linker command failed with exit code 1 (use -v to see invocation)


error: aborting due to previous error

error: could not compile `tinyvm`.
```
{{% /expand %}}

The fix is actually quite simple.

```diff
diff --git a/build.rs b/build.rs
index 6f274c8..af9d467 100644
--- a/build.rs
+++ b/build.rs
@@ -9,7 +9,6 @@ fn main() {
     Build::new()
         .warnings(false)
         .file(src.join("tvm_file.c"))
-        .file(src.join("tvm_htab.c"))
         .file(src.join("tvm_lexer.c"))
         .file(src.join("tvm_memory.c"))
         .file(src.join("tvm_parser.c"))
```

And trying to run the `tvmi` example again crashes, just as you'd expect a
program full of `unimplemented!()` to.

```console
$ cargo run --example tvmi -- vendor/tinyvm/programs/tinyvm/fact.vm
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/examples/tvmi vendor/tinyvm/programs/tinyvm/fact.vm`
thread 'main' panicked at 'not yet implemented', src/htab.rs:14:57
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace.
```

When adding FFI support for a new type, the easiest place to start is often
with the constructor and destructor.

{{% notice info %}}
The C code can only ever access our `HashTable` via a pointer, so we need to
allocate one on the heap and then pass ownership of that heap-allocated object
to the caller.
{{% /notice %}}

```rust
// src/htab.rs

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_create() -> *mut HashTable {
    let hashtable = Box::new(HashTable::default());
    Box::into_raw(hashtable)
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_destroy(htab: *mut HashTable) {
    if htab.is_null() {
        // nothing to free
        return;
    }

    let hashtable = Box::from_raw(htab);
    // explicitly destroy the hashtable
    drop(hashtable);
}
```


{{% notice warning %}}
It is important that callers only ever destroy the `HashTable` by using the
`tvm_htab_destroy()` function!

If they don't do that and instead try to call `free()` directly, we'll
almost certainly have a bad time. At best, it'll leak a bunch of memory, but
it's also quite possible that our Rust `Box` doesn't use the same heap as
`malloc()` and `free()`, meaning freeing a Rust object from C could corrupt
the heap and leave the world in a broken state.
{{% /notice %}}

Adding items to our hashmap is almost as easy to implement.

```rust
// src/hmap.rs

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct Item {
    /// An integer value.
    value: c_int,
    /// An opaque value used with [`tvm_htab_add_ref()`].
    ///
    /// # Safety
    ///
    /// Storing the contents of a `void *` in a `Vec<u8>` *would* normally
    /// result in alignment issues, but we've got access to the `libtvm` source
    /// code and know it will only ever store `char *` strings.
    opaque_value: Vec<u8>,
}

impl Item {
    pub(crate) fn integer(value: c_int) -> Item {
        Item {
            value,
            opaque_value: Vec::new(),
        }
    }

    pub(crate) fn opaque<V>(opaque_value: V) -> Item
    where
        V: Into<Vec<u8>>,
    {
        Item {
            value: 0,
            opaque_value: opaque_value.into(),
        }
    }

    pub(crate) fn from_void(pointer: *mut c_void, length: c_int) -> Item {
        // we need to create an owned copy of the value
        let opaque_value = if pointer.is_null() {
            Vec::new()
        } else {
            unsafe {
                std::slice::from_raw_parts(pointer as *mut u8, length as usize)
                    .to_owned()
            }
        };

        Item::opaque(opaque_value)
    }
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_add(
    htab: *mut HashTable,
    key: *const c_char,
    value: c_int,
) -> c_int {
    let hashtable = &mut *htab;
    let key = CStr::from_ptr(key).to_owned();

    hashtable.0.insert(key, Item::integer(value));

    // the only time insertion can fail is if allocation fails. In that case
    // we'll abort the process anyway, so if this function returns we can
    // assume it was successful (0 = success).
    0
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_add_ref(
    htab: *mut HashTable,
    key: *const c_char,
    value_ptr: *mut c_void,
    length: c_int,
) -> c_int {
    let hashtable = &mut *htab;
    let key = CStr::from_ptr(key).to_owned();

    hashtable.0.insert(key, Item::from_void(value_ptr, length));

    0
}
```

{{% notice note %}}
It's important to make sure we're using a `CString` as the hashtable key here
instead of a normal `String`. A `*const c_char` can contain *any* non-null
bytes, whereas a Rust `String` requires the string to be valid UTF-8.

We could probably get away with converting the `CStr` to a `&str` and then an
owned `String` because most input will be ASCII, but considering we'd need one
or two `unwrap()`s, it's easier to just do things correctly and store a
`CString`.
{{% /notice %}}

The two `*_find()` functions can be delegated straight to the inner
`HashMap<CString, Item>`.

The only thing we need to be careful about is making sure the right value is
returned when an item can't be found. In this case, by looking at
`tvm_htab.c` we can see that `tvm_htab_find()` returns `-1` and
`tvm_htab_find_ref()` returns `NULL`.

```rust
// src/hmap.rs

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_find(
    htab: *mut HashTable,
    key: *const c_char,
) -> c_int {
    let hashtable = &mut *htab;
    let key = CStr::from_ptr(key);

    match hashtable.get(key) {
        Some(item) => item.value,
        None => -1,
    }
}

#[no_mangle]
pub unsafe extern "C" fn tvm_htab_find_ref(
    htab: *mut HashTable,
    key: *const c_char,
) -> *mut c_char {
    let hashtable = &mut *htab;
    let key = CStr::from_ptr(key);

    match hashtable.0.get(key) {
        Some(item) => item.value_ptr as *mut c_char,
        None => ptr::null_mut(),
    }
}
```

Now we've actually implemented the stubbed out functions, everything should work
again.

The easiest way to check is by running our example.

```rust
cargo run --example tvmi -- vendor/tinyvm/programs/tinyvm/fact.vm
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/examples/tvmi vendor/tinyvm/programs/tinyvm/fact.vm`
1
2
6
24
120
720
5040
40320
362880
3628800
```

And to double-check we can run it through `valgrind` to make sure we aren't
leaking memory or doing anything dodgy with pointers.

```console
$ valgrind target/debug/examples/tvmi vendor/tinyvm/programs/tinyvm/fact.vm
==1492== Memcheck, a memory error detector
==1492== Copyright (C) 2002-2017, and GNU GPL'd, by Julian Seward et al.
==1492== Using Valgrind-3.15.0 and LibVEX; rerun with -h for copyright info
==1492== Command: target/debug/examples/tvmi vendor/tinyvm/programs/tinyvm/fact.vm
==1492==
1
2
6
24
120
720
5040
40320
362880
3628800
==1492==
==1492== HEAP SUMMARY:
==1492==     in use at exit: 0 bytes in 0 blocks
==1492==   total heap usage: 270 allocs, 270 frees, 67,129,392 bytes allocated
==1492==
==1492== All heap blocks were freed -- no leaks are possible
==1492==
==1492== For lists of detected and suppressed errors, rerun with: -s
==1492== ERROR SUMMARY: 0 errors from 0 contexts (suppressed: 0 from 0)
```

Success!

## Implementing Preprocessing

The `tinyvm` virtual machine consumes [a simplified form of assembly][grammar]
similar to traditional Intel x86 assembly. The first step in parsing `tinyvm`
assembly is to run a preprocessor which interprets `%include filename` and
`%define identifier value` statements.

This sort of text manipulation should be a lot easier to accomplish using
Rust's `&str` types, so let's have a look at the interface our crate needs to
implement.

```c
// vendor/tinyvm/include/tvm/tvm_preprocessor.h

#ifndef TVM_PREPROCESSOR_H_
#define TVM_PREPROCESSOR_H_

#include "tvm_htab.h"

int tvm_preprocess(char **src, int *src_len, struct tvm_htab_ctx *defines);

#endif
```

Using `char **` and `int *` for the `src` and `src_len` variables may seem a
bit odd at first, but if you were to write the equivalent in Rust you'd get
something like this:

```rust
fn tvm_preprocess(
    src: String,
    defines: &mut HashTable,
) -> Result<String, PreprocessorError> {
    ...
}
```

The C code is just using output parameters to swap the `src` string in-place
because it can't return both a new string and an error code.

Before we do anything else, we should write a test for `tvm_preprocess()`. That
way we can ensure our Rust function is functionally equivalent to the original.

We're interacting with the filesystem so we'll want to pull in
[the `tempfile` crate][tempfile].

```console
$ cargo add --dev tempfile
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding tempfile v3.1.0 to dev-dependencies
```

We'll also need the `libc` crate because we're going to be passing `libtvm`
strings which it may need to free.

```console
cargo add libc
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding libc v0.2.66 to dev-dependencies
```

Looking at the source code, we can see that the `tvm_preprocess()` function
will keep resolving `%include`s and `%define`s until there are none left.

First let's create a test to make sure the preprocessor handles `%define`s. We
know this code already works (it's the code from `tinyvm` after all), so there
shouldn't be any surprises.


```rust
// src/preprocessing.rs

#[cfg(test)]
mod tests {
    use crate::ffi;
    use std::{
        ffi::{CStr, CString},
        io::Write,
        os::raw::c_int,
    };

    #[test]
    fn find_all_defines() {
        let src = "%define true 1\nsome random text\n%define FOO_BAR -42\n";
        let original_length = src.len();
        let src = CString::new(src).unwrap();

        unsafe {
            // get a copy of `src` that was allocated using C's malloc
            let mut src = libc::strdup(src.as_ptr());
            let mut len = original_length as c_int;
            let defines = ffi::tvm_htab_create();

            let ret = ffi::tvm_preprocess(&mut src, &mut len, defines);

            // preprocessing should have been successful
            assert_eq!(ret, 0);

            // make sure the define lines were removed
            let preprocessed = CStr::from_ptr(src).to_bytes();
            let preprocessed =
                std::str::from_utf8(&preprocessed[..len as usize]).unwrap();
            assert_eq!(preprocessed, "\nsome random text\n\n");

            // make sure the "true" and "FOO_BAR" defines were set
            let true_define =
                ffi::tvm_htab_find_ref(defines, b"true\0".as_ptr().cast());
            let got = CStr::from_ptr(true_define).to_str().unwrap();
            assert_eq!(got, "1");
            let foo_bar =
                ffi::tvm_htab_find_ref(defines, b"FOO_BAR\0".as_ptr().cast());
            let got = CStr::from_ptr(foo_bar).to_str().unwrap();
            assert_eq!(got, "-42");

            // clean up our hashtable and copied source text
            ffi::tvm_htab_destroy(defines);
            libc::free(src.cast());
        }
    }
}
```

Weighing in at 45 lines that's a lot more than I usually like when writing
tests, but there's a fair amount of extra code required to convert back and
forth between C strings.

We also need to test including another file.

```rust
// src/preprocessing.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn include_another_file() {
        const TOP_LEVEL: &str = "first line\n%include nested\nlast line\n";
        const NESTED: &str = "nested\n";

        // the preprocessor imports files from the filesystem, so we need to
        // copy NESTED to a temporary location
        let mut nested = NamedTempFile::new().unwrap();
        nested.write_all(NESTED.as_bytes()).unwrap();
        let nested_filename = nested.path().display().to_string();

        // substitute the full path to the "nested" file
        let top_level_src = TOP_LEVEL.replace("nested", &nested_filename);
        std::fs::write(&nested, NESTED).unwrap();

        unsafe {
            let top_level_src = CString::new(top_level_src).unwrap();
            // create a copy of the top_level_src which can be freed by C
            let mut src = libc::strdup(top_level_src.as_ptr());
            let mut len = libc::strlen(src) as c_int;
            let defines = ffi::tvm_htab_create();

            // after all that setup code we can *finally* call the preprocessor
            let ret = ffi::tvm_preprocess(&mut src, &mut len, defines);

            assert_eq!(ret, 0);

            // make sure the define and import lines were removed
            let preprocessed = CStr::from_ptr(src).to_bytes();
            let got =
                std::str::from_utf8(&preprocessed[..len as usize]).unwrap();

            // after preprocessing, all include and define lines should have
            // been removed
            assert_eq!(got, "first line\nnested\nlast line\n");

            ffi::tvm_htab_destroy(defines);
            libc::free(src.cast());
        }
    }
```

{{% notice note %}}
As an aside, this test was originally written to nest things three layers
deep (e.g. `top_level.vm` includes `nested.vm` which includes `really_nested.vm`)
to make sure it handles more than one level of `%include`, but no matter how
it was written the test kept segfaulting.

Then I tried running the original C `tvmi` binary...

```console
$ cd vendor/tinyvm/
$ cat top_level.vm
  %include nested
$ cat nested.vm
  %include really_nested
$ cat really_nested.vm
  Hello World
$ ./bin/tvmi top_level.vm
  [1]    10607 segmentation fault (core dumped)  ./bin/tvmi top_level.vm
```

Turns out the original `tinyvm` will crash for some reason when you have
multiple layers of includes 😕
{{% /notice %}}

Okay, so now we've got some tests we can start to implement
`tvm_preprocess()`.


First off we should define an error type.

```rust
// src/preprocessing.rs

#[derive(Debug)]
pub enum PreprocessingError {
    FailedInclude {
        name: String,
        inner: IoError,
    },
    DuplicateDefine {
        name: String,
        original_value: String,
        new_value: String,
    },
    EmptyDefine,
    DefineWithoutValue(String),
}
```

Looking at the [`process_includes()` and `process_derives()`
functions][preprocessor.c], both seem to scan through a string looking for a
particular directive, then replace that line with something else (either the
contents of a file or nothing if the line should be removed).

We should be able to extract that logic into a helper and avoid unnecessary
duplication.

```rust
// src/preprocessing.rs

/// Scan through the input string looking for a line starting with some
/// directive, using a callback to figure out what to replace the directive line
/// with.
fn process_line_starting_with_directive<F>(
    mut src: String,
    directive: &str,
    mut replace_line: F,
) -> Result<(String, usize), PreprocessingError>
where
    F: FnMut(&str) -> Result<String, PreprocessingError>,
{
    // try to find the first instance of the directive
    let directive_delimiter = match src.find(directive) {
        Some(ix) => ix,
        None => return Ok((src, 0)),
    };

    // calculate the span from the directive to the end of the line
    let end_ix = src[directive_delimiter..]
        .find('\n')
        .map(|ix| ix + directive_delimiter)
        .unwrap_or(src.len());

    // the rest of the line after the directive
    let directive_line =
        src[directive_delimiter + directive.len()..end_ix].trim();

    // use the callback to figure out what we should replace the line with
    let replacement = replace_line(directive_line)?;

    // remove the original line
    let _ = src.drain(directive_delimiter..end_ix);
    // then insert our replacement
    src.insert_str(directive_delimiter, &replacement);

    Ok((src, 1))
}
```

Now we've got our `process_line_starting_with_directive()` helper we can
implement include parsing.

```rust
// src/preprocessing.rs

fn process_includes(
    src: String,
) -> Result<(String, usize), PreprocessingError> {
    const TOK_INCLUDE: &str = "%include";

    process_line_starting_with_directive(src, TOK_INCLUDE, |line| {
        std::fs::read_to_string(line).map_err(|e| {
            PreprocessingError::FailedInclude {
                name: line.to_string(),
                inner: e,
            }
        })
    })
}
```

Unfortunately, `%define` parsing is a little more involved.

```rust
// src/preprocessing.rs

n process_defines(
    src: String,
    defines: &mut HashTable,
) -> Result<(String, usize), PreprocessingError> {
    const TOK_DEFINE: &str = "%define";

    process_line_starting_with_directive(src, TOK_DEFINE, |line| {
        parse_define(line, defines)?;
        Ok(String::new())
    })
}

fn parse_define(
    line: &str,
    defines: &mut HashTable,
) -> Result<(), PreprocessingError> {
    if line.is_empty() {
        return Err(PreprocessingError::EmptyDefine);
    }

    // The syntax is "%define key value", so after removing the leading
    // "%define" everything after the next space is the value
    let first_space = line.find(' ').ok_or_else(|| {
        PreprocessingError::DefineWithoutValue(line.to_string())
    })?;

    // split the rest of the line into key and value
    let (key, value) = line.split_at(first_space);
    let value = value.trim();

    match defines.0.entry(
        CString::new(key).expect("The text shouldn't contain null bytes"),
    ) {
        // the happy case, this symbol hasn't been defined before so we can just
        // insert it.
        Entry::Vacant(vacant) => {
            vacant.insert(Item::opaque(value));
        },
        // looks like this key has already been defined, report an error
        Entry::Occupied(occupied) => {
            return Err(PreprocessingError::DuplicateDefine {
                name: key.to_string(),
                original_value: occupied
                    .get()
                    .opaque_value_str()
                    .unwrap_or("<invalid>")
                    .to_string(),
                new_value: value.to_string(),
            });
        },
    }

    Ok(())
}
```

To access the text stored in our hashtable, we'll need to give `Item` a
couple helper methods:

```rust
// src/htab.rs

impl Item {
    ...

    pub(crate) fn opaque_value(&self) -> &[u8] { &self.opaque_value }

    pub(crate) fn opaque_value_str(&self) -> Option<&str> {
        std::str::from_utf8(self.opaque_value()).ok()
    }
}
```

At this point it's a good idea to add some more tests.

```rust
// src/preprocessing.rs

#[cfg(test)]
mod tests {
    ...

    #[test]
    fn empty_string() {
        let src = String::from("");
        let mut hashtable = HashTable::default();

        let (got, replacements) = process_defines(src, &mut hashtable).unwrap();

        assert!(got.is_empty());
        assert_eq!(replacements, 0);
        assert!(hashtable.0.is_empty());
    }

    #[test]
    fn false_percent() {
        let src = String::from("this string contains a % symbol");
        let mut hashtable = HashTable::default();

        let (got, replacements) =
            process_defines(src.clone(), &mut hashtable).unwrap();

        assert_eq!(got, src);
        assert_eq!(replacements, 0);
        assert!(hashtable.0.is_empty());
    }

    #[test]
    fn define_without_key_and_value() {
        let src = String::from("%define\n");
        let mut hashtable = HashTable::default();

        let err = process_defines(src.clone(), &mut hashtable).unwrap_err();

        match err {
            PreprocessingError::EmptyDefine => {},
            other => panic!("Expected EmptyDefine, found {:?}", other),
        }
    }

    #[test]
    fn define_without_value() {
        let src = String::from("%define key\n");
        let mut hashtable = HashTable::default();

        let err = process_defines(src.clone(), &mut hashtable).unwrap_err();

        match err {
            PreprocessingError::DefineWithoutValue(key) => {
                assert_eq!(key, "key")
            },
            other => panic!("Expected DefineWithoutValue, found {:?}", other),
        }
    }

    #[test]
    fn valid_define() {
        let src = String::from("%define key value\n");
        let mut hashtable = HashTable::default();

        let (got, num_defines) = process_defines(src.clone(), &mut hashtable).unwrap();

        assert_eq!(got, "\n");
        assert_eq!(num_defines, 1);
        assert_eq!(hashtable.0.len(), 1);
        let key = CString::new("key").unwrap();
        let item = hashtable.0.get(&key).unwrap();
        assert_eq!(item.opaque_value_str().unwrap(), "value");
    }
}
```

At this point we've reproduced most of the preprocessing logic, so now we just
need a function which will keep expanding `%include` statements and handling
`%define`s until there's nothing more to do.

```rust
// src/preprocessing.rs

pub fn preprocess(
    src: String,
    defines: &mut HashTable,
) -> Result<String, PreprocessingError> {
    let mut src = src;

    loop {
        let (modified, num_includes) = process_includes(src)?;
        let (modified, num_defines) = process_defines(modified, defines)?;

        if num_includes + num_defines == 0 {
            return Ok(modified);
        }

        src = modified;
    }
}
```

Of course, this `preprocess()` function is only accessible to Rust. We need to
create an `extern "C" fn` which translates arguments from C types to something
Rust can handle, then translate back to C land at the end.

```rust
// src/preprocessing.rs

#[no_mangle]
pub unsafe extern "C" fn tvm_preprocess(
    src: *mut *mut c_char,
    src_len: *mut c_int,
    defines: *mut tvm_htab_ctx,
) -> c_int {
    if src.is_null() || src_len.is_null() || defines.is_null() {
        return -1;
    }

    // Safety: This assumes the tvm_htab_ctx is actually our ported HashTable
    let defines = &mut *(defines as *mut HashTable);

    // convert the input string to an owned Rust string so it can be
    // preprocessed
    let rust_src = match CStr::from_ptr(*src).to_str() {
        Ok(s) => s.to_string(),
        // just error out if it's not valid UTF-8
        Err(_) => return -1,
    };

    match preprocess(rust_src, defines) {
        Ok(s) => {
            let preprocessed = CString::new(s).unwrap();
            // create a copy of the preprocessed string that can be free'd by C
            // and use the output arguments to pass it to the caller
            *src = libc::strdup(preprocessed.as_ptr());
            // the original C implementation didn't add a null terminator to the
            // preprocessed string, so we're required to set the length as well.
            *src_len = libc::strlen(*src) as c_int;

            // returning 0 indicates success
            0
        },
        // tell the caller "an error occurred"
        Err(_) => -1,
    }
}
```

{{% notice tip %}}
You may have noticed that our `tvm_preprocess()` doesn't have any preprocessing
logic, and is more like an adapter to translate arguments and return values, and
make sure errors are propagated correctly.

This is no accident.

The secret to FFI code is to write as little as possible, and avoid *"clever"*
tricks. Unlike most Rust code, making mistakes in these sorts of interop
functions can lead to unsound logic and memory bugs.

Creating a thin wrapper around our `preprocess()` function also makes things
easier later on, because when more of the codebase is written in Rust we can
delete the wrapper and call `preprocess()` directly.
{{% /notice %}}

Now the `tvm_preprocess()` function is defined we should be good to go.

```console
 Compiling tinyvm v0.1.0 (/home/michael/Documents/tinyvm-rs)
error: linking with `/usr/bin/clang` failed: exit code: 1
  |
  = note: "/usr/bin/clang" "-Wl,--as-needed" "-Wl,-z,noexecstack" "-m64" "-L" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.13h6j6k0dzqf6zi2.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.13l2b4uvr7p3ht4k.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.14bdbjhozo3id49g.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.14fw2gyd6mrq5730.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.19xc7n0bb25uaxgk.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1duzy573vjvyihco.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1e0yejy24qufh7ie.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1k4xuir9ezt4vkzp.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1mqdnrarww1zjlt.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1ubflbxzxkx7grpn.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1vtvcpzzusyku3mk.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1wal3ebwyfg4qllf.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.235k75fk09i43ba3.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.253rt7mnjcp3n8ex.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.27phuscrye2lmkyq.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2bwv51h7gucjizh0.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2ghuai4hs88aroml.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2gqnd9h4nmhvgxbn.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2hjvtf620gtog0qz.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2hq7kc2w3vix8i5q.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2ibwag4iedx494ft.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2jdt9fes53g5mxlp.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2kv4bwega1wfr8z6.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2lja418hz58xlryz.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2o0foimqe73p8ujt.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2ouuhyii88vg8tqs.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2tnynvvdxge4sv9a.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2u1hzhj3v0d8kn4s.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2v1ii2legejcp3ir.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2vkkoofkb7zs04v1.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2w5mgql1gpr1f9uz.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2wdyioq7lxh9uxu7.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2wokgurbjsmgz12r.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.2wwcrmvusj07mx2n.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.310mxv7piqfbf4tr.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.3352aele91geo33m.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.36f4wrjtv0x5y00b.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.38f6o2m900r5q63j.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.3b67z5wg30f9te4l.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.3gyajmii4500y81t.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.3ovwslgcz03sp0ov.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.3vwhwp967j90qfpp.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.41ox17npnikcezii.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4472ut4qn508rg19.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4bbcvjauqmyr7tjc.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4c9lrc1xbvaru030.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4fzwdkjhjtwv5uik.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4gy2dy14zw2o60sh.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4i8qxpi0pmwn8d2e.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4isstj7ytb9d9yep.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4isz4o5d1flv8pme.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4lnnaom9zd4u3xmv.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4mgvbbhn4jewmy60.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4q7wf9d53jp9j6y6.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4qimnegzmsif2zbr.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4scm7492lh4yspgt.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4ten9b8okg10ap4i.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4vrj7dhlet4j6oe.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4wtf4i2ggbrvqt63.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4zsqxnhj8yusiplh.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.50o8i1bmvqwd5eg7.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.50urmck1r52hucuw.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.51w3uc6agh3gynn3.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.55o6ad6nlq4o2zyt.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.57gih8p2bu1jbo0l.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.57rpuf5wpgkfmf1z.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.5920w55mlosqy9aj.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.5c1ra5cheein740g.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.5cuuq0m7tzehyrti.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.5e85z18y46lhofte.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.6yu7c01lw47met2.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.cn69np51jgriev2.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.d224rq9cs4mbv0q.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.e0vaqgnhc25c4ox.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.edm0ce3nfzegp4d.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.elxjhifv4wlzkc2.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.ifqyaukx6gnbb0a.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.kr8s9rcy6ux2d02.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.ley637x8c2etn66.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.njyqsm0frvb1j4d.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.r9ttxk3s5kacz9k.rcgu.o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.xrorvssabbgfjqz.rcgu.o" "-o" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88" "/home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.1iplfu0pt8fy07e4.rcgu.o" "-Wl,--gc-sections" "-pie" "-Wl,-zrelro" "-Wl,-znow" "-nodefaultlibs" "-L" "/home/michael/Documents/tinyvm-rs/target/debug/deps" "-L" "/home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out" "-L" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib" "-Wl,-Bstatic" "-Wl,--whole-archive" "-ltvm" "-Wl,--no-whole-archive" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libtest-a39a3e9a77b17f55.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libterm-97a69cd310ff0925.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libgetopts-66a42b1d94e3e6f9.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libunicode_width-dd7761d848144e0d.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_std_workspace_std-f722acdb78755ba0.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/libtempfile-b08849d192e5c2e1.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/librand-c85ceffb304c7385.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/librand_chacha-4e4839e3036afe89.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/libc2_chacha-7555b62a53de8bdf.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/libppv_lite86-0097c0f425957d6e.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/librand_core-de2208c863d15e9b.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/libgetrandom-c696cd809d660e17.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/liblibc-d52d0b97a33a5f02.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/libremove_dir_all-4035fb46dbd6fb92.rlib" "/home/michael/Documents/tinyvm-rs/target/debug/deps/libcfg_if-6adeb646d05b676c.rlib" "-Wl,--start-group" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libstd-974c3c08f6def4b3.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libpanic_unwind-eb49676f33a2c8a6.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libhashbrown-7ae0446feecc60f2.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_std_workspace_alloc-2de299b65d7f5721.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libbacktrace-64514775bc06309a.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libbacktrace_sys-1ed8aa185c63b9a5.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_demangle-a839df87f563fba5.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libunwind-8e726bdc2018d836.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libcfg_if-5285f42cbadf207d.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/liblibc-b0362d20f8aa58fa.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/liballoc-f3dd7051708453a4.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/librustc_std_workspace_core-83744846c43307ce.rlib" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libcore-d5565a3a0f4cfe21.rlib" "-Wl,--end-group" "/home/michael/.rustup/toolchains/nightly-x86_64-unknown-linux-gnu/lib/rustlib/x86_64-unknown-linux-gnu/lib/libcompiler_builtins-ea790e85415e3bbf.rlib" "-Wl,-Bdynamic" "-lutil" "-lutil" "-ldl" "-lrt" "-lpthread" "-lgcc_s" "-lc" "-lm" "-lrt" "-lpthread" "-lutil" "-lutil" "-fuse-ld=lld"
  = note: ld.lld: error: duplicate symbol: tvm_preprocess
          >>> defined at preprocessing.rs:13 (src/preprocessing.rs:13)
          >>>            /home/michael/Documents/tinyvm-rs/target/debug/deps/tinyvm-8eca24ff9a1cde88.4mgvbbhn4jewmy60.rcgu.o:(tvm_preprocess)
          >>> defined at tvm_preprocessor.c:135 (vendor/tinyvm/libtvm/tvm_preprocessor.c:135)
          >>>            tvm_preprocessor.o:(.text.tvm_preprocess+0x0) in archive /home/michael/Documents/tinyvm-rs/target/debug/build/tinyvm-3f1a2766f78b5580/out/libtvm.a
          clang: error: linker command failed with exit code 1 (use -v to see invocation)


error: aborting due to previous error

error: could not compile `tinyvm`.

To learn more, run the command again with --verbose.
```

Oh, the linker is complaining because both `preprocessing.rs` and
`tvm_preprocessor.c` define a `tvm_preprocess()` function. Looks like we forgot
to remove `tvm_preprocessor.c` from the build...

```diff
diff --git a/build.rs b/build.rs
index 0ed012c..42b8fa0 100644
--- a/build.rs
+++ b/build.rs
@@ -14,6 +14,7 @@ fn main() {
         .file(src.join("tvm_memory.c"))
         .file(src.join("tvm_parser.c"))
         .file(src.join("tvm_program.c"))
-        .file(src.join("tvm_preprocessor.c"))
         .file(src.join("tvm.c"))
         .include(&include)
         .compile("tvm");
(END)
```

Let's try again.

```console
cargo run --example tvmi -- vendor/tinyvm/programs/tinyvm/fact.vm
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `target/debug/examples/tvmi vendor/tinyvm/programs/tinyvm/fact.vm`
1
2
6
24
120
720
5040
40320
362880
3628800
```

Much better!

Remember that example from before where `tvmi` would crash when encountering
includes three levels deep? As a happy side-effect, porting to Rust means nested
includes *Just Work*.

{{% notice note %}}
You may have also noticed that our `preprocess()` function doesn't use any of
the hashtable functions from `tvm_htab.h`. Instead we take advantage of the fact
that the module has already been ported to Rust and just use the Rust types
directly.

That's the beauty of this process. Once you've moved something to Rust you can
leverage that to use the types/functions directly to get some easy wins in
error handling and ergonomics.
{{% /notice %}}

## Conclusion

If you're still reading by this point, congratulations, we've just ported two
modules from `tinyvm` to Rust.

Unfortunately this article is already long enough, but hopefully by now you
can see the general pattern,

1. Look through the application's header files and find an easy function/module
2. Write some tests so you understand how the existing function should work
3. Write equivalent functions in Rust and make sure they pass the same tests
4. Create a thin shim which exports the Rust function with the same C interface,
   making sure to remove the original function/module from the build so the
   linker uses the Rust code instead of C
5. Go to step 1

The best thing about this method is you are incrementally improving a
codebase while while ensuring the application still works and avoiding a
ground-up rewrite.

Kinda like changing your tyre while driving down the highway.

{{< figure src="/img/changing-tyre.gif"
    caption="The preferred method of porting an application from C to Rust"
    alt="Changing tyres while driving" >}}

[previous-riir]: {{< ref "how-not-to-riir/index.md" >}}
[p-invoke]: https://docs.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke
[template]: https://github.com/Michael-F-Bryan/github-template
[cg]: https://crates.io/crates/cargo-generate
[tinyvm]: https://github.com/jakogut/tinyvm
[cc]: https://crates.io/crates/cc
[tempfile]: https://crates.io/crates/tempfile
[extern]: https://doc.rust-lang.org/reference/items/external-blocks.html
[bg]: https://crates.io/crates/bindgen
[grammar]: https://github.com/jakogut/tinyvm/blob/10c25d83e442caf0c1fc4b0ab29a91b3805d72ec/SYNTAX
[preprocessor.c]: https://github.com/jakogut/tinyvm/blob/10c25d83e442caf0c1fc4b0ab29a91b3805d72ec/libtvm/tvm_preprocessor.c
[rewrites]: https://www.joelonsoftware.com/2000/04/06/things-you-should-never-do-part-i/
