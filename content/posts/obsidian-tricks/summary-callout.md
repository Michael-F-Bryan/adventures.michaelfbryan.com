---
title: "Obsidian Tricks: The Summary Callout"
date: "2025-07-19T22:36:07+08:00"
tags: ["Obsidian", "Atomic Notes"]
---

{{% notice note %}}
The [`[!summary]` callout](https://help.obsidian.md/callouts#Supported+types) is a crucial component of an *Atomic Note*, serving as a concise overview that captures the essence of the note's content. This section at the beginning of each note helps readers quickly grasp the main concept and decide whether to read further.

Feel free to use this article as a prompt to generate your own summary callout 😉
{{% /notice %}}

## Purpose and Structure

- **Quick Overview:** Provides readers with essential information without requiring them to read the entire note
- **Placement:** Always at the top of the note, after *Front Matter* (if present)
- **Format:** Uses the blockquote syntax with callout type: `> [!summary]` (variations like `[!SUMMARY]` or `[!Summary]` are acceptable)
- **Length:** Typically 1-3 sentences or 3-5 bullet points for complex topics

## Content Guidelines

- **Focus:**
   - Capture the core idea without including supporting details
   - Answer "What is it?" and "Why is it important?"
   - Include key relationships to other concepts when relevant
- **Style:**
   - Clear, direct, and professional tone
   - Active voice and present tense
   - Avoid jargon unless essential to the concept
- **Links:**
   - Include essential `[[wiki-links]]` to related core concepts
   - Don't overload with links - only the most relevant ones
- **Formatting:**
   - Use emphasis (*italics* or **bold**) for critical terms
   - Include code snippets in backticks for technical terms
   - Break complex summaries into bullet points for readability

## Context-Specific Patterns

### Technical Concepts

{{% notice example %}}
A `[[Git]]` branch is a lightweight, movable pointer to a `[[commit]]`, enabling parallel development streams within a `[[repository]]`. `[[Branches]]` allow developers to work on features or fixes independently without affecting the main codebase.
{{% /notice %}}

### Processes and Procedures

{{% notice example %}}
The `[[Code Review]]` process is a systematic examination of code changes before they are merged into `[[the main branch]]`. It ensures code quality, knowledge sharing, and early bug detection.
{{% /notice %}}

### Educational Content or Web Clippings

Often used in conjunction with [Obsidian Web Clipper](https://obsidian.md/clipper).

{{% notice example %}}
This tutorial covers the fundamentals of `[[React Hooks]]`, including:
- Understanding the hooks lifecycle
- Common hooks (`useState`, `useEffect`)
- Creating custom hooks
Prerequisites: Basic `[[React]]` and `[[JavaScript]]` knowledge.
{{% /notice %}}

You can generate it with the following prompt:

```jinja
{{"Create a structured summary of the article starting with 1–2 sentences
overviewing the key message, followed by key points covering insights,
arguments, supporting evidence, practical applications, and related concepts.
For each point, include wikilinks to things like products and tools, people and
companies, domain-specific terms, and other related concepts from my Obsidian
knowledge base using double square brackets (e.g. `[[concept]]`) where
applicable. Present the final summary as a single flat list of bullet points
(using `-`), without section headings. Nesting may be used (sparingly) for
sub-points."|callout:("Summary", "TL;DR:")}}

{{content}}
```

## Best Practices

- **Clarity:**
   - Use clear, concise language
   - Avoid ambiguous terms
   - Define acronyms on first use
- **Completeness:**
   - Ensure it can stand alone as a quick reference
   - Include all essential elements of the concept
   - Don't rely on external context
- **Consistency:**
   - Maintain uniform formatting across notes
   - Use similar structures for similar types of content
   - Follow established patterns in your knowledge base
- **Updates:**
   - Revise the summary when the main content changes
   - Keep links current and relevant
   - Refine based on how the note is used

## Common Pitfalls to Avoid

- **Too Long:** Summaries shouldn't be mini-articles
- **Too Vague:** "This note is about X" doesn't add value
- **Too Many Links:** Not every term needs to be linked
- **Duplicate Content:** Don't just copy the first paragraph
- **Missing Context:** Ensure it makes sense to first-time readers
