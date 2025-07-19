---
title: "Obsidian Tricks: Daily Notes"
date: "2025-07-28T12:00:00+08:00"
draft: true
tags: ["Obsidian", "Personal Knowledge Management"]
description: |
   Daily notes are the secret sauce that transforms a collection of random notes into a living, breathing knowledge system. They're like having a personal assistant who remembers not just what happened, but when it happened and who was involved.
---

If you're new to Personal Knowledge Management, let me share something that took me years to fully appreciate: **daily notes are the secret sauce that transforms a collection of random notes into a living, breathing knowledge system**.

Here's the thing most people miss when they start with PKM—it's not about having perfect notes, it's about **connecting your notes to real moments in time**. Daily notes do exactly that. They're like having a personal assistant who remembers not just what happened, but **when** it happened and **who** was involved.

## The "Aha!" Moment: From Chaos to Clarity

Let me paint you a picture. Without daily notes, your vault might look like this:
- A meeting note about discussing project timelines with Sarah
- A capture note about some interesting article you read
- A random thought about a business idea
- Another meeting note with a different team

These notes exist in isolation. You have to manually hunt through everything to find connections.

**With daily notes, magic happens**. Every note automatically connects to a specific date, which means:
- You can instantly see what else was happening when you met with Sarah
- You remember what you were thinking about when you captured that article
- You can track how your business idea evolved over time
- You understand the context of decisions made in meetings

## How Daily Notes Actually Work (The Simple Version)

Every daily note in your vault uses a simple template that creates automatic connections:

```yaml
---
tags: [note/daily]
ISO Date: 2025-07-15
Year: "[[2025]]"
Month: "[[July 2025]]"
Week: "[[Week 29, 2025]]"
---
```

The real magic happens with this simple dataview query:

````markdown
## See Also
```dataview
LIST FROM [[]]
```
````

This one line automatically shows **every single note that mentions this date**. It's like having a time machine that shows you everything that happened on any given day.

Obsidian's [built-in backlinks feature](https://help.obsidian.md/plugins/backlinks) is sufficient, too, but using dataview lets you do some more interesting things like filtering or showing a table with metadata.

## The Four Ways Your Notes Connect to Time (And Why Each Matters)

### 1. **Meeting Notes** → Daily Notes: "Who Did I Talk To?"

When you create a meeting note, you include the date:

```yaml
---
Date: "[[July 15, 2025]]"
Attendees: ["[[Michael Bryan]]", "[[Sarah Johnson]]"]
Organisation: "[[TechCorp]]"
tags: [note/meeting]
---
```

**Why this is valuable**: Six months later, when Sarah mentions "Remember that thing we discussed about the project timeline?", you can:
- Go to Sarah's entity note
- See all your meetings with her
- Click on the specific date
- Instantly recall the full context of that conversation

This is **relationship context on steroids**. You'll never again have that awkward moment of "I remember we talked about this, but I can't remember what we decided."

### 2. **Capture Notes** → Daily Notes: "What Was I Learning?"

Every time you capture knowledge, you link it to when you learned it:

```yaml
---
Link: "https://example.com/article"
Author: "[[Author Name]]"
Created: "[[July 8, 2025]]"
tags: [note/capture]
---
```

**Why this is valuable**: Knowledge acquisition patterns become visible. You might discover:
- You learn best on Tuesday mornings
- Certain topics cluster around specific life events
- Your interests evolve in response to work challenges
- You can trace how one article led to a chain of discovery

### 3. **Project Planning** → Daily Notes: "What Was I Working On?"

When you plan projects, you reference specific dates:

```markdown
| Duration | 10 days, Friday [[September 1, 2023]] to Sunday [[September 10, 2023]] |
```

**Why this is valuable**: Project context becomes effortless. You can:
- See what other projects were competing for attention
- Understand why certain decisions were made
- Track how your priorities shifted over time
- Remember the external factors that influenced your work

### 4. **Entity Interactions** → Daily Notes: "When Did I Last Connect?"

When you mention people, places, or organizations in daily notes:

```markdown
## Random Notes
- Call to [[Lucas]] at 14:29 about [[LandSAR]] deployment
- Grocery shopping at [[Woolworths]]
```

**Why this is valuable**: This creates a **interaction timeline** for every person and organization in your life. Before your next meeting with Lucas, you can quickly check when you last talked and what you discussed.

