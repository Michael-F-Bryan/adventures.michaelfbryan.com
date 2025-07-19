---
title: "Obsidian Tricks: Entity Notes"
date: "2025-07-23T12:00:00+08:00"
draft: true
tags: ["Obsidian", "Personal Knowledge Management", "Atomic Notes"]
description: |
   An entity is a person, place, or organization that you want to track in your Second Brain. By creating separate notes in your Obsidian vault for each entity and using the power of backlinks, you can create a rich, interconnected knowledge base.
---

An entity is a person, place, or organization that you want to track in your *Second Brain*. By creating separate notes in your *Obsidian* vault for each entity and using the power of backlinks, you can create a rich, interconnected knowledge base.

### The Power of Backlinks

When you create a dedicated note for an entity like `[[Michael Bryan]]` or `[[Wasmer]]`, every time you mention that entity in any other note, Obsidian automatically creates a backlink. This creates a **dynamic, interconnected web of knowledge** that reveals patterns and connections you might not have noticed otherwise.

#### Example Benefits:

**Before Entity Notes:**
- You write about a meeting with Michael Bryan in your daily notes
- You write about Wasmer's product in a project note
- You write about Michael's advice in a career planning note
- These mentions remain isolated and disconnected

**After Entity Notes:**
- All mentions of `[[Michael Bryan]]` are automatically linked
- His entity note shows backlinks to every conversation, meeting, and reference
- You can instantly see the full history of your relationship and interactions
- Patterns emerge: "I seem to ask Michael about career advice frequently"
- Context is preserved: "That Wasmer meeting was right after Michael joined the company"

### The Network Effect

The more entity notes you create, the more valuable your entire vault becomes. Each new entity note increases the potential for meaningful connections, and each new mention strengthens the existing network. This creates a **compounding effect** where your knowledge management system becomes increasingly valuable over time.

Entity notes work synergistically with other PKM practices:
- **Daily Notes**: Mentioning entities creates automatic relationship tracking
- **Project Notes**: Entity links provide context and stakeholder information
- **Meeting Notes**: Participants and organizations are automatically connected
- **Areas of Interest**: Entities reveal who and what organizations are relevant to each area

## Creating Your First Entity Note

### Step 1: Choose Your Entity Type

Your vault should contain three main types of entities:

- **People** (`entity/person`): Colleagues, family, friends, contacts
- **Organizations** (`entity/organisation`): Companies, institutions, groups
- **Places** (`entity/location`): Locations, venues, attractions

### Step 2: Use the Right Template

Start with the appropriate template from your Templates folder:

**For People:**

````md
---
Link:
LinkedIn:
GitHub:
Country:
tags:
  - entity/person
---

Work History:
-

Education:
-

## Meetings

```dataview
LIST
FROM #note/meeting WHERE contains(file.outlinks, [[]])
```
````

**For Organizations:**

````md
---
tags:
  - entity/organisation
Link:
LinkedIn:
Country:
GitHub:
---

> [!SUMMARY]
> TODO: write a one-line description of the company

Known Employees:

```dataview
LIST FROM #entity/person WHERE contains(file.outlinks, [[]])
```
````

**For Places:**

````md
---
Link: <>
Address: "42 Wallaby Way, Sydney, Australia"
tags: "#entity/location/attraction"
---

> [!SUMMARY]
> TODO: Write up a brief description

Opening Hours:
- xxx
````

### Step 3: Enrich with Context

The key difference between a good and poor entity note is **context**. Here's what transforms a basic template into a valuable knowledge asset:

#### Essential Elements:
1. **Summary**: Use a `[!summary]` callout to explain who/what this entity is and why it matters to you
2. **Relationships**: Link to other entities (`[[Michael Bryan]]` works at `[[Wasmer]]`)
3. **Personal Context**: Explain your connection and why this entity is relevant
4. **Background**: Include a brief background of the entity, including their employment history, achievements, and any other relevant information (LinkedIn is your friend here)
5. **Rich Metadata**: Include all relevant links (LinkedIn, GitHub, personal website, etc.) and aliases
6. **Dynamic Content**: Use dataview queries to show related meetings and notes

#### Example Transformation:

**Poor Entity (minimal):**

```md
---
tags: [entity/person]
---
Michael Bryan - software engineer
```

**Rich Entity (contextual):**

````md
---
aliases: [Michael, Mike]
LinkedIn: https://linkedin.com/in/michael-bryan-564889199/
Country: "[[Australia]]"
tags: [entity/person]
---

> [!summary]
> Sibling of [[Jeremy Bryan|Jeremy]] and [[Vanessa Bryan|Vanessa]]. Son of [[Hugh Bryan|Hugh]] and [[Leonie Bryan|Leonie]]. Boyfriend of [[Gabbey Parker]].

[[Myers-Briggs Type Indicator]]: ISTJ-A (Logistician - assertive)

Work History:

- [[Multiversal Ventures]]
  - Senior Software Engineer (March 2024 -)
- Senior Software Engineer at [[Wasmer]] (August 2022 - January 2024)
- Lead Software Engineer at [[Hammer of the Gods]] (February 2021 - August 2022)
- [[Wintech Engineering]]
	- Software Engineer (March 2017 - November 2020)
	- Software Engineering Intern (November 2016 - February 2017)

Extra-Curricular:
- Member of [[Communications Support Unit|CSU]] (November 2018 -)
	- [[Training Manager]] (September 2023 -)

## Meetings

```dataview
LIST FROM #note/meeting WHERE contains(file.outlinks, [[]])
SORT file.name
```
````

## Best Practices for Entity Management

### 1. **Start Simple, Build Over Time**
- Begin with the template and basic information
- Add details as you interact with the entity
- Let the note evolve organically through backlinks

### 2. **Maintain Consistency**
- Always use the same entity name format: `[[First Last]]` for people
- Use consistent tagging: `entity/person`, `entity/organisation`, `entity/location`
- Include aliases for alternative names or nicknames

### 3. **Focus on Relationships**
- Link entities to each other: `[[Person]]` works at `[[Company]]`
- Use dataview queries to show connections dynamically
- Update related entities when creating new ones

### 4. **Leverage Automation**
- Use dataview queries to show related meetings, notes, and people
- Let backlinks reveal patterns and connections automatically
- Keep contact information current but don't over-engineer

### 5. **Provide Personal Context**
- Always explain why this entity matters to you
- Include the story of how you encountered them
- Add personal experiences and interactions

## Common Pitfalls to Avoid

- **Minimal Information**: Just a name and website link won't provide value
- **No Relationship Context**: Isolated entities miss the network effect
- **Generic Descriptions**: Make it specific to your experience and context
- **Outdated Information**: Regularly review and update key details
- **Over-Engineering**: Don't create entities for every person you mention once

## Maintenance Strategy

1. **Regular Review**: Monthly check of key entities for outdated information
2. **Update Relationships**: When creating new entities, update related existing ones
3. **Expand Over Time**: Add new information as you interact with entities
4. **Use Graph View**: Periodically explore connections in the graph view
5. **Monitor Backlinks**: Check entity backlinks to discover new patterns

Remember: The goal is to create a rich, interconnected knowledge base that provides valuable context about the people, organizations, and places that matter in your life and work. Start small, be consistent, and let the network effects compound over time.
