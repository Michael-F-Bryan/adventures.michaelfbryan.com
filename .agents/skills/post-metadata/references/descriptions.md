# Generating post descriptions

## Why this needs care

The `description` in a post's front matter is the highest-leverage text on the site that nobody reads while writing it. In this Hugo setup it feeds four surfaces at three different widths:

| Surface | Source | Budget |
|---|---|---|
| Google result snippet | `<meta name="description">` | ~155 characters |
| Open Graph / Twitter card | `og:description` | ~155–200 |
| Homepage "Recent posts" list | `truncate 180` | 180 |
| Posts index entries | `truncate 200` | 200 |

`themes/hugo-coder/layouts/partials/head/meta-tags.html` resolves it as `.Description | default .Summary | default .Site.Params.description`, so a post with no `description` falls back to `.Summary` — the rendered opening paragraph, heading-anchor text and all. That is why untouched posts ship meta descriptions containing the literal string "Link to heading".

RSS does not use this field; `index.xml` carries full rendered content. It is not a constraint.

**~155 characters is the binding number.** Write to it and the description renders whole on every surface. Longer and Google cuts it mid-word.

The character budget is a constraint, not the editorial objective. A description can fit perfectly and still sound like promotional copy that Michael would never say.

## Strategy

One sub-agent per article, Sonnet, using the prompt below. Work in batches of 5–10 so repeated phrasing is visible before it spreads across the archive.

After each batch, run the checker:

```sh
./.agents/skills/post-metadata/scripts/check.py content/posts/one.md content/posts/two.md
```

It enforces the 120–155 character band, sentence completeness, plain text, and corpus-wide uniqueness. It also warns on banned phrasing, title repetition, and near-duplicates.

Passing the checker is necessary but not sufficient. It cannot decide whether a description sounds like Michael, has manufactured stakes, blames an anonymous actor, or follows a setup-and-payoff formula. Read every proposed value and ask:

1. Would this sound ordinary if Michael said it to a technical peer who asked what the article was about?
2. Does it state the subject and distinctive scope without turning the article into a miniature trailer?
3. Are its specific nouns central to the article, rather than details chosen because they make the sentence sound vivid?
4. Does the batch vary naturally, or has every description inherited the same cadence?
5. Does it sound like ordinary technical prose rather than a compressed design document full of abstract benefits?
6. Is it a description rather than a title-like command such as "Run X to achieve Y"?
7. If the article is an owned account of values, career, experience, or working style, does the description use first person rather than profile or catalogue language?

Sonnet follows the editorial constraints more reliably than Haiku, but character counting is still not deterministic. When the checker reports a length error, reply in the same sub-agent session with the measured count and one of these correction prompts. Repeat at most three times, checking the result after every turn.

For a value over 155 characters:

```text
The description is {count} characters, so it fails the 120–155 character contract. Remove secondary details rather than compressing them. Preserve the governing subject and one distinguishing detail. Keep it as one plain declarative sentence that starts with the subject, never a command or a repetition of the title. Read the title followed by the description; if they make the same claim, rewrite from context the title omits. Do not add a hook, anonymous actor, blame, withheld payoff, or "Here's how" ending. Return only the revised description.
```

For a value under 120 characters:

```text
The description is {count} characters, so it fails the 120–155 character contract. Add one concrete, central detail from the article; do not add padding, a second sentence, or a generic benefit. Keep it as one plain declarative sentence that starts with the subject, never a command or a repetition of the title. Read the title followed by the description; if they make the same claim, rewrite from context the title omits. Do not add a hook, anonymous actor, blame, withheld payoff, or "Here's how" ending. Return only the revised description.
```

For another checker finding that is genuinely a defect, quote the measured finding rather than asking for a general improvement:

```text
The metadata checker reports: {finding}. Rewrite the description only enough to fix that defect while preserving its central subject and ordinary, non-promotional register. Keep it as one plain declarative sentence of 120–155 characters, start with context the title does not supply, and return only the revised description.
```

Warnings require judgement. Do not send a correction merely because the checker printed one; first confirm that it identifies a real problem in this description.

For a first-person article that came back as a profile, catalogue entry, or detached summary:

```text
This article is an owned first-person account, but the description keeps the author at a distance or narrates the act of writing. Rewrite it as a direct first-person statement of the actual experience, preference, or value. Do not begin with "I explain", "I describe", "I discuss", or "I reflect on". Preserve the article's scope and uncertainty; do not turn it into a biography, value stack, slogan, or sales pitch. Keep it as one plain declarative sentence of 120–155 characters and return only the revised description.
```

If three corrections still do not fit, discard that conversation and start fresh. Never make a malformed value authoritative merely because the model tried several times.

Series are another failure mode. *Adventures in Motion Control* has ten published instalments, and an agent seeing one in isolation will reach for the series framing every time. Series navigation is rendered elsewhere; each description must distinguish its own article.

Show the batch to the user before writing to any file.

## The sub-agent prompt

Pass this verbatim, with the article appended under a `## Article` heading.

