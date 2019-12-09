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

It looks like we wrote 1,445,344 bytes in 3.879 seconds for a throughput of
approximately 372.6 KB/sec. For comparison, the equivalent pure Rust program
(`fn main() { loop { println!("Polling"); } }`) printed 2,240,816 bytes in
4.225 for a throughput of 530.4 KB/sec.

That's pretty good!

## Declaring the Rest of the Platform Interface

Okay, so we know how to expose functions to the WASM code so it can interact
with the rest of the environment. Now the next task is look at the problem
we're trying to solve, and provide functions which will help solve it. While
this section will be fairly specific to my use case (creating some sort of
programmable logic controller that people can upload code to), it should be
fairly easy to adapt to suit your application.

In our system, there are a handful of ways a program can interact with the
outside world:

- Log a message so it can be printed to some sort of debug window
- Read an input from some memory-mapped IO
- Write an output to some memory-mapped IO
- Get the current time
- Read and write named global variables

The easiest way to declare which functions will be exposed by the runtime
("intrinsics") is with a normal C header file. This may seem a bit strange
for a Rust project, but just hear me out...

1. A header file decouples the declaration of a function from its
   implementation.
2. You can use `bindgen` to generate the corresponding Rust declarations
3. Using C header files enables people to write code for our application in
   other languages (mainly C and C++)

First off, it's a good idea to explain how we'll be handling fallible
operations. We'll be returning error codes, where anything other than
`WASM_SUCCESS` indicates an error.

```c
// src/intrinsics.h

/**
 * The various error codes used by this library.
 *
 * Every non-trivial function should return a wasm_result_t to indicate
 * whether it executed successfully.
 */
enum wasm_result_t {
    // The operation was successful.
    WASM_SUCCESS = 0,
    // An unspecified error occurred.
    WASM_GENERIC_ERROR = 1,
    // Tried to access an input/output address which is out of bounds.
    WASM_ADDRESS_OUT_OF_BOUNDS = 2,
    // Tried to read an unknown variable.
    WASM_UNKNOWN_VARIABLE = 3,
    // Tried to read/write a variable using the wrong type (e.g. you tried to
    // write a boolean to an integer variable).
    WASM_BAD_VARIABLE_TYPE = 4,
};
```

Instead of our original `print()` function, let's create a fully-fledged logger.

```c
// src/intrinsics.h

/**
 * The log levels used with `wasm_log()`.
 */
enum wasm_log_level {
    LOG_ERROR = 0,
    LOG_WARN = 1,
    LOG_INFO = 2,
    LOG_DEBUG = 3,
    LOG_TRACE = 4,
};

/**
 * Log a message at the specified level, including information about the file
 * and line the message was logged from.
 */
int wasm_log(int level, const char *file, int file_len, int line,
             const char *message, int message_len);
```

We should also make a helper macro so people don't constantly need to enter in
the filename and line number.

```c
// src/intrinsics.h

/**
 * Convenience macro for logging a message.
 */
#define LOG(level, message) wasm_log(level, __FILE__, strlen(__FILE__), __LINE__, message, strlen(message))
```

Next we'll give users a way to read input and write output. The runtime will
make sure inputs are copied to a section of memory before calling `poll()` and
outputs will sit in another section of memory and be synchronised with the real
world after `poll()` completes. This is somewhat similar to how [Memory-mapped
IO][mmio] works in embedded systems, or the [Process Image][img] on a PLC.

It's not uncommon to have batches of 16 digital outputs or read from a 24-bit
analogue sensor, so let's allow users to read/write in batches instead of one
bit/byte at a time.

```c
// src/intrinsics.h

/**
 * Read from an input from memory-mapped IO.
 */
int wasm_read_input(uint32_t address, char *buffer, int buffer_len);

/**
 * Write to an output using memory-mapped IO.
 */
int wasm_write_output(uint32_t address, const char *data, int data_len);
```

Measuring the time should be fairly straightforward. The user doesn't
necessarily care about the actual time (plus [timezones are complicated!][tz])
so the we'll provide a way to get the number of seconds and nanoseconds since an
arbitrary point in time (probably when the runtime started) and they can use
that to see how much time has passed.

```c
// src/intrinsics.h

/**
 * Get a measurement of a monotonically nondecreasing clock.
 *
 * The absolute numbers don't necessarily mean anything, the difference
 * between two measurements can be used to tell how much time has passed.
 */
int wasm_current_time(uint64_t *secs, uint32_t *nanos);
```

