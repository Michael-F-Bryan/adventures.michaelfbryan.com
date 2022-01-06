---
title: "An Incremental Computation Engine"
date: "2022-01-06T10:19:56+08:00"
draft: true
tags:
- Rust
- Architecture
series:
- Laskea
---

- Experiment for work
- End goal is to create an IDE-like experience where we provide the user with
  diagnostics/feedback in realtime
- Excuse to try out different ways of tackling a problem
- Already used by some well-known projects like rust-analyzer and chalk

{{% notice note %}}
Everything written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug in the article, let me know on the
blog's [issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/laskea
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com/issues
{{% /notice %}}

## Overall Design

For this experiment we want to make an app which you can open in the browser and
use to define certain "rules". The app will then take any rules defined by the
user and try to evaluate them, noting down either a result or an error message.

Each "rule" has a label that can be used to refer to that rule, plus an
expression, where the supported expressions are

- a string constant
- a HTTP request, where the user can trigger the request and a response (or
  error) will be received asynchronously
- an equality check which tells you whether a previous rule evaluated to a
  specific string
- a getter which takes the result of a previous rule and extracts one of its
  properties

Just reading through that list, you can probably already imagine several failure
modes that we'll need to handle. Some of these are:

- Multiple rules with the same label
- A HTTP request which fails (404, invalid URL, etc.)
- trying to get the result of a rule which doesn't exist
- reading a property that doesn't exist

We can handle this by saying each rule evaluates to a `Value`, where a `Value`
is defined as

```ts
type Value =
    | { type: "number", value: number }
    | { type: "string", value: string }
    | { type: "boolean", value: boolean }
    | { type: "object", value: any }
    | { type: "indetermimate" }
    | { type: "error", value: string }
```

Of note, an `error` indicates an error has occurred and passes the error message
back to the caller. The `indeterminate` variant is reserved for situations
where the result of a rule isn't known because either the value isn't available
yet (i.e. the HTTP request), or it depends on the result of a rule which failed
(i.e. returned an `error` or `indeterminate` value).

## Naming Things

As we all know, there are 2 hard problems in computer science: cache
invalidation, naming things, and off-by-1 errors.

I'm assuming everyone has read the title of this article and
as you've probably guessed, *Laskea* isn't a word the typical English speaker will
see around the place. I've been hanging out with some Finns lately, so I thought
it might be cute to ~~bastardize~~ reuse one of their words.

*Laskea* means *evaluate* or *compute* in Finnish.

## The Engine

The `laksea-engine` crate is a Rust library that contains the core logic of our
application.

This contains things like the definition for what a *Node* is, how the result of
each node is calculated, and diagnostics that may be sent to the user (e.g.
*"Reference Error: `Foo` reads from `Bar.field`, but no such property exists"*).

All of this is wrapped up in a query system which will cache previous results,
and try very hard to only recompute things when it is absolutely necessary.

### Salsa

To quote the [Salsa][salsa] README, Salsa is

> A generic framework for on-demand, incrementalized computation.

It was originally developed by [Niko Matsakis][niko] for use in Chalk, the next
iteration of Rust's type checker, and took a lot of inspiration from `rustc`'s
existing query system. As you can expect, the way Salsa is implemented fits
quite well with modern compiler design.

The general premise is that your business logic is formulated as a set of
"queries", where each query is a pure function that takes some keys and
generates some outputs.

There are two kinds of queries, *Inputs* and *Functions*, where *Inputs* are
set by the caller to provide inputs to the entire system and *Functions* are
pure functons which use their keys and the result of other queries to compute
a value.

This is all pretty straightforward.

The thing that makes Salsa so special is that it will transparently track the
result of each query and use the fact that queries are pure (i.e. have no
side-effects) to aggressively cache previously computed values.

This caching is a lot smarter than the *"have my inputs changed"* strategy used
by tools like `make`. If an input is invalidated, any queries which depend on
that input are also invalidated, however if we re-run the query and find that
its result hasn't changed we can stop invalidating queries and avoid a bunch
of unnecessary work.

