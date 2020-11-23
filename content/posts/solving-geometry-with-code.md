---
title: "Solving Math Problems With Code"
date: "2020-11-23T01:36:05+08:00"
draft: true
---

I created a CAD/CAM package at my previous job, and a very common task would
be to take some theoretical computational geometry algorithm and turn it into
code for use in the CAD system.

I eventually got quite good at this, so I'm going to write down the system I
came up with in the hope that others can gain insight.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/💩🔥🦀
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

<!-- Mention [line simplification][simplification] as prior art -->

## Step 0: Research

- Wikipedia
- Google
- Academic Papers
- Existing products

## Step 1: Thinking About the Public API

- No code exists in a vacuum
- What seams do I want to provide?
- What parts of the algorithm need to be controlled by the caller? (strategy
  pattern or dependency injection)
- Allow for flexibility and change later on (up to and including ripping out
  the existing implementation)

## Step 2: Initial Implementation

## Step 3: Integration

## Step 4: Review and Integration Testing

- Now you've integrated it in, was your original design correct? If not, how
  should it be changed?
- Make sure the happy path works
- Try a bunch of things a normie would do and start looking for edge cases
- Is this implementation intuitive?
- Do we need a v2?

## Conclusions

[simplification]: {{< ref "/posts/line-simplification.md" >}}
[law]: https://meta.wikimedia.org/wiki/Cunningham%27s_Law
