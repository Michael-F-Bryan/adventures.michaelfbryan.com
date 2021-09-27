---
title: "Daily Rust: Slice Patterns"
publishDate: "2021-08-14T00:00:00+00:00"
tags:
- Daily Rust
- Rust
series:
- Daily Rust
---

[Rust 1.26][release-1-26] introduced a nifty little feature called *Basic Slice
Patterns* which lets you pattern match on slices with a known length. Later on
in [Rust 1.42][release-1-42], this was extended to allow using `..` to match on
"everything else".

As features go this may seem like a small addition, but it gives developers an
opportunity to write much more expressive code.

{{% notice note %}}
The code written in this article is available in the various playground links
dotted throughout. Feel free to browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Handling Plurality

One of the simplest applications of slice patterns is to provide user-friendly
messages by matching on fixed length slices.

Often it's nice to be able to customise your wording depending on whether there
were 0, 1, or many items. For example, this snippet...

```rust
fn print_words(sentence: &str) {
    let words: Vec<_> = sentence.split_whitespace().collect();

    match words.as_slice() {
        [] => println!("There were no words"),
        [word] => println!("Found 1 word: {}", word),
        _ => println!("Found {} words: {:?}", words.len(), words),
    }
}

fn main() {
    print_words("");
    print_words("Hello");
    print_words("Hello World!");
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=b5f39a8f3b759134bc1b5f1ccf71b58e)

... will generate this output:

```
There were no words
Found 1 word: Hello
Found 2 words: ["Hello", "World!"]
```

## Matching the Start of a Slice

The `..` syntax is called a "rest" pattern and lets you match on (surprise,
surprise) the rest of the slice.

According to the [ELF Format][elf], all ELF binaries must start with the
sequence `0x7f ELF`.  We can use this fact and rest patterns to implement our
own `is_elf()` check.


```rust
use std::error::Error;

fn is_elf(binary: &[u8]) -> bool {
    match binary {
        [0x7f, b'E', b'L', b'F', ..] => true,
        _ => false,
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let current_exe = std::env::current_exe()?;
    let binary = std::fs::read(&current_exe)?;

    if is_elf(&binary) {
        print!("{} is an ELF binary", current_exe.display());
    } else {
        print!("{} is NOT an ELF binary", current_exe.display());
    }

    Ok(())
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=f26b605fc432a06fb062ebe56fee289f)

## Checking for Palindromes

A very common introductory challenge in programming is to write a check for
palindromes.

We can use the fact that the `@` symbols binds a new variable to whatever it
matches, and our ability to match on both the start and end of a slice to
create a particularly elegant `is_palindrome()` function.

```rust
fn is_palindrome(items: &[char]) -> bool {
    match items {
        [first, middle @ .., last] => first == last && is_palindrome(middle),
        [] | [_] => true,
    }
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=baeec729aea945d2cd98387d1333ba8f)

## A Poor Man's Argument Parser

Another way you might want to use slice patterns is by "peeling off" desired
prefixes or suffixes.

Although more sophisticated crates like [`clap`][clap] and
[`structopt`][structopt] exist, we can use this to implement our own basic
argument parser.

```rust
fn parse_args(mut args: &[&str]) -> Args {
    let mut input = String::from("input.txt");
    let mut count = 0;

    loop {
        match args {
            ["-h" | "--help", ..] => {
                eprintln!("Usage: main [--input <filename>] [--count <count>] <args>...");
                std::process::exit(1);
            }
            ["-i" | "--input", filename, rest @ ..] => {
                input = filename.to_string();
                args = rest;
            }
            ["-c" | "--count", c, rest @ ..] => {
                count = c.parse().unwrap();
                args = rest;
            }
            [..] => break,
        }
    }

    let positional_args = args.iter().map(|s| s.to_string()).collect();

    Args {
        input,
        count,
        positional_args,
    }
}

struct Args {
    input: String,
    count: usize,
    positional_args: Vec<String>,
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=aa016782dab527e80014c932fb769734)

## Irrefutable Pattern Matching

Although not technically part of the *Slice Patterns* feature, you can use
pattern matching to destructure fixed arrays outside of a `match` or `if let`
statement.

This can be useful in avoiding clunkier sequences based on indices which will
never fail.

```rust
fn format_coordinates([x, y]: [f32; 2]) -> String {
    format!("{}|{}", x, y)
}

fn main() {
    let point = [3.14, -42.0];

    println!("{}", format_coordinates(point));

    let [x, y] = point;
    println!("x: {}, y: {}", x, y);
    // Much more ergonomic than writing this!
    // let x = point[0];
    // let y = point[1];
}
```

[(playground)](https://play.rust-lang.org/?version=stable&mode=debug&edition=2018&gist=dfbcc3a1bcf3545e3a15fedd57abe8cd)

## Conclusions

As far as features go in Rust slice patterns aren't overly complex but when used
appropriately, they can really improve the expressiveness of your code.

This was a lot shorter than my usual deep dives, but hopefully you learned
something new. Going forward I'm hoping to create more of these *Daily Rust*
posts, copying shamelessly from Jonathan Boccara's [Daily C++][daily-c++].

[release-1-26]: https://blog.rust-lang.org/2018/05/10/Rust-1.26.html#basic-slice-patterns
[release-1-42]: https://blog.rust-lang.org/2020/03/12/Rust-1.42.html#subslice-patterns
[elf]: https://en.wikipedia.org/wiki/Executable_and_Linkable_Format
[clap]: https://crates.io/crates/clap
[structopt]: https://crates.io/crates/structopt
[daily-c++]: https://www.fluentcpp.com/2017/04/04/the-dailies-a-new-way-to-learn-at-work/
