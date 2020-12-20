---
title: "Implementing an Undo/Redo Mechanism"
date: "2019-12-29T20:11:44+08:00"
draft: true
math: true
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

It's a feature we all use hundreds of times a day, but have you ever stopped
to question how the Undo/Redo function works?

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
- If you've pressed *Undo* a couple times, executing an operation will change
  the *Document* and forget any previously undone operations (meaning you can't
  hit *Redo* to get back to before you started pressing *Undo*)

## Taking Snapshots

By far the easiest way to implement an Undo/Redo mechanism is by taking a
snapshot of the *Document* after every operation and store them in a list.

The implementation then looks something like this:

```rust
pub struct Document {
    // pretend this contains lots of important business data
}

pub struct UndoRedoBuffer {
    /// Snapshots of the last `n` document versions.
    snapshots: Vec<Document>,
    /// The index of the "current" snapshot to allow *Redo*-ing an operation,
    /// where earlier snapshots will have a lower `cursor` value.
    cursor: usize,
}

impl UndoRedoBuffer {
    pub fn execute<F>(&mut self, mut document: Document, operation: F) -> Document
        where F: FnOnce(&mut Document)
    {
        // remove all previously undone operations
        let _ = self.snapshots.drain(self.cursor..);
        // then quickly add a snapshot to the buffer
        self.snapshots.push(document.clone());
        // and update the document accordingly
        operation(&mut document);

        document
    }

    pub fn undo(&mut self) -> Option<Document> {
        if self.cursor == 0 {
            return None;
        }

        self.cursor -= 1;
        self.snapshots.get(self.cursor).cloned()
    }

    pub fn redo(&mut self) -> Option<Document> {
        if self.cursor == self.snapshots.len() {
            return None;
        }

        self.cursor += 1;
        self.snapshots.get(self.cursor).cloned()
    }
}
```

{{% notice note %}}
I haven't run this code, so I'm not sure if the ordering of operations is 100%
correct, or even that it compiles, but hopefully you'll get the gist...
{{% /notice %}}

This can be written in a variety of ways based on your language's preferred
programming paradigm, but the basic idea is the same. **Every time something
happens make a copy of the world so we can revert back later**.

This approach has one massive benefit. It's really easy to implement.

If you just need to get *something* up and running for a prototype, or need to
retrofit an Undo/Redo mechanism to an existing application that doesn't have one
(my sincerest condolences) then this is the approach I'd recommend.

That said, there are a couple drawbacks...

For starters, this isn't an overly *"elegant"* approach. If we're a text
editor and the user adds one line to a 1000-line document, we'll need to
store the original 1000 lines plus 1001 lines for the latest snapshot. That's
1000 lines of duplicated content, and keeping redundant copies of data feels
unnecessary. As software engineers we take pride in our work, and inelegant
solutions have a way of getting under your skin.

However, the more serious issue is to do with *Memory Usage*. Taking snapshots
of the entire document means it'll consume a *lot* of memory. The central
*document* your application is editing tends to take up a non-trivial amount of
memory on it's own, so snapshotting the entire document when only part has
changed tends to chew up a lot of memory.

Imagine a contrived example where the user opens a 100 line document then
adds another 100 lines to the end of a document, one line at a time. The
application's memory usage would look something like this:

{{% latex %}}
    memory\_usage_0 &= 100 * line\_cost \\
    memory\_usage_{N+1} &= memory\_usage_N + (memory\_usage_N + line\_cost) \\
    \therefore memory\_usage(n) &\approx O \large( n^2 \large) \\
    where ~ n&: \text{Depth of Undo/Redo buffer}
{{% /latex %}}

To make matters worse, when study common usage patterns (i.e. watch over
someone's shoulder as they use your software) you'll see the vast majority
of undoable operations are small incremental additions to the document. That
means the vast majority of memory usage will.

The easiest way to curb this runaway memory usage is by simply adding a limit
to the number of times users can press *Undo*. But again, that can feel quite
unsatisfying because you're adding artificial limits to what a user can do
because the developer chose a poor algorithm for implementing Undo/Redo.

This approach also involves a lot of copying, and when a `Document` may
contain tens of thousands of items (and in my line of work it's not
unheard-of for that number to go over half a million) just the act of
duplicating a `Document` after every change can cause the application to become
unusable.

## The Command Pattern

An alternative approach is to use something called the [*Command Pattern*][cmd].

The pattern itself is almost trivial. We're encapsulating a function call (or
in our case, two function calls) in an object so this object can be stored or
used to represent an operation.

