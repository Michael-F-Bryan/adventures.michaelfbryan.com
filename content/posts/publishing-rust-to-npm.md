---
title: "Publishing Rust to NPM"
date: "2020-03-03T23:22:37+08:00"
draft: true
tags:
- rust
- typescript
- WebAssembly
---

Based on a lot of the articles and comments I've read online, the general
sentiment seems to be that [WebAssembly][wa] is a shiny new tool with lots of
promise, but the ecosystem is nonexistent and nobody ([other than malware
authors][malware-use]) is really using it in the wild.

I don't think that's the case, though.

A while back I made [a library][gcode-rs] for parsing [G-code][wiki], the
language that most computer-controlled machines (CNC mills, 3D printers, etc.)
use. This library is written in Rust and targeted at embedded devices, but
I've been wanting to leverage the hard work done by Rust's [WebAssembly Working
Group][wasm-wg] to compile the library to WebAssembly and publish it to NPM. 

That way others have access to battle-tested G-code parser, and it'll make it a
lot easier to create a browser-based demo in the future. It's also a good way
to see what it takes to publish WebAssembly in 2020.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/gcode-rs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Setting Up the Build

Our first step in making the `gcode` crate (the Rust term for a library or
package) available on NPM is to create the library skeleton and set up our
build.

{{% notice note %}}
I *could* take the easy path here and just tell you to use the 
[rust-webpack-template][template], but then we'd be copying someone else's 
solution and wouldn't actually understand how Rust code can be bundled into a
JS library.

I also don't do much in the JavaScript world and would like to peel away the
layers of magic to see what `rust-webpack-template` is doing for me.

[template]: https://github.com/rustwasm/rust-webpack-template/
{{% /notice %}}

I'll start by `cd`-ing into a checkout of the [`gcode`][gcode-rs] repository and
create a new project.

```console
$ cd ~/Documents/gcode-rs
$ mkdir wasm && cd wasm
$ yarn init
yarn init v1.22.1
question name (wasm): @michael-f-bryan/gcode
question version (1.0.0):
question description: An interface to the Rust gcode parser library
question entry point (index.js): ts/index.ts
question repository url: https://github.com/Michael-F-Bryan/gcode-rs
question author: Michael-F-Bryan <michaelfbryan@gmail.com>
question license (MIT): MIT OR Apache-2.0
question private:
success Saved package.json
Done in 77.44s.
$ mkdir ts
$ touch ts/index.ts
```

I'm a pretty big fan of using the type system to prevent errors and make APIs
more discoverable, so I'll also add TypeScript to the project.

```console
$ tsc --init
message TS6071: Successfully created a tsconfig.json file.
```

It's a good idea to update `tsconfig.json` to remove the boilerplate generated
by `tsc`.

```json
// wasm/tsconfig.json

{
  "compilerOptions": {
    "target": "es5",
    "module": "es6",
    "strict": true,
    "outDir": "dist",
    "sourceMap": true
  }
}
```

We'll be making a thin wrapper around the `gcode` crate which exposes key 
functionality and simplifies the API surface to make it more amenable to being
called from JavaScript. 

{{% notice note %}}
This is mainly because WebAssembly functions can't contain generics, and the
`gcode` crate uses generics to let users control things like memory usage.
embedded devices don't typically have a heap so you need to use buffers with
a pre-defined size (e.g. allowing gcodes to contain at most 5 arguments), but
on less constrained platforms (i.e. a normal PC) we want to take advantage of
the gigabytes of memory that are available.

It also helps prevent the `gcode` crate from being polluted with 
WebAssembly-specific functionality or idiosyncracies.
{{% /notice %}}

We can use `cargo` to create this `gcode-wasm` wrapper crate. I'm also going
to move the Rust source code to a `rust/` folder instead of `src/` (the
default) to prevent confusion.

```console
$ cargo init .
```

The `wasm/` folder inside the `gcode` repository now looks like this:

```
$ tree -I node_modules
wasm
├── Cargo.toml
├── index.ts
├── package.json
├── js
│   └── index.ts
├── rust
│   └── lib.rs
├── tsconfig.json
└── yarn.lock

1 directories, 6 files
```

I need to update `Cargo.toml` to tell it to look for `rust/lib.rs` instead of
the default entrypoint of `src/lib.rs`. While I'm at it, I'll add `gcode` and
`wasm-bindgen` (more about that one later) as dependencies from crates.io.

```toml
[package]
name = "gcode-wasm"
version = "0.1.0"
authors = ["Michael-F-Bryan <michaelfbryan@gmail.com>"]
edition = "2018"
publish = false

[dependencies]
gcode = "0.6.0"
wasm-bindgen = "0.2.59"

# we're using "rust/" instead of "src/" to prevent any mix-ups between the Rust
# world and the JS/TS world
[lib]
path = "rust/lib.rs"
crate-type = ["cdylib", "rlib"]
```

At the moment we've got a TypeScript package and a Rust crate, but we haven't
set things up so the Rust code can be compiled to WebAssembly and used from
TypeScript. For this we'll need a bundler, I'm going to use webpack because it
is the most popular and the necessary plugins have already been created.

