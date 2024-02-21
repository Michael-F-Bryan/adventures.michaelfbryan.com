---
title: "Embracing a New Chapter: My Farewell to Wasmer and the Journey Ahead"
date: "2024-01-30T17:00:00+08:00"
---

## Introduction

My journey at Wasmer has been a profound chapter in my life, filled with both incredible achievements and challenging moments. It's time for me to share an important decision about my career and the path I'm choosing to embark on.

## The Journey at Wasmer

Wasmer, though a small company, has enabled us to achieve some pretty impressive feats together.

My first project was to integrate WAI (our fork of `wit-bindgen` from around August 2022) with the Wasmer registry. This integration allowed users to publish WebAssembly libraries and we would automatically generate importable packages in Python or JavaScript that they could use to access the library's functionality. It's a little disappointing that our focus moved away from this integration ("[Wasmer Pack](https://github.com/wasmerio/wasmer-pack)") to [Wasmer Edge](https://wasmer.io/products/edge) so soon after we made the initial public release, but I guess that's inevitable for a small company with big ambitions.

More recently, I rewrote Wasmer's JavaScript SDK from the ground up to integrate with WASIX and the Wasmer registry. One of the features I'm particularly proud of was implementing a threadpool in the browser that allowed WASIX programs that had true multi-threading and were able to spawn sub-processes. This included a lot of tricky technical challenges, and forced me to dive into the nitty-gritty details of Web Workers, WebAssembly, `wasm-bindgen`, the WASIX filesystem, and more JavaScript/browser subtleties than I could have imagined.

There's no point creating something if people never figure out how to use it, and I believe I did a really good job with [the technical documentation](https://docs.wasmer.io/javascript-sdk) I created for the JavaScript SDK. A trick that worked really well is to add an entry to the "Troubleshooting" page every time someone ran into a common issue, rather than explaining things directly on Slack. The inspiration for this came from Alice Cecil in [her RustConf 2022 talk](https://www.youtube.com/watch?v=u3PJaiSpbmc&ab_channel=Rust) - *"If someone has a question and you can't find a link to their answer, your docs have failed"*.

## Decision to Depart

My decision to part ways with Wasmer was not made lightly. Over my 16 months with the company, I realised the alignment between my professional values and Wasmer's prevailing working environment and business objectives wasn't as harmonious as I had hoped. Over time this misalignment led to burnout, which caused me to step back and reconsider things.

It's important for me to acknowledge that this is as much about my own journey and understanding of my professional needs as it is about the company's culture and direction.

... That said, I think company culture and management *are* big contributors to me becoming so jaded and unmotivated. With things like this it's always useful to look at data and probably the most showing data point is that 10 people (11 if you count me) left the company in the period between August 2022 and January 2024 (17 months), of which at least 4 were directly asked to leave by the CEO. For a startup of 10 people, that sort of turnover is *insane*. During my exit interview (which I had to push for), the moment I brought up the company's turnover stats and suggested it might be because of the company's management, the *People Manager* (who's job is "Culture and Wellness") turned it back on me. Apparently people tend to demonise management when things aren't going so well, and that there was a point where I could have turned things around and fixed things, but I chose not to.

So yeah, it was a hard decision to leave because I loved my teammates and the project, but I'm confident it was the right one.

## The Road Ahead

I don't have any concrete plans just yet. Instead, I'd like to take a couple weeks to tinker on toy projects and reconnect with my passions.

Who knows, I might even get back to writing about technical things on this website again 🤔

To give people an idea of where my interests lie, I'm still super keen on WebAssembly and now I've got some free time I'd like to check out how far [The Component Model](https://component-model.bytecodealliance.org/) has progressed. I'm also really interested in machine learning and how you can use it in business settings (RIP [Hammer of the Gods](https://www.linkedin.com/company/hotg-ai/about/)). I wrote a CAD/CAM package for a CNC machine company in a previous life, and that's always left me with a desire to play with embedded systems.

As for technologies, with [over 7 years](https://users.rust-lang.org/u/michael-f-bryan/summary) of experience and 23.7 million crates.io downloads under my belt I'm fairly confident in calling myself a Rust expert. I've also started playing with Go again because it lends itself well to some of my toy projects, and of course I'll always need to use the ol' faithful TypeScript+React combo whenever I need to make a pretty frontend or dashboard.

## Message to the Team

To my colleagues at Wasmer, I've really enjoyed our time together and have learned so much from you.

While getting ready to leave, one thing that was really important to me was making sure you guys are set up for success. I'm aware of the challenges in other parts of the Wasmer codebase, and I've tried my best to make the handover as smooth as possible. The last thing I'd want is for my projects to turn into a puzzle for you to solve.

I was lucky enough to work with some people quite closely, and I want to share a quick message with them directly.

[Sebastien](https://github.com/ptitseb) - I've got a lot of respect for your knowledge and work ethic. I really enjoyed getting to know you and your sense of humour, and one day I hope I'll be able to consistently deliver and push things forward like you do.

[Rudra](https://github.com/dynamite-bud) - It makes me really happy to see how much you've grown since you first started at Wasmer, both as a software engineer, and more importantly, as a person. I'm really happy I got the opportunity to be your mentor and colleague, and can't wait to see where you go in the future.

[Christoph](https://github.com/theduke) - You are probably one of the most hardworking and talented programmers I've had the pleasure of working alongside. I've enjoyed rubbing shoulders with you at Wasmer and am very thankful for all the things you've taught me. Best of luck, mate.

[Ayush](https://github.com/ayys) - The unsung hero of Wasmer. I loved our pair programming sessions and working with you in person during the grand meetups. Thanks for sharing so much of your culture and teaching me how to eat rice with my hands 😛

To everyone else that I didn't get a chance to mention directly, I'd just love to say thank you for the wonderful time we've had together and I wish you the best of luck with your future endeavours.

## Closing Thoughts

Every journey has its ebbs and flows, and my time at Wasmer was no exception.

While it's time for me to seek new horizons, the experiences and friendships I've gained here will always resonate within me. I'm excited about what the future holds, and I look forward to crossing paths with the incredible people of Wasmer in this small, interconnected world of ours.


So long, and thanks for all the fish.

<small>
p.s. If you are looking to get a job with Wasmer or wanting to hear more before investing in the company, you can email me privately and I'd be happy to answer any questions you have.
</small>
