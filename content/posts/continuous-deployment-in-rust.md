---
title: "Continuous Deployment in Rust With GitHub Actions"
date: "2021-05-30T18:12:29+08:00"
draft: true
tags:
- Rust
- GitHub Actions
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
developers are good at it's spending 10 hours to automate away a 5 minute job.

In this case we want to develop system for Continuous Integration (automated
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

[rune]: https://github.com/hotg-ai/rune
[hotg]: https://hotg.ai/
[workspace]: https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html
[cargo-edit]: https:/crates.io/crates/cargo-edit
[pyo3]: https://crates.io/crates/pyo3
[maturin]: https://github.com/PyO3/maturin
[pytest]: https://pytest.org/
