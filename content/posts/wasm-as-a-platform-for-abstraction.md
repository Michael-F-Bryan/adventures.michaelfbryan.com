---
title: "WASM as a Platform for Abstraction"
date: "2019-12-07T17:25:07+08:00"
draft: true
tags:
- rust
- wasm
---

In a project I've been playing around with recently, we've encountered the
dilemma where you want to make it easy for users to write their own
application logic using the system, but at the same want to keep that logic
decoupled from the implementation details of whatever platform the
application is running on.

If you've been programming for any amount of time your immediate reaction is
probably *"why bother mentioning this, doesn't it just fall out of good
library design?"*, and normally I would totally agree with you, except I
forgot to mention a couple important details...

1. People need to be able to upload new code while the system is still running
2. This application will be interacting with the real world (think robots and
   automation), and we *really* don't want a crash in user-provided code to
   make the entire system stop responding

The normal solution for the first point is to use some sort of [plugin
architecture][plugins], however using something like *Dynamic Loading*
doesn't solve the second point and the large amounts of `unsafe` code needed
can arguably make the situation worse. For that we'll need some sort of
sandboxing mechanism.

Introducing...

{{< figure
    src="https://webassembly.org/css/webassembly.svg"
    link="https://webassembly.org/"
    alt="Web Assembly Logo"
    width="50%"
>}}

Web Assembly has gained a lot of traction over the last couple years as a way
to write code in any language and run it in the browser, but it can be used for
so much more.

There are already [several][wasmer] [general-purpose][lucet]
[runtimes][wasmtime] available for running WASM in a Rust program. These
runtimes give you a virtual machine which can run arbitrary code, and the
only way this code can interact with the outside world is via the functions you
explicitly give it access to.

{{% notice note %}}
Unfortunately, the code behind this post isn't publicly available (yet!). It's
actually part of a larger project I've been experimenting with and the final
version will probably end up quite different to what you see here.

That said, feel free to copy code or use it as inspiration for your own
projects. If you found this useful or spotted a bug, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Getting Started

I've chosen to use the [`wasmer`][wasmer] crate because its interface seems to
be the most amenable to embedding.

Let's start things off by creating a new crate for the project.

```console
$ cargo new --lib wasm
     Created library `wasm` package
```

We'll also want to add the `wasmer-runtime` as a dependency.

```console
$ cd wasm && cargo add wasmer-runtime
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding wasmer-runtime v0.11.0 to dependencies
```

{{% notice tip %}}
You may have noticed I'm using `cargo add` here instead of manually editing
the `Cargo.toml` file. You can get this nifty little subcommand from the
[cargo-edit][ce] crate (`cargo install cargo-edit`).

[ce]: https://crates.io/crates/cargo-edit
{{% /notice %}}

Let's start off by creating a wrapper around an instantiated WASM module. This

```rust
// src/lib.rs

use wasmer_runtime::error::Error as WasmerError;

/// A user-provided program loaded into memory.
pub struct Program {
    instance: wasmer_runtime::Instance,
}

impl Program {
    pub fn load(wasm: &[u8]) -> Result<Self, WasmerError> {
        let imports = wasmer_runtime::imports!();
        let instance = wasmer_runtime::instantiate(wasm, &imports)?;

        Ok(Program { instance })
    }
}
```

We just want to get things running, so for now we won't bother exposing any
host functions to the user-provided program. Hence the empty `imports!()` call.

Motion control systems typically work by rapidly polling each task in turn,
so let's give `Program` a `poll()` method which will call the WASM module's
`poll()` function.


```rust
// src/lib.rs

impl Program {
    ...

    pub fn poll(&mut self) -> Result<(), WasmerError> {
        self.instance.call("poll", &[])?;

        Ok(())
    }
}
```

Technically we now have everything necessary to load and poll a program, so
let's give it a shot. We'll need to create an executable and our project
could do with an example showing how to run a program, so we should be able to
kill two birds with one stone.

```rust
// examples/basic-runtime.rs

use rustmatic_wasm::Program;
use std::{env, error::Error};

fn main() -> Result<(), Box<dyn Error>> {
    let wasm_file = match env::args().skip(1).next() {
        Some(filename) => filename,
        None => panic!("Usage: basic-runtime <wasm-file>"),
    };

    let wasm = std::fs::read(&wasm_file)?;
    let mut program = Program::load(&wasm)?;

    loop {
        program.poll()?;
    }
}
```

