# Sentence architecture (Michael)

Use this reference for sentence-level choices: length, variation, complexity, punctuation, fragments, and recurring structures. All examples are from the analysed posts.

## Length

**Overall:** Medium to long dominates; short sentences are used deliberately for emphasis, pivot, or punch.

### Short (≤ ~10 words)

Reserved for emphasis, pivot, or punch.

- *"Motivation is a funny thing."*
- *"It's also really hard."*
- *"Don't be that guy."*
- *"After all, the simplest code is no code."*
- *"So long, and thanks for all the fish."*
- *"LGTM 👍"*

### Medium (roughly 12–22 words)

Common for explanations and instructions.

- *"I thought it might be helpful to write down some of the core principles and values that guide my professional life."*
- *"The Rust language gives you a lot of really powerful tools for adding flexibility and extensibility to your applications (e.g. traits, enums, macros), but all of these happen at compile time."*

### Long (25+ words)

Frequent in technical or conceptual explanations, often with multiple clauses.

- *"Eventually, I realized that what felt natural to me - the way I naturally think through problems, acknowledge uncertainty, and build understanding - was apparently unusual in technical writing."*
- *"When you know something is going to be difficult, **warn readers before they encounter it:**"*

**Summary:** Average sentence length sits in the medium range. Long sentences carry detail and qualification; short ones mark rhythm breaks and emphasis.

---

## Variation (rhythm)

**Deliberate variation:** Short sentences often follow longer blocks to create emphasis or a change of pace.

- Short after long: *"It's also really hard."* — immediately after a multi-sentence paragraph on naming and communication. *"Don't be that guy."* — after describing the engineer who says *"it's...complicated"* and leaves it there.
- Medium/short alternation: *"So yeah, it was a hard decision to leave because I loved my teammates and the project, but I'm confident it was the right one."* — shorter, conclusive sentence after a dense paragraph.
- Lists broken by full sentences: bullet lists are often interrupted by a full-sentence comment (e.g. *"Don't think of these as hard and fast rules. Instead, think of them more like factors that may contribute to low motivation or reduced performance."*) to reset rhythm.

**Summary:** Length is varied on purpose: long for explanation, short for payoff or transition.

---

## Complexity

**Mix of simple, compound, and complex;** technical posts favour complex sentences with subordination.

- **Simple declarative:** *"This can be achieved using a technique called [Dynamic Loading][wiki]."* *"Dynamic loading is a mechanism provided by all mainstream Operating Systems where a library can be loaded at runtime."*
- **Compound (and / but / or):** *"We also can't rewrite the code to not use global mutable state because it's closed-source, and even then would require tens of developer-years of effort."* *"I'm someone who's productivity levels change wildly depending on my motivation levels."*
- **Complex (subordinate clauses):** *"Normally you'd just reach for a `Box<dyn std::io::Write>` here, but as we've already mentioned Rust's trait objects aren't FFI-safe, meaning we need to be a little more creative."* *"When you assume confusion indicates explanation failure rather than reader failure, you start thinking about problems differently."*
- **Main clause then qualification:** *"9 times out of 10 taking the more complicated option will require you to do extra work that wasn't needed in the first place."*

**Summary:** Declarative for facts, compound for contrast, complex for technical reasoning, with frequent "X, but/meaning/so Y" shapes.

---

## Punctuation

**Em dashes, commas, and parentheses** are used more than semicolons; punctuation supports asides and lists.

- **Em dashes:** For asides, clarification, or an extra thought.  
  *"Eventually, I realized that what felt natural to me - the way I naturally think through problems, acknowledge uncertainty, and build understanding - was apparently unusual in technical writing."*
- **Semicolons:** Rare; when present, they link closely related clauses.
- **Parentheses:** For examples, abbreviations, or short asides.  
  *"(e.g. traits, enums, macros)"* *"(i.e. we need to deal with mutation)"* *"(see the section on techno-babble)"*
- **Colons:** Introduce lists, explanations, or "here's how" moments.  
  *"Here's what typically happens when engineers write documentation:"* *"The idea is you create a struct which will act as an *\"abstract base class\"*, a type which declares an interface which other types inherit from and implement methods for."*

**Summary:** Em dashes and parentheses for asides, colons for structure, semicolons used sparingly.

---

## Fragments

**Fragments are used for emphasis and voice,** not avoided.

- **Imperative or quasi-imperative:** *"Don't be that guy."* *"Don't try to use techno-babble to satisfy your ego, it ostracises people and gives us a bad name."*
- **Trailing thought or aside:** *"Kind of like a stream-of-consciousness documentary of my problem-solving process."* *"So long, and thanks for all the fish."*
- **Single-line reactions or sign-offs:** *"LGTM 👍"* *"Success!"*

**Summary:** Fragments are a deliberate choice for punch, rapport, or closing a section.

---

## Signature structures (quick reference)

| Aspect | Pattern |
|--------|--------|
| **Length** | Medium default; short for emphasis; long for technical explanation. |
| **Variation** | Deliberate: short sentences after long blocks for punch or conclusion. |
| **Complexity** | Mix: simple for facts, compound for contrast, complex for reasoning. |
| **Punctuation** | Em dashes and parentheses for asides; colons for lists; semicolons rare. |
| **Fragments** | Used for emphasis, voice, and closing ("Don't be that guy", "LGTM 👍"). |
| **Openings** | Personal, scenario-based, or short hook then expansion. |
| **Transitions** | "Here's the thing", "There's quite a lot going on here, so let's unpack it", "Now that we've…", "Let me show you". |
| **Lists** | Bold lead-ins, numbered steps, "First… Then… Finally…". |
| **Closings** | Reflective summary, invitation to feedback, callback or sign-off. |

For more openings, transitions, closings, and quoted exemplars, see [phrases-and-examples.md](phrases-and-examples.md).
