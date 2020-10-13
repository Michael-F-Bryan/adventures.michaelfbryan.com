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

## Compiling the Futhark Code

Instead of generating machine code like most compilers, the `futhark` compiler
has several code generators for targeting different languages and platforms.

This includes generators for

- Sequential C code - typically used when you want to run the code on your CPU
  (e.g. for debugging or as a fallback when dedicated hardware isn't available)
- Sequential Python code - for the same reasons as sequential C generator
- PyOpenCL - generate sequential Python code that uses the Python bindings to
  [OpenCL][open-cl] for offloading work to the GPU
- CUDA - generates C code that will configure a Nvidia GPU, compile a CUDA
  kernel containing your Futhark program, and marshal data back and forth

{{% notice note %}}
There is also a REPL for experimenting interactively.

While I usually prefer using a combination of intellisense, compile errors,
and unit tests for finding my way around, I tried the REPL out a couple times
to double-check my code worked as expected and it seemed to work pretty well.

[jupyter]: https://jupyter.org/
{{% /notice %}}

I'm going to use the CUDA backend for this project because my laptop has an
Nvidia card. There isn't much point walking through the process for installing
drivers and dependencies because a lot of it is mentioned on [the Futhark
website][futhark-install] and the [Arch Wiki page][cuda-wiki].

The process for running our CUDA code generator is fairly straightforward.

```console
$ futhark cuda --library mandelbrot.fut
```

If everything goes to plan you should see `mandelbrot.h` and `mandelbrot.c`
appear in your current directory.

```console
$ ls
mandelbrot.c  mandelbrot.fut  mandelbrot.h  mandelbrot_test.fut
```

There is also the option of generating an executable by dropping the `--library`
flag, but we aren't interested in that right now.

Let's have a look at the header file `futhark` generated for us. You don't
need to read it all, but it's a good idea to skim through and look for terms
you recognise to help get a feel for how this library is laid out.

```c
// mandelbrot/futhark/mandelbrot.h

#pragma once

// Headers

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <cuda.h>
#include <cuda_runtime.h>
#include <nvrtc.h>


// Initialisation

int futhark_get_num_sizes(void);
const char *futhark_get_size_name(int);
const char *futhark_get_size_class(int);
struct futhark_context_config ;
struct futhark_context_config *futhark_context_config_new(void);
void futhark_context_config_free(struct futhark_context_config *cfg);
void futhark_context_config_add_nvrtc_option(struct futhark_context_config *cfg,
                                             const char *opt);
void futhark_context_config_set_debugging(struct futhark_context_config *cfg,
                                          int flag);
void futhark_context_config_set_profiling(struct futhark_context_config *cfg,
                                          int flag);
void futhark_context_config_set_logging(struct futhark_context_config *cfg,
                                        int flag);
void futhark_context_config_set_device(struct futhark_context_config *cfg, const
                                       char *s);
void futhark_context_config_dump_program_to(struct futhark_context_config *cfg,
                                            const char *path);
void
futhark_context_config_load_program_from(struct futhark_context_config *cfg,
                                         const char *path);
void futhark_context_config_dump_ptx_to(struct futhark_context_config *cfg,
                                        const char *path);
void futhark_context_config_load_ptx_from(struct futhark_context_config *cfg,
                                          const char *path);
void
futhark_context_config_set_default_group_size(struct futhark_context_config *cfg,
                                              int size);
void
futhark_context_config_set_default_num_groups(struct futhark_context_config *cfg,
                                              int num);
void
futhark_context_config_set_default_tile_size(struct futhark_context_config *cfg,
                                             int num);
void
futhark_context_config_set_default_threshold(struct futhark_context_config *cfg,
                                             int num);
int futhark_context_config_set_size(struct futhark_context_config *cfg, const
                                    char *size_name, size_t size_value);
struct futhark_context ;
struct futhark_context *futhark_context_new(struct futhark_context_config *cfg);
void futhark_context_free(struct futhark_context *ctx);

// Arrays

struct futhark_u32_2d ;
struct futhark_u32_2d *futhark_new_u32_2d(struct futhark_context *ctx, const
                                          uint32_t *data, int64_t dim0,
                                          int64_t dim1);
struct futhark_u32_2d *futhark_new_raw_u32_2d(struct futhark_context *ctx, const
                                              CUdeviceptr data, int offset,
                                              int64_t dim0, int64_t dim1);
int futhark_free_u32_2d(struct futhark_context *ctx,
                        struct futhark_u32_2d *arr);
int futhark_values_u32_2d(struct futhark_context *ctx,
                          struct futhark_u32_2d *arr, uint32_t *data);
CUdeviceptr futhark_values_raw_u32_2d(struct futhark_context *ctx,
                                      struct futhark_u32_2d *arr);
const int64_t *futhark_shape_u32_2d(struct futhark_context *ctx,
                                    struct futhark_u32_2d *arr);

// Opaque values

struct futhark_opaque_complex ;
int futhark_free_opaque_complex(struct futhark_context *ctx,
                                struct futhark_opaque_complex *obj);
struct futhark_opaque_rect ;
int futhark_free_opaque_rect(struct futhark_context *ctx,
                             struct futhark_opaque_rect *obj);

// Entry points

int futhark_entry_complex_new(struct futhark_context *ctx,
                              struct futhark_opaque_complex **out0, const
                              double in0, const double in1);
int futhark_entry_mandelbrot(struct futhark_context *ctx,
                             struct futhark_u32_2d **out0, const int32_t in0,
                             const int32_t in1, const
                             struct futhark_opaque_rect *in2, const
                             struct futhark_opaque_complex *in3);
int futhark_entry_rect_new(struct futhark_context *ctx,
                           struct futhark_opaque_rect **out0, const double in0,
                           const double in1, const double in2, const
                           double in3);

// Miscellaneous

int futhark_context_sync(struct futhark_context *ctx);
int futhark_context_clear_caches(struct futhark_context *ctx);
char *futhark_context_report(struct futhark_context *ctx);
char *futhark_context_get_error(struct futhark_context *ctx);
void futhark_context_pause_profiling(struct futhark_context *ctx);
void futhark_context_unpause_profiling(struct futhark_context *ctx);
#define FUTHARK_BACKEND_cuda
```

There are roughly three groups of functions here,

1. Context initialisation - you can imagine the various
  `futhark_context_config_set_XXX()` functions would map onto methods on some
   sort of `ContextBuilder` type in Rust.
2. Array and opaque object manipulation - these are a bunch of routines for
   creating, writing to, reading from, and destroying Futhark values.
3. Entrypoints - functions we can call to run our Futhark code and retrieve the
   results.

Now we've got a better idea of what we're working with let's compile it.

The first attempt is to just throw `futhark.c` at a C compiler and use the
error messages to figure out what libraries we need to link to.

```console
$ clang -c mandelbrot.c
mandelbrot.c:18:10: fatal error: 'cuda.h' file not found
#include <cuda.h>
         ^~~~~~~~
1 error generated.
```

{{% notice note %}}
I'm compiling to a plain object file for now because my end goal will be to
statically link the `mandelbrot` code into my Rust program.

If you want to use dynamic linking add the `-shared` flag. This can be kinda
annoying though, because it requires distributing the compiled library with
your executable.
{{% /notice %}}

It looks like `cuda.h` isn't in the list of paths included by default.
Normally this isn't an issue because header files are added to your system's
`/include/` directory, but I know Arch Linux installs CUDA to `/opt/cuda/`
and has the x86-64 headers in `/opt/cuda/targets/x86_64-linux/include`.

That's fine, we just need to add a `-I` flag.

```console
$ clang -c mandelbrot.c -I/opt/cuda/targets/x86_64-linux/include
mandelbrot.c:1466:56: warning: passing 'int32_t *' (aka 'int *') to parameter of type 'uint32_t *' (aka 'unsigned int *') converts between pointers to integer types with different sign [-Wpointer-sign]
        assert(futhark_values_u32_2d(ctx, result_6056, arr) == 0);
                                                       ^~~
/usr/include/assert.h:105:20: note: expanded from macro 'assert'
  ((void) sizeof ((expr) ? 1 : 0), __extension__ ({                     \
                   ^~~~
mandelbrot.c:80:65: note: passing argument to parameter 'data' here
                          struct futhark_u32_2d *arr, uint32_t *data);
                                                                ^

  (dozens of similar warnings)

14 warnings generated.
```

Okay, so it looks like the generated code trips a bunch of warnings. In this
case I'm just going to ignore them with the `-w` flag, assuming the Futhark
authors have already seen the warnings and decided they aren't an issue.

Next we can turn the object file into an `libmandelbrot.a` archive; this is the
library we'll be linking our Rust to.

```console
$ ar rc libmandelbrot.a mandelbrot.o
```

For demonstration purposes I'm going to create a Rust program that links to
our `libmandelbrot.a` and creates a `futhark_context`. We'll develop a better
system in the next section.

```rust
// mandelbrot/futhark/main.rs

#![allow(non_camel_case_types)]

extern "C" {
    fn futhark_context_config_new() -> *mut futhark_context_config;
    fn futhark_context_config_free(cfg: *mut futhark_context_config);
    fn futhark_context_new(cfg: *mut futhark_context_config) -> *mut futhark_context;
    fn futhark_context_free(ctx: *mut futhark_context);
}

// declare some opaque types to represent our context and config.
type futhark_context_config = std::ffi::c_void;
type futhark_context = std::ffi::c_void;

fn main() {
    unsafe {
        let cfg = futhark_context_config_new();
        println!("Config: {:?}", cfg);
        assert!(!cfg.is_null());
        let ctx = futhark_context_new(cfg);
        println!("Context: {:?}", ctx);
        assert!(!ctx.is_null());

        futhark_context_free(ctx);
        futhark_context_config_free(cfg);
    }
}
```

Similar to what we did when compiling `mandelbrot.o`, let's just throw this
`main.rs` at the Rust compiler and see what else it needs.

```console
$ rustc main.rs
error: linking with `cc` failed: exit code: 1
...
  = note: /usr/bin/ld: main.main.7rcbfp3g-cgu.5.rcgu.o: in function `main::main':
          main.7rcbfp3g-cgu.5:(.text._ZN4main4main17h2d6c3d678af9e020E+0x6): undefined reference to `futhark_context_config_new'
          /usr/bin/ld: main.7rcbfp3g-cgu.5:(.text._ZN4main4main17h2d6c3d678af9e020E+0x30): undefined reference to `futhark_context_new'
          /usr/bin/ld: main.7rcbfp3g-cgu.5:(.text._ZN4main4main17h2d6c3d678af9e020E+0x76): undefined reference to `futhark_context_free'
          /usr/bin/ld: main.7rcbfp3g-cgu.5:(.text._ZN4main4main17h2d6c3d678af9e020E+0x9d): undefined reference to `futhark_context_config_free'
          collect2: error: ld returned 1 exit status
```

We kinda expected that one. I haven't told `rustc` about our
`libmandelbrot.a` so the linker complained that it couldn't find functions
we've referred to (in this case, `futhark_context_config_new` and friends).
This requires telling it to link to the `mandelbrot` library (`-lmandelbrot`)
and that `libmandelbrot.a` is in the current directory (`-L.`).

```console
$ rustc main.rs -L. -lmandelbrot
error: linking with `cc` failed: exit code: 1
...
  = note: /usr/bin/ld: ./libmandelbrot.a(mandelbrot.o): in function `futhark_context_new':
          mandelbrot.c:(.text+0x897): undefined reference to `cuMemAlloc_v2'
          /usr/bin/ld: mandelbrot.c:(.text+0x8cd): undefined reference to `cuMemcpyHtoD_v2'
          /usr/bin/ld: mandelbrot.c:(.text+0x8ff): undefined reference to `cuMemAlloc_v2'
          /usr/bin/ld: mandelbrot.c:(.text+0x93e): undefined reference to `cuModuleGetFunction'
          /usr/bin/ld: mandelbrot.c:(.text+0x994): undefined reference to `cuModuleGetFunction'
...
```

Now we start getting to the interesting linker errors!

This mentions about 20 different functions, but the first couple start with
`cu`... I'm guessing because we had to include `cuda.h` we'll need to link to
the `cuda` library at some point so let's try adding a `-lcuda`.

```console
$ rustc main.rs -L. -lmandelbrot -lcuda
error: linking with `cc` failed: exit code: 1
...
  = note: /usr/bin/ld: ./libmandelbrot.a(mandelbrot.o): in function `cuda_nvrtc_build':
          mandelbrot.c:(.text+0x4d19): undefined reference to `nvrtcCreateProgram'
          /usr/bin/ld: mandelbrot.c:(.text+0x50b9): undefined reference to `nvrtcCompileProgram'
          /usr/bin/ld: mandelbrot.c:(.text+0x50d9): undefined reference to `nvrtcGetProgramLogSize'
          /usr/bin/ld: mandelbrot.c:(.text+0x5102): undefined reference to `nvrtcGetProgramLog'
...
          /usr/bin/ld: ./libmandelbrot.a(mandelbrot.o): in function `futhark_new_u32_2d':
          mandelbrot.c:(.text+0x1d8d): undefined reference to `cudaEventRecord'
...
          collect2: error: ld returned 1 exit status
```

Based on the name of the missing symbols (`nvrtcCreateProgram`, etc.) I'm
guessing we also need to link to the `nvrtc` library (short for *"NVIDIA Runtime
... something"*, I'm guessing).

Unfortunately `libnvrtc.so` isn't on the default search path so while we
*could* go looking for it ourselves (it's in `/opt/cuda/lib64/libnvrtc.so`
for me) there's a better way.

Most native libraries will register themselves with a program called
`pkg-config` when they are installed. This tells `pkg-config` important
things like where the include files are (used with `-I`), where compiled
libraries are installed to (used with `-L`), and what other libraries they
require.

That means we didn't actually need to go looking for `cuda.h` earlier, instead
we could have used `pkg-config`'s `--cflags` option.

```console
$ pkg-config --cflags cuda
-I/opt/cuda/targets/x86_64-linux/include
```

And likewise, instead of manually passing `-lcuda` to `rustc` we could have
used `pkg-config`'s `--libs` option.

```console
$ pkg-config --libs cuda
-L/opt/cuda/targets/x86_64-linux/lib -lcuda
```

That means our final `rustc` invocation looks like this:

```console
$ rustc main.rs -L. -lmandelbrot $(pkg-config --libs cuda nvrtc cudart)
```

{{% notice note %}}
After a bit of fiddling around and using `nm` to see what symbols were
declared by the various libraries in `/opt/cuda/targets/x86_64-linux/lib` I
figured out we also need to link to the CUDA runtime, `cudart`.
{{% /notice %}}

We can even run the compiled `main` program if everything goes to plan it should
exit successfully and print out the address of the `cfg` and `ctx` pointers.

```console
$ ./main
Config: 0x55dd20b5bdb0
Context: 0x55dd20b5beb0
$ echo $?
0
```

Those pointers are pretty close together so I'm assuming we were successful and
didn't just read garbage.

Anyway, this process was pretty manual, and while I'm happy to do it manually
once or twice when experimenting, Rustaceans are used to `cargo` and build
scripts doing the hard work of compiling and linking with native libraries.

## A Better Build Process

[futhark]:https://futhark-lang.org/
[futhark-blog]: https://futhark-lang.org/blog.html
[wiki]: https://en.wikipedia.org/wiki/Mandelbrot_set
[parallel]: https://en.wikipedia.org/wiki/Embarrassingly_parallel
[testing-docs]: https://futhark-book.readthedocs.io/en/latest/practical-matters.html
[open-cl]: https://documen.tician.de/pyopencl/
[install]: https://futhark.readthedocs.io/en/stable/installation.html
[cuda-wiki]: https://wiki.archlinux.org/index.php/GPGPU#CUDA
[futhark-install]: https://futhark.readthedocs.io/en/stable/installation.html
