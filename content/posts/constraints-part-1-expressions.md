---
title: "Geometric Constraint Solvers Part 1: Algebraic Expressions"
date: "2020-07-05T19:42:47+08:00"
draft: true
tags:
- Rust
- Geometric Constraint Solver
---

A really powerful tool in Computer Aided Design (CAD) is the ability to apply
*"constraints"* to your drawing. Constraints are a really powerful tool,
allowing the drafter to declare how parts of their drawing are related, then
letting the CAD program figure out how parameters can be manipulated in such
a way that

You can think of a constraint as some sort of mathematical relationship between
two or more parameters.

Some examples are:

- *"This interior angle is 45°"*
- *"That line is vertical"*
- *"Side A is perpendicular to side B"*

Graphically they'll be displayed something like this:

{{< figure
    src="https://raw.githubusercontent.com/solvespace/solvespace-web/dc2f3ed070d58eb827617633cd4bdc52b8c0ba00/pics/constraints-triangle-dim-2.png"
    link="http://solvespace.com/constraints.pl"
    caption="A constrained triangle in [SolveSpace](http://solvespace.com/)"
    alt="A constrained triangle in SolveSpace"
>}}

These constraints are declared mathematically, so a *"This line is vertical"*
constraint may be written as $line.start.x - line.end.x = 0$ and
$line.start.z - line.end.z = 0$ (assuming the $x$ axis is to the right and
the $z$ comes out of the page).

In response to input from the user (e.g. they click on the line and drag it
to the left), a constraint system will feed the perturbation into the system
of equations (e.g. the $line.start.y$ changes by $-0.1$ units) and based on
the available constraints and tie-breaking heuristics, it will figure out how
much each remaining variable must change. Execute at 60 FPS and you've got an
interactive, parametric CAD application.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/constraints
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}