In Rust parlance, it would look something like this:

```rust
pub trait Command {
    fn do(&self, document: &mut Document);
    fn undo(&self, document: &mut Document);
}
```

That way the `UndoRedoBuffer` can store a list of trait objects
(`Vec<Box<dyn Command>>`) and going forwards or backwards in the
`UndoRedoBuffer` is just a case of invoking the current `Command`'s `do()` or
`undo()` method on the `Document`.

```rust
pub struct Document {
    // pretend this contains lots of important business data
}

pub trait Command {
    fn do(&self, document: &mut Document);
    fn undo(&self, document: &mut Document);
}

pub struct UndoRedoBuffer {
    operations: Vec<Box<dyn Command>>,
    cursor: usize,
}

impl UndoRedoBuffer {
    pub fn execute<C>(&mut self, document: &mut Document, operation: F)
        where C: Command + 'static
    {
        operation.do(&mut document);
        self.operations.push(Box::new(operation));
    }

    pub fn undo(&mut self, document: &mut Document) {
        if self.cursor == 0 {
            return;
        }

        self.cursor -= 1;
        let op = &self.snapshots.get[self.cursor];

        op.undo(document);
    }

    pub fn redo(&mut self, document: &mut Document) {
        if self.cursor == self.snapshots.len() {
            return;
        }

        self.cursor += 1;
        let op = &self.snapshots.get[self.cursor];

        op.do(document);
    }
}
```

{{% expand "A ~~Rant~~ Note on Performance, Optimisation, and Virtual Dispatch" %}}
{{% notice info %}}
You may have noticed that we're using boxed trait objects (dynamic dispatch)
here instead of static dispatch, and it's common knowledge that dynamic
dispatch is a lot more expensive than static dispatch.

I can imagine someone's going to leap at the chance to propose a "better"
solution which uses complicated generics and type-level magic so LLVM can see
through all the layers of abstraction and generate super-performant inlined
calls tailored to each `Command`.

To which I would reply, *"yes your implementation is technically faster...
but you're kinda missing the point"*.

