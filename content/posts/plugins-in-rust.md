---
title: "Plugins in Rust"
date: "2019-09-30T00:04:58+08:00"
draft: true
tags:
- rust
---

Imagine you are implementing a calculator application and want users to be able
to extend the application with their own functionality. For example, imagine a
user wants to provide a `random()` function that generates *true* random numbers
using [random.org][r-o] instead of the pseudo-random numbers that a crate like
[rand][rand] would provide.

The Rust language gives you a lot of really powerful tools for adding
flexibility and extensibility to your applications (e.g. traits, enums,
macros), but all of these happen at compile time. Unfortunately, to get the 
flexibility that we're looking we'll need to be able to add new functionalty at
runtime.

This can be achieved using a technique called [Dynamic Loading][wiki].

## What Is Dynamic Loading?

Dynamic loading is a mechanism provided by all mainstream Operating Systems
where a library can be loaded at runtime so the user can retrieve addresses of
functions or variables. The address of these functions and variables can then
be used just like any other pointer.

On *nix platforms, the `dlopen()` function is used to load a library into memory
and `dlsym()` lets you get a pointer to something via its symbol name. Something
to remember is that symbols don't contain any type information so the caller
has to (`unsafe`-ly) cast the pointer to the right type.

This is normally done by having some sort of contract with the library being
loaded ahead of time (e.g. a header file declares the `"cos"` function is
`fn(f64) -> f64`).

Example usage from `man dlopen`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
// Defines LIBM_SO (which will be a string such as "libm.so.6")
#include <gnu/lib-names.h>  

// the type signature used by our cosine function
typedef double (*trig_func)(double);

int main() {
    char *error;

    // load the libm library into memory
    void *handle = dlopen(LIBM_SO, RTLD_LAZY);

    // handle loading failures
    if (!handle) {
        fprintf(stderr, "unable to load libm: %s\n", dlerror());
        return EXIT_FAILURE;
    }

    // Clear any existing errors
    dlerror();

    // get a pointer to the "cos" symbol and cast it to the right type
    trig_func cosine = (trig_func) dlsym(handle, "cos");

    // were we able to find the symbol?
    error = dlerror();
    if (error != NULL) {
        fprintf(stderr, "cos not found: %s\n", error);
        return EXIT_FAILURE;
    }

    // use our cosine function
    printf("cos(2.0) = %f\n", (*cosine)(2.0));

    // cleanup and exit
    dlclose(handle);
    return EXIT_SUCCESS;
}
```

The story is almost identical for Windows, except [`LoadLibraryA()`][loadlibrary],
[`GetProcAddress()`][gpa], and [`FreeLibrary()`][freelibrary] are used instead
of `dlopen()`, `dlsym()`, and `dlclose()`, respectively.

The [libloading][libloading] crate provides a high quality Rust interface to
the underlying platform's dynamic loading mechanism.

## Determining the Plugin Interface

The first step is to define a common interface that all plugins should satisfy.
This should be placed in some sort of "core" crate that both plugins and the
main application depend on.

This will usually take the form of a trait.

```rust
// core/src/lib.rs

pub trait Function {
    fn call(&self, args: &[f64]) -> Result<f64, InvocationError>;

    /// Help text that may be used to display information about this function.
    fn help(&self) -> Option<&str> {
        None
    }
}

pub enum InvocationError {
    InvalidArgumentCount { expected: usize, found: usize },
    Other { msg: String },
}
```

Now we've defined the application-level API, we also need a way to declare 
plugins so they're accessible when dynamically loading. This isn't difficult, 
but there are a couple gotchas to keep in mind to prevent undesired behaviour
(UB, crashes, etc.).

Some things to keep in mind:

- Rust doesn't have a stable ABI, meaning different compiler versions can 
  generate incompatible code, and
- Different versions of the `core` crate may have different definitions of the
  `Function` trait
- Each plugin will need to have some sort of `register()` function so it can
  construct a `Function` instance and give the application a `Box<dyn Function>`
  (we need dynamic dispatch because plugin registration happens at runtime
  and static dispatch requires knowing types at compile time)
- To avoid freeing memory allocated by a different allocator, each plugin
  will need to provide an explicit `free_plugin()` function, or the plugin and
  application both need to be using the same allocator

To prevent plugin authors from needing to deal with this themselves, we'll
provide a `export_plugin!()` macro that populates some `PluginDeclaration`
struct with version numbers and a pointer to the `register()` function provided
by a user.

The `PluginDeclaration` struct itself is quite simple:

```rust
// core/src/lib.rs

