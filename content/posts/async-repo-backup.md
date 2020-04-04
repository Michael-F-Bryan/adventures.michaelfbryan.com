---
title: "Creating Asynchronous Tools in Rust"
date: "2020-03-22T03:22:53+08:00"
draft: true
tags:
- rust
---

A couple years ago I created [a small utility][repo] which would create and
maintain a local copy of all the online projects I own or have expressed
interest in.

Having the source code for literally hundreds of cool things at your
fingertips is surprisingly useful. For one, it lowers the barrier to entry
when I want to see how something has been implemented (e.g. looking at the
code for `std::sync::Arc` to help answer a question on the Rust user forums).

It's also nice because I'll always have a copy of everything I've done in
case GitHub were to go away, or an excavator decides to dig in the wrong spot
and cuts the internet for the street... Don't laugh, it actually happened
in the first week of my first job as a professional coder 🙃

The utility itself is really simple:

1. Use the GitHub and GitLab APIs to find all repositories I (or an
   organisation I'm a part of) own, plus anything I've starred
2. For each repository, run `git clone` or `git pull` to make sure I've got an
   up-to-date copy in the specified backup folder (e.g. 
   `/mnt/github.com/Michael-F-Bryan/arcs` for [Michael-F-Bryan/arcs][arcs])

By now you're probably thinking to yourself *"but Michael, you've just spent
the last 3 paragraphs talking about how awesome this tool is. If it works so
well, what's the point of this article?"*

And yeah, it is a really nifty tool, but it's not perfect. You see...

- I own over 150 repositories on GitHub and have starred over 600. 
- GitLab is a bit better (maybe 100 projects?) because it's mostly work-related
  or private things that other people don't need to see
- Each API call and `git` command is run sequentially on a single thread using
  blocking IO
- Running the tool takes half an hour or more
- The whole GitLab side is broken and always errors out (I suspect their API 
  has changed since I first wrote this thing in 2017)

I'd also like to create a non-trivial project using async-await in Rust so
thought it'd be a good excuse for a rewrite.

{{% notice note %}}
The code written in this article is available [on GitHub][repo]. Feel free to
browse through and steal code or inspiration.

If you found this useful or spotted a bug, let me know on the blog's
[issue tracker][issue]!

[repo]: https://github.com/Michael-F-Bryan/repo-backup
[issue]: https://github.com/Michael-F-Bryan/adventures.michaelfbryan.com
{{% /notice %}}

## Planning

When starting a new project I always like to write down my requirements and
design goals before diving into any code, even if it's just a couple dot
points. 

That gives me an initial direction and lets me allocate resources by saying
*"yes we need an `AbstractSingletonProxyFactoryBean` here"*, or *"no, feature
X doesn't need to be configurable"*.

{{% notice tip %}}
It's fun to create elegant layers of abstraction or provide the user with
lots of knobs they can tweak, but it's also fun to get to the finish line
with something to show for your efforts.
{{% /notice %}}

### Requirements

Requirements are the things that are absolutely necessary. Not being able to
fulfill any of them is an immediate deal-breaker.

At the bare minimum, if we're creating a tool for backing up git repositories
we need to:

- give the user a way to tell our tool where it can find repositories
  - it *must* support [github.com][gh] and [gitlab.com][gl]
- ask those locations for all repositories matching our criteria (owned by a
  specific user, starred repositories, etc.)
- download a fresh copy of the repository if we've never seen it before, or
- fetch recent changes and fast-forward the local copy to the most recent 
  version

### Design Goals

Something to keep in mind is that I'm doing this in my own time, and because
I want to. That means I'm not working towards a deadline and can afford to do
things *The Right Way*, even if it might take a bit longer than the hackier
path which still fullfills the requirements.

I also like to take pride in my work 🙂

A big quality-of-life feature is meaningful diagnostics and graceful error
handling. Sometimes something can go wrong when running `git pull` (e.g.
there were changes in the directory and git doesn't want to overwrite them)
or somewhere along the line something unexpected happens (like a project not
having a `master` branch) and the application needs to handle that correctly.
Leaving a repository in a broken state or forcing the user to manually
troubleshoot is bad for user experience.

I als want to be able to do other things while the backup is going on in the
background. That means Youtube shouldn't start lagging because we're
saturating my laptop's WiFi with `git clone`s, and it shouldn't pin all CPUs
at 100%.

- Well-written code
- Robust error handling
- Good quality user feedback
- Use asynchronous programming to maximise parallelism
- Don't overdo it and starve the rest of the system of resources

[repo]: https://github.com/Michael-F-Bryan/repo-backup
[arcs]: https://github.com/Michael-F-Bryan/arcs
[gh]: https://github.com/
[gl]: https://gitlab.com/