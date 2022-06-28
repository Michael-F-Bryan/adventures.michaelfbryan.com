---
title: "Announcing Cargo WAPM"
date: "2022-06-28T15:53:04+08:00"
draft: true
_build:
  list: true
---

Here at [Hammer of the Gods][hotg], we write [*a lot*][proc-blocks] of Rust code
that gets compiled to WebAssembly for use in our containerisation technology,
Rune.

We have over 30 different processing blocks[^1] and as you can imagine,
publishing and versioning each of WebAssembly module manually isn't practical.
For that, we lean on the [WebAssembly Package Manager][wapm] to do all the heavy
lifting.

The nice thing is that WAPM is a language-agnostic package manager, meaning
it's just as easy for Rune to run WebAssembly modules written in C++ as it is
to use Rust. However, because WAPM is language-agnostic it means it's...
\**ahem\**...  not specific to any one language.

This presents a dilemma though, because manually compiling your Rust crate to
WebAssembly and packaging it in the form that WAPM expects is a bit of a pain.

Therefore, we made a simple `cargo wapm` subcommand to automate the process and
we've spent the last two months internally dogfooding it.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/hotg-ai/cargo-wapm
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Publishing a WebAssembly Package Manually

The [*Publishing your Package*][wapm-publish-docs] page from WAPM's
documentation already does a good job of explaining the publishing process, but
for the unfamiliar it looks something like this...

First, we need to tell the Rust compiler to generate a `*.wasm` file by setting
the `crate-type` key in our `Cargo.toml`.

```toml
[package]
name = "hello-world"
version = "0.1.0"
description = "A hello world example"
license = "MIT OR Apache-2.0"
repository = "https://github.com/hotg-ai/proc-blocks"
homepage = "https://hotg.ai/"
readme = "README.md"
edition = "2021"

[lib]
crate-type = ["cdylib", "rlib"]

...
```

Now we can cross-compile the crate to WebAssembly.

```console
$ cargo build --release --target=wasm32-unknown-unknown
   Compiling hello-world v0.1.0 (/tmp/hello-world)
    Finished release [optimized] target(s) in 0.35s
```

Next, we need to create a `wapm.toml` manifest. The [*Manifest*][wapm-manifest]
section goes through all the keys, but these are the ones you'll typically want
to set:

```toml
[package]
name = "Michael-F-Bryan/hello-world"
version = "0.1.0"
description = "A hello world example"
license = "MIT OR Apache-2.0"
repository = "https://github.com/hotg-ai/proc-blocks"
homepage = "https://hotg.ai/"
readme = "README.md"

[[module]]
name = "hello_world"
source = "target/wasm32-unknown-unknown/release/hello_world.wasm"
abi = "none"  # processing blocks use a Rune-specific ABI, not WASI
```

Finally, assuming you've already [installed the `wapm` CLI][install-wapm] and
[authenticated][wapm-auth] with WAPM, the package is ready for publishing.

```console
$ wapm publish
Successfully published package `Michael-F-Bryan/hello-world@1.0.0`
```

From there, users can [see the package][hello-world] on WAPM and use it like
normal.

For those familiar with other package managers like Cargo and NPM this process
won't be surprising. However, I would like to draw your attention to something...

Except for the namespace [^2], the `wapm.toml` we wrote is almost
entirely copied from our `Cargo.toml`.

What's worse is that when we update `Cargo.toml` (e.g. to change the version
number), we'll need to manually update `wapm.toml` to match.

We're also hard-coding the path to the compiled binary, so if we want to publish
a version with debug symbols or switch from `wasm32-unknown-unknown` to
`wasm32-wasi`, we'll need to update the path appropriately. There's also the
technicality that the `source` path can't go outside the `wapm.toml` file's
directory, meaning you can't publish anything in a [Cargo Workspace][workspaces]
because the WebAssembly module will typically be in `../target/`.

## Publishing a WebAssembly Package With Cargo WAPM

Now, let's go through the same process with `cargo wapm`.

First, you will need to install the `cargo wapm` subcommand.

```console
$ cargo install cargo-wapm
    Updating crates.io index
  Downloaded cargo-wapm v0.1.1
  ...
   Installed package `cargo-wapm v0.1.1` (executable `cargo-wapm`)
$ cargo wapm --help
Publish a crate to the WebAssembly Package Manager

USAGE:
    wapm [OPTIONS]

OPTIONS:
        --all-features
    -d, --dry-run                          [env: DRY_RUN=]
        --debug                            Compile in debug mode
        --exclude <EXCLUDE>                Packages to ignore
        --features <FEATURES>              A comma-delimited list of features to enable
    -h, --help                             Print help information
        --manifest-path <MANIFEST_PATH>    [env: MANIFEST_PATH=]
        --no-default-features
    -w, --workspace                        [env: WORKSPACE=]
```