pub struct PluginDeclaration {
    pub rustc_version: &'static str,
    pub core_version: &'static str,
    pub register: extern "C" fn(&mut dyn PluginRegistrar),
}
```

With the `PluginRegistrar` being a trait that has a single method.

```rust
// core/src/lib.rs

pub trait PluginRegistrar {
    fn register_function(&mut self, name: &str, function: Box<dyn Function>);
}
```

To get the version of `rustc`, we'll add a `build.rs` script to the `core` crate
and pass the version number through as an environment variable.

```rust
// core/build.rs

fn main() {
    let version = rustc_version::version().unwrap();
    println!("cargo:rustc-env=RUSTC_VERSION={}", version);
}
```

We're using the [`rustc_version`][rustc_version] crate to fetch `rustc`'s
version number. Don't forget to add it to `core/Cargo.toml` as a build
dependency:

```console
$ cd core
$ cargo add rustc_version
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding rustc_version v0.2.3 to build-dependencies
```

Now all we need to do is embed the version numbers as static strings.

```rust
// core/src/lib.rs

pub static CORE_VERSION: &str = env!("CARGO_PKG_VERSION");
pub static RUSTC_VERSION: &str = env!("RUSTC_VERSION");
```

Our `export_plugin!()` macro now becomes almost trivial:

```rust
// core/src/lib.rs

#[macro_export]
macro_rules! export_plugin {
    ($register:expr) => {
        #[doc(hidden)]
        #[no_mangle]
        pub static plugin_declaration: $crate::PluginDeclaration = $crate::PluginDeclaration {
            rustc_version: $crate::RUSTC_VERSION,
            core_version: $crate::CORE_VERSION,
            register: $register,
        };
    };
}
```

## Creating a Plugin

Now we have a public plugin interface and a mechanism for registering new 
plugins, lets actually create one.

First we'll need to create a `plugins_random` crate and add it to the workspace.

```console
$ cargo new --lib random --name plugins_random
     Created library `plugins_random` package
$ cat Cargo.toml
[workspace]
members = ["core", "random"]
```

Next, make sure the `plugins_random` crate pulls in `plugins_core`.

```console
$ cd random
$ cargo add ../core
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding plugins_core (unknown version) to dependencies
```

This crate will need to be compiled as a dynamic library (`*.so` in *nix,
`*.dll` on Windows) so it can be loaded at runtime.

```toml
# random/Cargo.toml

[package]
name = "plugins_random"
version = "0.1.0"
authors = ["Michael Bryan <michaelfbryan@gmail.com>"]
edition = "2018"

[lib]
crate-type = ["cdylib"]

[dependencies]
plugins_core = { path = "../core" }
```

Recompiling should show a `libplugins_random.so` file in the `target/` directory.

```console
$ cargo build --all
   Compiling semver-parser v0.7.0
   Compiling semver v0.9.0
   Compiling rustc_version v0.2.3
   Compiling plugins_core v0.1.0 (/home/michael/Documents/plugins/core)
   Compiling plugins_random v0.1.0 (/home/michael/Documents/plugins/random)
    Finished dev [unoptimized + debuginfo] target(s) in 1.32s
$ ls ../target/debug 
build deps examples incremental libplugins_core.d libplugins_core.rlib
libplugins_random.d libplugins_random.so
```

Now things are set up, we can start implementing our `random()` plugin.

Looking at the [Random Integer Generator][rand-int] page, retrieving a set of 
random integers is just a case of sending a GET request to 
`https://www.random.org/integers/`.

For example, to get 10 numbers from 1 to 6 in base 10 and one number per line:

