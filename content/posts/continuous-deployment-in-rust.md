---
title: "Continuous Deployment in Rust With GitHub Actions"
date: "2021-05-30T18:12:29+08:00"
draft: true
tags:
- Rust
- GitHub Actions
- CI/CD
---

I'm currently working with [Hammer of the Gods][hotg] on a project [Rune][rune],
a command-line tool which takes in a declaration for a machine learning pipeline
and generates a WebAssembly binary that can easily be deployed on a variety of
devices.

The exact application isn't important for this article, but a key aspect is
that we've got several interlinked projects written in a variety of programming
languages and the `rune` CLI is just one piece of it.

Developers working on other projects like the mobile app won't necessarily want
to be compiling `rune` from scratch every time (or maybe won't even know how to
compile Rust code), yet they'll still need to use `rune` and want access to all
the latest features and bug-fixes. Additionally, you might have users who want
to live on the bleeding edge and don't want to be manually cutting a new release
every day or to for these people to consume.

However, we're developers who write software, and if there is anything
developers are good at it's spending dozens of hours to automate away a 5 minute
job 😉

In this case we want to develop a system for Continuous Integration (automated
testing) and Continuous Deployment (automated releases) which will:

- Compile and run the test suite for every change that gets pushed to GitHub
- Generate API docs and deploy them to GitHub Pages when merging into `master`
- Create a `cargo xtask dist` helper
- Generate nightly builds of the CLI tool and Python bindings
- Use GitHub Actions to push the nightly builds to GitHub Releases whenever the
  code changed
- Publish new releases to GitHub Actions with pre-compiled binaries whenever
  a new tag is created

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/cdir
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## The Project

Before we can start automating things we should get to know the project we'll be
working with. For the sake of this article I'm going to create a simplified
version of `rune`.

This project has 3 core elements:

1. A core library which contains all of our business logic
2. A command-line program which wraps the core library
3. Python bindings which expose the core library's functionality for use
   while prototyping

First, let's create a new git repository and initialise the three `cargo`
projects, using [a workspace][workspace] to make sure they share the same
dependencies and build directory.

This is an example of doing continuous delivery in Rust, so let's use `cdir` for
short.

```console
$ git init cdir
$ cd cdir
$ cargo new --lib --name=cdir-core core
$ cargo new --lib --name=cdir-python python
$ cargo new --bin --name=cdir-cli cli
$ cat Cargo.toml
  [workspace]
  members = ["cli", "core", "python"]
```

We should end up with a repository that looks roughly like this:

```console
$ tree
  ./cdir/
  ├── Cargo.toml
  ├── cli/
  │   ├── Cargo.toml
  │   └── src
  │       └── main.rs
  ├── core/
  │   ├── Cargo.toml
  │   └── src/
  │       └── lib.rs
  ├── python/
  │   ├── Cargo.toml
  │   └── src/
  │       └── lib.rs
  ├── LICENSE.md
  └── README.md
```

### The `cdir-core` Crate

Now let's populate `cdir-core` with some functionality. This isn't meant to be
an in-depth Rust tutorial so let's just create a function for adding two
numbers.

```rust
// core/src/lib.rs

/// Add two numbers together.
pub fn add(a: u32, b: u32) -> u32 {
    a + b
}
```

We'll also add some tests to make sure the implementation is correct.

```rust
// core/src/lib.rs

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn two_plus_two_is_four() {
        assert_eq!(add(2, 2), 2 + 2);
    }
}
```

### The `cdir-cli` Crate

Now we've got some functionality it's time to expose it as a command-line
application.

We'll use the `cargo add` subcommand (from [the `cargo-edit` crate][cargo-edit])
to add our `cdir-core` library as a dependency as well as `structopt`, a nice
command-line parser library.

```console
$ cd cli
$ cargo add ../core structopt
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding cdir-core (unknown version) to dependencies
      Adding structopt v0.3.21 to dependencies
```

The executable itself isn't overly interesting. We create an `Args` struct
which `structopt` will parse arguments into.

