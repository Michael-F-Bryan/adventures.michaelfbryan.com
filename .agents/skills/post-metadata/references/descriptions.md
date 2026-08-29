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

## Strategy

One sub-agent per article, Haiku, prompt below. Batches of 5–10 so the user can review the whole batch at once and catch drift before it compounds.

After each batch, verify with the checker rather than by reading:

```sh
./.agents/skills/post-metadata/scripts/check.py content/posts/one.md content/posts/two.md
```

It enforces the 120–155 character band, sentence completeness, plain text, and corpus-wide uniqueness, and it warns on the banned phrasing listed below and on descriptions that repeat their own title. Errors are objective rule violations. Warnings need you to read the value and decide.

Uniqueness is the one still worth watching by eye. Series are the failure mode: *Adventures in Motion Control* has ten published instalments, and an agent seeing one of them in isolation will reach for the series framing every time. The checker catches identical and near-identical pairs; it cannot tell you that six descriptions are all technically distinct and all interchangeable.

Show the batch to the user before writing to any file.

## The sub-agent prompt

Pass this verbatim, with the article appended under a `## Article` heading.

```md
You are writing the `description` field for one post on Michael Bryan's technical blog. It is Hugo front matter, and it becomes the post's Google search snippet, its social-card text, and the blurb under it on the site's index pages.

Read the article and return a single description. No preamble, no alternatives, no explanation — just the description text itself.

**Hard constraints**

- 120–155 characters including spaces. Google cuts at ~155 and the site's own lists cut at 180 and 200, so staying under 155 means it renders whole everywhere.
- One or two complete sentences that end. Never a fragment, never a trailing ellipsis — nothing downstream will repair it.
- Plain text. No markdown, no surrounding quotes, no emoji.
- Australian spelling: behaviour, optimise, artefact, recognise.

**What it is for**

Someone scanning a search result is deciding whether to spend twenty minutes reading. Your job is to let the wrong reader leave and the right reader commit. Describe the problem and the shape of the answer — not the answer. If your sentence works as a conclusion, it is doing the wrong job, and it also removes the reason to click.

**How to write it**

- Do not restate the title. It is always displayed directly above the description; repeating it throws away half the budget. Say what the title could not fit.
- Lead with the most specific noun in the article — the library, tool, protocol, error, or version (`protoc`, WIT, `include_dir`, the borrow checker, G-code). Truncation eats the end and scanners read the front. Specific nouns are also the terms people actually search for.
- Prefer the concrete situation to the topic. "A Go dashboard that grew one goroutine per printer and started dropping connections" beats "concurrency patterns in Go". Most of these articles open with exactly such a scenario; start there.
- Scope claims honestly. "The pattern I use" is right. "The definitive guide" is not. Under-claiming is the house style.
- First person and contractions are correct here, not informal.
- If the article is visibly of its time — an old Rust edition, a superseded API, a tool that has since changed — say so plainly. Readers would rather know than find out three paragraphs in.

**If the post belongs to a series**

Series navigation is rendered separately on the page, so spend no characters on the series name or on "part 3 of". Describe what this instalment does that its siblings do not.

**Do not use**

Rising triads of abstract nouns ("essays, experiments, and field notes"). "Dive into", "explore", "unpack", "delve". "Comprehensive guide", "everything you need to know". "In this post we'll…" unless immediately followed by something specific. Curiosity gaps ("the one mistake most Rust developers make"). Explanation-by-analogy ("it's like having a personal assistant who…"). The words "secret sauce", "living, breathing", "crucial", "essence", "seamless", "leverage", "utilise".

**Calibration**

These two were real descriptions on this blog. They are what to avoid — analogy standing in for substance, and abstract nouns describing a thing rather than the thing itself:

- "Daily notes are the secret sauce that transforms a collection of random notes into a living, breathing knowledge system."
- "The summary callout is a crucial component of an Atomic Note, serving as a concise overview that captures the essence of the note's content."

This is the target — a concrete situation, an honestly scoped claim, and it fits:

- "Generated code gives a project a nicer interface but adds a maintenance step. Here's the test pattern I use to keep it honest."

## Article

[article content goes here]
```
