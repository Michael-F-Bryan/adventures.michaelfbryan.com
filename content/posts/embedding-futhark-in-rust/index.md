---
title: "Embedding Futhark in Rust"
date: "2020-10-11T23:45:54+08:00"
draft: true
tags:
- Rust
- Unsafe Rust
- FFI
- Futhark
---

Over the last year or so I've been keeping an eye on the [Futhark][futhark]
programming language, a small programming language designed to be compiled to
efficient parallel code that can be run on a GPU.

Something I really like about this language is that it isn't trying to solve
all your problems or replace existing general-purpose languages. Instead it
has been designed to fill the niche of hardware accelerated data processing
and enable easy integration with non-Futhark code for the rest of your
application logic.

Their [blog posts][futhark-blog] are also quite well written, too.

To help raise awareness for this young project (and so I have notes to look
back on six months from now) I thought I'd go through the steps for embedding
Futhark code in a Rust program for rendering [the Mandelbrot set][wiki].

{{% notice note %}}
The code written in this article is available on GitHub
([futhark-rs][f]/[mandelbrot][m]). Feel free to browse through and steal code
or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[f]: https://github.com/Michael-F-Bryan/futhark-rs
[m]: https://github.com/Michael-F-Bryan/mandelbrot
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Calculating the Mandelbrot Set in Futhark

As one of the most well known [embarrassingly parallel][parallel] problems in
computer science, calculating the Mandelbrot set seems like a perfect
candidate for demonstrating Futhark's strengths. This is a set for which
every point, $Z$, on the complex plane, the series $Z_{n+1} = Z^2 + C$
doesn't blow up to infinity.

You can visualise this set by counting the number of iterations before $Z$
crosses an arbitrary threshold, then map the iteration count to a colour map.

{{< figure
    src="https://upload.wikimedia.org/wikipedia/commons/thumb/2/21/Mandel_zoom_00_mandelbrot_set.jpg/512px-Mandel_zoom_00_mandelbrot_set.jpg"
    link="https://commons.wikimedia.org/wiki/File:Mandel_zoom_00_mandelbrot_set.jpg"
    caption="Created by Wolfgang Beyer with the program Ultra Fractal 3. / CC BY-SA (http://creativecommons.org/licenses/by-sa/3.0/)"
    alt="Mandel zoom 00 mandelbrot set"
>}}

To get started, let's define some functions for working with complex numbers.

```haskell
-- mandelbrot/futhark/mandelbrot.fut

type complex = { real: f64, imaginary: f64 }

let magnitude (number: complex): f64 =
    let {real=re, imaginary=im} = number
    in
        f64.sqrt ((re*re) + (im*im))

let add (first: complex) (second: complex): complex =
    let {real=a, imaginary=b} = first
    let {real=c, imaginary=d} = second
    in
        { real = a+c, imaginary = b+d }

let mul (first: complex) (second: complex): complex =
    let {real=a, imaginary=b} = first
    let {real=c, imaginary=d} = second
    in
        { real = a*c - b*d, imaginary = a*d + b*c }

let square (c: complex): complex = mul c c

let dot (number: complex): f64 =
    let {real=re, imaginary=im} = number
    in
        re*re + im*im
```

While the syntax feels a bit weird to me (I'm used to languages based on C or
Pascal syntax), if you squint a bit you'll see familiar concepts like record
types (`complex`), destructuring (`let {real=re, imaginary=im} = ...`), and
function application (`f64.sqrt (re*re) + (im*im)`).

Next let's write a function which keeps iterating $Z_{n+1} = Z^2 + C$ until
$|Z| > 2$ (anything with a magnitude greater than 2 is guaranteed to
diverge), or we reach some maximum number of iterations and are confident the
number won't diverge.

Where we'd normally reach for a simple `while` loop if writing Rust, the
`iterate_while` function is more convenient in this situation.

Here is it's signature:

```haskell
val iterate_while 'a: (predicate: a -> bool) -> (next: a -> a) -> (x: a) -> a
```

You can see that `interate_while` takes a `predicate` and a `next` function,
and will keep applying `next` to the current value until `predicate` returns
`false`.

In this case I've used a tuple of `(u32, complex)`, where the first item is how
many iterations we've executed and the second is the current $Z$ value.