Next we need a way for different programs to communicate. For this, the
runtime will maintain a table of *"global variables"* which can either be
booleans, integers, or floating-point numbers (`bool`, `i32`, and `f64`
respectively).

```c
// src/intrinsics.h

/**
 * Read a globally defined boolean variable.
 *
 * Reading an unknown variable or trying to access a variable using the wrong
 * type will result in an error.
 */
int wasm_variable_read_boolean(const char *name, int name_len, bool *value);
int wasm_variable_read_double(const char *name, int name_len, double *value);
int wasm_variable_read_int(const char *name, int name_len, int32_t *value);

/**
 * Write to a globally defined boolean variable.
 *
 * This may fail if the variable already exists and has a different type.
 */
int wasm_variable_write_boolean(const char *name, int name_len, bool value);
int wasm_variable_write_double(const char *name, int name_len, double value);
int wasm_variable_write_int(const char *name, int name_len, int32_t value);
```

Add in a couple `#include`s and a header guard, and we should now have a proper
definition of the functionality exposed by the runtime.

## Dependency Injection

We now have a fairly solid interface that can be used by WASM code, but it'd
be really nice if we didn't hard-code the implementation for each function.
Luckily the `Ctx` passed to our functions by wasmer allows you to attach a
pointer to arbitrary data (`*mut c_void`) via [`Ctx::data`][ctx-data].

The normal way this is done is using *Dependency Injection*. Accept a generic
`Environment` object in the `poll()` method then set `Ctx::data` to point to
this `Environment` object while `poll()` is running.

First we're going to need an error type and a way to work with global variables
that may have different types.

```rust
// src/lib.rs

#[derive(Debug)]
pub enum Error {
    AddressOutOfBounds,
    UnknownVariable,
    BadVariableType,
    Other(Box<dyn std::error::Error>),
}

#[derive(Debug, Copy, Clone, PartialEq)]
pub enum Value {
    Bool(bool),
    Integer(i32),
    Float(f64),
}
```

Now we can define the `Environment` trait. It's essentially the Rust version of
our `intrinsics.h`, so its definition shouldn't be too surprising.

```rust
// src/lib.rs

pub trait Environment {
    fn elapsed(&self) -> Result<Duration, Error>;

    fn read_input(
        &self,
        address: usize,
        buffer: &mut [u8],
    ) -> Result<(), Error>;

    fn write_output(
        &mut self,
        address: usize,
        buffer: &[u8],
    ) -> Result<(), Error>;

    fn log(&self, record: &Record) -> Result<(), Error>;

    fn get_variable(&self, name: &str) -> Result<Value, Error>;

    fn set_variable(&mut self, name: &str, value: Value) -> Result<(), Error>;
}
```

The next thing we need to do is use the `data: *mut c_void` field on `Ctx` to
make sure each host function gets a reference to the current `Environment`.

This can be tricky because we're interacting with a lot of `unsafe`
code, in particular:

- We can't make the `poll()` function generic over any type `E: Environment`
  because then when `Ctx::data` is read by our functions, they won't know
  which type of `*mut E` to cast it to. The easiest way around this is to use
  dynamic dispatch (i.e. `&mut dyn Environment`)
- You can't cast a fat pointer (`&mut dyn Environment`) to a thin pointer
  (`*mut c_void`) so we need a second level of indirection
- The item pointed to by `Ctx::data` (our `Environment` object) is only
  guaranteed to stay valid for the duration of `poll()` so we need to make sure
  it gets cleared before returning
- Code that we call may `panic!()` and we need to make sure `Ctx::data` is
  cleared *no matter what*, otherwise we'll be leaving a dangling pointer behind
  and future calls may try to use it

To solve the first two problems we'll introduce an intermediate `State` object
which can be placed on the stack.

```rust
// src/lib.rs

/// Temporary state passed to each host function via [`Ctx::data`].
struct State<'a> {
    env: &'a mut dyn Environment,
}
```

From here, the naive implementation for `poll()` would look something like this:

```rust
// src/lib.rs

impl Program {
    ...

    pub fn poll(&mut self, env: &mut dyn Environment) -> Result<(), Error> {
        let mut state = State { env };
        self.instance.context_mut().data = &mut state as *mut State as *mut _;

        self.instance.call("poll", &[])?;

        Ok(())
    }
}
```

