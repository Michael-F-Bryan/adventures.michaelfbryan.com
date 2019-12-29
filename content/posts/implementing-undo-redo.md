---
title: "Implementing an Undo/Redo Mechanism"
date: "2019-12-29T20:11:44+08:00"
draft: true
---

Alongside copy and paste, being able to undo and redo changes is one of those
fundamental features that make interactive tools like text editors and
browsers possible. With the possibility of undo, users can explore and work
without fear of mistakes, because you can easily zoom back and forth in
history.

If you are writing any sort of interactive application, having a robust
Undo/Redo mechanism is a fundamental part of the user experience. There's
nothing more frustrating than accidentally clicking the wrong thing or
pressing a key and not being able to take it back...except when hitting undo
doesn't revert the world to the way it was before the mistake, and then
pressing redo and undo a bunch of times causes the world to become more and
more broken (more on that later).

I've had to implement this a couple times in real world applications, so I
thought I'd take advantage of the Christmas period lull to write up different
ways to tackle this problem.

{{% notice note %}}
All code written in this article is part of my [`Michael-F-Bryan/arcs`
project on GitHub][repo]. Feel free to browse through and steal code or
inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

## What Problem Are We Trying To Solve?

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}