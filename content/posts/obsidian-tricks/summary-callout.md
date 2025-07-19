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

````md
---
aliases: Access Tokens
---

> [!SUMMARY]
> A token, typically in the [[JSON Web Tokens|JWT]] format, issued by a server
> when the user logs in that lets users make secure calls to an API server.

User tokens can be used by client applications to access protected resources on
a server on behalf of a user.

Anyone that holds an access token can use it. As such, you need a way to
minimize the fallout from a compromised access token. One method is to issue
tokens that have a short lifespan.

Here is an example access token that might be issued by [[Auth0]]:

```json
{
  "iss": "https://YOUR_DOMAIN/",
  "sub": "auth0|123456",
  "aud": [
    "my-api-identifier",
    "https://YOUR_DOMAIN/userinfo"
  ],
  "azp": "YOUR_CLIENT_ID",
  "exp": 1489179954,
  "iat": 1489143954,
  "scope": "openid profile email address phone read:appointments"
}
```
````

### Entities

From my note on *Anduril Industries*:

````md
---
aliases: Anduril
Link: https://www.anduril.com/
LinkedIn: https://www.linkedin.com/company/andurilindustries
Country: [[United States]]
tags: "#entity/organisation"
---

> [!SUMMARY]
> A [[Tech Company]] in the [[defence]] space that develop cutting-edge military
> technology.

## Etymology

Named after [Andúril](https://lotr.fandom.com/wiki/And%C3%BAril) from the
[[Lord of the Rings]].

> [!quote] JRR Tolkein
> Very bright was that sword when it was made whole again; the light of the sun
> shone redly in it, and the light of the moon shone cold, and its edge was hard
> and keen. And Aragorn gave it a new name and called it Andúril, Flame of the
> West.

Known Employees:

```dataview
LIST FROM #entity/person WHERE contains(file.outlinks, [[]])
```
````

### Educational Content or Web Clippings

Often used in conjunction with [Obsidian Web Clipper](https://obsidian.md/clipper).

```md
---
Link: https://dannb.org/blog/2024/obsidian-use-your-notes/
Author: "[[Dann Berg]]"
Published: 2024-03-20
Created: "[[April 10, 2025]]"
tags:
  - note/capture
  - source/article/clipping
---

> [!Summary] TL;DR:
> This article provides five practical methods for utilizing your notes
> effectively, emphasizing the importance of processing, revisiting, and
> publishing them.
>
> - Always process your notes after writing to enhance their clarity and usefulness.
>   This includes re-reading, formatting key phrases, summarizing, and tagging
>   relevant notes. Consider using [[Zettelkasten]] methodology for organization.
> - Implement a [[Random Note Friday]] to revisit old notes and integrate them
>   with current knowledge. Use the [[Random Note]] feature in [[Obsidian]] to
>   discover forgotten insights.
> - Utilize the [[Graph View]] in [[Obsidian]] to identify and connect lonely
>   notes with others in your vault, enhancing the interconnectedness of your
>   knowledge.
> - Add a `> [!Summary]` to notes for quick reference and organization. This
>   aids in creating a [[Dataview]] table for easy access to summaries across your vault.
> - Publish your writings to solidify your understanding and build an online
>   presence. Consider platforms like [[Medium]], [[WordPress]], or creating a
>   [[Hugo]] site to share your insights.

Congratulations. You’re now a diligent note-taker. Your [[Graph View]] makes
internet strangers green with envy. You’ve got systems upon systems, and
specific homes for every piece of information you want to squirrel away.

Now what?

...
```

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
