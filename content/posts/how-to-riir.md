---
title: "How to RiiR"
date: "2019-11-30T00:17:06+08:00"
draft: true
tags:
- rust
---

In [a previous article][previous-riir] we've talked about how you can avoid
rewriting a library in Rust when you don't need to. But what about the times
when you really *do* need to?

In most languages you'd need to rewrite the entire library from the ground
up, waiting until the port is almost finished before you can start seeing
results. These sorts of ports tend to be quite expensive and error-prone, and
often they'll fail midway and you'll have nothing to show for your effort.

However, Rust has a killer feature when it comes to this sort of thing. It
can call into C code with no overhead (i.e. you don't need automatic
marshalling like [C#'s P/Invoke][p-invoke]) and it can expose functions which
can be consumed by C just like any other C function. This opens the door for an
alternative approach:

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
but it *does* contain several examples that we can use to explore the high-level
functionality.

Okay, so we know we can build it from the command-line without much hassle, now
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
it'll be much easier to delete `.files()` calls when individual files are
ported.

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

[previous-riir]: {{< ref "how-not-to-riir/index.md" >}}
[p-invoke]: https://docs.microsoft.com/en-us/dotnet/standard/native-interop/pinvoke
[template]: https://github.com/Michael-F-Bryan/github-template
[cg]: https://crates.io/crates/cargo-generate
[tinyvm]: https://github.com/jakogut/tinyvm
[cc]: https://crates.io/crates/cc
[extern]: https://doc.rust-lang.org/reference/items/external-blocks.html
[bg]: https://crates.io/crates/bindgen