```console
$ yarn add --dev ts-loader webpack webpack-cli
...
Done in 12.50s.
```

First I'll copy the webpack config file from [the TypeScript docs][ts-webpack].

```js
// wasm/webpack.config.js

const path = require('path');

module.exports = {
    entry: './ts/index.ts',
    devtool: 'inline-source-map',
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
        ],
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js'],
    },
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
};
```

Next we're going to use the [`@wasm-tool/wasm-pack-plugin`][webpack-plugin] to
compile our Rust code.

```console
$ yarn add --dev @wasm-tool/wasm-pack-plugin
...
Done in 5.28s.
```

Update the webpack config to use the new packages.

```diff
 // wasm/webpack.config.js

 const path = require('path');
+const WasmPackPlugin = require("@wasm-tool/wasm-pack-plugin");

 module.exports = {
     entry: './ts/index.ts',
@@ -16,7 +17,12 @@ module.exports = {
         extensions: ['.tsx', '.ts', '.js'],
     },
     output: {
-        filename: 'bundle.js',
+        filename: '[name].js',
         path: path.resolve(__dirname, 'dist'),
     },
+    plugins: [
+        new WasmPackPlugin({
+            crateDirectory: __dirname,
+        }),
+    ]
 };
```

This requires the `wasm-pack` binary to be available on our `$PATH`. If you 
don't already have it, you can use `cargo` to install it... This may take a 
while because `wasm-pack` is a big program.

```console
$ cargo install wasm-pack
    Updating crates.io index
    Downloaded wasm-pack v0.9.1
    ...
    Finished release [optimized] target(s) in 3m 36s
  Installing /home/michael/.cargo/bin/wasm-pack
   Installed package `wasm-pack v0.9.1` (executable `wasm-pack`)
```

Now, if all goes to plan, we should be able to run webpack and it'll compile
and bundle our code. For convenience I added a `watch` script to `package.json`
which will start webpack in watch mode.

```console
$ yarn watch
yarn run v1.22.1
$ webpack --watch --mode=development
ℹ️  Compiling your crate in development mode...

[INFO]: Checking for the Wasm target...
[INFO]: Compiling to Wasm...
    Finished dev [unoptimized + debuginfo] target(s) in 0.03s
[INFO]: :-) Done in 0.20s
[INFO]: :-) Your wasm pkg is ready to publish at /home/michael/Documents/gcode-rs/wasm/pkg.
✅  Your crate has been correctly compiled

Hash: ceb00db7e3c88aba23b8
Version: webpack 4.42.0
Time: 1535ms
Built at: 03/08/2020 3:50:09 AM
  Asset      Size  Chunks             Chunk Names
main.js  86.7 KiB    main  [emitted]  main
Entrypoint main = main.js
[./ts/index.ts] 12 bytes {main} [built]
```

Awesome!

Next, let's try to make sure things are working by writing a dummy function in
Rust and calling it from `ts/index.ts`.

```rust
// wasm/rust/lib.rs

use wasm_bindgen::prelude::wasm_bindgen;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {}!", name)
}
```

{{% notice note %}}
You'll notice we're annotating `greet()` with a `#[wasm_bindgen]` attribute. 
wasm-bindgen is a Rust library and CLI tool that facilitate high-level
interactions between wasm modules and JavaScript, and the `#[wasm_bindgen]`
attribute is where a lot of the magic happens.

The [wasm-bindgen docs][wasm-bindgen-docs] explain how it works a lot better
than I can, so I'd recommend having a skim through them if you're curious.

[wasm-bindgen-docs]: https://rustwasm.github.io/wasm-bindgen/
{{% /notice %}}


We'll also add a `greet()` call to the top of `ts/index.ts`.

```ts
// wasm/ts/index.ts

import * as wasm from "../pkg/index";

wasm.greet("World");
```

Let's jump back to the console running `webpack --watch` to see how it went.

```text
...

Hash: ceb00db7e3c88aba23b8
Version: webpack 4.42.0
Time: 1519ms
Built at: 03/08/2020 4:15:41 AM
  Asset      Size  Chunks             Chunk Names
main.js  86.7 KiB    main  [emitted]  main
Entrypoint main = main.js
[./ts/index.ts] 59 bytes {main} [built]
[./pkg/index.js] 3.03 KiB {main} [built]
[./pkg/index_bg.wasm] 49.4 KiB {main} [built]
    + 4 hidden modules

ERROR in ./pkg/index_bg.wasm
WebAssembly module is included in initial chunk.
This is not allowed, because WebAssembly download and compilation must happen asynchronous.
Add an async splitpoint (i. e. import()) somewhere between your entrypoint and the WebAssembly module:
* ./ts/index.ts --> ./pkg/index.js --> ./pkg/index_bg.wasm
* ... --> ./pkg/index.js --> ./pkg/index_bg.wasm --> ./pkg/index.js --> ./pkg/index_bg.wasm
```

Well that's interesting!

