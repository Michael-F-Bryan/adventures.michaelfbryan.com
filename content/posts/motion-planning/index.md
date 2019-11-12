---
title: "Motion Planning"
date: "2019-11-06T07:52:36+08:00"
draft: true
tags:
- adventures-in-motion-control
- rust
---

When we left off [last time][next-step] we'd created a `Translator` which
lets us parse [*dwell*, *linear interpolation*, and *circular interpolation*
commands][translator-cb] from G-code.

Now we need to process those commands and turn them into a motion plan that can
then be executed.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration. 

If you found this useful or spotted a bug, let me know on the blog's 
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/adventures-in-motion-control
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
[crate]: crates.io/crates/noise-gate
{{% /notice %}}


[next-step]: {{< ref "working-with-gcode.md#the-next-step" >}}
[translator-cb]: https://github.com/Michael-F-Bryan/adventures-in-motion-control/blob/a30bc0c6699c2dad12dc76674957ac45220bf17e/motion/src/movements/translator.rs#L201-L218