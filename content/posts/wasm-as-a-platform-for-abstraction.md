---
title: "WASM as a Platform for Abstraction"
date: "2019-12-07T17:25:07+08:00"
draft: true
tags:
- rust
- wasm
---

In a project I've been playing around with recently, we've encountered the
dilemma where you want to make it easy for users to write their own
application logic using the system, but at the same want to keep that logic
decoupled from the implementation details of whatever platform the
application is running on.

## What do you mean by a platform for abstraction?

This all sounds quite abstract and theoretical, so I'll give you a real life
example of how application logic and the underlying runtime can be successfully
decoupled.

At `$JOB`, one of our projects uses a proprietary motion controller as the
brains controlling a robotic system. The way you program this system is via a
custom *Domain Specific Language* (DSL). A simple program may look something
like this:

```bas
' check if there's anything at the entry sensor
IF input(3) = ON THEN
  ' make sure all further commands are sent to axis 5
  base(5)
  ' start the conveyor
  forward
  ' keep moving forward until we're in position
  WAIT UNTIL input(2) = OFF
  ' then stop the conveyor
  stop
END
```

While seemingly innocuous, I've seen those 4 lines of code require several
hundred lines of C to achieve the equivalent functionality.

- Reading an input may be done by communicating with a bank of IOs over an
  EtherCAT bus or I2C, possibly with multiple different types of IO device
  available at the same time
- Axis 5
- Axis 5 is actually sending messages to a servo drive over the EtherCAT bus
- Several programs can be running concurrently (the runtime handles pre-emptive
  multitasking) and that `WAIT UNTIL some_condition` statement lets you
  suspend the current program until a particular condition is satisfied

