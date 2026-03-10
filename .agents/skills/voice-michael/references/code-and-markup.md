# Code and markup (Michael)

Use this reference when drafting technical or explanatory content. Michael's posts use code, tables, and structural markup as vehicles for explanation and to keep prose readable—not as decoration. Derived from analysis of the selected blog posts.

## Code blocks

### Role

- **Main vehicle for explanation** — Show a full or substantial snippet, then unpack in prose. Common pattern: code block → "There's quite a lot going on here, so let's unpack it" → stepwise explanation (e.g. writing-technical-content, pragmatic-global-state).
- **Inline with prose** — Short blocks (a few lines) to illustrate a single point immediately after a sentence.
- **Reference** — Complete examples (e.g. full `main()`, header file) the reader can copy; often with file-path comments at the top.

### Conventions

- **File-path comment** at top of block when it helps: `// core/src/lib.rs`, `// src/file_handle.rs`, `// vendor/tinyvm/include/tvm/tvm_htab.h` (plugins-in-rust, ffi-safe-polymorphism, how-to-riir).
- **Console/terminal blocks** — Shell commands and output in fenced blocks, preserving prompts and output (e.g. `cargo build`, `valgrind` output).
- **Long or noisy blocks** — Wrapped in `{{% expand "label" %}}` so the main narrative stays scannable (e.g. pragmatic-global-state C++ wall, how-to-riir linker errors).

### When code is light or absent

- Personal/reflective posts (how-i-work, farewell-wasmer, motivation, announcing-adventures) typically have no code blocks.
- turning-feature-requests uses lists and a figure; words-are-hard uses blockquotes and Mermaid, not traditional code.

## Inline code

- **Backticks** for: function/symbol names (`dlopen()`, `stateful_open()`), types/traits (`Box<dyn Function>`, `*mut FileHandle`), file paths (`core/src/lib.rs`), commands (`cargo run --example tvmi`), technical identifiers (`O(n^2)`, `RTLD_LAZY`, `#[repr(C)]`).
- **First mention** — New terms (function, type, command) introduced with backticks.
- **Searchable/copy-paste** — Anything the reader might search for or type gets backticks.
- **In list items** — Use backticks for commands, function names, and technical symbols even when they appear inside bullet or numbered list items (e.g. `git bisect run cargo test`, `cargo test`). Do not leave commands as plain text in lists.

## Tables and lists (instead of markdown tables)

- **No markdown table syntax** in the analysed posts. Comparisons and options use **parallel bullet lists** or **numbered lists** (e.g. "Building Up Approach" vs "Unpack Approach" as two bullet lists; error enums, steps, "questions to ask" as lists).
- **Numbered lists** when order matters: unpack steps, process steps, learning phases (e.g. 1. Present solution 2. Acknowledge complexity 3. Break down…; "1. Look through… 2. Write some tests…" in how-to-riir).
- **Bullet lists** for attributes, options, non-sequential items; unpacking one idea (one sentence then 5–6 bullets); questions to ask; short takeaways. Typical length 3–7 items.
- **Nested lists** — Bold category then sub-bullets (e.g. how-i-work: **Technical Excellence** with sub-bullets; obsidian-tricks: bold sub-heads with bullets).
- **Process and how-to** — Process posts often use **multiple or nested lists** (bold subhead + sub-bullets, or several short lists) to break steps and options. When the piece describes several strategies or sub-steps in one section, prefer nested bullets or a second list instead of one long paragraph. Avoid long paragraphs of sequential instructions where a list would be clearer.
- Lists **break up dense prose** and **structure the argument**: one claim or sentence, then evidence or implications as bullets.

## Shortcodes and callouts

**Syntax:** This blog uses **Hugo** shortcodes for callouts. Use `{{% notice type %}}` … `{{% /notice %}}` (e.g. `{{% notice tip %}}`, `{{% notice note %}}`), not Obsidian-style `> [!tip]` or other Markdown-only callout syntax. Output should be valid for Hugo.

| Type                       | Use                                                                                                 |
| -------------------------- | --------------------------------------------------------------------------------------------------- |
| **{{% notice note %}}**    | Repo/source link, "code on GitHub", issue tracker, meta comment.                                    |
| **{{% notice tip %}}**     | Practical advice (e.g. ownership/trust in how-i-work; "in practical terms" in pid-for-programmers). |
| **{{% notice info %}}**    | Scope or definition (e.g. "when I refer to *global state*…").                                       |
| **{{% notice warning %}}** | Safety or caveats (e.g. provenance, destroy-only-via-X).                                            |
| **{{% expand "label" %}}** | Long code or terminal output so the main narrative stays scannable.                                 |
| **{{< figure >}}**         | Diagrams, GIFs, screenshots — with `src`, `caption`, and `alt`.                                     |

**Process or how-to pieces:** Real process posts (how-i-work, plugins-in-rust, writing-technical-content) often include **at least one** notice (tip / note / info / warning)—e.g. tip for core takeaway, note for repo or meta. When drafting a process or how-to piece, consider one **tip** or **note** callout for the central lesson, a practical one-liner, or repo/meta, rather than defaulting to no callouts (unless the piece is deliberately minimal).

Other: `{{< x >}}` (tweet), `{{< mermaid >}}`, `{{% latex %}}` where needed.

## Other markup

- **Headings** — H2 for main sections, H3 for subsections; short and scannable. TOC where the post is long.
- **Bold** for key terms and list labels (e.g. **Technical Excellence**, **Static Dispatch**); **italics** for emphasis and informal wording (*it's complicated*, *good enough*).
- **Blockquotes** for quoted dialogue, definitions, standards, parables (e.g. words-are-hard Charlie/Sam story; C17 standard cite in ffi-safe-polymorphism).
- **Links** on first mention of a concept or tool; reference-style or inline; internal refs via `{{< ref >}}`.

## In practice

- Technical posts interleave: short prose → code or list → prose that unpacks → next idea. Not "wall of prose then wall of code."
- When explaining a concept, consider a small code snippet, a bullet list, or parallel lists instead of another paragraph. Tables are rare; lists do the work.
- Inline code for anything the reader might type, search for, or need to recognise.

## Relationship to other references

- [distinctive-techniques.md](distinctive-techniques.md) — "Unpack" pattern and concrete-first teaching rely on code and examples.
- [structural-moves.md](structural-moves.md) — Paragraph length and rhythm; lists and code blocks are part of that rhythm.
- [avoidances.md](avoidances.md) — No "code dump then minimal commentary"; code serves the explanation.