```console
$ curl 'https://www.random.org/integers/?num=10&min=1&max=6&col=1&base=10&format=plain' 
5
2
6
4
5
2
1
4
1
3
```

This turns out to be almost trivial to implement thanks to the
[`reqwest`][reqwest] crate.

First we'll create a helper struct for the arguments to pass to *random.org*.

```rust
// random/src/lib.rs

struct RequestInfo {
    min: i32,
    max: i32,
}

impl RequestInfo {
    pub fn format(&self) -> String {
        format!(
            "https://www.random.org/integers/?num=1&min={}&max={}&col=1&base=10&format=plain",
            self.min, self.max
        )
    }
}
```

Then write a function that calls `reqwest::get()` using the formatted URL and
parses the response body.

```rust
// random/src/lib.rs

fn fetch(request: RequestInfo) -> Result<f64, InvocationError> {
    let url = request.format();
    let response_body = reqwest::get(&url)?.text()?;
    response_body.trim().parse().map_err(Into::into)
}
```

To make `?` work nicely, I've also added a `From` impl which lets us create an
`InvocationError` from anything that is `ToString` (which all 
`std::error::Error` types implement).

```rust
// core/src/lib.rs

impl<S: ToString> From<S> for InvocationError {
    fn from(other: S) -> InvocationError {
        InvocationError::Other {
            msg: other.to_string(),
        }
    }
}
```

Finally, we just need to create a `Random` struct which will implement our 
`Function` interface.

```rust
// random/src/lib.rs

pub struct Random;

impl Function for Random {
    fn call(&self, _args: &[f64]) -> Result<f64, InvocationError> {
        fetch(RequestInfo { min: 0, max: 100 })
    }
}
```

Ideally our `random()` function should have a couple overloads so users can
tweak the random number's properties.

```rust
// get a random number between 0 and 100
fn random() -> f64;
// get a random number between 0 and max
fn random(max: f64) -> f64;
// get a random number between min and max
fn random(min: f64, max: f64) -> f64;
```

The logic for turning the `&[f64]` args into a `RequestInfo` can be neatly 
extracted into its own function.

```rust
// random/src/lib.rs

fn parse_args(args: &[f64]) -> Result<RequestInfo, InvocationError> {
    match args.len() {
        0 => Ok(RequestInfo { min: 0, max: 100 }),
        1 => Ok(RequestInfo {
            min: 0,
            max: args[0].round() as i32,
        }),
        2 => Ok(RequestInfo {
            min: args[0].round() as i32,
            max: args[1].round() as i32,
        }),
        _ => Err("0, 1, or 2 arguments are required".into()),
    }
}
```

And then we just need to update the `Function` impl accordingly.

```rust
// random/src/lib.rs

impl Function for Random {
    fn call(&self, args: &[f64]) -> Result<f64, InvocationError> {
        parse_args(args).and_then(fetch)
    }
}
```

Now our `random()` function is fully implemented, we just need to make a 
`register()` function and call `plugins_core::export_plugin!()`.

```rust
// random/src/lib.rs

plugins_core::export_plugin!(register);

extern "C" fn register(registrar: &mut dyn PluginRegistrar) {
    registrar.register_function("random", Box::new(Random));
}
```

## See Also

- [Building a Simple C++ Cross-platform Plugin System](https://sourcey.com/articles/building-a-simple-cpp-cross-platform-plugin-system)
- [The (unofficial) Rust FFI Guide: Dynamic Loading & Plugins](https://michael-f-bryan.github.io/rust-ffi-guide/dynamic_loading.html)
- [Plugins in C](https://eli.thegreenplace.net/2012/08/24/plugins-in-c)

[r-o]: https://random.org/
[rand]: https://crates.io/crates/rand
[wiki]: https://en.wikipedia.org/wiki/Dynamic_loading
[loadlibrary]: https://docs.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibrarya
[gpa]: https://docs.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getprocaddress
[freelibrary]: https://docs.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-freelibrary
[libloading]: https://docs.rs/libloading/
[rustc_version]: https://docs.rs/rustc_version/
[rand-int]: https://www.random.org/integers/
[reqwest]: https://crates.io/crates/reqwest