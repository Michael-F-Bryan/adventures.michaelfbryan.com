# Assigning post tags

## Why this needs care

Tags are reader navigation, not search-engine keywords. This site links the Topics index from the main navigation, gives every tag its own archive, and shows article tags as part of the post context. Each tag therefore makes a promise: a reader who clicks it should find a coherent set of articles that reward the click.

The previous archive-wide overhaul is the calibration case. Blind per-article generation followed by mechanical tag reconciliation produced a keyword index:

| Published corpus metric | Generated proposal | Accepted result |
|---|---:|---:|
| Tag assignments | 209 | 136 |
| Unique tags | 100 | 40 |
| One-article tags | 67 | 10 |
| Articles with more than three tags | 44 | 0 |

Canonical spelling was not enough. The generated proposal still promoted incidental examples, broad professional labels, and every substantial subsection into tags. Fixing it required a deletion pass and restoring precise subjects that had been displaced.

Treat those numbers as a regression fixture, not a permanent quota. The corpus will grow. The useful invariant is that tags remain a small, controlled vocabulary whose archive pages have distinct reader value.

## Target shape

- Give an article **one to three tags**. Two is the normal shape: often a technology or domain plus the article's precise subject.
- Prefer an existing canonical tag when it makes the same promise to readers.
- Add a third tag only when it names another independently central subject, not merely a worked example, context, technique, or outcome.
- A singleton is a warning, not an automatic failure. Keep a precise one-article tag when dropping it would erase the article's actual subject. `Sandboxing`, `Reverse Engineering`, and `Third-Party Code` have all been legitimate examples on this site.
- Named sequences belong in Hugo's `series` taxonomy, not in `tags`.

The count is a forcing function. If four or five labels all appear supportable, decide which two or three best describe why someone would deliberately browse to this article.

## The selection test

For every candidate, ask:

> If a reader clicked this tag, would they expect and appreciate finding this article among the results?

Then apply these checks in order:

1. **Is it central?** The title, opener, argument, or a substantial share of the article should support it. A technology used in one code sample is not necessarily a subject.
2. **Is it a useful archive?** The label should name something a reader might deliberately browse, not a generic attribute such as `Thoughts`, `Tech`, or `Professional Development`.
3. **Does an existing tag make the same promise?** Reuse its exact spelling and casing. Do not split `G-Code`/`G-code`, `Vue.js`/`Vue`, or equivalent singular/plural forms.
4. **Would it duplicate another retained tag?** Related subjects may stay separate, but overlapping synonyms and broad/narrow pairs should not compete on the same article.
5. **What would be lost if it were removed?** Prefer the label that names the article's actual subject over a broad umbrella. `Extension Traits`, `Metaprogramming`, or `Unsafe Rust` is often more useful than `Systems Programming`.

Tag the article's argument, not everything it mentions. An article about a G-code parser written in Rust may warrant `Rust` and `G-Code`; it does not automatically warrant every protocol, data structure, or build tool appearing along the way.

## Preserve precise subjects

The archive review found a recurring failure: a precise central tag was removed in favour of broader or incidental labels.

Examples of what to preserve when the article supports them:

- `G-Code` over secondary implementation details such as WebAssembly message encoding;
- `Sandboxing` when isolation is the motivating constraint, even if testing also has a section;
- `Unsafe Rust` when raw pointers, FFI safety, or unsafe invariants are fundamental;
- `Extension Traits` or `Metaprogramming` when that is the technique being taught;
- `Career`, `Productivity`, or `Third-Party Code` when they name the governing problem better than languages mentioned as examples;
- a product or organisation name such as `Wasmer` when the article is specifically about it.

Do not preserve a historical tag merely because it exists. Preserve it when it still offers the clearest reader path.

## Separate series from subjects

Use front matter such as:

```yaml
series:
- Adventures in Motion Control
```

for a named sequence. The series taxonomy renders navigation between instalments and should carry the relationship that an old series-shaped tag previously approximated.

Series membership does not replace subject tags. An instalment still needs one to three tags describing what this particular article is about. Conversely, do not spend a tag on the series name once `series` records the relationship.

Do not assume a missing `series` field means the article is standalone. Check the title and opener for a named sequence, inspect explicit previous/next instalment links, and compare neighbouring posts with the live series taxonomy. Add series membership only when that evidence identifies a named sequence; ordinary links to related articles are not enough.

## Workflow

### 1. Inventory the live taxonomy

Generate the prompt-ready inventory from the repository root:

```sh
./.agents/skills/post-metadata/scripts/prompt-context.py
```