To use the `make` example, normally changing some whitespace in a core header
file will force you to recompile every `*.c` file that includes it, which then
forces you to re-link all binaries that use this `*.c` file. With Salsa, we
would notice that while the header file has changed its parsed AST is the same
and therefore nothing needs to be recompiled, cutting a potentially expensive
rebuild down to the 10ms or so it takes to re-parse the header file.

## WebAssembly Bindings

To make our engine accessible in the browser, we will need to compile it to
WebAssembly and expose a JavaScript-friendly API.

Luckily all the hard work is already handled by the Rust toolchain and ecosystem
so we only need to focus on writing the bindings.

Normally you just need to do `cargo build --target wasm32-unknown-unknown` to
compile a Rust crate to WebAssembly and everything will *Just Work*, however
WebAssembly has some pretty big limitations which restrict what your library can
expose. In particular, your library can only expose functions which use integers
and floats for the arguments and return values so it is impossible to send a
Rust object to JavaScript or send a JavaScript object or string to Rust.

A lot of these limitations will be resolved by the [*Interface Types
Proposal*][interface-types], but in the meantime we can use the
[`wasm-bindgen`][wasm-bindgen] crate to generate a lot of the necessary glue
code.

On top of that, we can use the [`wasm-pack`][wasm-pack] CLI tool to compile our
bindings to WebAssembly and generate a NPM package that can be consumed by
JavaScript.

## The Frontend

The UI for Laskea will be fairly simple - it's just a ReactJS web app you can
view in the browser.

### The UI

I'm not overly concerned about looks and developer experience for this
experiment, so the UI will be fairly minimal. It's essentially a page with rows
of nodes, where each row contains a list of text inputs and the exact inputs to
show will depend on which kind of node.

Maybe a picture might be easier to understand?

{{<figure
    src="../react-frontend.png"
    caption="The React Frontend"
    alt="The React Frontend"
>}}

Written as code, this might look like

```ts
const some_constant = "Hello, World!";
const response = await fetch("https://httpbin.org/ip").json();
const ip_address = response.origin;
const is_google_dns = ip_address == "8.8.8.8";
```

I've implemented most of Laskea up to and including the frontend, but I'm still
not sure how I want a node's result and/or errors to be displayed. You'll just
need to wait for the *Frontend* article to come out.

### The Build System

Under the hood the frontend will be written in TypeScript so we get nice things
like autocomplete and red squiggles in VS Code whenever there are any type
errors.

The world of web apps is a mess of complex inter-dependent build tools with
layers of plugin and abstractions and dependencies, then because configuring all
of this requires a lot of work people tools that write the boilerplate for you
or wrap all the configuration up in a single package. However, often you will
just want to tweak this configuration so people end up using hacks to inject
configuration into the the packages meant to configure the build tools.

A perfect example of this is React... Creating an empty React app using their
TypeScript template generates a about 70 lines of TypeScript and 30 lines of
configuration (the `tsconfig.json`).

```console
$ yarn create react-app laskea-frontend --template typescript
$ tokei
===============================================================================
 Language            Files        Lines         Code     Comments       Blanks
===============================================================================
 CSS                     2           51           45            0            6
 HTML                    1           43           20           23            0
 JSON                    3           94           94            0            0
 Markdown                1           46            0           26           20
 SVG                     1            1            1            0            0
 Plain Text              1            3            0            3            0
 TSX                     3           52           44            3            5
 TypeScript              3           21           14            5            2
===============================================================================
 Total                  15          311          218           60           33
===============================================================================
```

This seems pretty innocent, however what you don't realise is that
create-react-app uses "helper" scripts for building the project and configuring
Webpack.

Unfortunately, these helpers often aren't sufficient so you get packages like
[`craco`][craco] and [`react-app-rewired`][react-app-rewired] who's only purpose
is to monkeypatch create-react-app's "no config" config. That means we've got at
least 4 levels of "tools" - the TypeScript compiler or Babel transpiles
TypeScript to JavaScript, Webpack packages this up, `react-scripts` configures
webpack and injects plugins, and `craco`/`react-app-rewired` overrides
`react-scripts`.