And yes, while it *does* correctly thread our `&mut dyn Environment` through to
the instance-global context data, we've completely ignored the last two points;
preventing our temporary `state` pointer from dangling, even if `wasmer`
panics.

The normal way to implement this is by putting `self.instance.call("poll", &[])`
inside a closure, then using a helper function to

1. Do some setup
2. Call the closure from `std::panic::catch_unwind()`
3. Do safety-critical cleanup, then
4. Resume panicking

```rust
// src/lib.rs

impl Program {
    ...

    pub fn poll(&mut self, env: &mut dyn Environment) -> Result<(), Error> {
        let mut state = State { env };
        self.instance.context_mut().data = &mut state as *mut State as *mut _;

        self.with_environment_context(env, |instance| {
            instance.call("poll", &[])?;
            Ok(())
        })
    }

    fn with_environment_context<F, T>(
        &mut self,
        env: &mut dyn Environment,
        func: F,
    ) -> Result<T, Error>
    where
        F: FnOnce(&Instance) -> Result<T, Error>,
    {
        let mut state = State { env };
        let instance = &mut self.instance;

        // point the data pointer at our temporary state.
        instance.context_mut().data = &mut state as *mut State<'_> as *mut _;
        // we can't use the old state variable any more (we'd have aliased
        // pointers) so deliberately shadow it
        #[allow(unused_variables)]
        let state = ();

        // execute the callback. We need to catch panics so we can clear the
        // data pointer no matter what. Using AssertUnwindSafe is
        // correct here because we'll continue panicking once the data
        // pointer is cleared
        let got = panic::catch_unwind(AssertUnwindSafe(|| func(instance)));

        // make sure the context data pointer is cleared. We don't need to drop
        // anything because it was just a `&mut State
        instance.context_mut().data = ptr::null_mut();

        match got {
            Ok(value) => value,
            Err(e) => panic::resume_unwind(e),
        }
    }
}
```

{{% notice info %}}
If you spot something here that looks odd, or you feel like my logic may be
unsound, I really want to hear about it! If you're not sure how to contact
me, you can create an issue against this blog's [issue tracker][issue].

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

We can now start creating our host functions.

First up, let's implement `wasm_current_time()`. The general strategy is:

1. Get a pointer to our `State`
2. Call the corresponding method on the `&mut dyn Environment`
3. Error out if something went wrong
4. Copy the result into WASM memory

```rust
// src/lib.rs

const WASM_SUCCESS: i32 = 0;
const WASM_GENERIC_ERROR: i32 = 1;

fn wasm_current_time(
    ctx: &mut Ctx,
    secs: WasmPtr<u64>,
    nanos: WasmPtr<u32>,
) -> i32 {
    // the data pointer should have been set by `with_environment_context()`
    if ctx.data.is_null() {
        return WASM_GENERIC_ERROR;
    }

    let elapsed = unsafe {
        // the data pointer was set, we can assume it points to a valid State
        let state = &mut *(ctx.data as *mut State);

        // and now we can call
        match state.env.elapsed() {
            Ok(duration) => duration,
            Err(e) => {
                log::error!("Unable to get the elapsed time: {}", e);
                return e.code();
            },
        }
    };

    let memory = ctx.memory(0);
    // the verbose equivalent of a null check and `*secs = elapsed.as_secs()`
    match secs.deref(memory) {
        Some(cell) => cell.set(elapsed.as_secs()),
        None => return WASM_GENERIC_ERROR,
    }
    match nanos.deref(memory) {
        Some(cell) => cell.set(elapsed.subsec_nanos()),
        None => return WASM_GENERIC_ERROR,
    }

    WASM_SUCCESS
}
```

This part is up to you, but you *can* reduce a lot of the boilerplate around
this with a couple simple macros.

For example, instead of manually calling `deref()` on a `WasmPtr<T>` and
setting the `&Cell<T>` we could define a `wasm_deref!()` macro like so:

```rust
// src/lib.rs

macro_rules! wasm_deref {
    (with $ctx:expr, * $ptr:ident = $value:expr) => {
        match $ptr.deref($ctx.memory(0)) {
            Some(cell) => cell.set($value),
            None => return WASM_GENERIC_ERROR,
        }
    };
}
```

This reduces the bottom half of `wasm_current_time()` to

```rust
// src/lib.rs