```rust
// cli/src/main.rs

use structopt::StructOpt;

/// A program for adding two numbers together.
#[derive(Debug, StructOpt)]
struct Args {
    /// The first number.
    first: u32,
    /// The second number.
    second: u32,
}

fn main() {
    let Args { first, second } = Args::from_args();

    let sum = cdir_core::add(first, second);
    println!("{} + {} = {}", first, second, sum);
}
```

As a sanity check, we can run this from the command-line and make sure that
2 plus 2 does indeed equal 4.

```console
$ cargo run -- --help
cdir-cli 0.1.0
A program for adding two numbers together

USAGE:
    cdir-cli <first> <second>

FLAGS:
    -h, --help       Prints help information
    -V, --version    Prints version information

ARGS:
    <first>     The first number
    <second>    The second number

$ cargo run -- 2 2
2 + 2 = 4
```

### The `cdir-python` Crate

Now that we've got some functionality, we'll need to create some Python bindings
so our Python users can access it.

The easiest way to write Python bindings is with [the `pyo3` crate][pyo3] so
let's add the `pyo3` crate as a dependency and enable the `extension-module`
feature. Don't forget to add `cdir-core` as a dependency.

```console
$ cargo add pyo3 --features extension-module
$ cargo add ../core
```

We also need to make sure `rustc` generates a `cdylib` (i.e. a `*.dll` or `*.so`
file depending in the OS). This results in the following `Cargo.toml` file:

```toml
# python/Cargo.toml
[package]
name = "cdir-python"
version = "0.1.0"
edition = "2018"

[lib]
crate-type = ["cdylib", "rlib"]

[dependencies]
pyo3 = { version = "0.13.2", features = ["extension-module"] }
```

For the next part we can copy the initial example from `pyo3`'s user guide and
tweak it to wrap our `cdir_core::add()` function instead.

All we do is create a function with the `#[pymodule]` attribute that will be
called when CPython initialises our module and make sure it adds a function
wrapping `cdir_core::add()` to the new module.

```rust
// python/src/lib.rs
use pyo3::prelude::*;

/// Add two unsigned integers together.
#[pyfunction]
fn add(first: u32, second: u32) -> PyResult<u32> {
    Ok(cdir_core::add(first, second))
}

/// A Python module implemented in Rust.
#[pymodule]
fn cdir_python(_py: Python, m: &PyModule) -> PyResult<()> {
    let wrapped = pyo3::wrap_pyfunction!(add, m)?;
    m.add_function(wrapped)?;

    Ok(())
}
```

There is a tool called [`maturin`][maturin] which helps build and package
Python extension modules, and it's got a handy `maturin develop` command which
lets you play around with your code in a virtual environment without needing to
install it.

```console
# Create the virtual environment
$ python3 -m venv env
$ source env/bin/activate

$ maturin develop
🔗 Found pyo3 bindings
🐍 Found CPython 3.9 at python
   Compiling pyo3 v0.13.2
   Compiling cdir_python v0.1.0 (/home/michael/Documents/cdir/python)
    Finished dev [unoptimized + debuginfo] target(s) in 3.33s

$ python3
Python 3.9.5 (default, May 24 2021, 12:50:35)
[GCC 11.1.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> import cdir_python
>>> cdir_python.add(1, "asdf")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
TypeError: argument 'second': 'str' object cannot be interpreted as an integer
>>> cdir_python.add(2, 2)
4
```

This is nice, but our end goal is to set up a CI/CD system for our project and
a CI/CD system needs tests. In this case, we just care that our bindings "work"
so we'll create a smoke test which tries uses some basic functionality and
makes sure it doesn't blow up.

```python
# python/tests/smoke_test.py
import cdir_python

def test_two_plus_two():
    assert cdir_python.add(2, 2) == 4
```

We can now use [the `pytest` testing framework][pytest] to run the test and make
sure it passes.

```console
$ pip install pytest
$ env/bin/pytest
========================== test session starts ==========================
platform linux -- Python 3.9.5, pytest-6.2.4, py-1.10.0, pluggy-0.13.1
rootdir: /home/michael/Documents/cdir/python
collected 1 item

tests/smoke_test.py .                                             [100%]

=========================== 1 passed in 0.01s ===========================
```

The [*Using Rust from Python*][pyo3-user-guide] section of the pyo3 user guide
also contains a note for MacOS users. Apparently how the MacOS linker looks up
symbols is different to Linux and Windows so we need to pass some extra flags to
`rustc`.