At most, a user may only trigger a `Command` maybe three or four times a
second (imagine they're hammering *Undo*), but the `Command::do()`
implementation itself may trigger hundreds of changes. It almost goes without
saying that this massively outweighs any performance improvements static
dispatch could provide. So if you want to improve performance your time is
better spent optimising `Command` implementations than removing dynamic
dispatch.

Another thing to take into account is developer time and mental overhead. Using
fancy tricks with generics and the type system is fun and can sometimes help
squeeze out every last drop of performance, but it also adds a lot of cognitive
load to users and reviewers of your API. Generics have a tendency to infect
other code with type variables and trait bounds, and adds a **lot** of
incidental complexity (see [*The Two Root Causes of Software
Complexity*][complexity]).

I often see this mentality on the Rust user forums, where someone gets
themselves tied up in lifetimes or makes their code unreadable because they
bent over backwards trying to avoid something "slow" like a `clone()` or dynamic
dispatch. I'm a big advocate of taking the pragmatic approach, **do the simplest
thing to solve your problem** and don't blindly follow performance advice from
cargo cultists. Later on if you identify a performance problem you can come back
and rewrite that area of code to be better, and after going through this process
a couple times you'll develop a deeper understanding of these sorts of things,
allowing you to know when something is actually necessary.

That said, when you finally realise you *do* need these sorts of performance
tricks it's reassuring to know they're there.

Okay, rant over. Now back to our regularly scheduled program...

[complexity]: https://pressupinc.com/blog/2014/05/root-causes-software-complexity/
{{% /notice %}}
{{% /expand %}}

This approach is a lot more appealing because you only store the information
necessary to execute or reverse an operation. If you were to move a chunk of
text around inside a file the `MoveText` command only really needs to contain
a handful of integers, namely the start and end indices for the selection, and
an offset to indicate where the text moves to.

When `Command`s only take up dozens of bytes, this approach becomes so cheap
that allowing "infinite" undos becomes not only feasible, it just makes
sense. It also allows you to get better memory usage than the "theoretical"
minimum of the sum of additions and removals because we're lazily
reconstructing the change every time instead of storing a copy of it.

... However, like most engineering decisions switching from *Snapshots* to
the *Command Pattern* comes with its own trade-offs. In this case we trade
developer time for runtime performance.

You see, every `Command` needs to have an `undo()` function. And because this
algorithm's correctness depends upon being able to `do()` an action then
`undo()` it to get back to *exactly* where we started, you end up needing to
write as many tests for a `Command`'s `undo()` as you do for its `do()`.

It may not sound like a big deal, but when you have 20 or 30 different
`Command`s this starts to get pretty repetitive. It also makes it easy to be
lazy and "accidentally" forget to write tests for `undo()` operation 🙄

Another problem is that it's often *impossible* to reverse an operation by
playing it backwards. For example, in a raster image editor like PhotoShop
applying a *Blur* to an area of the canvas will throw away information about
the pixels.

For these sorts of "lossy" commands the only feasible way to implement `do()`
and `undo()` is by taking a snapshot of the target area before and after a
change and blindly copying the changed data across.

## A Hybrid of Taking Snapshots and The Command Pattern

Okay, so by now we've seen two separate algorithms for implementing an Undo/Redo
mechanisms, both with their own strengths and tradeoffs.

It'd be nice if there was a way to get the ease of development associated
with taking snapshots, while also maintaining the memory usage
characteristics of *The Command Pattern*.

> We can solve any problem by introducing an extra level of
> indirection (... except for the problem of too many levels of indirection)
>
> <cite>[David Wheeler][indirection]</cite>

If you squint and tilt your head a bit, version control systems like `git`
are actually quite similar to our Undo/Redo mechanism. You have the current
state of the world, and a mechanism for applying and reverting changes to see
the state of the world at a different point in time.

This realisation presents a third Undo/Redo algorithm, we can execute a bunch of
changes and add *"diffs"* to the `UndoRedoBuffer`.

However, instead of making a copy of the world before and after a set of
changes have occurred like `git` would (expensive!), we can go one better and
record the changes as they are executed.

Phrased as a Rust trait, our `Command`s would look like:

```rust
// arcs/src/commands/mod.rs

pub trait Command {
    fn execute<W: World>(&self, world: &mut W);
}
```

The `World` trait is used to represent anything that looks like the world, as
far as our `Command` is concerned.

We'll be build on the [`arcs`][arcs] crate started in [Using the ECS Pattern
Outside of Game Engines][ecs] so we mean `World` in [the ECS
sense][specs::World] (i.e. a container with one or more `Entities` that can
have associated data in the form of `Component`s).

```rust
// arcs/src/commands/mod.rs

pub trait World {
    type EntityBuilder: Builder;

    fn create_entity(&mut self) -> Self::EntityBuilder;
    fn delete_entity(&mut self, entity: Entity);
    fn set_component<C: Component + Clone>(&mut self, entity: Entity, component: C);
    fn get_component<C: Component>(&self, entity: Entity) -> Option<&C>;
    fn delete_component<C: Component + Clone>(&mut self, entity: Entity);
}
```

This can be trivially implemented for the `specs::World` type to let us execute
`Command`s directly against a world (e.g. for setting up tests).

The magic comes when we create a `ChangeRecorder`...

[vim-change-case]: https://vim.fandom.com/wiki/Switching_case_of_characters
[cmd]: https://sourcemaking.com/design_patterns/command
[indirection]: https://en.wikipedia.org/wiki/Fundamental_theorem_of_software_engineering
[ecs]: {{< ref "/posts/ecs-outside-of-games.md" >}}
[arcs]: https://github.com/Michael-F-Bryan/arcs
[specs::World]: https://docs.rs/specs/0.15.1/specs/struct.World.html
