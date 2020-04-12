---
title: "How I Reverse Engineered the LastPass CLI Tool"
date: "2020-04-13T00:53:39+08:00"
draft: true
tags:
- Rust
- I Made a Thing
---

A couple days ago I was writing an install script for [my dotfiles][dotfiles]
and reached a point where I wanted to grab some secrets (my SSH keys) from my
LastPass vault and copy them to the file system.

This is easy enough to do using the browser plugin, or even when working with
their [command line tool (`lpass`)][lastpass-cli] in an interactive way, but
I found there was no way to ask `lpass` which files are attached to a secret,
and get the output in a machine readable format.

Like most self-respecting members of the open-source community, I
[filed an issue][issue-547] on their GitHub page and started digging into the
source code to find where changes might need to be made. That way I can make
the change myself if it's easy enough, or I'll be able to provide someone else
with a bit more information.

However, reading through the source code got me thinking. There currently
aren't any libraries for working with LastPass, and although the `lpass`
tool's source code is GPL'd and on GitHub, by reading the source code you can
quickly tell it was only ever intended as a command-line tool.

Soo..... Why not rewrite it in Rust?

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/lastpass
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## A Quick Note On Goals

In the long run, I'd like for this to be a fully-featured library for working
with a LastPass vault. Although, in the short term I'm going to make a beeline
for downloading and decrypting attachments, seeing as that was the original
inspiration for this endeavour.

Someone may want to create a nice command-line tool on top of the library, but
I don't have any intention of being that someone (for now, anyways).

I've also got a lot of experience writing FFI code, so I'm intending to write
bindings so the library is usable from Python (my dotfiles install script is
written in Python) and C. I might wait a bit to flesh out the crate's API
though, that way I'll have a better idea of how the bindings should be
consumed and it'll reduce unnecessary code churn.

The `lpass` tool has roughly three responsibilities,

1. Communicate with the LastPass HTTP API
2. Perform the appropriate crypto so we can encrypt/decrypt the LastPass vault
3. Use the file system and a daemon to allow caching of the vault and persist
   login sessions across multiple invocations of the `lpass` command (e.g. so
   you don't need to keep entering your master password every time)

As a library, the third point is usually left up to the frontend application
so we've already made our job easier.

I'd also consider the HTTP bit a solved problem. The [`reqwest`][reqwest]
crate provides a robust and fully-featured asynchronous HTTP client, and we
can leverage [`serde`][serde]'s serialisation superpowers to make sending or
receiving structured data a breeze.

I'm a little worried about the crypto side of things. On one hand, we don't
need to implement any cryptography routines ourselves (the [`aes`][aes] and
[`pbkdf2`][pbkdf2] crates already exist and are well-respected), but it's
easy to mess things up an accidentally introduce a security vulnerability.

I figure the best course of action here is to just copy what `lpass` do. If
my code generates byte-for-byte identical input and output, we should be as
secure as `lpass` 🤷‍

## Baby Steps

<!--
    TODO: write about
    - Download the lastpass/lastpass-cli source code
    - Find how you log in
    - Backtrack to something easier
    - Implement logging out
-->

## Creating an Abstraction for Key Management

<!--
    TODO: write about
    - what keys are needed to log in?
    - how do I get the iteration count?
    - generate a login key
    - generate a decryption key
    - implement decryption routines for DecryptionKey
 -->

## Logging In

<!--
    TODO: write about
    - Create the login key
    - construct+send the post request
    - parse the results into a session
    - decode the private key
-->

## Parsing the Vault Into Memory
<!--
    TODO: write about
    - grab a copy of the vault
    - what are chunks?
    - what's with the big if-else chain?
    - parsing account info
    - parsing attachment metadata
 -->

## Downloading Attachments
<!--
    TODO: write about
    - download the attachment
    - decrypting the filename
    - decrypting the account's attachment key
    - using the attachment key to decode the attachment
    - turn it back into binary (from base64)
    - put it all together in an example application
 -->


## Conclusions

Oh, and I'm still working on [my dotfiles script][install-py] by the way.

I know it's massively over-engineered (after all, there's no kill like
overkill), but it's quite liberating to know that hitting a single button is
enough to install all the software I need, set up the correct keys and config
files, and apply little tweaks like a udev rule for rearranging my windows
and workspaces when the second monitor is plugged in.

{{% notice note %}}
Also I'd be keen to hear from you if you are a developer from LastPass! What
are your thoughts on my efforts? Has the analysis been accurate, and can you
spot any bugs or issues?

I feel like having an official library that lets developers work with the
LastPass API can enable a lot of benefits for customers, and I'd like to help
out on that front.
{{% /notice %}}

[dotfiles]: https://github.com/Michael-F-Bryan/dotfiles
[lastpass-cli]: https://github.com/lastpass/lastpass-cli
[issue-547]: https://github.com/lastpass/lastpass-cli/issues/547
[cleanup]: https://gcc.gnu.org/onlinedocs/gcc/Common-Variable-Attributes.html#index-cleanup-variable-attribute
[install-py]: https://github.com/Michael-F-Bryan/dotfiles/blob/master/install.py
[reqwest]: https://crates.io/crates/reqwest
[serde]: https://serde.rs/
[aes]: https://crates.io/crates/aes
[pbkdf2]: https://crates.io/crates/pbkdf2