```toml
# .cargo/config.toml

[target.x86_64-apple-darwin]
rustflags = [
  "-C", "link-arg=-undefined",
  "-C", "link-arg=dynamic_lookup",
]

[target.aarch64-apple-darwin]
rustflags = [
  "-C", "link-arg=-undefined",
  "-C", "link-arg=dynamic_lookup",
]
```

Of course, in `rune` I only figured this out after one of our developers
complained that the project no longer compiled on his Mac and we spent hours
trying to debug the problem.

## A Basic CI System

The first piece in our CI/CD system is being able to run the test suite every
time code gets pushed up to our GitHub repository.

We'll primarily be using GitHub Actions for CI/CD as (in my experience) it tends
to be easier to work with than Travis or Appveyor. As a component of the wider
GitHub platform, jumping back and forth between PRs, issues, and CI also feels
smoother.

To get started with GitHub Actions you need to define a workflow, a series of
"jobs" which will be triggered every time an event happens (e.g. new code is
pushed up or you created a tag). Each job is executed on its own machine and
will go through a series of tasks before competing with a
successful/unsuccessful status.

For a Rust project, the basic workflow will check out the repository, set up the
Rust toolchain, then run `cargo check`, `cargo build`, and `cargo test`. This
should be done every time code is pushed to GitHub or when a Pull Request is
created.

```yml
# .github/workflow/main.yml

name: Continuous Integration
on:
- push
- pull_request
jobs:
  compile-and-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Initialize the Rust Toolchain
      uses: actions-rs/toolchain@v1
      with:
        profile: minimal
        toolchain: stable
    - name: Type Checking
      uses: actions-rs/cargo@v1
      with:
        command: check
        args: --workspace --verbose
    - name: Compile
      uses: actions-rs/cargo@v1
      with:
        command: build
        args: --workspace --verbose
    - name: Test
      uses: actions-rs/cargo@v1
      with:
        command: test
        args: --workspace --verbose
```

{{% notice tip %}}
When running a command in CI it's always a good idea to use the `--verbose`
flag, if one is available.

The most annoying part of setting up a CI/CD system is that you'll often need to
wait 5-10 minutes to see the effect of any change. That includes any debug
prints you might need to add before you can even get started fixing a broken
build.

Making sure you log all the information you'll need *before* you need to start
troubleshooting CI problems can often save you 2 or 3 extra runs (i.e. half an
hour of waiting).
{{% /notice %}}

To help speed up a build, we can run the [`actions/cache`][cache] action after
the repository is checked out to cache build artefacts. Instead of rebuilding
our entire project from scratch every time we'll hopefully be able to reuse the
result of the last the last successful CI run.

For larger projects this can be the difference between a 25 minute CI run and a
7 minute run and can really help improve the developer experience.

Caching is only effective when build artefacts *can* be reused though. That
means we'll need to use a "key" which is unique for each OS, job, and set of
dependencies involved because changing any of those will often invalidate the
entire cache.

```yml
# .github/workflow/main.yml

jobs:
  compile-and-test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: actions/cache@v2
      with:
          path: |
          ~/.cargo/registry
          ~/.cargo/git
          target
          key: ${{ runner.os }}-${{ github.workflow }}-${{ github.job }}-${{ hashFiles('**/Cargo.lock') }}
    - ...
```

At the moment our `compile-and-test` job is only running on Ubuntu (the
`runs-on: ubuntu-latest` line), but to ensure good coverage we'd also like to
run the test suite on Windows and Mac.

You can tell GitHub actions to run the same job using different configurations
(in this case, on 3 different OSes) with [a job matrix][matrix].

```yaml
# .github/workflow/main.yml

jobs:
  compile-and-test:
    strategy:
      matrix:
        os:
        - ubuntu-latest
        - macos-latest
        - windows-latest
    runs-on: ${{ matrix.os }}
    steps:
    - ...
```

While we're at it, let's update the matrix to also test against different
versions of Rust.