fn wasm_current_time(
    ctx: &mut Ctx,
    secs: WasmPtr<u64>,
    nanos: WasmPtr<u32>,
) -> i32 {
    ...

    wasm_deref!(with ctx, *secs = elapsed.as_secs());
    wasm_deref!(with ctx, *nanos = elapsed.subsec_nanos());

    WASM_SUCCESS
}
```

We can replace the error handling around calling `env.elapsed()` with another
macro. While we're at it, we should also iterate over each `cause` in an error
and print a "backtrace".

```rust
// src/lib.rs

impl Error {
    fn code(&self) -> i32 {
        match self {
            Error::AddressOutOfBounds => WASM_ADDRESS_OUT_OF_BOUNDS,
            Error::UnknownVariable => WASM_UNKNOWN_VARIABLE,
            Error::BadVariableType => WASM_BAD_VARIABLE_TYPE,
            _ => WASM_GENERIC_ERROR,
        }
    }
}

impl<'a> State<'a> {
    /// # Safety
    ///
    /// This assumes the [`Ctx`] was set up correctly using
    /// [`Program::with_environment_context()`].
    unsafe fn from_ctx(ctx: &mut Ctx) -> &'a mut State<'a> {
        assert!(!ctx.data.is_null());
        &mut *(ctx.data as *mut State)
    }
}

/// Convenience macro for executing a method using the [`Environment`] pointer
/// attached to [`Ctx::data`].
///
/// # Safety
///
/// See [`State::from_ctx()`] for the assumptions and invariants around safety.
macro_rules! try_with_env {
    ($ctx:expr, $method:ident ( $($arg:expr),* ), $failure_msg:expr) => {{
        // the data pointer should have been set by `with_environment_context()`
        if $ctx.data.is_null() {
            return WASM_GENERIC_ERROR;
        }

        let state = State::from_ctx($ctx);

        // call the method using the provided arguments
        match state.env.$method( $( $arg ),* ) {
            // happy path
            Ok(value) => value,
            Err(e) => {
                // log the original error using the failure_msg
                log::error!(concat!($failure_msg, ": {}"), e);

                // then iterate through the causes and log those too
                let mut cause = std::error::Error::source(&e);
                while let Some(inner) = cause {
                    log::error!("Caused by: {}", inner);
                    cause = inner.source();
                }

                // the operation failed, return the corresponding error code
                return e.code();
            }
        }
    }};
}
```

With those two changes, our `wasm_current_time()` function now spends a lot more
time doing "interesting" things and isn't as cluttered by error-handling.

```rust
// src/lib.rs

fn wasm_current_time(
    ctx: &mut Ctx,
    secs: WasmPtr<u64>,
    nanos: WasmPtr<u32>,
) -> i32 {
    let elapsed = unsafe {
        try_with_env!(ctx, elapsed(), "Unable to calculate the elapsed time")
    };

    wasm_deref!(with ctx, *secs = elapsed.as_secs());
    wasm_deref!(with ctx, *nanos = elapsed.subsec_nanos());

    WASM_SUCCESS
}
```

{{% notice warning %}}
It may not necessarily be a good thing to introduce macros which try to
handle error cases and `unsafe` code automatically.

The best `unsafe` code is stupid and boring because another programmer can
easily skim through the function and check it for correctness, because
everything does what it says on the tin. Burying error cases and `unsafe`ty
by using macros or helper functions may just make it easy to obfuscate otherwise
obvious bugs.

The decision is very much up to the author's discretion.
{{% /notice %}}

## Creating Our *"Standard Library"*

## Writing Programs in Other Languages

## Conclusion

[plugins]: {{< ref "plugins-in-rust.md" >}}
[wasmer]: https://github.com/wasmerio/wasmer
[lucet]: https://github.com/bytecodealliance/lucet
[wasmtime]: https://github.com/bytecodealliance/wasmtime
[mmio]: https://en.wikipedia.org/wiki/Memory-mapped_I/O
[img]: http://www.eng.utoledo.edu/~wevans/chap3_S.pdf
[tz]: https://www.youtube.com/watch?v=-5wpm-gesOY
[ctx-data]: https://docs.rs/wasmer-runtime/0.11.0/wasmer_runtime/struct.Ctx.html#structfield.data