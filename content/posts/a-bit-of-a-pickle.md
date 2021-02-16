---
title: "A Bit of a Pickle"
date: "2021-12-01T08:00:00+08:00"
draft: true
tags:
- People Skills
---

A while back I got myself into a bit of a pickle.

I was 25 at the time and had quit my previous job as a Software Engineer at
Wintech to look for new opportunities. I'm not quite sure what my plans were,
or even if I had any proper plans at that point, but I got it into my head
that I would take a month or two off then look for a job which would recognise
me for what I'm *really worth*.

Fast-forward about 3 months and I've achieved nothing of note. Zip, Zilch,
Nada. Then all of a sudden people start contacting me for collaborations or
potential jobs.

There were a couple really interesting opportunities, but at the time I felt
the one most likely to eventuate and keep me gainfully employed was a job
from Wintech to convert Profiler 9 to "Profiler 8.2". This is where we would
re-skin the existing Profiler 9 to look as close as possible to Profiler 8.

I jumped on the opportunity and very quickly created a rough outline of the
work that needed doing and put together an ambitious timeline.

## The Problem

I started off really strong with a lot of momentum. The first task (redoing
toolbars) was completed exactly when I said it would be, but then I ran into
menus and the wheels just fell off.

The entire task was *massive* and I'd only budgeted 1-2 days for it. Add to
that the fact that a lot of the work was tedious (create new command, wire it
up to a menu item, find the code that should be called, tweak when it is
enabled/disabled, test, rinse and repeat x40 - soooo much busy work) and I
almost immediately fell into despair.

To fulfil the *"identical to Profiler 8"* requirement I felt like I had to do
things in a way that I don't agree with and that were actively decreasing the
quality of my work. Of course my previous implementation was subtly
incompatible with the way Profiler 8 wanted things to be done, so all of that
work needed to be thrown away and done again.

You can see how this might be a bit disheartening.

When I was originally negotiating this project I didn't properly think about
how I'd feel while doing it. I quit Wintech Engineering because I felt like I
was no longer being challenged and the entire industry's culture of risk
aversion and *"if it ain't broke, don't fix it"* was frustrating me. I *knew*
this deep down, but kinda disregarded it and figured I'd be able to soldier
on through.

{{% notice tip %}}
Don't be too eager to sign the contract. Before committing to anything, ask
yourself:

- Is this project in my best interest?
- What do you want to get out of it?
- Am I passionate about the topic?
- How will I *feel* while doing this?
- Can you soldier on through the undesirable parts? Do you want to?

If any of those questions raises a red flag, **address it**.
{{% /notice %}}

In the meantime, I'd already started negotiating (and committed to) a
freelancing gig with a startup in San Francisco. This job ticked all my boxes,

- I would be working as part of a team
- It would be a fast-paced environment
- The project would have lots of interesting technical challenges
- It used technologies I wanted to use, and most importantly
- Taking on the project would take my career in a direction I wanted it to go

The contrast between the two was like night and day.

I guess the root problem is that:

- I've committed myself to do something which I don't think I want to do
- I've committed myself to do something I really want to do
- I over-promised on the less desirable thing, and
- I'm not sure I will have the time or motivation to do both

## The Greater Context

Of course nothing happens in a vacuum and all of this was going on within the
greater context of me running my life.

### Goals and Aspirations

My core goals are to

- Work with a team of like-minded individuals on something I'm deeply passionate
  about
- Have a partner I can share my life with and always depend on
- Always be expanding my knowledge and tackling intellectually stimulating
  challenges
- Do things in the present which won't make future Michael sad/regretful

Something I've identified is that throughout my life I haven't really
followed things through to the end, and instead quit midway or taken the easy
way out.

Look at my unfinished engineering degree, the myriad of incomplete projects
on my GitHub, **Profiler 9**, the telemetry system I did for Curtin
Motorsport Team, the list goes on.

I don't really have anything I can point to and say *"I made that"*... and
that's a big thing to me.

If I want to be recognised for my intelligence and skill then I need to give
them tangible examples, and not just rely on my ability to make people think
I am intelligent through what I tell them.

### Mortality

Another thing that's been really weighing on my mind over the last 5 months or
so is that I only have a limited life span. Entropy always marches on and
everyone knows they'll die some day, but how many *know* know?

I've been alive for as long as I can remember, and contemplating the fact
that the day *will* come where I can no longer experience or interact with
the world fills me with pure terror. There's also nothing anyone can do to
prevent it, and that helplessness really sucks.

At least if there was a solution you'd have a small glimmer of hope and could
go through life without the helplessness and terror... Ah, ignorance is
bliss.

However, the thing I *can* control is how I go about my life today and the
experiences and memories I make along the way.

I really want my life to have meaning and a positive impact on everyone
around me. Some form of immortality through recognition wouldn't be bad,
either; I don't want to just fade into obscurity.

## Options

As I see it, there are only really two options here:

1. Keep going with the project, renegotiating the scope or timeline to come
   up with something more achievable
3. Walk away

{{< figure
    src="/img/brainstorm.jpeg"
    link="/img/brainstorm.jpeg"
    target="blank_"
    caption="Brain Dump"
    alt="Whiteboard split into two sections, &quot;Renegotiate&quot; and &quot;Quit&quot;, listing pros and cons"
>}}

### Renegotiate

The first option is to continue on with the project and just renegotiate the
scope or timeline. It's also the easiest in the short term because I won't
need to have any hard conversations.

It'll be a bit embarrassing that I misjudged the amount of work required, but
the project manager has already given me a way to deal with that by keeping
track of roadblocks I encounter along the way.

One thing about working for yourself is that you spend large amounts of time
at home with nobody but yourself for company. This means you aren't
distracted by others, but it also means that you don't have anyone to bounce
ideas off and lack the routine that comes with a normal 9-5 office job. Not
having the constant threat of a co-worker looking over to see you playing
games or wasting time makes it a lot easier to get distracted, even if they
wouldn't care or nobody ever looks.

The issue that really kicked off my doubts and triggered my despair was how
much I'd underestimated the menu task. I've since figured out a solution to one
of the tricky problems, so that should help unblock me... Now I've just got to
finish it off.

Continuing with the project would also be a pretty big deal for me. It'd mean
I've overcome my knee-jerk reaction to quit the moment things start getting
tough and am following through with something I've committed to.

This project has three main priorities:

1. The resulting application should be functionally identical to Profiler 8
2. The project needs to be completed ASAP
3. The codebase needs to be maintainable

We've kinda got one of those *"you have 3 options, choose 2"* situations, here.

If I were to take this path I would:

- Ask to revisit the timeline and re-evaluate how much work is required now
  that I have access to Profiler 8 and its source code
- Come in 3 days a week (Monday/Wednesday/Friday) under the pretence of
  addressing roadblocks early, having someone to bounce ideas off and
  establishing a bit of routine
- Work on the second project during my evenings and weekends

