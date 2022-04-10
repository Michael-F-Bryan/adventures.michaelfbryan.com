---
title: "Deploying WebAssembly in the Real World"
date: "2022-03-13T19:34:21+08:00"
draft: true
tags:
- Rust
- WebAssembly
- Architecture
---

While browsing the Rust User Forums the other day, I came across
[Fornjot][fornjot], a code-first CAD program written by a friend, and one of
their issues jumped out at me - [*Switch model system to WASM
(hannobraun/Fornjot#71)*][Fornjot-71].

The way Fornjot currently works is by implementing each primitive component
(sketches, cuboids, cylinders, etc.) in its shared library which is loaded and
executed at runtime. That way Fornjot can provide a stable set of core
abstractions for manipulating shapes, then users can modify their models and
reload them at runtime (often called ["Hot Module Replacement"][hmr] in the
JavaScript world).

You could easily imagine an ecosystem evolving around Fornjot where users
develop their own models and share them with others.

The current system of natively compiled libraries has a couple flaws,
though:

- You need to recompile the model for every platform it may be used on
- Users will be literally downloading and executing untrusted code
- The current interface is kinda unsound because it passes Rust types across
  the FFI boundary. This is unsound because there is no guarantee the code for
  manipulating a `HashMap` in Fornjot will match up with the code for
  manipulating `HashMap` inside the model (I've been bitten by this before - see
  [`rust-lang/rust#67179`][rust-67179])

Fortunately, I've spent the last year using a technology that aims to solve
exactly these problems - WebAssembly!

{{% notice error %}}
TODO:
- Come up with a strong "thesis statement" for the article
- Make this flow nicely
- Relate it to an architecture I want to use at HOTG
{{% /notice %}}

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/modern-webassembly
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Defining our Interfaces

If we want to solve Fornjot's model problem our first task is to define the
interfaces used by our various components to communicate, and the way we will
do this is via [WIT files][wit].

If you are familiar with gRPC, a `*.wit` file fills the same role as a
`*.proto` file. You use a domain specific language to declare the interface
between both sides, then use a code generator to generate strongly-typed glue
code.

We'll start by defining the host (Fornjot) interface because it's easiest.

```
// fornjot-v1.wit

/// Log a message at the specified verbosity level.
log: function(level: log-level, msg: string)

enum log-level {
  verbose,
  debug,
  info,
  warning,
  error,
}
```

Although the syntax is a bit unfamiliar, you should be able to get the gist.
All our host provides is a `log()` function for printing messages.

Our host also needs to provide some contextual information to let users modify
the generated shape.

To do this, we'll define a [resource][resource] called `context` which lets
us look up an argument by its name. Obviously, there is a possibility that the
argument we want isn't defined, so the return value is wrapped in an `option`.

```
// fornjot-v1.wit

resource context {
    get-argument: function(name: string) -> option<string>
}
```

A `resource` is roughly analogous to an interface in Java or a trait object in
Rust.

{{% notice note %}}
For those that are familiar with ongoing WebAssembly proposals, you
might recognise that a `resource` sounds awfully similar to [*WebAssembly
Interface Types*][wit-proposal].

This isn't a coincidence!

The `wit-bindgen` tool currently implements them by manually managing the memory
of these objects and referring to them via indices, but you can imagine how one
day we'll be able to update `wit-bindgen` and magically gain access to interface
types with no extra code changes.

[wit-proposal]: https://github.com/WebAssembly/interface-types/blob/main/proposals/interface-types/Explainer.md
{{% /notice %}}

Next up is the WIT file defining the functionality our guest will expose.

For our purposes, each model should provide a function for finding out more
about it (name, description, version number, etc.) and a function for generating
the shape.

This is where the `on-load()` function and our `metadata` type come in.

```
// model-v1.wit

record metadata {
    name: string,
    description: string,
    version: string,
}

/// A callback that is fired when a model is first loaded, allowing Fornjot to
/// find out more about it.
on-load: function() -> metadata
```

{{% notice info %}}
Depending on the target language, a [record][record] is normally converted into
a struct or class by the code generator. It's just a "plain old data" type with
no attached behaviour.

[record]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md#item-record-bag-of-named-fields
{{% /notice %}}

Next up we have the function that will be called by the host when it wants to
generate a model, `generate()`.

```
// model-v1.wit

generate: function(ctx: context) -> expected<shape, error>

record error {
    message: string,
}

record shape {
    vertices: list<vertex>,
    faces: list<tuple<u32, u32, u32>>,
}

record vertex {
    x: f32,
    y: f32,
    z: f32,
}
```

The `expected<shape, error>` should look familiar to Rustaceans. Functions in a
WIT file signal errors by returning something which is either the OK value
(`shape`) or the unsuccessful value (`error`). In Rust, we might call this a
`Result`.

Now, our `generate()` function accepts a `context` argument but `model-v1.wit`
doesn't actually contain a definition for it.

What we need to do is [import][use] `context` from `fornjot-v1.wit` at the top
of our file.

```
// model-v1.wit

use { run-context } from fornjot-v1
```

## Implementing The Guest

Now we have an interface to code against, let's implement a simple model.

First, we need to create a new Rust crate and the `wit-bindgen` crate for
implementing the guest side of the interface.

```console
$ cargo new --lib guest
$ cd guest
$ cargo add --git https://github.com/bytecodealliance/wit-bindgen wit-bindgen-rust
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding wit-bindgen-rust (unknown version) to dependencies
```

{{% notice note %}}
We need to add `wit-bindgen` as a git dependency because it hasn't been
published on crates.io yet. Hopefully it'll be released one day, but today is
not that day.
{{% /notice %}}

Next we need to generate our glue code. Fortunately, the `wit-bindgen-rust`
crate provides two procedural macros which we can point at our `*.wit` files to
unlock the magic.

```rs
// guest/src/lib.rs

wit_bindgen_rust::import!("../fornjot-v1.wit");
wit_bindgen_rust::export!("../model-v1.wit");
```

{{% notice tip %}}
The import/export terminology really confused me at first because, as we'll see
later, what you import and what you export will change depending on whether your
code is running as the guest or the host.

The way I think of it is that `wit_bindgen_rust::import!()` generates glue code
for *import*ing functions from somewhere outside this crate. The
`wit_bindgen::export!()` macro will generate the appropriate `extern "C"`
functions for letting outside code use our crate's functionality.

I'm not sure whether that clears things up or just makes things more confusing.
Oh well, I tried 😅
{{% /notice %}}

Now, if you tried to compile just this code you would see some funny compile
errors.

```console
$ cargo check
   Checking guest v0.1.0 (/home/michael/Documents/modern-webassembly/guest)
error[E0412]: cannot find type `Context` in module `super`
 --> guest/src/lib.rs:2:1
  |
2 | wit_bindgen_rust::export!("../model-v1.wit");
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ not found in `super`
  |
  = note: consider importing one of these items:
          crate::fornjot_v1::Context
          std::task::Context
          core::task::Context
  = note: this error originates in the macro `wit_bindgen_rust::export` (in Nightly builds, run with -Z macro-backtrace for more info)

error[E0412]: cannot find type `ModelV1` in module `super`
 --> guest/src/lib.rs:2:1
  |
2 | wit_bindgen_rust::export!("../model-v1.wit");
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ not found in `super`
  |
  = note: consider importing this trait:
          crate::model_v1::ModelV1
  = note: this error originates in the macro `wit_bindgen_rust::export` (in Nightly builds, run with -Z macro-backtrace for more info)
```

To decipher these error messages, let's use `cargo expand` to see the exact
code `wit_bindgen_rust::export!()` generated.

```rs

mod model_v1 {
  ...

  #[export_name = "generate"]
  unsafe extern "C" fn __wit_bindgen_generate(arg0: i32) -> i32 {
    let result0 =
      <super::ModelV1 as ModelV1>::generate(wit_bindgen_rust::Handle::from_raw(arg0));

    ...
  }

  pub trait ModelV1 {
    /// An optional callback invoked when a handle is finalized
    /// and destroyed.
    fn drop_context(val: super::Context) {
        drop(val);
    }
    /// A callback that is fired when a model is first loaded, allowing Fornjot to
    /// find out more about it.
    fn on_load() -> Metadata;
    fn generate(ctx: wit_bindgen_rust::Handle<super::Context>) -> Result<Shape, Error>;
  }
}
```

Something that may jump out at you is the call to
`<super::ModelV1 as ModelV1>::generate()` and the `Handle<super::Context>`
argument.

This means our `model_v1` module expects the parent module to contain a
`ModelV1` struct (which implements the `ModelV1` trait) and some `Context`
object (remember, we imported `context` from `fornjot-v1.wit` instead of
defining it in `model-v1.wit`).

The message about a missing `Context` object is easy enough. In the top-level
`lib.rs` we just need to import the generated `fornjot_v1::Context` type.

```rs
// guest/src/lib.rs

use crate::fornjot_v1::Context;
```

Now we've got to define the `ModelV1` type and make sure it implements the
`model_v1::ModelV1` trait.

```rs
// guest/src/lib.rs

use crate::{fornjot_v1::Context, model_v1::{Metadata, Error}};

struct ModelV1;

impl model_v1::ModelV1 for ModelV1 {
    fn on_load() -> Metadata { todo!() }

    fn generate(ctx: Handle<Context>) -> Result<Shape, Error> {
      todo!()
    }
}
```

We can implement the `on_load()` method without too much difficulty by
leveraging [the environment variables][env-variables] `cargo` sets when
compiling each crate. Now our model's metadata should be automatically kept in
sync with the contents of `Cargo.toml`.

```rs
// guest/src/lib.rs

impl model_v1::ModelV1 for ModelV1 {
      fn on_load() -> Metadata {
        Metadata {
            name: env!("CARGO_MANIFEST_DIR").into(),
            description: env!("CARGO_PKG_DESCRIPTION").into(),
            version: env!("CARGO_PKG_VERSION").into(),
        }
    }

    ...
}
```

The `generate()` method is a little trickier so let's take it one step at a
time.

We're going to generate a square prism, using the `width` argument for our
square's edge lengths and the `depth` argument to figure out how far back the
prism goes.

That means we'll first need to get the `width` and `depth` arguments and parse
them as `f32`s.

```rs
// guest/src/lib.rs

use wit_bindgen_rust::Handle;

impl model_v1::ModelV1 for ModelV1 {
    ...

    fn generate(ctx: Handle<Context>) -> Result<Shape, Error> {
        let width: f32 = ctx
            .get_argument("width")
            .ok_or("The \"width\" argument is missing")?
            .parse()
            .map_err(|e| format!("Unable to parse the width: {}", e))?;

        let depth: f32 = ctx
            .get_argument("depth")
            .ok_or("The \"depth\" argument is missing")?
            .parse()
            .map_err(|e| format!("Unable to parse the depth: {}", e))?;

        ...
    }
}
```

Then we can construct the vertices and faces for our resulting shape. You can
probably figure these out using pen and paper, but I'm lazy and just copied it
from the internet.

```rs
// guest/src/lib.rs

impl model_v1::ModelV1 for ModelV1 {
    ...

    fn generate(ctx: Handle<Context>) -> Result<Shape, Error> {
        ...

        let vertices = vec![
            Vertex::new(0.0, 0.0, 0.0),
            Vertex::new(width, 0.0, 0.0),
            Vertex::new(width, width, 0.0),
            Vertex::new(0.0, width, 0.0),
            Vertex::new(0.0, width, depth),
            Vertex::new(width, width, depth),
            Vertex::new(0.0, 0.0, depth),
        ];

        let faces = vec![
            (0, 2, 1), // face front
            (0, 3, 2),
            (2, 3, 4), // face top
            (2, 4, 5),
            (1, 2, 5), // face right
            (1, 5, 6),
            (0, 7, 4), // face left
            (0, 4, 3),
            (5, 4, 7), // face back
            (5, 7, 6),
            (0, 6, 7), // face bottom
            (0, 1, 6),
        ];

        Ok(Shape { faces, vertices })
    }
}
```

A nice thing about the way methods are implemented in Rust is that any module
can attach methods to any type in that crate.

This means we can reduce the noise when defining `vertices` by giving `Vertex` a
basic constructor.

```rs
// guest/src/lib.rs

impl Vertex {
    fn new(x: f32, y: f32, z: f32) -> Self { Vertex { x, y, z } }
}
```

We can also make `?` work by defining a conversion that creates a
`model_v1::Error` from anything that can be turned into a string.

```rs
// guest/src/lib.rs

impl<S: Into<String>> From<S> for Error {
    fn from(s: S) -> Self { Error { message: s.into() } }
}
```

To compile our guest to WebAssembly, we need to make sure our `crate-type`
field in `Cargo.toml` includes `cdylib`.

```toml
# guest/Cargo.toml
[package]
name = "guest"
version = "0.1.0"
edition = "2021"
description = "A module for generating a square prism."

[lib]
crate-type = ["rlib", "cdylib"]

...
```

Now we can compile to WebAssembly.

```console
$ cargo build --target wasm32-unknown-unknown --release
   ...
   Compiling wit-bindgen-rust v0.1.0 (https://github.com/bytecodealliance/wit-bindgen#c9b113be)
   Compiling guest v0.1.0 (/home/michael/Documents/modern-webassembly/guest)
    Finished release [optimized] target(s) in 3.71s
```

{{% notice tip %}}
Don't forget to install the `wasm32-unknown-unknown` target if you haven't
already.

```console
$ rustup target install wasm32-unknown-unknown
```
{{% /notice %}}

As a sanity check, we can use `wasm-objdump` from [the WebAssembly Binary
Toolkit][wabt] to inspect our compiled `guest.wasm` binary.

```
$ wasm-objdump --details ../target/wasm32-unknown-unknown/release/guest.wasm
guest.wasm:     file format wasm 0x1

Section Details:

Type[21]:
  - type[0] (i32, i32) -> nil
  - type[1] (i32, i32, i32) -> i32
  - type[2] (i32, i32) -> i32
  - type[3] (i32) -> nil
  - ...
Import[3]:
  - func[0] sig=3 <_ZN68_$LT$guest..fornjot_v1..Context$u20$as$u20$core..ops..drop..Drop$GT$4drop5close17h2350df99eb7559c2E> <- canonical_abi.resource_drop_context
  - func[1] sig=4 <_ZN5guest8model_v186_$LT$impl$u20$wit_bindgen_rust..LocalHandle$u20$for$u20$guest..fornjot_v1..Context$GT$3get3get17h511cbcb0cddd0a79E> <- canonical_abi.resource_get_context
  - func[2] sig=5 <_ZN5guest10fornjot_v17Context12get_argument10wit_import17h0df2b308226a6ba0E> <- fornjot-v1.context::get-argument
Function[206]:
  - ...
  - func[5] sig=6 <on-load>
  - func[6] sig=4 <generate>
  - ...
Table[1]:
  - ...
Memory[1]:
  - ...
Global[3]:
  - global[0] i32 mutable=1 <__stack_pointer> - init i32=1048576
  - global[1] i32 mutable=0 <__data_end> - init i32=1066176
  - global[2] i32 mutable=0 <__heap_base> - init i32=1066176
Export[8]:
  - memory[0] -> "memory"
  - func[5] <on-load> -> "on-load"
  - func[6] <generate> -> "generate"
  - global[1] -> "__data_end"
  - global[2] -> "__heap_base"
  - ...
```

There are plenty of other goodies in `wasm-objdump`'s output which might
interest those who are familiar with how WebAssembly is implemented, and I'd
love to nerd out on it with you some time, but for now it's enough to see our
`on-load` and `generate` functions are being exported.

## Implementing The Host

Okay, so now we've got some WebAssembly, let's build something to load it and
call functions.

I'm thinking we should create a CLI tool that looks something like this:

```console
$ ./host some-model x=5 y=7
```

The idea is that our `host` binary would try to load all WebAssembly files in
a pre-defined directory looking for the model with the name, `some-model` (as
reported via our `Metadata`). Once we find the model we can call its
`generate()` function, passing in the arguments `x: "5"` and `y: "7"`.

Like all Rust CLI programs, we'll start off by creating a new crate and adding
some dependencies.

```console
$ cargo new --bin host && cd host
$ cargo add anyhow structopt tracing tracing-subscriber wasmer
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding anyhow v1.0.56 to dependencies
      Adding structopt v0.3.26 to dependencies
      Adding tracing v0.1.32 to dependencies
      Adding tracing-subscriber v0.3.9 to dependencies
      Adding wasmer v2.2.0 to dependencies
```

We also need to add the `wit-bindgen-wasmer` package. The `wit-bindgen` family
of packages aren't published to crates.io, so we'll pull the crate directly
from GitHub.

```console
$ cargo add --git https://github.com/wasmerio/wit-bindgen wit-bindgen-wasmer
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding wit-bindgen-wasmer to dependencies.
```

### Host Glue Code

Similar to when we were writing the guest, we have `import!()` and `export!()`
macros that generate glue code for our WIT files.

```rs
// main.rs

wit_bindgen_wasmer::import!("model-v1.wit");
wit_bindgen_wasmer::export!("fornjot-v1.wit");

fn main() { todo!(); }
```

{{% notice note %}}
Keep an eye on the `import!()` and `export!()` macros. We are now writing the
host, which means we'll be importing `model-v1.wit` functions from our guest and
exposing ("exporting") `fornjot-v1.wit` functions to it.
{{% /notice %}}

By inspecting our host's API docs (`cargo doc --open`) we can see that the
`export!()` macro generated a bunch of code.

```rs
// generated by wit_bindgen_wasmer::export!()

mod fornjot_v1 {
  pub fn add_to_imports<T>(store: &Store, imports: &mut ImportObject, data: T)
  where
    T: FornjotV1,
  {
    ...
  }

  pub trait FornjotV1: Sized + WasmerEnv + 'static {
    type Context: Debug;
    fn log(&mut self, level: LogLevel, msg: &str);

    fn context_current(&mut self) -> Self::Context;

    fn context_get_argument(
        &mut self,
        self_: &Self::Context,
        name: &str
    ) -> Option<String>;

    fn drop_context(&mut self, _state: Self::Context) { }
  }

  pub enum LogLevel {
    Verbose,
    Debug,
    Info,
    Warning,
    Error,
  }
}
```

The key things to notice are that

1. A `FornjotV1` trait was introduced with methods for every function that was
   defined in our `fornjot-v1.wit` file
2. An `add_to_imports()` function was added which registers our `FornjotV1`
   implementation's methods with the `wasmer::ImportObject` so they can be
   accessed by the guest

The `import!()` macro also expanded to some code, but because we are accessing
existing functionality instead of injecting our own we're given a `ModelV1`
wrapper struct.

```rs
// generated by wit_bindgen_wasmer::import!()

mod model_v1 {
  struct ModelV1 { ... }

  impl ModelV1 {
    /// Instantiates the provided module using the specified parameters,
    /// wrapping up the result in a structure that translates between wasm and
    /// the host.
    ///
    /// The imports provided will have intrinsics added to it automatically, so
    /// it’s not necessary to call add_to_imports beforehand. This function will
    /// instantiate the module otherwise using imports, and both an instance of
    /// this structure and the underlying wasmer::Instance will be returned.
    pub fn instantiate(
      store: &Store,
      module: &Module,
      imports: &mut ImportObject
    ) -> Result<(Self, Instance)> {
      ...
    }

    /// A callback that is fired when a model is first loaded, allowing Fornjot
    /// to find out more about it.
    pub fn on_load(&self) -> Result<Metadata, RuntimeError> { ... }

    fn generate(&self) -> Result<Result<Shape, Error>, RuntimeError> { ... }
  }
}
```

(we also got structs for `Shape`, `Vertex`, and `Metadata`, but they are
implemented exactly as you'd expect and quite uninteresting)

### Loading a Model's Metadata

Armed with this new knowledge and the ["Hello World" example][wasmer-usage] from
the `wasmer` crate's API docs, we can start to load our model.

We'll start by creating a struct that implements the `fornjot_v1::FornjotV1`
trait, adding it to our imports object, and using that to load the WebAssembly
module.

Here's the quickest, hackiest implementation I could come up with:

```rs
fn main() {
  // Load the WebAssembly module
  let wasm = std::fs::read("model.wasm").unwrap();
  let module = Module::new(&store, &wasm).unwrap();

  // Set up the host functions
  let store = Store::default();
  let mut imports = ImportObject::default();
  let host_functions = HostFunctions::default();
  fornjot_v1::add_to_imports(&store, &mut imports, host_functions);

  // instantiate the WebAssembly module
  let (model, _instance) =
      model_v1::ModelV1::instantiate(&store, &module, &mut imports).unwrap();

  // and use it
  let metadata = model.on_load().unwrap();
  println!("{:#?}", metadata);
}

#[derive(Clone, Default, WasmerEnv)]
struct HostFunctions;

impl fornjot_v1::FornjotV1 for HostFunctions {
  type Context = ();
  fn log(&mut self, _: LogLevel, _: &str) { todo!() }
  fn context_current(&mut self) -> <Self as FornjotV1>::Context { todo!() }
  fn context_get_argument(
      &mut self,
      _ctx: &<Self as FornjotV1>::Context,
      _argument: &str,
  ) -> Option<String> { todo!() }
}
```

There are many things that are terrible about this code. It'll blow up the
moment the user strays from the beaten path, the `model.wasm` file is
hard-coded, all host functions are unimplemented, etc, etc

But... It works!

```console
$ cargo run
Metadata {
    name: "cuboid-model",
    description: "A module for generating a cuboid.",
    version: "0.1.0",
}
```

### Running the Generator Function

The entire reason behind what we're doing is to allow loading new models
dynamically at runtime and using them to generate shapes.

That means we'll need to call the `model` variable's `generate()` function.
While we're at it, we'll need to implement the `fornjot_v1::FornjotV1` trait
properly to avoid panicking on a `todo!()`.

The idea behind the `FornjotV1` trait's `Context` type is to give each model
access to state that is specific to that `generate()` call. In this case, the
only state we are sharing with the model is a dictionary of arguments, so we'll
use a `HashMap<String, String>` wrapped in a `Arc<Mutex<...>>`. We use an `Arc`
so we have access to our arguments both inside the WebAssembly module and from
the host, and the `Mutex` lets us update the arguments after the module is
instantiated.

```rs
use std::{collections::HashMap, sync::{Arc, Mutex}};

type Arguments = Arc<Mutex<HashMap<String, String>>>;

impl fornjot_v1::FornjotV1 for HostFunctions {
  type Context = Arguments;

  ...

  fn context_get_argument(
    &mut self,
    ctx: &<Self as FornjotV1>::Context,
    argument: &str,
  ) -> Option<String> {
    ctx.lock().expect("The lock was poisoned").get(argument).cloned()
  }
}
```

We can pass the `Arguments` in by storing them in the `HostFunctions` struct.

```rs
struct HostFunctions {
  arguments: Arguments,
}

impl fornjot_v1::FornjotV1 for HostFunctions {
  ...

  fn context_current(&mut self) -> Self::Context {
    Arc::clone(&self.arguments)
  }

  ...
}
```

{{% notice note %}}
This effectively means there is only one set of arguments per instance of the
WebAssembly module, but it's sufficient for demonstration purposes.

Normally, you would associate each instance of a model with an ID (e.g.
`cuboid-1234`) and that ID would be passed to `generate()` so the model knows
which `Context` to ask for.
{{% /notice %}}

We also have a `log()` method to implement, but it's easy enough to just pass
that through to `tracing`.

```rs
impl fornjot_v1::FornjotV1 for HostFunctions {
  fn log(&mut self, level: LogLevel, msg: &str) {
    match level {
      LogLevel::Error => tracing::error!(msg),
      LogLevel::Warning => tracing::warn!(msg),
      LogLevel::Info => tracing::info!(msg),
      LogLevel::Debug => tracing::debug!(msg),
      LogLevel::Verbose => tracing::trace!(msg),
    }
  }
}
```

The only other change we need to make is updating `main()` to create a set of
`Arguments`, populate them, and pass them to the `HostFunctions` struct.

```rs
fn main() {
  let wasm = std::fs::read("model.wasm").unwrap();

  let mut arguments = HashMap::new();
  arguments.insert("width".to_string(), "3.14".to_string());
  arguments.insert("depth".to_string(), "10".to_string());
  let arguments = Arc::new(Mutex::new(arguments));

  ...
  let host_functions = HostFunctions { arguments };
  ...

  let shape = model.generate().unwrap();
  println!("{:?}", shape);
}
```

This generates roughly what we expect:

```console
$ cargo run
Ok(Shape {
  vertices: [
    Vertex { x: 0.0, y: 0.0, z: 0.0 },
    Vertex { x: 3.14, y: 0.0, z: 0.0 },
    Vertex { x: 3.14, y: 3.14, z: 0.0 },
    Vertex { x: 0.0, y: 3.14, z: 0.0 },
    Vertex { x: 0.0, y: 3.14, z: 10.0 },
    Vertex { x: 3.14, y: 3.14, z: 10.0 },
    Vertex { x: 0.0, y: 0.0, z: 10.0 }
  ],
  faces: [
    (0, 2, 1), (0, 3, 2), (2, 3, 4), (2, 4, 5), (1, 2, 5), (1, 5, 6),
    (0, 7, 4), (0, 4, 3), (5, 4, 7), (5, 7, 6), (0, 6, 7), (0, 1, 6)
  ]
})
```

### Making the Host less Hacky



## Deploying using WAPM

So we've implemented our guest and host, now what?

Normally if you are creating a plugin system you'll want to give your users a
way to share plugins... preferably without needing to download binaries from
some shady site.

For that, we can reach for WAPM, the [WebAssembly Package Manager][wapm].

- Publish the guest to WAPM
  - Hint that it'd be really nice if Wasmer provided a `cargo wapm` sub-command
    for publishing a crate to WAPM 😉
- Use `wapm install` to add our `guest.wasm` file to `wapm_packages/`

## Conclusions

It's been 3 years since [the WebAssembly spec reached 1.0][wasm-1.0] and the
community has grown in leaps and bounds. Back when [I first
started][first-article] playing with WebAssembly there were only a handful of
immature implementations, and you needed to write a non-trivial amount of
`unsafe` code in order to get anything working.

Nowadays, we've got nice things like [`wit-bindgen`][wit-bindgen] for defining
interfaces and generating all that `unsafe` glue code, a multitude of high
quality WebAssembly runtimes (e.g. [`wasmer`][wasmer], [`wasmtime`][wasmtime],
and [`wasmi`][wasmi] - check [Awesome Wasm][awesome] for more), and even [a
package manager][wapm] for distributing compiled `*.wasm` binaries!

Now, I'm going to let you in on a little secret... The aim of this article isn't
actually to implement Fornjot's model system[^1], the goal was to explore some
techniques and technologies I'd like to use at work. I just wanted to avoid
distracting people with the complexity of a Machine Learning pipeline compiler
with runtimes ("hosts", as this article calls them) written in several languages
and deployed on a wide range of platforms.

If you've stuck with me until now, there's a good chance you find this topic
interesting. We're always on the lookout for new talent, so if any of the
buzzwords mentioned in this article sound interesting to you, flick us an email
on careers@hotg.ai or check out [our careers page][careers].

[^1]: Although if they want to use it as inspiration or copy sample code,
be my guest 🙂

[wasm-1.0]: https://github.com/WebAssembly/spec/releases/tag/wg-1.0
[first-article]: {{< ref "/posts/wasm-as-a-platform-for-abstraction" >}}
[wit-bindgen]: https://github.com/bytecodealliance/wit-bindgen
[wapm]: https://wapm.io/
[wasmer]: https://wasmer.io/
[wasmtime]: https://wasmtime.dev/
[wasmi]: https://github.com/paritytech/wasmi
[awesome]: https://github.com/mbasso/awesome-wasm#non-web-embeddings
[Fornjot]: https://github.com/hannobraun/Fornjot/
[Fornjot-71]: https://github.com/hannobraun/Fornjot/issues/71
[hmr]: https://webpack.js.org/concepts/hot-module-replacement/
[rust-67179]: https://github.com/rust-lang/rust/issues/67179
[wit]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md
[resource]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md#item-resource
[use]: https://github.com/bytecodealliance/wit-bindgen/blob/main/WIT.md#item-use
[env-variables]: https://doc.rust-lang.org/cargo/reference/environment-variables.html#environment-variables-cargo-sets-for-crates
[wabt]: https://github.com/WebAssembly/wabt
[careers]: https://hotg.dev/careers
[wasmer-usage]: https://docs.rs/wasmer/latest/wasmer/#usage
