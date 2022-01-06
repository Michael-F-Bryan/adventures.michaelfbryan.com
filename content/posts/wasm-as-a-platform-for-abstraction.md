---
title: "WebAssembly as a Platform for Abstraction"
date: "2019-12-15T11:55:00+08:00"
tags:
- Rust
- WebAssembly
---

In a project I've been playing around with recently, we've encountered the
dilemma where you want to make it easy for users to write their own
application logic using the system but at the same time want to keep that logic
decoupled from the implementation details of whatever platform the
application is running on.

If you've been programming for any amount of time your immediate reaction is
probably *"why bother mentioning this, doesn't it just fall out of good
library design?"*, and normally I would totally agree with you, except I
forgot to mention a couple of important details...

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

Web Assembly has gained a lot of traction over the last couple of years as a way
to write code in any language and run it in the browser, but it can be used for
so much more.

There are already [several][wasmer] [general-purpose][lucet]
[runtimes][wasmtime] available for running Wasm in a Rust program. These
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

Let's start off by creating a wrapper around an instantiated Wasm module.

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
so let's give `Program` a `poll()` method which will call the Wasm module's
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

use wasm::Program;
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

We'll also need a dummy program that can be compiled to Wasm and fed to our
`basic-runtime` example.

```rust
// example-program.rs

#[no_mangle]
pub extern "C" fn poll() {}
```

Now we should be able to compile the `example-program.rs` to Wasm and run it.

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
doesn't actually do anything, so we just created an expensive busy loop.

Let's give the Wasm code a way to print messages to the screen.

The way this is done is via that `imports!()` macro from earlier, basically
any function defined inside `imports!()` is accessible to the Wasm code.
`wasmer` imposes some strict constraints on the functions which may be exposed
to Wasm, restricting arguments and return values to `i32`, `i64`, `f32`, `f64`,
and pointers.

Functions may optionally accept a `&mut wasmer_runtime::Ctx` as the first
argument, this is useful for interacting with the runtime (e.g. to access
Wasm memory or call a function) or accessing contextual information attached
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

Okay, so we know how to expose functions to the Wasm code to let it interact
with the rest of the environment. Now the next task is look at the problem
we're trying to solve, and provide functions which will help solve it.

While this section will be fairly specific to my use case (creating some sort
of programmable logic controller that people can upload code to), it should
be fairly easy to adapt to suit your application.

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

Next we'll give users a way to read input and write output.

The runtime will make sure inputs are copied to a section of memory before
calling `poll()` and outputs will sit in another section of memory and be
synchronised with the real world after `poll()` completes. This is somewhat
similar to how [Memory-mapped IO][mmio] works in embedded systems, or the
[Process Image][img] on a PLC.

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

We now have a fairly solid interface that can be used by Wasm code, but it'd
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
        self.instance.context_mut().data = &mut state as *mut State as *mut c_void;

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
4. Copy the result into Wasm memory

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

