---
title: "What Is PID?"
date: "2019-09-16T20:42:04+08:00"
draft: true
tags:
  - algorithms
---

PID, short for *proportional-integral-derivative* is a mathematical tool for
taking a measured input and a desired setpoint and figuring out an output which
will make the input closer to the setpoint.

The canonical example is a cruise control on a car. Ascending a hill would
lower the car's current speed (i.e. move the actual velocity away from the
desired velocity), the controller's PID algorithm would increase the throttle
to restore the measured speed to the desired speed with minimal delay and
overshoot.

{{% notice tip %}}
In practical terms, PID automatically applies accurate and responsive
corrections to a control function in order to minimise the error between the
desired input and its actual value.
{{% /notice %}}

<!-- We need MathJax to make the PID equation look pretty -->
<script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.1/MathJax.js?config=TeX-AMS-MML_HTMLorMML">
</script>