If you want to know the *actual* amount of configuration required to build a
simple React application, you can use the `yarn eject` script.

```console
yarn run v1.22.17
$ react-scripts eject
NOTE: Create React App 2+ supports TypeScript, Sass, CSS Modules and more without ejecting: https://reactjs.org/blog/2018/10/01/create-react-app-v2.html

✔ Are you sure you want to eject? This action is permanent. … yes
Ejecting...

Copying files into /tmp/laskea-frontend
  Adding /config/env.js to the project
  Adding /config/getHttpsConfig.js to the project
  ...
  Adding /scripts/start.js to the project
  Adding /config/webpack/persistentCache/createEnvironmentHash.js to the project

Updating the dependencies
  Removing react-scripts from dependencies
  Adding @babel/core to dependencies
  Adding @svgr/webpack to dependencies
  Adding babel-loader to dependencies
  ...
  Adding webpack to dependencies
  Adding webpack-dev-server to dependencies
  Adding webpack-manifest-plugin to dependencies
  Adding workbox-webpack-plugin to dependencies

Updating the scripts
  Replacing "react-scripts start" with "node scripts/start.js"
  Replacing "react-scripts build" with "node scripts/build.js"
  Replacing "react-scripts test" with "node scripts/test.js"

Configuring package.json
  Adding Jest configuration
  Adding Babel preset

Running yarn...
[1/4] Resolving packages...
[2/4] Fetching packages...
[3/4] Linking dependencies...
warning " > @testing-library/user-event@13.5.0" has unmet peer dependency "@testing-library/dom@>=7.21.4".
warning "eslint-config-react-app > eslint-plugin-flowtype@8.0.3" has unmet peer dependency "@babel/plugin-syntax-flow@^7.14.5".
warning "eslint-config-react-app > eslint-plugin-flowtype@8.0.3" has unmet peer dependency "@babel/plugin-transform-react-jsx@^7.14.9".
warning " > tailwindcss@3.0.11" has unmet peer dependency "autoprefixer@^10.0.2".
[4/4] Building fresh packages...
success Saved lockfile.
Ejected successfully!

Staged ejected files for commit.

Please consider sharing why you ejected in this survey:
  http://goo.gl/forms/Bi6CZjk1EqsdelXk1

Done in 3.85s.
```

Let's check the number of lines again.

```console
$ tokei
===============================================================================
 Language            Files        Lines         Code     Comments       Blanks
===============================================================================
 CSS                     2           51           45            0            6
 HTML                    1           43           20           23            0
 JavaScript             13         1776         1266          369          141
 JSON                    3          195          195            0            0
 Markdown                1           46            0           26           20
 SVG                     1            1            1            0            0
 Plain Text              1            3            0            3            0
 TSX                     3           52           44            3            5
 TypeScript              3           91           68            7           16
===============================================================================
 Total                  28         2258         1639          431          188
===============================================================================
```

2258 - 331 = 1927 new lines.

WTF?

C projects require less configuration!

Sorry, rant over.

Anyways... if possible I'd really like to use [Parcel][parcel] to compile my
frontend's source code into HTML, CSS, and JavaScript that a browser can
consume. It tends to *Just Work* without any of the bs you get from other build
tools.

## Conclusion

[salsa]: https://github.com/salsa-rs/salsa
[niko]: https://github.com/nikomatsakis
[interface-types]: https://github.com/WebAssembly/interface-types/blob/7c01976facffee3b705ba76431ade602e9084edc/proposals/interface-types/Explainer.md
[wasm-bindgen]: https://github.com/rustwasm/wasm-bindgen/
[wasm-pack]: https://rustwasm.github.io/wasm-pack/
[parcel]: https://parceljs.org/docs/
[craco]: https://github.com/gsoft-inc/craco
[react-app-rewired]: https://github.com/timarney/react-app-rewired