## The Compounding Value: Why This Gets Better Over Time

Here's where daily notes become truly powerful — they create **compound value** that grows exponentially:

### Pattern Recognition

After a few months, you'll start noticing patterns:
- You have better conversations with certain people on specific days
- Your energy levels affect what type of work you do
- Certain topics keep coming up in different contexts
- Your network connections reveal unexpected opportunities

### Effortless Context Switching

When someone asks "What were we working on in March?":
- Go to the *March 2025* monthly note
- See all daily notes from that month
- Click on specific dates for detailed context
- Instantly understand what was happening

### Relationship Intelligence

Before meeting with anyone, you can:
- Check their [entity note]({{< relref "entity-notes" >}}) for background
- Review recent daily notes mentioning them
- Understand the current context of your relationship
- Prepare more meaningful conversations

## The Network Effect: Where Things Get Really Interesting

The combination of daily notes and [entity notes]({{< relref "entity-notes" >}}) creates something I call **temporal relationship mapping**:

```
[[Michael Bryan]] ←→ [[July 15, 2025]] ←→ [[Multiversal Ventures]]
```

This simple connection tells you:
- **Who**: Michael Bryan
- **When**: July 15, 2025
- **What**: Related to Multiversal Ventures
- **Why**: Check the daily note for context

Multiply this by hundreds of people, organizations, and dates, and you have a **living map of your professional and personal network** that shows not just who you know, but **when** and **why** you know them.

If I ever need to investigate something or synthesize my knowledge, I can open the vault up in [Cursor](https://www.cursor.com/) and it'll have all of the context it needs.

## Practical Daily Workflows (Start Here)

### Morning: Set Your Temporal Context

- Open today's daily note
- Review yesterday's note to maintain continuity
- If you ever need to jot something down, add it to the "Random Notes" section for that day (this is a good place to capture random thoughts, ideas, or tasks and link them to relevant notes)
- Bonus marks if you [use the Obsidian Tasks plugin](https://ryan.himmelwright.net/post/started-using-obsidian-tasks-plugin/) to automate your to-do list

### Evening: Capture Your Day

- Add key interactions to today's daily note
- Link to any new people or organizations you encountered
- Note any insights or decisions made
- Don't overthink it—just capture what felt significant

### Weekly: Find Your Patterns

- Review the past week's daily notes
- Look for recurring themes or people
- Notice what energized or drained you
- Plan the upcoming week based on these insights

## Common Beginner Mistakes (And How to Avoid Them)

### 1. **Over-Structuring Daily Notes**
**Don't do this**: Create elaborate daily note templates with dozens of sections
**Do this**: Keep it simple—random notes, log section, and the "See Also" dataview query

### 2. **Inconsistent Date Formats**
**Don't do this**: Mix formats like `[[2025-07-15]]` and `[[July 15, 2025]]`
**Do this**: Always use `[[Month D, YYYY]]` format for consistency

### 3. **Trying to Capture Everything**
**Don't do this**: Write detailed journal entries in daily notes
**Do this**: Use daily notes as connection points, not comprehensive records

### 4. **Ignoring the Temporal Hierarchy**
**Don't do this**: Focus only on individual daily notes
**Do this**: Use monthly/quarterly notes to see bigger patterns

## The Long-Term Payoff

After using daily notes for a year, you'll have something remarkable: **a complete temporal map of your intellectual and professional journey**. You'll be able to:

- Trace how ideas evolved over time
- Understand the context of past decisions
- See patterns in your relationships and work
- Navigate your knowledge through time, not just by topic

## Start Small, Think Big

Don't try to implement everything at once. Start with:
1. Create a daily note template (use mine as a starting point)
2. Link meeting dates to daily notes
3. Add a "See Also" section with the dataview query
4. Consistently use the same date format

The temporal backbone will build itself as you use it. Within a month, you'll start seeing connections you never noticed before. Within six months, you'll wonder how you ever managed without it.

As of this writing, I have 1134 daily notes in my vault, with a total of 58,883 words and about 3259 outbound links. That's a pretty comprehensive web of notes detailing the last 3+ years of my life!

Remember: The goal isn't perfect daily notes — it's **connected** daily notes that reveal the story of how your knowledge, relationships, and projects evolved over time. That's the real power of PKM.
