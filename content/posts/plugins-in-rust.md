---
title: "Plugins in Rust"
date: "2019-09-30T22:04:58+08:00"
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

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's 
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/plugins_in_rust
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

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
    pub register: unsafe extern "C" fn(&mut dyn PluginRegistrar),
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

## Loading Plugins

Now we've defined a plugin we need a way to load it into memory and use it as
part of our application.

The first step is to create a new crate and add some dependencies.

```console
$ cargo new --lib --name plugins_app app
$ cat Cargo.toml
[workspace]
members = ["core", "random", "app"]
$ cd app
$ cargo add libloading ../core
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding libloading v0.5.2 to dependencies
      Adding plugins_core (unknown version) to dependencies
```

When a library is loaded into memory, we need to make sure that it outlives 
anything created from it. For example, a trait object's vtable (and all the 
functions it points to) is embedded in the library's code. If we tried to invoke
a plugin object's methods after its parent library was unloaded from memory,
we'd try to execute garbage and crash the entire application.

This means we need a way to make sure plugins can't outlive the library they
were loaded from.

We'll do this using the [*Proxy Pattern*][proxy].

```rust
// app/src/main.rs

/// A proxy object which wraps a [`Function`] and makes sure it can't outlive
/// the library it came from.
pub struct FunctionProxy {
    function: Box<dyn Function>,
    _lib: Rc<Library>,
}

impl Function for FunctionProxy {
    fn call(&self, args: &[f64]) -> Result<f64, InvocationError> {
        self.function.call(args)
    }

    fn help(&self) -> Option<&str> {
        self.function.help()
    }
}
```

We also need something which can contain all loaded plugins.

```rust
// app/src/main.rs

pub struct ExternalFunctions {
    functions: HashMap<String, FunctionProxy>,
    libraries: Vec<Rc<Library>>,
}

impl ExternalFunctions {
    pub fn new() -> ExternalFunctions {
        ExternalFunctions::default()
    }

    pub fn load<P: AsRef<OsStr>>(&mut self, library_path: P) -> io::Result<()> {
        unimplemented!()
    }
}
```

The `ExternalFunctions::load()` method is the real meat and potatoes of our 
plugin system. It's where we:

1. Load the library into memory
2. Get a reference to the static `PluginDeclaration`
3. Check the `rustc` and `plugins_core` versions match
4. Create a `PluginRegistrar` which will create `FunctionProxy`s associated with
   the library
5. Pass the `PluginRegistrar` to the plugin's `register()` function
6. Add any loaded plugins to the internal functions map

The `PluginRegistrar` type itself is almost trivial:

```rust
// app/src/main.rs

struct PluginRegistrar {
    functions: HashMap<String, FunctionProxy>,
    lib: Rc<Library>,
}

impl PluginRegistrar {
    fn new(lib: Rc<Library>) -> PluginRegistrar {
        PluginRegistrar {
            lib,
            functions: HashMap::default(),
        }
    }
}

impl plugins_core::PluginRegistrar for PluginRegistrar {
    fn register_function(&mut self, name: &str, function: Box<dyn Function>) {
        let proxy = FunctionProxy {
            function,
            _lib: Rc::clone(&self.lib),
        };
        self.functions.insert(name.to_string(), proxy);
    }
}
```

And now our `PluginRegistrar` helper is implemented, we have everything required
to complete `ExternalFunctions::load()`.

```rust
// app/src/main.rs

impl ExternalFunctions {
    ...

    /// Load a plugin library and add all contained functions to the internal
    /// function table.
    ///
    /// # Safety
    ///
    /// A plugin library **must** be implemented using the
    /// [`plugins_core::plugin_declaration!()`] macro. Trying manually implement
    /// a plugin without going through that macro will result in undefined
    /// behaviour.
    pub unsafe fn load<P: AsRef<OsStr>>(
        &mut self,
        library_path: P,
    ) -> io::Result<()> {
        // load the library into memory
        let library = Rc::new(Library::new(library_path)?);

        // get a pointer to the plugin_declaration symbol.
        let decl = library
            .get::<*mut PluginDeclaration>(b"plugin_declaration\0")?
            .read();

        // version checks to prevent accidental ABI incompatibilities
        if decl.rustc_version != plugins_core::RUSTC_VERSION
            || decl.core_version != plugins_core::CORE_VERSION
        {
            return Err(io::Error::new(
                io::ErrorKind::Other,
                "Version mismatch",
            ));
        }

        let mut registrar = PluginRegistrar::new(Rc::clone(&library));

        (decl.register)(&mut registrar);

        // add all loaded plugins to the functions map
        self.functions.extend(registrar.functions);
        // and make sure ExternalFunctions keeps a reference to the library
        self.libraries.push(library);

        Ok(())
    }
}
```

{{% notice note %}}
Note the *Safety* section in the function's doc-comments. The process of
loading a plugin is inherently `unsafe` (the compiler can't guarantee
whatever is behind the `plugin_declaration` symbol is a `PluginDeclaration`)
and this section documents the contract that must be upheld.
{{% /notice %}}

## Using the Plugin

At this point we've actually completed the plugin system. The only thing left is
to demonstrate it works and start using the thing.