/// Convenience macro for executing a method using the [`Environment`] pointer
/// attached to [`Ctx::data`].
///
/// # Safety
///
/// This assumes the [`Ctx`] was set up correctly using
/// [`Program::with_environment_context()`].
macro_rules! try_with_env {
    ($ctx:expr, $method:ident ( $($arg:expr),* ), $failure_msg:expr) => {{
        // the data pointer should have been set by `with_environment_context()`
        if $ctx.data.is_null() {
            return WASM_GENERIC_ERROR;
        }

        let state = &mut *($ctx.data as *mut State);

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

The best `unsafe` code is boring because another programmer can easily skim
through the function and check it for correctness because everything does
what it says on the tin. Burying error cases and `unsafe` by using macros or
helper functions may just make it easy to obfuscate otherwise obvious bugs.

The decision is very much up to the author's discretion.
{{% /notice %}}

Next we'll wire up the `wasm_log` function. The plan is to massage the provided
information into a form Rust's [`log`][log] crate can handle, then let the
`Environment` pass the resulting `LogRecord` through to its logger.

```rust
// src/lib.rs

fn wasm_log(
    ctx: &mut Ctx,
    level: i32,
    file: WasmPtr<u8, Array>,
    file_len: i32,
    line: i32,
    message: WasmPtr<u8, Array>,
    message_len: i32,
) -> i32 {
    // Note: We can't directly accept the Level enum here because out-of-range
    // enum variants are UB
    let level = match level {
        LOG_ERROR => Level::Error,
        LOG_WARN => Level::Warn,
        LOG_INFO => Level::Info,
        LOG_DEBUG => Level::Debug,
        LOG_TRACE => Level::Trace,
        _ => Level::Debug,
    };
    let filename = file.get_utf8_string(ctx.memory(0), file_len as u32);
    let message = message
        .get_utf8_string(ctx.memory(0), message_len as u32)
        .unwrap_or_default();
gt
    unsafe {
        try_with_env!(
            ctx,
            // unfortunately constructing a log record and using it needs to be
            // in a single statement because lifetimes
            // https://users.rust-lang.org/t/using-format-args-and-log-builder/22695
            log(&Record::builder()
                .level(level)
                .file(filename.as_deref())
                .line(Some(line as u32))
                .args(format_args!("{}", message))
                .build()),
            "Logging failed"
        );
    }

    WASM_SUCCESS
}
```

Implementing the other host functions follows the same steps. After writing a
couple of these function "trampolines", it goes from being a scary `unsafe`
task to a mechanical job of translating arguments and error values.

{{% expand "A big wall of code that translates arguments and error values." %}}
```rust
// src/lib.rs

impl TryFrom<Value> for bool {
    type Error = Error;

    fn try_from(other: Value) -> Result<bool, Self::Error> {
        match other {
            Value::Bool(b) => Ok(b),
            _ => Err(Error::BadVariableType),
        }
    }
}

impl TryFrom<Value> for i32 {
    type Error = Error;

    fn try_from(other: Value) -> Result<i32, Self::Error> {
        match other {
            Value::Integer(i) => Ok(i),
            _ => Err(Error::BadVariableType),
        }
    }
}

impl TryFrom<Value> for f64 {
    type Error = Error;

    fn try_from(other: Value) -> Result<f64, Self::Error> {
        match other {
            Value::Float(f) => Ok(f),
            _ => Err(Error::BadVariableType),
        }
    }
}

impl From<bool> for Value {
    fn from(b: bool) -> Value { Value::Bool(b) }
}

impl From<i32> for Value {
    fn from(i: i32) -> Value { Value::Integer(i) }
}
impl From<f64> for Value {
    fn from(d: f64) -> Value { Value::Float(d) }
}

fn wasm_read_input(
    ctx: &mut Ctx,
    address: u32,
    buffer: WasmPtr<u8, Array>,
    buffer_len: i32,
) -> i32 {
    let mut temp_buffer = vec![0; buffer_len.try_into().unwrap()];

    unsafe {
        try_with_env!(
            ctx,
            read_input(address.try_into().unwrap(), &mut temp_buffer[..]),
            "Unable to read the input"
        );
    }

    wasm_deref!(with ctx, *buffer = for byte in temp_buffer);

    WASM_SUCCESS
}

fn wasm_write_output(
    ctx: &mut Ctx,
    address: u32,
    data: WasmPtr<u8, Array>,
    data_len: i32,
) -> i32 {
    let buffer: Vec<u8> =
        match data.deref(ctx.memory(0), 0, data_len.try_into().unwrap()) {
            Some(slice) => slice.iter().map(|cell| cell.get()).collect(),
            None => return WASM_GENERIC_ERROR,
        };

    unsafe {
        try_with_env!(
            ctx,
            write_output(address.try_into().unwrap(), &buffer),
            "Unable to set outputs"
        );
    }

    WASM_SUCCESS
}

fn variable_get_and_map<F, Q, T>(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: WasmPtr<Q>,
    map: F,
) -> i32
where
    F: FnOnce(T) -> Q,
    T: TryFrom<Value>,
    Q: wasmer_runtime::types::ValueType,
{
    let name = match name
        .get_utf8_string(ctx.memory(0), name_len.try_into().unwrap())
    {
        Some(n) => n,
        None => return WASM_GENERIC_ERROR,
    };

    let variable = unsafe {
        try_with_env!(
            ctx,
            get_variable(name),
            "Unable to retrieve the variable"
        )
    };

    let variable = match T::try_from(variable) {
        Ok(v) => v,
        _ => return WASM_BAD_VARIABLE_TYPE,
    };

    match value.deref(ctx.memory(0)) {
        Some(cell) => {
            cell.set(map(variable));
            WASM_SUCCESS
        },
        None => WASM_GENERIC_ERROR,
    }
}

fn wasm_variable_read_boolean(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: WasmPtr<u8>,
) -> i32 {
    variable_get_and_map(
        ctx,
        name,
        name_len,
        value,
        |b: bool| if b { 1 } else { 0 },
    )
}

fn wasm_variable_read_int(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: WasmPtr<i32>,
) -> i32 {
    variable_get_and_map(ctx, name, name_len, value, |i| i)
}

fn wasm_variable_read_double(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: WasmPtr<f64>,
) -> i32 {
    variable_get_and_map(ctx, name, name_len, value, |d| d)
}

fn set_variable<F, Q, T>(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: Q,
    map: F,
) -> i32
where
    F: FnOnce(Q) -> T,
    T: Into<Value>,
{
    let name = match name
        .get_utf8_string(ctx.memory(0), name_len.try_into().unwrap())
    {
        Some(n) => n,
        None => return WASM_GENERIC_ERROR,
    };

    let value = map(value).into();

    unsafe {
        try_with_env!(
            ctx,
            set_variable(name, value),
            "Unable to set the variable"
        )
    };

    WASM_SUCCESS
}

fn wasm_variable_write_boolean(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: u8,
) -> i32 {
    set_variable(ctx, name, name_len, value, |v| v != 0)
}

fn wasm_variable_write_int(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: i32,
) -> i32 {
    set_variable(ctx, name, name_len, value, |v| v)
}

fn wasm_variable_write_double(
    ctx: &mut Ctx,
    name: WasmPtr<u8, Array>,
    name_len: i32,
    value: f64,
) -> i32 {
    set_variable(ctx, name, name_len, value, |v| v)
}
```
{{% /expand %}}

## Creating Our *"Standard Library"*

Technically we now have everything we need so users can write programs that run
on our motion controller, but manually writing `extern` blocks at the top of
every program is pretty clunky.

In most systems you'll have a *"Standard Library"* which provides bindings to
the host environment (typically the OS) and higher-level abstractions. Why
should our system be any different?

We'll start by creating a new crate for our standard library, imaginatively
called `wasm_std`, and add it to the current workspace.

```console
$ cd ..
$ cargo new --lib --name wasm_std std
     Created library `wasm_std` package
```

{{% notice info %}}
I've also moved `intrinsics.h` (declaring the host interface) to this
`std` crate because it's a more appropriate place.
{{% /notice %}}

Before we can throw `intrinsics.h` at `bindgen` we need to create type
definitions for the various integer types in `stdint.h`. Normally `bindgen`
would be able to use types from `std::os::raw`, but because we aren't using the
standard library we don't have access to them. Likewise we can't use the types
from `libc` because that would mean linking to `libc`, which isn't an option
either. See the [issue on GitHub][bg-issue] if you're interested.

```rust
// std/src/ctypes.rs

//! Re-exports of C types on a "normal" x86 computer. Normally you'd use
//! `std::os::raw` or `libc`, but in our case that's not possible.
//!
//! Most of these definitions are copied straight from `libc`'s source code.

#![allow(bad_style, dead_code)]

// src/libc/unix/linux_like/linux/gnu/b64/x86_64/mod.rs
pub type c_char = i8;
pub type wchar_t = i32;

// src/libc/unix/linux_like/linux/gnu/b64/x86_64/not_x32.rs
pub type c_long = i64;
pub type c_ulong = u64;

// src/libc/unix/mod.rs
pub type c_schar = i8;
pub type c_uchar = u8;
pub type c_short = i16;
pub type c_ushort = u16;
pub type c_int = i32;
pub type c_uint = u32;
pub type c_float = f32;
pub type c_double = f64;
pub type c_longlong = i64;
pub type c_ulonglong = u64;
pub type intmax_t = i64;
pub type uintmax_t = u64;
pub type size_t = usize;
pub type ptrdiff_t = isize;
pub type intptr_t = isize;
pub type uintptr_t = usize;
pub type ssize_t = isize;
```

We can now generate declarations for `intrinsics.h`. This will
be analogous to [`std::intrinsics`][std-intrinsics] in Rust's standard library.

After a bit of trial and error, this incantation seemed to generate the output
we want without trying to add declarations for half of `libc`.

```console
$ cp ../intrinsics.h .
$ bindgen intrinsics.h \
    --whitelist-type 'wasm_.*' \
    --whitelist-function 'wasm_.*' \
    --output src/intrinsics.rs \
    --use-core \
    --ctypes-prefix crate::ctypes \
     --raw-line '#![allow(bad_style, dead_code)]'
$ tail src/intrinsics.rs
extern "C" {
    /// Write to a globally defined integer variable.
    ///
    /// This may fail if the variable already exists and has a different type.
    pub fn wasm_variable_write_int(
        name: *const ::std::os::raw::c_char,
        name_len: ::std::os::raw::c_int,
        value: i32,
    ) -> wasm_result_t;
}
```

Our `lib.rs` needs to be updated to use `intrinsics`.

```rust
// std/lib.rs

//! The standard library, providing host bindings and abstractions.

// we are the standard library.
#![no_std]

pub mod intrinsics;
```

While it's still quite small at the moment, as we gain more experience using
this system we'll be able to move commonly-used elements into the standard
library to provide a more *batteries included* feel.

{{% notice tip %}}
Seeing as the end goal is for users to write programs for our controller in
any language, not just Rust, this may eventually require tools like
[*Interface Types*][interface-types].
{{% /notice %}}

Now we have a standard library we can rewrite our previous `example-program.rs`.

```console
$ cd ../examples/wasm-programs
$ rm example-program.rs
$ cargo new example-program
$ cd example-program
```

We need to add our standard library as a dependency.

```console
$ cargo add ../../../std
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding wasm-std (unknown version) to dependencies
```

Because this crate is being compiled to Wasm we'll need to make sure it is
compiled using the `cdylib` crate type.

```toml
# examples/wasm-programs/example-program/Cargo.toml

[package]
name = "example-program"
version = "0.1.0"
authors = ["Michael Bryan <michaelfbryan@gmail.com>"]
edition = "2018"

[lib]
crate-type = ["cdylib"]

[dependencies]
wasm-std = { path = "../../../../std/" }
```

At some point we'll want to create a nice `println!()` macro instead of
invoking the `wasm_log()` intrinsic directly, but for now here's the
equivalent of our original program.

```rust
// examples/wasm-programs/example-program/src/lib.rs

#![no_std]

use wasm_std::intrinsics::{
    self, wasm_log_level_LOG_INFO as LOG_INFO,
    wasm_result_t_WASM_SUCCESS as WASM_SUCCESS,
};

#[no_mangle]
pub extern "C" fn poll() {
    unsafe {
        let file = file!();
        let msg = "Polling\n";

        let ret = intrinsics::wasm_log(
            LOG_INFO,
            file.as_ptr() as *const _,
            file.len() as _,
            line!() as _,
            msg.as_ptr() as *const _,
            msg.len() as _,
        );

        assert_eq!(ret, WASM_SUCCESS);
    }
}
```

We should now be able to build this crate.

```console
$ cargo build
   Compiling wasm-std v0.1.0 (/home/michael/Documents/wasm/std)
   Compiling example-program v0.1.0 (/home/michael/Documents/wasm/examples/wasm-programs/example-program)
error: `#[panic_handler]` function required, but not found

error: aborting due to previous error

error: could not compile `example-program`.

To learn more, run the command again with --verbose.
```

Oops! Looks like using `assert_eq!()` requires code for handling panics.

To make sure normal users don't need to define a `#[panic_handler]` for every
program, we'll implement it in our standard library. We can just use Wasm's
`unreachable` command for now. This will trigger the corresponding "trap" on the
Wasm virtual machine and immediately stop execution.

```rust
// std/src/sys.rs

#![cfg(all(not(test), target_arch = "wasm32"))]

use core::panic::PanicInfo;

#[panic_handler]
pub fn panic_handler(info: &PanicInfo) -> ! {
    core::arch::wasm32::unreachable()
}
```

Now we can successfully compile and run our program.

```console
$ cargo build --target wasm32-unknown-unknown
   Compiling wasm-std v0.1.0 (/home/michael/Documents/wasm/std)
   Compiling example-program v0.1.0 (/home/michael/Documents/wasm/examples/wasm-programs/example-program)
    Finished dev [unoptimized + debuginfo] target(s) in 0.21s
$ ls target/wasm32-unknown-unknown/debug
build  deps  example_program.d  example_program.wasm  examples  incremental
$ cd ../../..
$ cargo run --example basic-runtime -- examples/wasm-programs/example-program/target/wasm32-unknown-unknown/debug/example_program.wasm

^C
```

Oh, we forgot to add `env_logger` as a dev-dependency and initialize it in the `basic-runtime.rs` example.

```diff
diff --git a/wasm/examples/basic-runtime.rs b/wasm/examples/basic-runtime.rs
index de2017d..586d54d 100644
--- a/wasm/examples/basic-runtime.rs
+++ b/wasm/examples/basic-runtime.rs
@@ -2,6 +2,8 @@ use wasm::{InMemory, Program};
 use std::env;

 fn main() -> Result<(), Box<dyn std::error::Error>> {
+    env_logger::init();
+
     let wasm_file = match env::args().skip(1).next() {
         Some(filename) => filename,
         None => panic!("Usage: basic-runtime <wasm-file>"),
```

Now it should work.

```console
RUST_LOG=info cargo run --example basic-runtime -- examples/wasm-programs/example-program/target/wasm32-unknown-unknown/debug/example_program.wasm
   Compiling wasm v0.1.0 (/home/michael/Documents/wasm)
    Finished dev [unoptimized + debuginfo] target(s) in 1.14s
     Running `/home/michael/Documents/wasm/target/debug/examples/basic-runtime examples/wasm-programs/example-program/target/wasm32-unknown-unknown/debug/example_program.wasm`
[2019-12-11T10:12:25Z INFO ] Polling
[2019-12-11T10:12:25Z INFO ] Polling
[2019-12-11T10:12:25Z INFO ] Polling
[2019-12-11T10:12:25Z INFO ] Polling
[2019-12-11T10:12:25Z INFO ] Polling
[2019-12-11T10:12:25Z INFO ] Polling
^C
```

Huzzah!

## Testing Everything

So now we can run an example program, but needing to manually set up a crate
and compile it every time isn't the best method of testing. It'd be better if
our test suite could automatically compile and run a collection of programs,
feeding it pre-defined inputs, and making sure it behaved as expected.

Rust's [compiletest][ct] is a really good example of this in action. At this
point it's worth taking a peek at `rustc`'s test suite to see how similar
projects are tested. Hopefully we can use it as inspiration.

When testing the compiler's error message the compiler's test suite will contain
a `*.rs` file containing code which annotates offending lines (e.g. using a
comment like `//~ ERROR: ...`) and a `*.stderr` file containing the exact output
from STDOUT.

A simple example of this is
[rust/src/test/ui/empty/empty-linkname.rs][empty-linkname.rs] for detecting
when the `name` parameter passed to `#[link]` is empty.

```rust
#[link(name = "")] //~ ERROR: given with empty name
extern {
}

fn main() {}
```

The contents of [empty-linkname.stderr][empty-linkname.stderr] looks like this:

```
error[E0454]: `#[link(name = "")]` given with empty name
  --> $DIR/empty-linkname.rs:1:1
   |
LL | #[link(name = "")]
   | ^^^^^^^^^^^^^^^^^^ empty name given

error: aborting due to previous error

For more information about this error, try `rustc --explain E0454`.
```

We can take a fairly similar approach when designing a test suite for the
runtime. Tests will consist of two files, some source code (written in Rust) and
a file containing some representation of the expected output.

The main difference between our runtime's tests and `rustc`'s UI tests is
that we'll need to incorporate a time element into the expected output. The
output is also less tangible, `rustc`'s error messages are just text written to
STDERR compared to the array of binary that our runtime uses for outputs.

It's also easy for `rustc`'s test suite to compile a single `*.rs` file and
inspect the output, it's something you could concievably implement using a
bash script. On the other hand, our compilation process is non-trivial, and
the requirement for inspecting changing inputs over time requires us to
instrument the runtime to insert checks for expected behaviour after every
call to `Program::poll()`.

Based on our previous experimentation, let's write down a simple testing
procedure:

1. Write a file containing some program that uses our standard library and
  does something interesting
2. Create a new crate in a temporary directory (e.g. `/tmp.123/`)
3. Make sure that crate depends on our standard library
4. Copy the file from step 1 to `lib.rs` in the temporary crate
5. Compile it
6. Find the `*.wasm` file under
   `/tmp.123/target/wasm32-unknown-unknown/debug/` and read it into memory
7. Use `Program::load()` to instantiate that Wasm module
8. Continually `poll()` the program setting up inputs according to some
   pre-defined *Recipe* and make sure outputs change as expected

This may end up being a little complex so let's create a `wasm-test` helper
crate and add it to our workspace.

```console
$ cargo new --lib wasm-test
```

We'll also be needing a couple dependencies.

```console
$ cargo add log tempfile serde serde_derive serde_json anyhow ../wasm
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding log v0.4.8 to dependencies
      Adding tempfile v3.1.0 to dependencies
      Adding serde v1.0.103 to dependencies
      Adding serde_derive v1.0.103 to dependencies
      Adding serde_json v1.0.44 to dependencies
      Adding anyhow v1.0.25 to dependencies
      Adding wasm (unknown version) to dependencies
```

Looking back at steps 2 and 3, when creating our temporary crate we'll need to
make sure the `Cargo.toml` is set up correctly. There are a lot of advanced
templating libraries out there, but for our purposes `string.replace()`-style
"templates" should be more than sufficient.

```rust
// wasm-test/src/compile.rs

const CARGO_TOML_TEMPLATE: &str = r#"
[package]
name = "$TEST_NAME"
version = "0.1.0"
authors = ["Michael Bryan <michaelfbryan@gmail.com>"]
edition = "2018"

[dependencies]
wasm-std = { path = "$STD_PATH" }

[lib]
path = "lib.rs"
crate-type = ["cdylib"]
"#;
```

The other compilation-related tasks are fairly straightforward to automate
using by just shelling out to `std::process::Command`. We can develop better
tooling in time, but this crude implementation should suffice for now.

```rust
// wasm-test/src/compile.rs

use anyhow::{Error, Context};
use std::{fs, path::Path};
use tempfile::TempDir;

fn compile_to_wasm(
    name: &str,
    src: &str,
    target_dir: &Path,
    std_manifest_dir: &Path,
) -> Result<Vec<u8>, Error> {
    // first we'll need a directory for our crate
    let dir = TempDir::new().context("Unable to create a temporary dir")?;

    // then create a Cargo.toml file
    let std_manifest_dir = std_manifest_dir.display().to_string();
    let cargo_toml = CARGO_TOML_TEMPLATE
        .replace("$TEST_NAME", name)
        .replace("$STD_PATH", &std_manifest_dir);
    let cargo_toml_path = dir.path().join("Cargo.toml");
    fs::write(&cargo_toml_path, cargo_toml)
        .context("Couldn't write Cargo.toml")?;

    // copy our source code across
    fs::write(dir.path().join("lib.rs"), src)
        .context("Couldn't write lib.rs")?;

    // compile to wasm
    let output = Command::new("cargo")
        .arg("build")
        .arg("--manifest-path")
        .arg(&cargo_toml_path)
        .arg("--target-dir")
        .arg(&target_dir)
        .arg("--target")
        .arg("wasm32-unknown-unknown")
        .arg("--offline")
        .status()
        .context("Unable to start cargo")?;

    anyhow::ensure!(output.success(), "Compilation failed");

    // look for the Wasm file using a hard-coded path
    let blob = target_dir
        .join("wasm32-unknown-unknown")
        .join("debug")
        .join(name)
        .with_extension("wasm");

    fs::read(&blob)
        .with_context(|| format!("Unable to read \"{}\"", blob.display()))
}
```

To avoid having to always provide the `target_dir` and `std_manifest_dir`
parameters every time we can wrap them up inside some sort of `Compiler` struct.

```rust
// wasm-test/src/compile.rs

#[derive(Debug, Clone, PartialEq)]
pub struct Compiler {
    std_manifest_dir: PathBuf,
    target_dir: PathBuf,
}
```

From here, instantiating a Wasm program can be implemented as a method on
`Compiler` which just calls `compile_to_wasm()` and `Program::load()`.

```rust
// wasm-test/src/compile.rs

use wasm::Program;

impl Compiler {
    pub fn instantiate(&self, name: &str, src: &str) -> Result<Program, Error> {
        let wasm = compile_to_wasm(
            name,
            src,
            &self.target_dir,
            &self.std_manifest_dir,
        )
        .unwrap();

        Program::load(&wasm)
            .map_err(|e| anyhow::format_err!("Wasm loading failed: {}", e))
    }
}
```

Next, we need some sort of `TestCase` which can be loaded from disk. In this
case `some-program.rs` will be the code being tested and `some-program.json`
will contain a `Recipe` dictating the expected behaviour.

We'll need to derive `Serialize` and `Deserialize` so the `Recipe` can be loaded
from JSON.

```rust
// wasm-test/src/test_case.rs

use serde_derive::{Deserialize, Serialize};
use std::time::Duration;

/// A single test case.
#[derive(Debug, Clone, PartialEq)]
pub struct TestCase {
    pub name: String,
    pub src: String,
    pub recipe: Recipe,
}

/// A series of snapshots containing inputs and expected outputs for the test
/// program.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Recipe {
    pub passes: Vec<Pass>,
}

/// The inputs and expected outputs for a single call to [`Program::poll()`].
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Pass {
    #[serde(with = "humantime_serde")]
    pub elapsed: Duration,
    pub inputs: Vec<u8>,
    pub expected_outputs: Vec<u8>,
    #[serde(default)]
    pub expected_log_messages: Vec<String>,
}
```

We'll also need constructors which can load a `TestCase` from a `*.rs` and
`*.json` file on disk.

```rust
// wasm-test/src/test_case.rs

use anyhow::{Context, Error};

impl TestCase {
    pub fn load<P, Q>(src_file: P, recipe_file: Q) -> Result<TestCase, Error>
    where
        P: AsRef<Path>,
        Q: AsRef<Path>,
    {
        let src_file = src_file.as_ref();
        let name =
            src_file
                .file_name()
                .and_then(|n| n.to_str())
                .ok_or_else(|| {
                    anyhow::format_err!("Unable to determine the filename")
                })?;

        let src = fs::read_to_string(src_file)
            .context("Couldn't read the source file")?;
        let recipe = fs::read_to_string(recipe_file)
            .context("Couldn't read the recipe file")?;

        TestCase::parse(name, src, recipe)
    }

    pub fn parse<N, S, R>(name: N, src: S, recipe: R) -> Result<TestCase, Error>
    where
        N: Into<String>,
        S: Into<String>,
        R: AsRef<str>,
    {
        let name = name.into();
        let src = src.into();
        let recipe = serde_json::from_str(recipe.as_ref())
            .context("Recipe parsing failed")?;

        Ok(TestCase { name, src, recipe })
    }
}
```

We also need an implementation of `Environment` for testing purposes. This is
the *"instrumenting"* part mentioned earlier.

```rust
// wasm-test/src/environment.rs

use log::Level;
use std::time::Duration;

#[derive(Debug, Default, Clone, PartialEq)]
pub struct TestEnvironment {
    pub elapsed: Duration,
    pub inputs: Vec<u8>,
    pub outputs: Vec<u8>,
    pub log_messages: Vec<(Level, String)>,
    pub variables: HashMap<String, Value>,
}
```

Implementing the `Environment` trait is more tedious than anything else.

```rust
// wasm-test/src/environment.rs

use wasm::{Environment, Error as WasmError};

impl wasm::Environment for TestEnvironment {
    fn elapsed(&self) -> Result<Duration, WasmError> { Ok(self.elapsed) }

    fn read_input(
        &self,
        address: usize,
        buffer: &mut [u8],
    ) -> Result<(), WasmError> {
        let src = self
            .inputs
            .get(address..address + buffer.len())
            .ok_or(WasmError::AddressOutOfBounds)?;
        buffer.copy_from_slice(src);

        Ok(())
    }

    fn write_output(
        &mut self,
        address: usize,
        buffer: &[u8],
    ) -> Result<(), WasmError> {
        let dest = self
            .outputs
            .get_mut(address..address + buffer.len())
            .ok_or(WasmError::AddressOutOfBounds)?;
        dest.copy_from_slice(buffer);

        Ok(())
    }

    fn log(&mut self, record: &Record<'_>) -> Result<(), WasmError> {
        self.log_messages
            .push((record.level(), record.args().to_string()));
        Ok(())
    }

    fn get_variable(&self, name: &str) -> Result<Value, WasmError> {
        self.variables
            .get(name)
            .copied()
            .ok_or(WasmError::UnknownVariable)
    }

    fn set_variable(
        &mut self,
        name: &str,
        value: Value,
    ) -> Result<(), WasmError> {
        use std::collections::hash_map::Entry;

        match self.variables.entry(name.to_string()) {
            Entry::Vacant(vacant) => {
                vacant.insert(value);
            },
            Entry::Occupied(mut occupied) => {
                if occupied.get().kind() == value.kind() {
                    occupied.insert(value);
                } else {
                    return Err(WasmError::BadVariableType);
                }
            },
        }

        Ok(())
    }
}
```

We should also add some code for doing the setup and comparison steps when
polling.

```rust
// wasm-test/src/environment.rs

use crate::Pass;
use anyhow::Error;

impl TestEnvironment {
    pub fn setup(&mut self, pass: &Pass) {
        self.elapsed = pass.elapsed;
        self.load_inputs(&pass.inputs);
        self.outputs.clear();
        self.outputs
            .extend(std::iter::repeat(0).take(pass.expected_outputs.len()));
        self.log_messages.clear();
    }

    fn load_inputs(&mut self, inputs: &[u8]) {
        self.inputs.clear();
        self.inputs.extend(inputs);
    }

    pub fn compare(&self, pass: &Pass) -> Result<(), Error> {
        if self.outputs != pass.expected_outputs {
            anyhow::bail!("{:?} != {:?}", self.outputs, pass.expected_outputs);
        }

        // create a temporary set containing all log messages
        let mut log_messages: Vec<_> = self
            .log_messages
            .iter()
            .map(|(_, msg)| msg.clone())
            .collect();

        for msg in &pass.expected_log_messages {
            match log_messages.iter().position(|logged| logged.contains(msg)) {
                Some(position) => {
                    // we've found the message, remove it from the list of
                    // candidates and go to the next one.
                    log_messages.remove(position);
                },
                None => anyhow::bail!(
                    "Unable to find log message \"{}\" in {:?}",
                    msg,
                    self.log_messages
                ),
            }
        }

        if !log_messages.is_empty() {
            anyhow::bail!("Unexpected log messages: {:?}", log_messages);
        }

        Ok(())
    }
}
```

Our `wasm-test` crate can now compile a Rust program to Wasm and link it to our
standard library, instantiate the Wasm module, load a pre-defined test recipe,
and create a test `Environment`.

Now we just need a way to execute a particular test case and the `wasm-test`
crate will be complete.

```rust
// wasm-test/src/lib.rs

mod compile;
mod environment;
mod test_case;

pub use compile::Compiler;
pub use environment::TestEnvironment;
pub use test_case::{Pass, Recipe, TestCase};

use anyhow::{Context, Error};

pub fn run_test_case(
    compiler: &Compiler,
    test_case: &TestCase,
) -> Result<(), Error> {
    let mut wasm = compiler
        .instantiate(&test_case.name, &test_case.src)
        .context("Unable to load the Wasm module")?;
    let mut env = TestEnvironment::default();

    for pass in &test_case.recipe.passes {
        env.setup(pass);

        wasm.poll(&mut env)
            .map_err(|e| Error::msg(e.to_string()))
            .context("Polling failed")?;

        env.compare(pass).context("Output comparison failed")?;
    }

    Ok(())
}
```

Now the `wasm-test` crate is up and running we can go back to the `wasm` crate's
integration tests.

I've copied the `example-program.rs` from the last section into the
`tests/data/` directory and written up a simple `example_program.json` file
which will make sure it prints `"Polling"`.

```json
// tests/data/example_program.json

{
    "passes": [
        {
            "elapsed": "50ms",
            "inputs": [],
            "expected_outputs": [],
            "expected_log_messages": [
                "Polling"
            ]
        }
    ]
}
```

To make sure we've wired up the `wasm_write_output()` function correctly,
there's also a `set_outputs.rs` test program.

```rust
// tests/data/set_outputs.rs

#![no_std]

use wasm_std::intrinsics::{
    self, wasm_result_t_WASM_SUCCESS as WASM_SUCCESS,
};

const ADDRESS: u32 = 1;

#[no_mangle]
pub extern "C" fn poll() {
    let payload = [1, 2, 3, 4, 5];

    unsafe {
        let ret = intrinsics::wasm_write_output(
            ADDRESS,
            payload.as_ptr(),
            payload.len() as _,
        );
        assert_eq!(ret, WASM_SUCCESS);
    }
}
```

And its accompanying `*.json` file:

```json
// tests/data/set_outputs.json

{
    "passes": [
        {
            "elapsed": "50ms",
            "inputs": [],
            "expected_outputs": [0, 1, 2, 3, 4, 5, 0]
        }
    ]
}
```

Now we just need to make sure the test programs get run and behave as expected.

For this we'll create the aptly-named `behaviour_tests.rs` integration test
under `tests/`.

Thanks to the work we did earlier, loading and running an integration test
becomes really easy.

```rust
// tests/behaviour_tests.rs

use anyhow::Context;
use wasm_test::{TestCase, Compiler};

#[test]
fn set_outputs() {
    let _ = env_logger::try_init();

    let src = include_str!("data/set_outputs.rs");
    let recipe = include_str!("data/set_outputs.json");

    let tc = TestCase::parse(set_outputs, src, recipe)
        .context("Unable to load the test case").unwrap();
    let compiler = Compiler::default();

    wasm_test::run_test_case(&compiler, &tc).unwrap();
}
```

If we want to make more tests, one way would be to copy the `set_outputs`
function and replace every instance of `"set_outputs"` with the name of the
tests.

That sounds kinda annoying.

Normally you would try to extract the testing logic out into another function,
but that wouldn't let us run each test program as its own test. Luckily, macros
exist for exactly this sort of thing!

```rust
// tests/behaviour_tests.rs

use anyhow::Context;
use wasm_test::{Compiler, TestCase};

macro_rules! wasm_test {
    ($filename:ident, $( $rest:ident ),*) => {
        wasm_test!($filename);
        wasm_test!($($rest),*);
    };
    ($filename:ident) => {
        #[test]
        fn $filename() {
            let _ = env_logger::try_init();

            let src = include_str!(concat!("data/", stringify!($filename), ".rs"));
            let recipe = include_str!(concat!("data/", stringify!($filename), ".json"));

            let tc = TestCase::parse(stringify!($filename), src, recipe)
                .context("Unable to load the test case").unwrap();
            let compiler = Compiler::default();

            wasm_test::run_test_case(&compiler, &tc).unwrap();
        }
    };
}

wasm_test!(example_program, set_outputs);
```

We can check that these tests are actually working by inserting some deliberate
bugs.

```diff
diff --git a/tests/data/example_program.json b/tests/data/example_program.json
index 63d5ade..4df1806 100644
--- a/tests/data/example_program.json
+++ b/tests/data/example_program.json
@@ -1,10 +1,12 @@
 {
     "passes": [
         {
             "elapsed": "50ms",
             "inputs": [],
             "expected_outputs": [],
             "expected_log_messages": [
-                "Polling"
+                "Polling",
+                "Another log message"
             ]
         }
     ]
diff --git a/tests/data/set_outputs.rs b/tests/data/set_outputs.rs
index b65ada6..aedf856 100644
--- a/tests/data/set_outputs.rs
+++ b/tests/data/set_outputs.rs
@@ -4,7 +4,7 @@ use wasm_std::intrinsics::{
     self, wasm_result_t_WASM_SUCCESS as WASM_SUCCESS,
 };

-const ADDRESS: u32 = 1;
+const ADDRESS: u32 = 0;

 #[no_mangle]
 pub extern "C" fn poll() {
```

And if we execute the test suite again, we're shown a couple errors:

```console
$ cargo test
Finished test [unoptimized + debuginfo] target(s) in 0.24s

     Running /home/michael/Documents/wasm/target/debug/deps/behaviour_tests-321146c56a045437

running 2 tests
   Compiling set_outputs v0.1.0 (/tmp/.tmpYX6WZH)
    Finished dev [unoptimized + debuginfo] target(s) in 0.24s
   Compiling example_program v0.1.0 (/tmp/.tmpk3eAvE)
    Finished dev [unoptimized + debuginfo] target(s) in 0.77s
test example_program ... FAILED
test set_outputs ... FAILED

failures:

---- example_program stdout ----
thread 'example_program' panicked at 'called `Result::unwrap()` on an `Err` value: Output comparison failed

Caused by:
    Unable to find log message "Another log message" in [(Info, "Polling")]', src/libcore/result.rs:1189:5
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace.

---- set_outputs stdout ----
thread 'set_outputs' panicked at 'called `Result::unwrap()` on an `Err` value: Output comparison failed

Caused by:
    [1, 2, 3, 4, 5, 0, 0] != [0, 1, 2, 3, 4, 5, 0]', src/libcore/result.rs:1189:5


failures:
    example_program
    set_outputs

test result: FAILED. 0 passed; 2 failed; 0 ignored; 0 measured; 0 filtered out

error: test failed, to rerun pass '--test behaviour_tests'
```

## Conclusion

It's been a long road, but now we have a really good foundation for working with
Wasm programs!

There's still a lot of room for improvement, and the host environment still looks
quite bare, but this implementation does everything I need to unblock other
parts of my project.

## Useful Links

- [Bringing WebAssembly outside the web with WASI](https://www.youtube.com/watch?v=fh9WXPu0hw8)
- [The Wasmer Website](https://wasmer.io/)

[plugins]: {{< ref "plugins-in-rust.md" >}}
[wasmer]: https://github.com/wasmerio/wasmer
[lucet]: https://github.com/bytecodealliance/lucet
[wasmtime]: https://github.com/bytecodealliance/wasmtime
[mmio]: https://en.wikipedia.org/wiki/Memory-mapped_I/O
[img]: http://www.eng.utoledo.edu/~wevans/chap3_S.pdf
[tz]: https://www.youtube.com/watch?v=-5wpm-gesOY
[ctx-data]: https://docs.rs/wasmer-runtime/0.11.0/wasmer_runtime/struct.Ctx.html#structfield.data
[log]: https://crates.io/crates/log
[std-intrinsics]: https://doc.rust-lang.org/std/intrinsics/index.html
[interface-types]: https://github.com/WebAssembly/interface-types/blob/master/proposals/interface-types/Explainer.md
[bg-issue]: https://github.com/rust-lang/rust-bindgen/issues/1583
[ct]: https://rust-lang.github.io/rustc-guide/compiletest.html
[empty-linkname.rs]: https://github.com/rust-lang/rust/blob/cf7e019b42cd523d91cb350ab49acbda1b11e571/src/test/ui/empty/empty-linkname.rs
[empty-linkname.stderr]: https://github.com/rust-lang/rust/blob/master/src/test/ui/empty/empty-linkname.stderr