```yaml
# .github/workflow/main.yml

jobs:
  compile-and-test:
    strategy:
      matrix:
        ...
        rust:
        - stable
        - nightly
       - 1.52 # Minimum Supported Rust Version
    steps:
    - ...
    - name: Initialize the Rust Toolchain
      uses: actions-rs/toolchain@v1
      with:
        profile: minimal
        toolchain: ${{ matrix.rust }}
    - ...
```

You'll also want to add `${{ matrix.rust }}` to the cache key so we don't try
using the `stable` cache on a `nightly` build.

## API Docs

You can access the API docs for any released crates by going to the crate's page
on https://docs.rs/, but that won't work for people wanting to make use of new
features that haven't been released yet.

Luckily GitHub Pages is free for all public projects, so let's take the pages
generated by `cargo doc` and host the API docs there.

The core thing we need is a GitHub Action which uploads the contents of a folder
to GitHub Pages. There are a bunch of these available and you can even do it
manually using just `git`, but I've had a decent amount of success with
[`JamesIves/github-pages-deploy-action`][pages].

Next we'll add a second job to our `main.yml` workflow file. Unlike the normal
integration tests we only need to generate API docs for one OS, so that
simplifies things.

```yml
# .github/workflow/main.yml

  api-docs:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: actions/cache@v2
      with:
        path: |
          ~/.cargo/registry
          ~/.cargo/git
          target
        key: ${{ matrix.rust }}-${{ runner.os }}-${{ github.workflow }}-${{ github.job }}-${{ hashFiles('**/Cargo.lock') }}
    - name: Initialize the Rust Toolchain
      uses: actions-rs/toolchain@v1
      with:
        profile: minimal
        toolchain: stable
    - name: Generate API Docs
      uses: actions-rs/cargo@v1
      with:
        command: doc
        args: --workspace --verbose
```

You'll see that most of the steps are the same; we check out the repo, load the
cache, and initialise Rust, The main difference is that instead of using the
`actions-rs/cargo` action to build the workspace, we just call to `cargo doc`.

This will just generate the API docs, though, and when the run ends all docs
will be thrown away. We still need to use the
`JamesIves/github-pages-deploy-action` action to upload the docs, but we'll need
to be smart and make sure they only get deployed for code on the `master`
branch. We don't particularly want someone to make a PR to the repo and find
that they've hijacked our docs. Not limiting the GitHub Pages deploy action to
`master` also opens you up to the much more likely scenario that you'll upload
docs for functionality that doesn't exist in `master` yet and confuse a bunch of
your users.

The `if` property on a step can be used to enable/disable that
step [based on a condition][yml-if].

```yml
# .github/workflow/main.yml

  api-docs:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - ...
    - name: Upload API Docs
      uses: JamesIves/github-pages-deploy-action@4.1.1
      if: github.ref == 'refs/heads/master'
      with:
        branch: gh-pages
        folder: target/doc
```

There's no point providing API docs that people don't know about, so let's
update the project's README with a link. While we're at it we'll also add a
badge indicating whether CI is passing for `master` or not (hint: this should
always be green).

```md
# Continuous Deployment in Rust

[![Continuous Integration](https://github.com/Michael-F-Bryan/cdir/actions/workflows/main.yml/badge.svg)](https://github.com/Michael-F-Bryan/cdir/actions/workflows/main.yml)

([API Docs](https://michael-f-bryan.github.io/cdir))
```

## Generating a Release Bundle

Now we've set up the CI part of our CI/CD system let's figure out how to
generate releases (i.e. the deployment bit). To do this we need something which
will compile our project and package it up into something someone can download
and install on their machine.

A common pattern when you need to do non-trivial internal tasks on a Rust
project is that of [the `cargo xtask`][xtask], first popularised by
[matklad][matklad] in his work on `rust-analyzer`.

The idea is that you'll create a small Rust program which does your task instead
of relying on a shell script.

The distinguishing features of `cargo xtask` are:

- It doesn't require any other binaries besides `cargo` and `rustc`, it fully
  bootstraps from them
- Unlike `bash`, it can more easily be cross platform, as it doesn't use the
  shell.
- You can do tasks which involve a fair amount of complexity or use more than
  just strings (vectors, hash maps, generics, etc.) without it turning into an
  unreadable mess

The first step is to add a `xtask` binary to our workspace.

