---
name: post-metadata
description: Use when writing, backfilling, or auditing Hugo front-matter descriptions, search snippets, social-card text, series, or tags for posts in this repository.
---

# Post metadata

Front-matter metadata for this blog is chrome, not content. A description should be a compact, factual account of what an article covers, written in Michael's ordinary voice — not an abstract, a conclusion, or promotional copy. Tags and series are reader navigation.

## Read the reference for the field you are working on

| Field | Reference |
|---|---|
| `description` | [references/descriptions.md](references/descriptions.md) |
| `tags` and `series` | [references/tags.md](references/tags.md) |

Each one holds the measured constraints, the generation strategy, and the sub-agent prompt for its field. They are deliberately not repeated here. Do not generate metadata from this page alone.

## Tools

Both find the repository from their own location, so they run from anywhere.

| Script | Use |
|---|---|
| `scripts/prompt-context.py` | Print the live tag vocabulary and series list, ready to paste into a sub-agent prompt. |
| `scripts/check.py [post ...]` | Verify a batch against the rules in both references. Exits non-zero on errors; `--help` for options. |

## Orchestrator rules

These hold whichever field you are working on:

1. Work in batches small enough for the user to review in one sitting — five to ten posts.
2. Never regenerate the whole archive in one shot. The user asked for batches specifically so that drift and near-duplicates are caught while they are still cheap to fix.
3. Run `scripts/check.py` over the batch before showing it to anyone, and read the warnings rather than only counting them.
4. Show the user the batch — path, current value, proposed value — and wait for approval.
5. Apply approved changes to front matter only. Do not touch article bodies during metadata work.

A per-article sub-agent proposes. It cannot see the rest of the corpus, so it cannot decide: reconciling against the live vocabulary, migrating named sequences to `series`, and making the final cut are yours.

## House rules

- Australian spelling: behaviour, optimise, artefact, recognise.
- Contractions and first person are correct, not informal.
- Under-claim. "The pattern I use" beats "the definitive guide".
- The site's own voice guidance lives in the `voice-michael` skill; the references here assume it rather than repeating it.