For our purposes, it should be good enough to create a command-line app that
loads a library then invokes a function by name, passing in any specified
arguments.

```
Usage: app <plugin-path> <function> <args>...
```

First we'll create a quick `Args` struct to parse our command-line arguments 
into.

```rust
// app/src/main.rs

struct Args {
    plugin_library: PathBuf,
    function: String,
    arguments: Vec<f64>,
}
```

Then hack together a quick'n'dirty command-line parser. Real applications should
prefer to use something like `clap` or `structopt` instead.

```rust
// app/src/main.rs

impl Args {
    fn parse(mut args: impl Iterator<Item = String>) -> Option<Args> {
        let plugin_library = PathBuf::from(args.next()?);
        let function = args.next()?;
        let mut arguments = Vec::new();

        for arg in args {
            arguments.push(arg.parse().ok()?);
        }

        Some(Args {
            plugin_library,
            function,
            arguments,
        })
    }
}
```

We'll also need a way to `call()` a function by name.

```rust
// app/src/main.rs

impl ExternalFunctions {
    ...

    pub fn call(&self, function: &str, arguments: &[f64]) -> Result<f64, InvocationError> {
        self.functions
            .get(function)
            .ok_or_else(|| format!("\"{}\" not found", function))?
            .call(arguments)
    }
}
```

By default a `cdylib` will use the system allocator, but executables aren't guaranteed
to use

According to the docs from `std::alloc`,

> Currently the default global allocator is unspecified. Libraries, however,
> like `cdylib`s and `staticlib`s are guaranteed to use the `System` by default.

To make sure there's no chance of allocator mismatch (i.e. a plugin allocates
a `String` using the `System` allocator and we try to free it using Jemalloc) we
need to explicitly declare that the app uses the `System` allocator.

```rust
// app/src/main.rs

use std::alloc::System;

#[global_allocator]
static ALLOCATOR: System = System;
```

And finally, we can write `main()`'s body.

```rust
// app/src/main.rs

fn main() {
    // parse arguments
    let args = env::args().skip(1);
    let args = Args::parse(args)
        .expect("Usage: app <plugin-path> <function> <args>...");

    // create our functions table and load the plugin
    let mut functions = ExternalFunctions::new();

    unsafe {
        functions
            .load(&args.plugin_library)
            .expect("Function loading failed");
    }

    // then call the function
    let result = functions
        .call(&args.function, &args.arguments)
        .expect("Invocation failed");

    // print out the result
    println!(
        "{}({}) = {}",
        args.function,
        args.arguments
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join(", "),
        result
    );
}
```

If everything goes to plan, the `app` tool should *Just Work*.

```console
$ cargo run -- ../target/release/libplugins_random.so random
random() = 40
$ cargo run -- ../target/release/libplugins_random.so random 42
random(42) = 15
$ cargo run -- ../target/release/libplugins_random.so random 42 64
random(42, 64) = 54

# Note: the function doesn't support 3 arguments
$ cargo run -- ../target/release/libplugins_random.so random 1 2 3    
thread 'main' panicked at 'Invocation failed: Other { msg: "0, 1, or 2 arguments are required" }', src/libcore/result.rs:1165:5
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace.
```

If a plugin author forgot to invoke the `export_plugin!()` macro, they may see
an error like this:

```console
$ cargo run -- ../target/debug/libplugins_random.so random  
    Finished dev [unoptimized + debuginfo] target(s) in 0.02s
     Running `/home/michael/Documents/plugins/target/debug/plugins_app ../target/debug/libplugins_random.so random`
thread 'main' panicked at 'Function loading failed: Custom { kind: Other, error: "../target/debug/libplugins_random.so: undefined symbol: plugin_declaration" }', src/libcore/result.rs:1165:5
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace.
```

This is saying we couldn't find the `plugin_declaration` symbol. You can
use the `nm` tool to help with troubleshooting, it shows all symbols exported by
a library.

```console
nm ../target/release/libplugins_random.so  | grep plugin            
00000000004967b0 D plugin_declaration
0000000000056c60 t _ZN12plugins_core8Function4help17hc92b9e8d4917f964E
0000000000057f60 t _ZN14plugins_random8register17hd43ebfdd726021a4E
0000000000057f80 t _ZN65_$LT$plugins_random..Random$u20$as$u20$plugins_core..Function$GT$4call17h7434ef9b1f1ca59eE
00000000000590f0 t _ZN78_$LT$plugins_core..InvocationError$u20$as$u20$core..convert..From$LT$S$GT$$GT$4from17h3a759bcd267b48a1E
```

And there you have it, a relatively simple, yet safe and robust, plugin
system which you can use in your own projects.

## See Also

- [Building a Simple C++ Cross-platform Plugin System](https://sourcey.com/articles/building-a-simple-cpp-cross-platform-plugin-system)
- [The (unofficial) Rust FFI Guide: Dynamic Loading & Plugins](https://michael-f-bryan.github.io/rust-ffi-guide/dynamic_loading.html)
- [Plugins in C](https://eli.thegreenplace.net/2012/08/24/plugins-in-c)
- The code written alongside this article [on GitHub](https://github.com/Michael-F-Bryan/plugins_in_rust)

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
[proxy]: https://refactoring.guru/design-patterns/proxy