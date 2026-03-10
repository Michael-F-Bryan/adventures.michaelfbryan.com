# Distinctive techniques (Michael)

Use this reference for the techniques that make this voice recognizable: unpack-first, alternatives-before-committing, concrete-first teaching, callouts, evidence, and pattern interrupts. All examples are from the analysed posts.

## 1. "Unpack" as a named technique

**Pattern:** Present complete, working solution → Acknowledge complexity → Break down into digestible pieces.

- *"When you need to explain something complex, resist the urge to build it up piece by piece. Instead, show the complete solution first, then systematically break it down."*
- *"There's quite a lot going on here, so let's unpack it a bit."* (recurring after showing full code or a dense block.)
- Same move in practice: after showing the full header file, *"There's quite a lot going on here, so let's unpack it."*

## 2. Alternatives before committing

Ask first whether a fancy solution is needed, then list options (including "don't") before implementing.

- *"9 times out of 10 taking the more complicated option will require you to do extra work that wasn't needed in the first place."*
- *"Now before we go any further it is important to ask the question, *'do we actually **need** to come up with a fancy solution here?'*"*
- List options (Don't Allow Polymorphism → Pointer to Enum → …) then choose. Same move in global-state post: list of problems, then *"This necessitates a more pragmatic solution."*

## 3. Concrete-first teaching

**Pattern:** Show working code → Build understanding → Explain principles → Extend concepts.

- *"**Show working code → Build understanding → Explain principles → Extend concepts**"*
- *"See how the concrete example makes the abstract pattern immediately understandable?"*
- **Context hook over abstract opener:** Compare *"FFI-safe polymorphism is a technique for..."* with *"I was building a plugin system for my CAD application when I ran into a fundamental problem... Sound familiar?"*

## 4. Rhetorical devices

### Questions

- **Rhetorical/inclusive:** *"I mean, haven't we all been there?"*
- **Challenging the premise:** *"do we actually **need** to come up with a fancy solution here?"*
- **Reader-directed:** *"I don't know about you, but usually when I see this sort of code I'll start thinking of using [RAII]."*
- **Self-questioning as setup:** *"The engineer in me wants to find out why, and what I can do to fix it."*

### Analogies

- **Personified systems:** *"Pretend there's a customer named Charlie who wants to buy a dozen fidget spinners... From there, Charlie's computer sends the order to Sam (the web server)..."*
- **Personifying algorithms:** *"you don't say 'lines we've already visited are weighted higher', you say 'the algorithm really doesn't want to go over lines it's already visited'."*
- **Process analogy:** *"Kinda like changing your tyre while driving down the highway."*
- **Pragmatic shrug:** *"sometimes you've got to break a couple eggs to make an omelette 🤷‍"*

### Callbacks

- Repeated structural phrase: *"There's quite a lot going on here, so let's unpack it a bit."*
- Revisiting a principle: *"Remember: the goal isn't to use every technique in every article."*
- Softening absolutes: *"Don't think of these as hard and fast rules. Instead, think of them more like factors..."*
- Pop-culture sign-off: *"So long, and thanks for all the fish."*

## 5. Explicit ownership and deference

- **First-person framing:** *"I thought it might be helpful to write down..."*
- **Crediting others:** *"Joel Spolsky does a much better job of explaining this than I ever could."*; *"Ralf Jung does a much better job of explaining the subtleties of provenance so I'll just defer to his articles."*

## 6. Repo + issue tracker in callouts

Recurring block across technical posts:

- Code on GitHub.
- *"Feel free to browse through and steal code or inspiration"*
- *"If you found this useful or spotted a bug, let me know on the blog's [issue tracker][issue]!"*

## 7. Real terminal output and errors

- Including failure modes (panic/backtrace when plugin author forgets `export_plugin!()`).
- Compiler errors as documentation: *"And this is what `rustc` will emit:"* plus full error output.
- Valgrind / Miri as proof.

## 8. How evidence is presented

- **Anecdotes:** Personal project as hook; job-inspired work; feature-request story (*"I'd engineered myself into a corner!"*); teaching moment (radio course, map-drawing); career narrative with numbers.
- **Logic and structure:** List then implement; standards and citations (C17 for first-member pointer equivalence); prior art in callouts (*"This isn't a novel technique. It's actually already used by frameworks like Microsoft's *COM*, Gnome's *GObject*..."*).
- **Data and tangibles:** Concrete stats (turnover at Wasmer; crates.io downloads); concrete "done" criteria (*"Don't forget to come up with an unambiguous definition of *'done'*."*).

## 9. Pattern interrupts

- **Short, blunt sentences:** *"It's also really hard."*; *"After all, the simplest code is no code."*; *"Don't be that guy."*
- **Humour and pop culture:** Sign-off (*"So long, and thanks for all the fish."*); GIF caption (changing tyre while driving); casual confirmation (*"LGTM 👍"*).
- **Emoji (sparing):** 🤷‍, 🙂, 😛, 🤔.
- **Reframing difficulty:** *"Here's where it gets interesting..."* instead of "this is hard"; *"It only took about 50 lines, but we've..."* — understatement after a dense section.
- **Honest or self-deprecating asides:** *"I never really thought about *how* I was writing it."*; *"But here's the thing that took me embarrassingly long to realize"*; explicit invitation for private email.
- **Diagrams and visuals:** Mermaid state machine; problem visualised with caption; learning-curve figure.

## 10. Shortcodes and callouts

- **`notice` (tip/note/info/warning):** tip — core values, practical definitions, safety notes, design patterns; note — repo + issue tracker, assumptions, meta-commentary; info — definitions, examples; warning — provenance, unsafe, API contracts.
- **Other:** `expand` for big walls of code or linker output; `figure` for diagrams/GIFs; `mermaid` for state machines; `latex` for equations.
- **Role:** Scannability; meta (article demonstrates the principles it teaches); safety and contracts; reproducibility (code on GitHub + "spot a bug" → issue tracker).

---

## Summary: distinctive techniques

1. **"Unpack"** — Show the full thing first, then *"There's quite a lot going on here, so let's unpack it a bit."*
2. **Alternatives first** — Ask "do we need this?" then list options (including "don't") before implementing.
3. **Concrete-first teaching** — Working code or scenario before abstract explanation; context hook over jargon-led openings.
4. **Structured callouts** — tip/note/info/warning for asides, repo links, safety, and meta-commentary; expand for long code/errors.
5. **Evidence mix** — Anecdotes (CAD, radio course, Wasmer), concrete numbers where they matter, and citations (standards, Joel Spolsky, Ralf Jung).
6. **Pattern interrupts** — Short declarative lines ("It's also really hard." "Don't be that guy."), pop-culture sign-offs, rare emoji, and reframing difficulty as "interesting".
7. **Reader-facing invites** — Issue tracker, "let me know", Reddit thread, private email for sensitive topics.
8. **Real artifacts** — Terminal output, compiler errors, Valgrind/Miri, and GIFs used as part of the argument, not decoration.