```console
$ cargo new --bin xtask
$ cat Cargo.toml
[workspace]
members = ["cli", "core", "python", "xtask"]
```

We also need to add some dependencies, namely `zip` for generating zip archives,
`structopt` for parsing command-line arguments, `once_cell` for lazily computed
constants, and `anyhow` to give us more usable error messages. While we're at
it, let's also throw in `log` and `env_logger` so we can see what is happening.

```console
$ cd xtask
$ cargo add zip structopt anyhow
    Updating 'https://github.com/rust-lang/crates.io-index' index
      Adding zip v0.5.12 to dependencies
      Adding structopt v0.3.21 to dependencies
      Adding once_cell v1.7.2 to dependencies
      Adding anyhow v1.0.40 to dependencies
      Adding log v0.4.14 to dependencies
      Adding env_logger v0.8.3 to dependencies
```

Now we've pulled in some dependencies, let's have a think about what sorts of
things a release bundle should include. At the bare minimum we'll need to
include the executable itself, our `README.md` so people know what it does, and
the license files because copyright is important.

The `xtask` binary is designed to support multiple subcommands so we'll start
off defining an `enum` and deriving `StructOpt` so it can be automatically
parsed from the command line arguments.

```rust
// xtask/src/main.rs

#[derive(Debug, StructOpt)]
pub enum Cmd {
    /// Create a release archive.
    Dist {
        /// The `cdir` project's root directory.
        #[structopt(short, long, parse(from_os_str), default_value = &*DEFAULT_PROJECT_ROOT)]
        project_root: PathBuf,
    },
}
```

We need to know where the project's root directory is because that'll tell us
the `target/` directory's location and where we should be running commands from.
However, making users pass that in manually or forcing them to only ever run
`xtask` from the root directory can be annoying, so we provide a default that
uses `git` to find the project root for us.

```console
$ git rev-parse --show-toplevel
/home/michael/Documents/cdir
```

This is fairly straightforward to translate to use `std::process::Command`.

```rust
// xtask/src/main.rs

use anyhow::{Context, Error};
use std:process::{Command, Stdio};
use once_cell::sync::Lazy;

static DEFAULT_PROJECT_ROOT: Lazy<String> =
    Lazy::new(|| git_repo_root().unwrap_or_else(|_| String::from(".")));

fn git_repo_root() -> Result<String, Error> {
    let output = Command::new("git")
        .arg("rev-parse")
        .arg("--show-toplevel")
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .context("Unable to execute `git`")?;

    let output = std::str::from_utf8(&output.stdout).context("git returned invalid UTF-8")?;

    Ok(output.trim().to_string())
}
```

We are now ready to write our `main()` function

```rust
// xtask/src/main.rs

fn main() -> Result<(), Error> {
    env_logger::init();
    let cmd = Cmd::from_args();

    match cmd {
        Cmd::Dist { project_root } => dist(project_root)?,
    }

    Ok(())
}
```

The `dist()` function is composed of two phases, compiling the binary and adding
all the files to a zip archive.

```rust
// xtask/src/main.rs

use std::path::PathBuf;

fn dist(project_root: PathBuf) -> Result<(), Error> {
    log::info!("Generating a release bundle");

    compile_cdir_cli(&project_root)?;
    generate_release_bundle(&project_root)?;

    Ok(())
}
```

Compiling the `cdir` CLI tool is handled almost the same way as
`git rev-parse --show-toplevel`, except we want all the output to print to the
terminal instead of being captured.

```rust
// xtask/src/main.rs

use std::path::Path;

fn compile_cdir_cli(project_root: &Path) -> Result<(), Error> {
    log::debug!("Compiling `cdir-cli`");
    let cargo = std::env::var("CARGO").unwrap_or_else(|_| String::from("cargo"));

    let status = Command::new(cargo)
        .arg("build")
        .arg("--release")
        .arg("--package=cdir-cli")
        .current_dir(project_root)
        .status()
        .context("Unable to start `cargo`")?;

    anyhow::ensure!(status.success(), "Compiling `cdir-cli` failed");

    Ok(())
}
```

