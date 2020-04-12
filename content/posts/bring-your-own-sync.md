---
title: "Bring Your Own Sync"
date: "2019-11-23T00:39:31+08:00"
draft: true
tags:
- Rust
---

The other day I was looking through *The Rust Nomicon* and came across
[this page][nomicon]:

> **Implementing Arc and Mutex**
>
> Knowing the theory is all fine and good, but the best way to understand
> something is to use it. To better understand atomics and interior mutability,
> we'll be implementing versions of the standard library's Arc and Mutex types.
>
> TODO: ALL OF THIS OMG

Which got me thinking, *how does someone go about implementing `Arc<T>`?*



[nomicon]: https://doc.rust-lang.org/beta/nomicon/arc-and-mutex.html