```haskell
-- mandelbrot/futhark/mandelbrot.fut

-- How many iterations until the value starts diverging?
let iterations (max_iterations: u32)
               (upper_bound: f64)
               (c: complex)
               (initial_z: complex): u32 =
    let (i, _) = iterate_while
        (\(i, z) -> i < max_iterations && (magnitude z) < upper_bound)
        (\(i, z) -> (i+1, (add (square z) c)))
        (0, initial_z)
    in
        i
```

Now we have a function for counting the iterations for some complex number, $Z$,
we can use it to populate a big matrix with the iteration counts for every
"pixel" in our image.

Here are a couple constants and a `rect` type for representing the area being
visualised.

```haskell
-- mandelbrot/futhark/mandelbrot.fut

type rect = {top: f64, left: f64, width: f64, height: f64}

let upper_bound: f64 = 4.0
let max_iterations: u32 = 200
```

We also need to expose a couple constructor functions so the calling code is
able to create a `complex` number or `rect`. We use the `entry` keyword instead
of the usual `let` for declaring functions which should be exposed via our C
API.

```haskell
-- mandelbrot/futhark/mandelbrot.fut

-- Expose a complex number constructor.
entry complex_new (real: f64) (imaginary: f64): complex = {real, imaginary}

-- Expose a rect constructor.
entry rect_new (top: f64) (left: f64) (width: f64) (height: f64): rect =
    {top, left, width, height}
```

And finally we have the library's main entry point, `mandelbrot`. This takes
some dimensions defining the size of the generated image, plus a `viewport`
and the $C$ in $Z_{n+1} = Z^2 + C$.

```haskell
-- mandelbrot/futhark/mandelbrot.fut

-- Calculate part of the Mandelbrot set.
entry mandelbrot (width: i32)
                 (height: i32)
                 (viewport: rect)
                 (c: complex) : [width][height]u32 =
    tabulate_2d width height (\i j ->
        let real = viewport.left + (f64.i32 i) * viewport.width / (f64.i32 width)
        let imaginary = viewport.top + (f64.i32 j) * viewport.height / (f64.i32 height)
        in
            iterations max_iterations upper_bound c {real, imaginary}
    )
```

The `tabulate_2d` function is part of the language prelude and lets you
create a 2D array by calling a function to initialise each cell. Futhark does
the hard work of distributing the tasks to each of the GPU's cores and
marshalling the results back to the CPU so the caller can read the results.

Its signature looks something like this:

```haskell
val tabulate_2d 'a: (n: i64) -> (m: i64) -> (f: i64 -> i64 -> a) -> *[n][m]a
```

We can also test our code by using the `futhark test` command. Futhark comes
with testing built directly into the tools and has [some fairly complete
documentation][testing-docs] on how it works.

Here's a test file which imports our `iterations` function and throws a couple
known inputs at it, making sure we receive the desired outputs.

```haskell
-- mandelbrot/futhark/mandelbrot_test.fut

import "./mandelbrot"

-- Iterations
-- ==
-- entry: test_iterations
-- input { 100 2.0 [0.0, 0.0] [0.0, 0.0]}
-- output {100}
-- input { 100 2.0 [1.0, 0.0] [0.5, 0.0]}
-- output {2}

entry test_iterations (max_iterations: i32)
                      (upper_bound: f64)
                      (z: [2]f64)
                      (c: [2]f64): i32 =
    let it = iterations
                (u32.i32 max_iterations)
                upper_bound
                { real = c[0], imaginary = c[1] }
                { real = z[0], imaginary = z[1] }
    in
        i32.u32 it
```

And we can execute the tests from a terminal.

```console
$ futhark test mandelbrot_test.fut
┌──────────┬────────┬────────┬───────────┐
│          │ passed │ failed │ remaining │
├──────────┼────────┼────────┼───────────┤
│ programs │ 1      │ 0      │ 0/1       │
├──────────┼────────┼────────┼───────────┤
│ runs     │ 2      │ 0      │ 0/2       │
└──────────┴────────┴────────┴───────────┘
```

The ASCII art table for displaying a summary of results is a nice touch.

[futhark]:https://futhark-lang.org/
[futhark-blog]: https://futhark-lang.org/blog.html
[wiki]: https://en.wikipedia.org/wiki/Mandelbrot_set
[parallel]: https://en.wikipedia.org/wiki/Embarrassingly_parallel
[testing-docs]: https://futhark-book.readthedocs.io/en/latest/practical-matters.html
