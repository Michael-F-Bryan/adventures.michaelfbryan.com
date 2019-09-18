---
title: "Initial Motion System"
date: "2019-09-18T23:44:10+08:00"
draft: true
tags:
- adventures-in-motion-control
- rust
---

Now we've got [some simple automation][previous] code, lets start a proper
*Motion* system.

Most *Motion* systems are designed around a *"control mode"*, a fancy term for
*"what is the machine doing right now?"* Common control modes are:

- `Idle` - the default control mode, machines revert to `Idle` whenever they're
  not doing anything
- `Automation` - running an automation sequence
- `Recipe` - executing a job (a set of instructions for how to execute a job
  and the motion parameters that should be used is often referred to as a
  *Recipe*)
- `Manual` - manual movement, where velocity may be controlled via a handset
  or the user invokes a *"jog to position"* function

There are several ways to transition between control modes.

- An `AutomationSequence` can end and we transition to `Idle`
- The machine may encounter a fault (e.g. by hitting a limit switch)
  returning to `Idle` and latching some fault flag
- The user may send a recipe to the machine and press the *GO* button (switching
  to the `Recipe` control mode)
- The current recipe finishes successfully (transition to `Idle`),
- and many more...

This all combines to make an interesting state machine diagram.

{{< mermaid >}}
graph LR;
    A[Automation];
    I((Idle));
    R[Recipe];
    M[Manual];

    I-- Start Automation Sequence -->A;
    A-- Fault -->I;
    linkStyle 1 stroke:red;
    A-- Completed -->I;
    linkStyle 2 stroke:green;

    I-- GO -->R;
    R-- Recipe Finished -->I;
    linkStyle 4 stroke:green;
    R-- Fault -->I;
    linkStyle 5 stroke:red;

    I-- Jog -->M;
    I-- Handset Button Pressed -->M;
    M-- Handset Button Released -->I;
    linkStyle 8 stroke:green;
    M-- Jog Position Reached -->I;
    linkStyle 9 stroke:green;
    M-- Fault -->I;
    linkStyle 10 stroke:red;
{{< /mermaid >}}

[previous]: {{< ref "simple-automation-sequences.md#the-next-step" >}}