The script discovers the repository from its own location and prints the complete `## Canonical vocabulary` and `## Known series` sections. Paste its standard output over the matching placeholders in the sub-agent prompt. To inspect another checkout, run it through uv with `--repository`:

```sh
uv run --script .agents/skills/post-metadata/scripts/prompt-context.py \
  --repository /path/to/adventures.michaelfbryan.com
```

It inspects all post front matter and records:

- canonical tag spelling and casing;
- published usage count for each tag;
- drafts separately from published articles;
- series names and membership;
- current totals for assignments, unique tags, singletons, and articles above three tags.

Do not copy a static vocabulary from this document. The repository is the source of truth.

### 2. Understand each article before looking at its old tags

Read the title, opener, headings, conclusion, and enough body to identify the article's argument. Generate a small set of semantic subjects from the content first. Looking at the old tags too early anchors the review on historical accidents.

### 3. Reconcile against the corpus

Map each semantic subject onto the live canonical vocabulary. Keep related but independently browsable subjects separate; merge labels only when their archive pages would substantially overlap or confuse readers.

A per-article agent may propose candidates, but it cannot make the final taxonomy decision in isolation. It does not know whether a label creates a duplicate archive, a new singleton, or a series-shaped tag. The orchestrator owns reconciliation.

### 4. Run the deletion pass

Reduce every article to one to three final tags. For each retained tag, require a short article-grounded reason. Reject candidates supported only by:

- an incidental example or passing mention;
- the fact that the article itself is technical writing;
- a language used only in a comparison;
- a broad outcome such as performance, productivity, or architecture when the article teaches something more specific;
- one subsection among several unrelated subjects;
- a transient version number that belongs in the title or description instead.

### 5. Review in batches, then write

Show the user a manageable batch containing the path, existing tags, proposed tags, and short rationale before changing files. After approval, change front matter only. Do not modify article bodies while doing metadata work.

## The sub-agent prompt

Append the live canonical vocabulary, known series, and article under the named headings.

```md
You are proposing final `tags` and optional `series` metadata for one post on Michael Bryan's technical blog. Tags are reader navigation, not a keyword cloud. Every retained tag creates or joins an archive page and must make a clear promise to someone who deliberately clicks it.

Read the article and return JSON only in this shape:

{
  "tags": ["Canonical Tag"],
  "evidence": {
    "Canonical Tag": "One short article-grounded reason this is a central browse subject."
  },
  "series": null,
  "rejected": {
    "Plausible Candidate": "Why it is incidental, duplicative, too broad, or better represented elsewhere."
  }
}

**Hard constraints**

- Return one to three final tags. Two is the normal target.
- Use the exact spelling and casing from the supplied canonical vocabulary whenever an existing tag makes the same reader promise.
- Add a new tag only when it names a central subject that no existing tag represents honestly. A precise singleton is allowed when a broader label would erase the article's subject, but it must be called out in `evidence`.
- Each retained tag must be supported by the title, opener, argument, or a substantial part of the article.
- Do not tag passing mentions, implementation details, illustrative languages, generic outcomes, or every subsection.
- Prefer the precise subject over a broad umbrella: `Extension Traits` over `Systems Programming`, or `G-Code` over `Message Protocols`, when that is what the article is actually about.
- Use `series` for a named sequence and do not repeat the series name in `tags`.
- Use conventional display-ready labels, not phrases invented by summarising the article.

**Reader test**

For every tag ask: If a reader clicked this tag, would they expect and appreciate finding this article among the results? If the honest answer is only "the article mentions or uses it", reject it.

## Canonical vocabulary

[canonical tags with published usage counts go here]

## Known series

[series names go here]

## Article

[article content goes here]
```

The returned JSON is a proposal, not authority. The orchestrator must still compare it with the rest of the batch and run the corpus checks below.

## Mechanical checks

After each batch, run the checker:

```sh
./.agents/skills/post-metadata/scripts/check.py content/posts/one.md content/posts/two.md
```

It enforces the one-to-three limit, exact canonical spelling — it fails on case, punctuation, and singular/plural collisions anywhere in the archive, not just within the batch — and series names that have leaked into `tags`. It also prints the corpus totals: assignments, unique tags, one-article tags, and the maximum tags on any article. Compare them against the previous run.

What it cannot check, and you must:

- whether a new tag earns its own archive page, or a retained one still names the article's actual subject;
- whether two related tags have started competing for the same readers;
- whether a missing `series` field means standalone or unnoticed;
- that only the intended front-matter fields changed — read `git diff`.

Metrics diagnose drift; they do not decide relevance. Finish by reading the outliers: every new singleton, every article at three tags, every removed precise tag, and every proposed merge between related subjects.
