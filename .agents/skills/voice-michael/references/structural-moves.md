# Structural moves (Michael)

Use this reference for openings, transitions, closings, and paragraph length. All examples are from the analysed posts.

## Openings

Openings are **varied** but cluster into: personal/introductory, scenario-based, prior-art callback, and definition-plus-example. Few posts use a question or a single bold claim as the very first line.

### Personal statement of intent / reflection

- *"I thought it might be helpful to write down some of the core principles and values that guide my professional life..."*
- *"I've been writing technical content for years, and I'll be honest - I never really thought about *how* I was writing it."*
- *"Motivation is a funny thing."*

### Quotation or saying + personal stance

- Opens with a well-known saying about hard problems in CS, then: *"I believe the ability to correctly communicate an idea or concept... is by far the most important. It's also really hard."*

### Scenario / "Imagine…"

- *"Imagine you are implementing a calculator application and want users to be able to extend the application with their own functionality."*

### Prior article or reference + pivot

- *"A while ago someone [posted a question] on the Rust User Forums... I'd like to explore my take on things."*
- *"In [a previous article] we've talked about how you can avoid rewriting a library in Rust... But what about the times when you really *do* need to?"*

### Definition + canonical example

- *"PID, short for *proportional-integral-derivative* is a mathematical tool..."* *"The canonical example is a cruise control on a car."*

### Received wisdom + concrete trigger

- *"One of the first things I learned when programming professionally is that *global variables are bad*... the other day I was working with a 3rd party native library, and it reminded *why* these best practices come about."*

**Summary:** Openings favour **personal context** (why I'm writing, what I've learned), **concrete scenarios** ("Imagine…", "At $JOB…"), or **callbacks** to prior posts/forum threads. Bold one-line claims or direct questions are rare; the hook is usually a short paragraph that sets scene and stakes.

### Process or "how I do X" pieces

For process or how-to pieces, include a **minimal personal frame or stake** in the opening (why this matters to me, what I've learned the hard way, or one concrete consequence) before diving into the first step. Avoid starting with the first step only. Example: "I've wasted plenty of time chasing flakes" could anchor the opening; real posts use openings like "I thought it might be helpful to write down..." or "Motivation is a funny thing." So: before the first procedural step, add a short sentence that sets stake or context.

---

## Section structure (headings)

When the piece has **three or more distinct logical sections** (e.g. how-i-work's Core Values, Working With Me, Anti-Values; or a "how I debug" post with reproduce / narrow the cause / avoid rabbit holes), use **H2** (and H3 where needed) to chunk content. Do not publish a multi-section piece with no headings. Real posts use H2 for main sections, H3 for subsections; headings are short and scannable. Structure matches real posts when each clear part has a heading.

---

## Transitions

Transitions are **signposted** more often than seamless. Recurring phrases and section headings make the path explicit.

### Explicit signposting

- *"Let me show you what this looks like in practice, then we'll unpack the underlying principles."*
- *"Before we dive into specific techniques, we need to understand the cognitive frameworks…"*
- *"Now that we've established the concrete-first approach, let's talk about handling complexity…"*
- *"There's quite a lot going on here, so let's unpack it a bit."*
- *"Without further ado, here's a header file..."*
- *"Now before we go any further it is important to ask the question..."*

### Section headers as transitions

Section headings often carry the transition ("## Be Respectful", "## The Next Step", "## Conclusions"). Between sections, a short bridge sentence is common: *"That segues nicely into the next point... Don't forget to be respectful."*

**Summary:** Transitions use "Now that…", "Let's…", "Before we dive…", "Returning to…", and "There's quite a lot going on here, so let's unpack it." Section headings do a lot of the work. Abrupt jumps are rare.

**Optional:** Before the last major section of a short piece, a single signpost ("One more thing", "One last point") can match the signposted flow of real posts. Consider it when the piece has a distinct "final section" and no other transition into it.

---

## Closings

Closings mix **summary**, **callback**, **practical next steps**, **invitation to contact**, and the occasional **cultural reference**. Call-to-action is common but low-pressure.

### Soft caveat / reframe

- *"Don't think of these as hard and fast rules. Instead, think of them more like factors that may contribute to low motivation or reduced performance."*

### Reflective + practical next steps + rhetorical question

- *"Remember: the best technical writing serves readers' actual needs while building long-term understanding."*
- *"I mean, why else do we do any of this if not to help each other learn and navigate the world more effectively?"*

### Conclusions + invitation to contact

- *"If you noticed anything unsound (or just plain incorrect) in my code, please [get in contact] because I want to hear from you!"*

### Cultural reference + p.s.

- *"So long, and thanks for all the fish."* with p.s. offering private email for job/culture questions.

### Ideal vs real world + signature line

- *"In an ideal world all code would be perfect... Unfortunately, this *isn't* an ideal world..."*
- *"That's one of the things I really like about the language, more often than not *if it compiles, it works*."*

**Summary:** Closings often include a **short summary** of the main idea, a **callback** (metaphor, quote, or "if it compiles, it works"), and either **next steps / repo link** or an **invitation** (email, Reddit, issue tracker). Tone is wrap-up rather than hard sell.

**Short process / how-to pieces:** Even short process pieces usually have an **explicit closing move**: a brief summary plus a **one-line soft caveat or reframe** where appropriate (e.g. "Don't think of these as hard and fast rules"; "your experience may differ"). If the piece would otherwise end on a purely utilitarian summary, add one short reflective or caveat sentence so the close matches the wrap-up tone of real posts.

---

## Paragraph length

**Mixed:** short punchy sentences for emphasis or pivot, longer flowing sentences for explanation. Technical posts use longer blocks around code; lists and callouts break the flow.

- **Short punchy (one- or two-line paragraphs):**
  *"It's also really hard."* *"Don't be that guy."*
  *"Motivation is a funny thing."*
  *"But that's not how I think about problems. And apparently, it's not how most people learn either."*
  *"Success!"* *"LGTM 👍"*

- **Medium / flowing:** Most body paragraphs are 3–6 sentences: one or two ideas, then development or example.

- **Long (around code or lists):** Multi-sentence setup before code blocks, then explanation after. Paragraphs can run 8–12 lines when introducing or unpacking code.

**Summary:** Paragraph length is **deliberately mixed**. Single-sentence paragraphs are used for emphasis or transition. Longer paragraphs appear around code and detailed explanation. Lists and callouts keep the page from feeling like a wall of text.

---

## Cross-post patterns (quick reference)

| Element               | Pattern                                                                                                                                                                                            |
| --------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Openings**          | Prefer personal context, scenario ("Imagine…"), or prior-art callback over a lone question or bold claim. First line often sets who this is for and why it matters.                                |
| **Transitions**       | Signpost: "Now that…", "Let's…", "There's quite a lot going on here, so let's unpack it." Section headings carry a lot of the transition load.                                                     |
| **Closings**          | Often: brief summary + callback or metaphor + soft CTA (repo, Reddit, email, "let me know"). Short process pieces: add one-line soft caveat or reframe after summary. Tone is wrap-up, not salesy. |
| **Section structure** | Use H2/H3 when the piece has 3+ distinct sections; do not publish multi-section pieces with no headings.                                                                                           |
| **Paragraphs**        | Mix short (one sentence) for punch and longer (several sentences) for explanation. Use lists and callouts to break up density.                                                                     |

For more quoted openings, transitions, closings, and exemplary sentences, see [phrases-and-examples.md](phrases-and-examples.md).
