---
title: "Making Life Plans"
date: "2020-11-07T03:40:09+08:00"
draft: true
tags:
- Ramblings
---

So I recently handed in my resignation at my (former) job, and now I've got a
bunch of decisions to make.

A big part of my plan was to deliberately *not* look for new work during my
notice period. I wanted to take a break to allow for personal development and
passion projects, and help recover a bit of [my lost enthusiasm][motivation]
free from external stressors.

I've been really lucky with my circumstances and can afford to spend a month
or two pursuing things that interest me. It's even better if those things
help show off my skills and abilities to prospective employers.

# Passion Projects

Often once you reach the intermediate-advanced level the only way to keep
developing your skills is by spending thousands of hours in the job. There's
a distinct lack of resources that help you learn the difference between a
professional software engineer and an ordinary coder.

About the best I've come across is [Jon Gjengset's streams on
YouTube][jon-youtube].

A lot of the content I post on this site tends to be once-off experiments or
extended tutorials, chock full of technical details and comments explaining
the thought process behind different choices. Although it often leads to
longer articles than most are willing to read, I personally really like this
format because it helps bridge that gap between newbie and expert. Funnily
enough, Jon explains this sentiment really well in [*Why are my videos so
damn long?!*][long-videos]

With that all said, I'd also like to have something more tangible to show for
my efforts and there are a couple larger projects I'd like to work on now
that I'm taking a "break".

A topic that really interests me is embedded systems and computational
geometry (using computers to do 2D or 3D maths), and I've been thinking of
ripping the control system out of a cheap 3D printer and implementing my own.

My main reservations are that 3D printers are already fairly mainstream so will
be quickly dismissed by people, and that *I don't actually need a 3D printer*
for anything I do.

Then, one day I was procrastinating on YouTube when I ran across this really
cool polar plotter.

{{< youtube id="7_aS0PbP8HY" >}}

Something like this really appeals to me. It's similar to a 3D printer but with
lower precision requirements (i.e. it's okay if I cut corners),
 the idea of a plotter because you get something novel at the
end, using polar coordinates will add a nice twist to the kinematics, and
there are lower expectations around precision so it's okay if I cut corners.

Hopefully you'll hear more about this over the next couple months.

# Professional Development and Project Management Skills

My previous workplace was a small business with highly competent, passionate
office staff. This led to a looser management style where individuals were
given a lot of autonomy to do carry out their job in a way that would best
benefit the company.

I still think this style of management worked really well, especially for
ongoing operations which already have a well-defined scope of work and
tasking (i.e. sales, marketing, building repeat machines), but it has a
couple weaknesses when it comes to project work.

Namely, a lot of responsibility is put on each individual to make sure their
projects are progressing as planned.

My biggest regret is that the major software project I was tasked with
implementing dragged on forever due to very poor project management. While I
would consider myself to be very technically competent, this was my first
professional job and I didn't have any prior experience with managing a large
project... Something I didn't identify as issue until much later because I
thought I knew what I was doing (see the [Dunning-Kruger
effect][dunning-kruger]).

This "poor project management" can be broken down to a couple points:

- Poorly defined project scope and objectives
- Scope creep
- No quantifiable measure of progress or roadmap (i.e. *"we've implemented 82%
  of items in 12 months and will be done in 4 months"*)

The original project scope amounted to *"the previous version of our CAD/CAM
package is unmaintainable. Rewrite it, but better"*.

At the time I didn't know that there's more to planning a large software
project (it ended up being about 200k lines of code), so I never pushed back
to make sure we understood the requirements and business needs ([*Project
Charter*][charter]) or fleshed out the work to be done and its scope ([*Work
Breakdown Structure*][breakdown]).

The *Technical Manager* (senior-most engineer and head of engineering) helped
by acting as a sounding board, we would get together every week or two to
choose priorities and let him keep the project progressing. This didn't
really work in practice though, because we were so focused on the next
fortnight that we never looked at the bigger picture.

In retrospect I'm not quite sure how we convinced ourself that a single Word
document containing a list of feature names was sufficient for planning and
progress tracking. With no proper definition of "done" it's easy to see why
it felt like things were taking longer than they needed to, and how the
manager (also the primary bug tester and a very detail-oriented person) would
inadvertently contribute to scope creep.

Not being able to properly *quantify* the project's level of completion meant
the business was never confident it was ready to be seen by customers. The
business didn't help by continually moving the goal posts when they insisted
on adding big new features that would incentivise people to use the new
product over the previous version... Even if they had no idea what these
features were, other than 100% necessary before the product would be deemed
"ready for market".

While this whole section may sound like a rant (and okay, I'll admit there's
a bit more negativity than I usually express), there is a purpose to it. This
whole experience was a 30-month long lesson with several important takeaways:

- Figure out what work needs to be done and actually write it down, specifying:
  - The definition of "done"
  - What is and isn't in scope
  - Estimated amount of time/money/effort
- Understand the big picture
  - Know the different phases in your project's life cycle
  - Measure and *quantify* your progress
- Say something when it feels like the project is meandering without direction
- Sometimes a little process can be a good thing
- I like to play the "inexperienced newbie" card, relying on others to manage
  me and make sure the right things are done at the right time


# GitHub

# Final Words


[motivation]: {{<ref "/posts/motivation.md" >}}
[jon-youtube]: https://www.youtube.com/channel/UC_iD0xppBwwsrM9DegC5cQQ
[long-videos]: https://www.youtube.com/watch?v=KPbrI3xWdCg
[charter]: https://www.pmi.org/learning/library/charter-selling-project-7473
[breakdown]:https://www.pmi.org/learning/library/applying-work-breakdown-structure-project-lifecycle-6979
[dunning-kruger]: https://en.wikipedia.org/wiki/Dunning%E2%80%93Kruger_effect
