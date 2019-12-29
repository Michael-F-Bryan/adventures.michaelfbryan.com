---
title: "Implementing an Undo/Redo Mechanism"
date: "2019-12-29T20:11:44+08:00"
draft: true
---

Alongside copy and paste, being able to undo and redo changes is one of those
fundamental features that make interactive tools like editors and designers
possible. With the possibility of undo, users can explore and work without
fear of mistakes, because you can easily zoom back and forth in history.

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

[repo]: https://github.com/Michael-F-Bryan/arcs
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## What Problem Are We Trying To Solve?

Before we dive into the code it's worth looking at examples in the real world
and trying to come up with a definition for Undo and Redo.

### Example 1: The Text Editor

The text editor is arguably the simplest useful application which incorporates
an Undo/Redo feature.

The editor displays the contents of a file, and over time the user does
things which change the file's contents.

Some operations which a user may execute that are undoable:

- Write a word
- Delete a word
- Insert characters midway through the file
- Cut a span of text to the clipboard
- Paste some text from the clipboard to a particular location
- Transform a span of text to uppercase (e.g. [`U` in vim][vim-change-case])

However, there are other operations which Undo/Redo ignores:

- Saving a file
- Selecting some text
- Scroll the viewport
- Opening a menu
- Changing editor preferences

Additionally, you'll notice that some operations will be "grouped" when hitting
Undo or Redo. For example, if I type 10 characters in my editor I can press the
*Undo* button once to get back to the start, instead of pressing *Undo* once for
every character.

### Example 2: A Graphical Diagram Editor

The second example is a graphical diagram editor I occasionally use for
brainstorming and state machine diagrams called [draw.io](https://draw.io/).

Typical undoable operations are:

- Drawing a container (e.g. rectangle, circle, thought bubble)
- Moving a container around
- Drawing a connector
- Repositioning a connector's "grip" points
- Changing the text inside a container
- Setting an item's colour
- Creating additional pages

Operations which are ignored by the Undo/Redo mechanism:

- Selecting an item
- Saving or exporting the drawing
- Zooming in and out
- Enabling/disabling plugins

### Specifying the Problem Space

After looking at those examples, and by using the many years of experience using
software, we can start to specify some of the core responsibilities for an
Undo/Redo mechanism and the basic environment they're used in.

- The application is interactive and used by humans
- There is some main *Document* which the human is editing, where a document is
  something like a *File Buffer* (in a text editor like vim) or a *Project* in a
  circuit designer like *Altium*
- You can Undo and Redo operations which "change" the *Document* in a way that
  affects its semantic
- Operations which are purely to facilitate viewing by the user (e.g. scrolling)
  or future undoable actions (e.g. selecting a span of text) can't be undone
- Pressing *Undo* will revert the most recently executed operation
- Pressing *Redo* will do over the most recently undone operations
- You can't *Redo* more operations than you've undone
- (depending on the implementation) you can only *Undo* a finite number of times

[vim-change-case]: https://vim.fandom.com/wiki/Switching_case_of_characters