```md
You are writing the `description` field for one post on Michael Bryan's technical blog. It becomes the post's Google search snippet, social-card text, and the short blurb on the site's index pages.

Read the article and return one description. No preamble, alternatives, explanation, or surrounding quotes — only the description text.

**Hard constraints**

- 120–155 characters including spaces. Silently count the final value and rewrite it until it fits.
- Write one complete sentence, normally 18–22 words. If it is too long, remove a secondary detail rather than using semicolons, fragments, or a second sentence.
- Start with a noun or noun phrase naming the subject. Never write an imperative sentence or begin with a command.
- Compare the draft with the title. Do not begin with the title, a plural form of it, or the same meaningful noun phrase; start with context the title does not supply.
- Read the title followed immediately by the description. If they sound like the same claim twice, rewrite the description around a problem, constraint, example, or trade-off the title does not name.
- Plain text. No markdown, surrounding quotes, or emoji.
- Australian spelling: behaviour, optimise, artefact, recognise.

**Editorial objective**

Write the plain, compact answer Michael might give a technical peer who asked, "What's this article about?"

State the article's central subject and the one detail that makes its treatment distinctive. Give the reader enough information to decide whether it is relevant without trying to sell the click. It is fine to reveal the method, result, or practical judgement when that is the clearest account of the article; do not withhold useful information to manufacture curiosity.

The register is conversational and technically precise, but restrained. Prefer an ordinary declarative sentence over a dramatic hook, balanced slogan, or copywriting payoff. Under-claim when the scope is personal or conditional.

**How to write it**

- Read the title, opener, conclusion, and the article's main technical sections before drafting.
- Identify the governing problem or subject, then the article's particular angle, method, or boundary.
- Prefer specific technical nouns when they are genuinely central. Do not promote a worked-example detail merely because it sounds concrete.
- Do not restate or paraphrase the title. The title is displayed directly above the description, so use the space to add scope or context. A title turned into a plural definition is still repetition.
- Use a subject-led declarative sentence, not an imperative that reads like another title.
- Prefer ordinary technical phrasing over compressed abstractions such as "makes concurrent coordination explicit and testable". Name the concrete boundary, mechanism, or constraint instead.
- When the article is primarily a first-person account of values, career, experience, or working style, use owned first person (`I`, `me`, or `my`). State the actual preference, experience, or judgement directly; do not narrate the article with "I explain", "I describe", "I discuss", or "I reflect on".
- Do not describe Michael from the outside, call the article "a personal reference", or turn it into a biography, catalogue entry, tidy value stack, or promise that every habit pays off.
- For neutral technical material, do not add first person or "Here's how I..." merely to manufacture personality.
- Contractions are natural but not mandatory.
- If the article is visibly of its time — an old Rust edition, a superseded API, or a tool that has since changed — say so plainly when that affects whether the article remains useful.
- If the post belongs to a series, describe what this instalment covers. Do not name the series or say "part 3 of".
- Do not cover the complete argument. When several details compete for space, retain the governing subject and one distinguishing detail, then stop.

**Avoid manufactured stakes**

Do not turn ordinary engineering history into an inciting incident followed by a promised payoff. In particular:

- no "X happened, then someone asked for Y. Here's how I fixed it" structure;
- no "the moment somebody forgets" or similar blame-oriented overstatement;
- no anonymous `someone` or `somebody` introduced only to create tension;
- no "Here's how I...", "Here's what happened", "and what I learned", or equivalent teaser ending;
- no implied call to click, reveal, journey, transformation, or curiosity gap.

Also avoid "This article explores", "dive into", "unpack", "delve", "comprehensive guide", "everything you need to know", "in this post we'll", "secret sauce", "living, breathing", "crucial", "essence", "seamless", "leverage", and "utilise".

**Calibration: what failed**

These descriptions obey the character limit and contain accurate details, but they are wrong for the site because they package ordinary engineering work as miniature trailers:

- "NewServer started five goroutines, then someone asked for graceful shutdown. Here's how I made a Go service's hidden architecture explicit."
- "Vendored ogen clients and OpenAPI schemas drift the moment somebody forgets a README instruction or hand-edits the output. Here's how I catch both."

Do not imitate their two-sentence problem/payoff cadence, anonymous actors, artificial immediacy, or "Here's how" ending.

This one is restrained but still fails because it merely turns the title *Run Your Code Generator as a Test* into a sentence:

- "Running a code generator from the test suite catches drift between authoritative schemas and generated output."

Start from context the title omits — in this case the maintenance trade-off, the two sources of drift, or what happens to the resulting diff — rather than repeating the title's instruction.

These two fail on reflective prose. The first sounds like an HR profile; the second sounds like catalogue metadata. Both keep the author at a distance instead of owning the judgement:

- "Michael works best with ownership and clear goals, favouring technical excellence and pragmatic solutions over unnecessary process or micromanagement."
- "A personal reference on professional values covering autonomy, pragmatism over cargo-culting, and why productive side-quests matter to good work."
- "I explain what I need to do good work well, including autonomy, honest feedback, and room for exploratory side-quests that pay off later."

The third example uses first person but still narrates the article and turns a qualified tendency into a promised payoff. First person should own the substance itself, not the act of explaining it.

**Calibration: target register**

These examples demonstrate the plain, factual register. They are not templates; vary the sentence shape according to the article.

- "Dynamic loading gives Rust applications a flexible plugin boundary but pushes memory safety across an interface the compiler cannot inspect."
- "A WebAssembly sandbox isolates uploaded code from the rest of a control system while keeping the boundary straightforward to test."
- "Entity notes give people, places, and organisations stable homes in an Obsidian vault, letting references accumulate around the same subject."
- "I work best with ownership, clear goals, and enough trust to solve problems properly, while keeping communication open when priorities change."

## Article

[article content goes here]
```
