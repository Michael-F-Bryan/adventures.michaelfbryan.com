---
title: "Announcing Adventures in Motion Control"
date: 2019-09-01T16:27:15+08:00
categories:
- blog
tags:
- adventures-in-motion-control
---

This is the first installation in my *Adventures in Motion Control* series.

At `$JOB` we build industrial CNC machines, and while developing a simulator
for our machines I noticed a distinct lack of online resources on how
they work under the hood. Hopefully this series will address the situation.

## The Goal

The goal for this series is to develop a simulator which will accurately reflect
how an embedded motion controller is implemented internally. 

This motion controller will be designed to control a 3D printer, with the
eventual idea being to compile everything to *WebAssembly* so the simulator will
run in the browser and users can explore it using a basic web UI.

## Identifying Requirements and Identifying Subsystems 

The first step in implementing any project is to specify exactly what you want
it to do (and *not* do) and the constraints imposed by hardware.

This project will simulate a 3D printer. Most 3D printers have 3 orthogonal
axes (hence the 3D bit) controlled using stepper motors. The printer will
have a pre-defined "working area", with [limit switches][limit-switch] at the
ends of each axis to make sure we don't go past the end of travel.

The only way an outside user can interact with the printer will be via a
[RS-232 connection][rs-232] (which we will model as a simple, bi-directional
byte stream). RS-232, often referred to as *Serial*, provides no guarantees
around framing (breaking bytes into individual "messages"), detecting
corrupted data, or that the other end has actually received our message. This
will all need to be accounted for.

The printer won't have any other physical inputs (e.g. push buttons or sensors)
or outputs (e.g. an LCD display).

Jobs will be sent to the motion controller over the serial connection in the
form of a [gcode][gcode] program.

The motion controller will need to expose some of its internal state to the
user for diagnostic purposes.

Users should be able to inject "errors" to see how the simulator would react.

The motion controller should be able to execute pre-defined automation
sequences. For example, bed levelling and axis calibration.

The motion controller will have a limited amount of non-volatile memory (e.g.
[an on-board flash chip][flash]) which can be used for caching jobs and
settings.

The simulator *won't* need to support flashing new "firmware". This means we
won't need to worry about having a bootloader, or deal with all the complexity
around rewriting firmware in-place and worry about ["bricking"][bricking] our
simulator.

The motion controller won't have access to nice things like multi-threading and
may only have access to a small amount of RAM (e.g. 192KB).

## The Next Step

Now we've got a rough understanding of the project the next step is to start
implementing it. The way I like to do things is by stubbing out just enough of
the top-level architecture to get a *Hello World* working then dive into one
area, preferably something fundamental so other systems can start making
progress.

To see the code, check out the
[Michael-F-Bryan/adventures-in-motion-control][repo] repository on GitHub.

[limit-switch]: https://en.wikipedia.org/wiki/Limit_switch
[rs-232]: https://en.wikipedia.org/wiki/RS-232
[flash]: https://en.wikipedia.org/wiki/Flash_memory
[gcode]: https://en.wikipedia.org/wiki/Gcode
[bricking]: https://en.wikipedia.org/wiki/Brick_(electronics)
[repo]: https://github.com/Michael-F-Bryan/adventures-in-motion-control