{{% notice tip %}}
When writing a program that is intended to be run as a `cargo` subcommand (our
end goal is to make it usable as `cargo xtask dist`) it's a good idea to check
the `CARGO` environment variable for the path to the `cargo` binary performing
the build. I believe that's so you always use the same version of `cargo`
regardless of where the subcommand runs (e.g. you may have told `rustup` to
override the version of `cargo` used within a certain directory).

See [*The Cargo Book*][book] for more info.

[book]: https://doc.rust-lang.org/cargo/reference/environment-variables.html#environment-variables-cargo-sets-for-3rd-party-subcommands
{{% /notice %}}

Ideally, when we generate a release bundle it will also include [the target
triple][triple] it was compiled for. That way users will be able to figure out
which release bundle to download for their OS.

There are crates which will figure this out for you (e.g.
[`guess_host_triple`][guess-host]), but the most reliable method is to just use
[the `TARGET` environment variable][build-env] that `cargo` passes to build
scripts when they run. From there we can pass it through to the `xtask` crate
by printing a special `"cargo:rustc-env=TARGET=..."` message.

```rust
// xtask/build.rs

fn main() {
    let target = std::env::var("TARGET").unwrap();
    println!("cargo:rustc-env=TARGET={}", target);
}
```

Now we've got the target triple, generating a release bundle is fairly
straightforward too. First we figure out where to write the bundle to.

```rust
// xtask/src/main.rs

fn filename(target_dir: &Path) -> PathBuf {
    target_dir.join(format!("cdir.{}.zip", env!("TARGET")))
}

fn generate_release_bundle(project_root: &Path) -> Result<(), Error> {
    let target = project_root.join("target");
    let filename = filename(&target);
    log::debug!("Generating a release bundle");

    ...
}
```

Then we create a new `ZipWriter` and use a `add_file()` helper to add files to
our archive.

```rust
// xtask/src/main.rs

fn generate_release_bundle(project_root: &Path) -> Result<(), Error> {
    ...

    let f = File::create(&filename)
        .with_context(|| format!("Unable to open \"{}\" for writing", filename.display()))?;

    let mut writer = ZipWriter::new(f);

    let cdir_cli = target.join("release").join(CDIR_CLI_BINARY);
    add_file(&mut writer, &cdir_cli)?;
    add_file(&mut writer, project_root.join("README.md"))?;
    add_file(&mut writer, project_root.join("LICENSE_MIT.md"))?;
    add_file(&mut writer, project_root.join("LICENSE_APACHE.md"))?;

    ...
}
```

And finally we tell the writer to write out any trailing metadata and flush to
disk.

```rust
// xtask/src/main.rs

fn generate_release_bundle(project_root: &Path) -> Result<(), Error> {
    ...

    writer
        .finish()
        .context("Unable to finalize the zipfile")?
        .flush()
        .context("Unable to flush to disk")?;

    log::debug!(
        "The release bundle was written to \"{}\"",
        filename.display()
    );

    Ok(())
}
```

The `add_file()` helper just copies a file from disk into the `ZipWriter`.

```rust
// xtask/src/main.rs

fn add_file<W>(w: &mut ZipWriter<W>, filename: impl AsRef<Path>) -> Result<(), Error>
where
    W: Write + Seek,
{
    let filename = filename.as_ref();
    let name = filename
        .file_name()
        .and_then(|n| n.to_str())
        .context("The file has no name")?;

    let mut f = File::open(filename)
        .with_context(|| format!("Unable to open \"{}\" for reading", filename.display()))?;

    w.start_file(name, FileOptions::default())?;
    let bytes_written = std::io::copy(&mut f, w)?;
    w.flush()?;

    log::debug!( "Added \"{}\" to the bundle ({} bytes)", filename.display(), bytes_written);

    Ok(())
}
```

That should finish off our `xtask dist` subcommand, let's run it in a terminal
and check out the results.

