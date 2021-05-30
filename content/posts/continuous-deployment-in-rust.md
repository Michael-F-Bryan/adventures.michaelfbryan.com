---
title: "Continuous Deployment in Rust With GitHub Actions"
date: "2021-05-30T18:12:29+08:00"
draft: true
tags:
- Rust
toc: true
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
the latest features and bugfixes. Additionally, you might have users who want to
live on the bleeding edge and don't want to be manually cutting a new release
every day or to for these people to consume.

However, we're developers who write software, and if there is anything
developers are good at it's spending 10 hours to automate away a 5 minute job.

In this case we want to develop a Continuous Integration/Continuous Deployment
system which will:

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

First, let's create a new git repository and initialize the three `cargo`
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

[rune]: https://github.com/hotg-ai/rune
[hotg]: https://hotg.ai/
[workspace]: https://doc.rust-lang.org/book/ch14-03-cargo-workspaces.html
[cargo-edit]: crates.io/crates/cargo-edit