It took a little digging, but it seems like [I'm not the first][wbg-700] Rust
user to run into this error when using webpack.

I *think* this is because WebAssembly can't really be stuffed into a single
`bundle.js` file, instead we can use webpack's code splitting functionality
so that anything which needs to call WebAssembly will download and compile it
separately. This requires adding some sort of "seam" so we can `await` the
WebAssembly download and compilation before we get access to the exported
functions.

After looking at [rustwasm/wasm-bindgen#700][wbg-700] it seems like the best
solution is to create a `bootstrap.js` who's sole purpose is to `import()`
(an asynchronous operation) the rest of the code, and tell webpack that
*that* is our entrypoint.

```js
// wasm/bootstrap.js

// We need a seam so the WebAssembly can be imported asynchronously
import("./ts/index.ts").catch(console.error);
```

We'll also need to update the webpack config appropriately.

```diff
 // wasm/webpack.config.js

 const WasmPackPlugin = require("@wasm-tool/wasm-pack-plugin");

 module.exports = {
-    entry: './ts/index.ts',
+    entry: './bootstrap.js',
     devtool: 'inline-source-map',
     module: {
         rules: [
```

Looking back at the webpack console, that seems to have made it happy again. 
You can also see that `./pkg/index_bg.wasm` (or WebAssembly code) is mentioned
in the list of built files.

```console
...

Hash: 380a3f3090f827e1f585
Version: webpack 4.42.0
Time: 1659ms
Built at: 03/08/2020 4:25:12 AM
                           Asset      Size  Chunks                         Chunk Names
                            0.js  67.9 KiB       0  [emitted]
                            1.js  10.8 KiB       1  [emitted]
2baf8b587bc538554c03.module.wasm  49.5 KiB       1  [emitted] [immutable]
                         main.js  25.2 KiB    main  [emitted]              main
Entrypoint main = main.js
[./bootstrap.js] 113 bytes {main} [built]
[./ts/index.ts] 59 bytes {1} [built]
[./pkg/index.js] 3.03 KiB {1} [built]
[./pkg/index_bg.wasm] 49.4 KiB {1} [built]
    + 4 hidden modules
```

 The code isn't overly readable because it is computer-generated and they are
 trying to handle varying levels of browser support, but if you skim through
 the generated bundle you can see the asynchronous WebAssembly downloading
 and compiling using things like `fetch()` and
 `WebAssembly.instantiateStreaming()`.

```js
// wasm/dist/main.js

/******/ 		// Fetch + compile chunk loading for webassembly
/******/
/******/ 		var wasmModules = {"1":["./pkg/index_bg.wasm"]}[chunkId] || [];
/******/
/******/ 		wasmModules.forEach(function(wasmModuleId) {
/******/ 			var installedWasmModuleData = installedWasmModules[wasmModuleId];
/******/
/******/ 			// a Promise means "currently loading" or "already loaded".
/******/ 			if(installedWasmModuleData)
/******/ 				promises.push(installedWasmModuleData);
/******/ 			else {
/******/ 				var importObject = wasmImportObjects[wasmModuleId]();
/******/ 				var req = fetch(__webpack_require__.p + "" + {"./pkg/index_bg.wasm":"2baf8b587bc538554c03"}[wasmModuleId] + ".module.wasm");
/******/ 				var promise;
/******/ 				if(importObject instanceof Promise && typeof WebAssembly.compileStreaming === 'function') {
/******/ 					promise = Promise.all([WebAssembly.compileStreaming(req), importObject]).then(function(items) {
/******/ 						return WebAssembly.instantiate(items[0], items[1]);
/******/ 					});
/******/ 				} else if(typeof WebAssembly.instantiateStreaming === 'function') {
/******/ 					promise = WebAssembly.instantiateStreaming(req, importObject);
/******/ 				} else {
/******/ 					var bytesPromise = req.then(function(x) { return x.arrayBuffer(); });
/******/ 					promise = bytesPromise.then(function(bytes) {
/******/ 						return WebAssembly.instantiate(bytes, importObject);
/******/ 					});
/******/ 				}
/******/ 				promises.push(installedWasmModules[wasmModuleId] = promise.then(function(res) {
/******/ 					return __webpack_require__.w[wasmModuleId] = (res.instance || res).exports;
/******/ 				}));
/******/ 			}
/******/ 		});
/******/ 		return Promise.all(promises);
/******/ 	};
```

## Exposing the GCode Crate with WebAssembly

## Creating Idiomatic TypeScript Bindings

## Testing, Examples, and Benchmarks

## Conclusions

[gcode-rs]: https://github.com/Michael-F-Bryan/gcode-rs
[wiki]: https://en.wikipedia.org/wiki/G-code
[wa]: https://webassembly.org/
[malware-use]: https://www.zdnet.com/article/half-of-the-websites-using-webassembly-use-it-for-malicious-purposes/
[wasm-wg]: https://github.com/rustwasm
[ts-webpack]: https://webpack.js.org/guides/typescript/
[webpack-plugin]: https://www.npmjs.com/package/@wasm-tool/wasm-pack-plugin
[wbg-700]: https://github.com/rustwasm/wasm-bindgen/issues/700