```console
$ RUST_LOG=debug cargo run --package xtask -- dist
   Compiling xtask v0.1.0 (/home/michael/Documents/cdir/xtask)
    Finished dev [unoptimized + debuginfo] target(s) in 0.48s
     Running `/home/michael/Documents/cdir/target/debug/xtask dist`
[2021-06-02T18:23:42Z INFO  xtask] Generating a release bundle
[2021-06-02T18:23:42Z DEBUG xtask] Compiling `cdir-cli`
    Finished release [optimized] target(s) in 0.02s
[2021-06-02T18:23:42Z DEBUG xtask] Generating a release bundle
[2021-06-02T18:23:44Z DEBUG xtask] Added "/home/michael/Documents/cdir/target/release/cdir-cli" to the bundle (3918968 bytes)
[2021-06-02T18:23:44Z DEBUG xtask] Added "/home/michael/Documents/cdir/README.md" to the bundle (1315 bytes)
[2021-06-02T18:23:44Z DEBUG xtask] Added "/home/michael/Documents/cdir/LICENSE_MIT.md" to the bundle (1075 bytes)
[2021-06-02T18:23:44Z DEBUG xtask] Added "/home/michael/Documents/cdir/LICENSE_APACHE.md" to the bundle (9723 bytes)
[2021-06-02T18:23:44Z DEBUG xtask] The release bundle was written to "/home/michael/Documents/cdir/target/cdir.x86_64-unknown-linux-gnu.zip"
```

The `zipinfo` command is also quite handy for inspecting zip archives.

```console
$ zipinfo target/cdir.x86_64-unknown-linux-gnu.zip
Archive:  target/cdir.x86_64-unknown-linux-gnu.zip
Zip file size: 1100780 bytes, number of entries: 4
-rw-r--r--  4.6 unx  3918968 b- defN 21-Jun-03 02:23 cdir-cli
-rw-r--r--  4.6 unx     1315 b- defN 21-Jun-03 02:23 README.md
-rw-r--r--  4.6 unx     1075 b- defN 21-Jun-03 02:23 LICENSE_MIT.md
-rw-r--r--  4.6 unx     9723 b- defN 21-Jun-03 02:23 LICENSE_APACHE.md
4 files, 3931081 bytes uncompressed, 1100358 bytes compressed:  72.0%
```

{{% notice tip %}}
You may also want to `strip` the generated binary to help decrease the archive
size even more. I'll leave that as an exercise for the reader.
{{% /notice %}}

We can make the `xtask` binary even easier to use by creating [a `cargo`
"alias"][alias].  This will let us run `cargo xtask dist` instead of needing to
use `cargo run` inside the `xtask/` directory or manually specify which package
it belongs to (`cargo run --package xtask -- dist`).

All we need to do is add it to our `config.toml`.

```toml
# .cargo/config.toml

[alias]
xtask = "run --package xtask --"
```

{{% notice note %}}
Often your use case will be simple enough that a shell script will suffice for
this task. If your project falls into this category and you don't feel the extra
hassle of making a `cargo xtask` is worth it then that's awesome, go with
whatever makes your life easier.

Unfortunately, `rune` didn't really have this luxury because we wanted to
include a bunch of extra stuff which required non-trivial preparation or worked
around subtle platform differences (e.g. the `find` on MacOS behaves differently
to GNU `find` and MacOS `strip` seemed to choke on our `librune.a`). For us it
was just nicer to write some Rust which did the work and use crates from
crates.io instead of system dependencies.
{{% /notice %}}


[rune]: https://github.com/hotg-ai/rune
[hotg]: https://hotg.ai/
[workspace]: https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html
[cargo-edit]: https:/crates.io/crates/cargo-edit
[pyo3]: https://crates.io/crates/pyo3
[maturin]: https://github.com/PyO3/maturin
[pytest]: https://pytest.org/
[cache]: https://github.com/actions/cache
[matrix]: https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions#jobsjob_idstrategy
[pyo3-user-guide]: https://pyo3.rs/master/index.html#using-rust-from-python
[pages]: https://github.com/JamesIves/github-pages-deploy-action
[yml-if]: https://docs.github.com/en/actions/reference/context-and-expression-syntax-for-github-actions
[matklad]: https://github.com/matklad/
[xtask]: https://github.com/matklad/cargo-xtask
[guess-host]: https://crates.io/crates/guess_host_triple
[triple]: https://doc.rust-lang.org/cargo/appendix/glossary.html#target
[build-env]: https://doc.rust-lang.org/cargo/reference/environment-variables.html#environment-variables-cargo-sets-for-build-scripts
[alias]: https://doc.rust-lang.org/cargo/reference/config.html#alias