We'll also need a dummy program that can be compiled to WASM and fed to our
`basic-runtime` example.

```rust
// example-program.rs

#[no_mangle]
pub extern "C" fn poll() {}
```

Now we should be able to compile the `example-program.rs` to WASM and run it.

```console
$ rustc example-program.rs --target wasm32-unknown-unknown --crate-type cdylib
$ ls
Cargo.toml  example-program.rs  example_program.wasm  examples  src
$ cargo run --example basic-runtime -- example_program.wasm
    Finished dev [unoptimized + debuginfo] target(s) in 0.21s
     Running `/home/michael/Documents/wasm/target/debug/examples/basic-runtime example_program.wasm`
^C
```

Well that was... anticlimatic. The `poll()` function in `example-program.rs`
doesn't actually do anything, so we've essentially created an expensive busy
loop.

Let's give the WASM code a way to print messages to the screen.

The way this is done is via that `imports!()` macro from earlier, basically
any function defined inside `imports!()` is accessible to the WASM code.
`wasmer` imposes some strict constraints on the functions which may be exposed
to WASM, restricting arguments and return values to `i32`, `i64`, `f32`, `f64`,
and pointers.

Functions may optionally accept a `&mut wasmer_runtime::Ctx` as the first
argument, this is useful for interacting with the runtime (e.g. to access
WASM memory or call a function) or accessing contextual information attached
to the `Instance`.

The code itself is rather straightforward:

```rust
// src/lib.rs

impl Program {
    pub fn load(wasm: &[u8]) -> Result<Self, WasmerError> {
        let imports = wasmer_runtime::imports! {
            "env" => {
                "print" => wasmer_runtime::func!(print),
            },
        };
        let instance = wasmer_runtime::instantiate(wasm, &imports)?;

        Ok(Program { instance })
    }

    pub fn poll(&mut self) -> Result<(), WasmerError> {
        self.instance.call("poll", &[])?;

        Ok(())
    }
}

/// Print the provided message to the screen.
///
/// Returns `-1` if the operation failed.
fn print(ctx: &mut Ctx, msg: WasmPtr<u8, Array>, length: u32) -> i32 {
    match msg.get_utf8_string(ctx.memory(0), length) {
        Some(msg) => {
            print!("{}", msg);
            0
        },
        None => -1,
    }
}
```

Now we can update the `example-program.rs` file to print `"Polling"` every time
it gets called.

```rust
// example-program.rs

extern "C" {
    /// Print a message to the screen.
    ///
    /// Returns -1 if the operation fails.
    fn print(msg: *const u8, length: u32) -> i32;
}

#[no_mangle]
pub extern "C" fn poll() {
    let msg = "Polling\n";

    unsafe {
        print(msg.as_bytes().as_ptr(), msg.len() as u32);
    }
}
```

We should now be able to recompile and run the program again.

```rust
$ rustc example-program.rs --target wasm32-unknown-unknown --crate-type cdylib
$ cargo run --example basic-runtime -- example_program.wasm
Polling
Polling
Polling
Polling
Polling
^C
```

Just for fun, let's compile this in release mode and see how much overhead going
through `wasmer` adds.

```console
$ cargo build --release --example basic-runtime
$ time ../target/release/examples/basic-runtime ./example_program.wasm > out.txt
^C
../target/release/examples/basic-runtime ./example_program.wasm > out.txt  1.09s user 2.79s system 99% cpu 3.879 total
$ wc out.txt
 180668  180668 1445344 out.txt
```

It looks like we wrote 1445344 bytes in 3.879 seconds for a throughput of
approximately 372.6 KB/sec. For comparison, the equivalent pure Rust program
(`fn main() { loop { println!("Polling"); } }`) printed 2240816 bytes in 4.225
for a throughput of 530.4 KB/sec.

That's pretty good!

[plugins]: {{< ref "plugins-in-rust.md" >}}
[wasmer]: https://github.com/wasmerio/wasmer
[lucet]: https://github.com/bytecodealliance/lucet
[wasmtime]: https://github.com/bytecodealliance/wasmtime