Next, add a `[package.metadata.wapm]` section to your `Cargo.toml` so we can
tell `cargo wapm` any extra information it needs to know.

```toml
...

[package.metadata.wapm]
namespace = "Michael-F-Bryan"
abi = "none"  # This tells `cargo wapm` to compile to wasm32-unknown-unknown
```

Now, let's do a dry run to see what would be published.

```console
$ cargo wapm --dry-run
2022-06-28T11:59:29.025090Z  INFO publish: cargo_wapm: Publishing dry_run=true pkg="hello-world"
Successfully published package `Michael-F-Bryan/hello-world@0.1.0`
[INFO] Publish succeeded, but package was not published because it was run in dry-run mode
2022-06-28T11:59:29.067902Z  INFO publish: cargo_wapm: Published! pkg="hello-world"
```

All the files that would normally be published to WAPM have been collected
into a single folder.

```console
$ tree target/wapm
target/wapm
└── hello-world
    ├── hello_world.wasm
    ├── README.md
    └── wapm.toml

1 directory, 3 files
```

We can also look at the generated `wapm.toml`.

```console
$ cat target/wapm/hello-world/wapm.toml
[package]
name = "Michael-F-Bryan/hello-world"
version = "0.1.0"
description = "A hello world example"
license = "MIT OR Apache-2.0"
readme = "README.md"
repository = "https://github.com/hotg-ai/proc-blocks"
homepage = "https://hotg.ai/"

[[module]]
name = "hello-world"
source = "hello_world.wasm"
abi = "none"
```

Unsurprisingly, it's almost identical to the handwritten `wapm.toml` except
the `readme`, `repository`, and `homepage` keys are in a different order.

Publishing a WebAssembly module that should be compiled in debug mode or with
certain [Cargo Features][features] enabled is just a case of adding some extra
flags.

```console
$ cargo wapm --debug --features some-feature
```

Something that sets `cargo wapm` aside from the normal `wapm` CLI is that *it
is workspace-aware*.

When publishing a new version of our processing blocks, we will typically run
the following command from the root directory of [the `hotg-ai/proc-blocks`
repository][proc-blocks].

```console
$ cargo wapm --workspace --exclude xtask --exclude hotg-rune-proc-blocks
```

(the `hotg-rune-proc-blocks` crate just contains shared abstractions and
utilities, while `xtask` is an internal tool following [the xtask
pattern][xtask])

This `--workspace` flag is worth its weight in gold[^3] when you've got 30
packages to publish!

The neat part is that all of this slots into existing tools and conventions like
the ubiquitous `Cargo.toml` file and [Cargo's `cargo metadata`
command][cargo-metadata]  for asking `cargo` about the packages in a workspace.

## Next Steps

The Cargo WAPM tool fits into our workflow quite well and we're happy with it,
so now we'd like you to give it a go.

We'd *especially* like to hear from other people in the industry that want to
make reusable WebAssembly modules.

[^1]: Our term for WebAssembly modules that implement individual transformations
in a data processing pipeline.

[^2]: The `Michael-F-Bryan` in `name = "Michael-F-Bryan/hello-world"`.

[^3]: Yes, I know digital concepts don't really weigh anything. It's a figure of
speech.

[hello-world]: https://wapm.io/Michael-F-Bryan/hello-world
[hotg]: https://hotg.ai/
[install-wapm]: https://docs.wasmer.io/ecosystem/wapm/getting-started
[proc-blocks]: https://github.com/hotg-ai/proc-blocks
[rune]: https://github.com/hotg-ai/rune
[wapm-auth]: https://docs.wasmer.io/ecosystem/wapm/publishing-your-package#creating-an-account-in-wapm
[wapm-manifest]: https://docs.wasmer.io/ecosystem/wapm/manifest
[wapm-publish-docs]: https://docs.wasmer.io/ecosystem/wapm/publishing-your-package
[wapm]: https://wapm.io/
[workspaces]: https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html
[features]: https://doc.rust-lang.org/cargo/reference/features.html
[xtask]: https://github.com/matklad/cargo-xtask
[cargo-metadata]: https://doc.rust-lang.org/cargo/commands/cargo-metadata.html
