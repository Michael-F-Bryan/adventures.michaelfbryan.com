# Document Structure Templates

## Standard Podcast Transcript Header

```markdown
# [Guest Name]: [Compelling Episode Title]

*[Podcast Name] Episode - [Host Names]*

---

## Timestamped Outline

**00:00** - [Compelling Chapter Title]
**08:15** - [Compelling Chapter Title]
**15:30** - [Compelling Chapter Title]
**24:45** - [Compelling Chapter Title]
**32:10** - [Compelling Chapter Title]
**41:20** - [Compelling Chapter Title]
**52:35** - [Compelling Chapter Title]
**1:04:50** - [Compelling Chapter Title]
**1:16:25** - [Compelling Chapter Title]
**1:28:15** - [Compelling Chapter Title]

---

## 00:00 [First Chapter Title]

**[Speaker Name]:** Content starts here...

**[Speaker Name]:** Response...

---

## 08:15 [Second Chapter Title]

**[Speaker Name]:** Content continues...
```

## Chapter Title Guidelines

### My First Million Style Rules

**Format**: `**MM:SS** - Descriptive Chapter Title`

**Length**: 10 chapters maximum for 45-60 minute episodes
- Focus on major topic changes
- Not minute-by-minute granularity
- Each chapter should represent a distinct section

**Characteristics of Good Titles**:
- Specific, not generic
- Action-oriented when possible
- Highlight transformation or insight
- Intrigue the reader
- Reference key names or concepts

### Good Chapter Title Examples

✅ **12:25** - The 13th Percentile to Grade Level Miracle
✅ **29:08** - Why Successful Reforms Don't Spread
✅ **32:48** - From Curmudgeon to Optimist: Entering Venture Capital
✅ **00:00** - The Accidental Paradigm Shift: How Claude Code Eliminated the Text Editor
✅ **15:30** - Ant-Fooding: Building for Yourself First
✅ **41:20** - Sub-Agents and Swarm Intelligence at Scale
✅ **1:04:50** - From CLI to Agent SDK: Beyond Coding Use Cases

### Poor Chapter Title Examples

❌ **12:25** - Michelle talks about her students
*Too generic and vague*

❌ **29:08** - Discussion about education reform
*Not specific or compelling*

❌ **32:48** - Career transition
*Too brief and uninteresting*

❌ **00:00** - Introduction
*Obvious and uninformative*

❌ **15:30** - Building products
*Lacks specificity*

## Speaker Name Formatting

### Consistency Rules

1. **Bold all speaker names**: `**Name:** Content`
2. Choose one format and stick with it throughout:
   - First names only (casual): `**Dan:** ...`, `**Cat:** ...`, `**Boris:** ...`
   - Full names (professional): `**Daniel Shipper:** ...`, `**Catherine Salgado:** ...`
   - First name + Last initial: `**Dan S.:** ...`, `**Cat S.:** ...`

3. For podcasts with 2-3 regular speakers, first names work best
4. For interviews or formal content, full names may be more appropriate
5. Never switch formats mid-transcript

### Host vs Guest Formatting

**Option 1: Same format for all**
```markdown
**Dan:** Question here?
**Boris:** Answer here.
```

**Option 2: Differentiate roles** (only when helpful)
```markdown
**Host (Dan):** Question here?
**Guest (Boris):** Answer here.
```

Use Option 1 for most cases. Use Option 2 only for:
- Panel discussions with many speakers
- Multi-host formats
- When speaker roles need clarification

## Alternative Formats

### Interview Format

For one-on-one interviews where context flows better without timestamps:

```markdown
# [Guest Name]: [Compelling Title]

*Interview with [Host Name]*

---

**[Host]:** Opening question...

**[Guest]:** Response...

**[Host]:** Follow-up...

**[Guest]:** Extended answer...
```

### Panel Discussion Format

For multiple guests:

```markdown
# [Topic]: [Panel Title]

*Panel Discussion - [Event Name]*

**Panelists:**
- [Name 1] - [Role/Company]
- [Name 2] - [Role/Company]
- [Name 3] - [Role/Company]

**Moderator:** [Name]

---

## Opening Remarks

**Moderator:** Welcome remarks...

**[Panelist 1]:** Response...

**[Panelist 2]:** Alternative view...
```

## Section Breaks

Use horizontal rules (`---`) to separate major sections or chapters:

```markdown
## 08:15 Chapter Title Here

Content of this chapter...

---

## 15:30 Next Chapter Title

Content of next chapter...
```

## Formatting Within Content

**Emphasis:**
- Use *italics* for thoughts, internal dialogue, or emphasis
- Use **bold** for key terms or phrases (sparingly)
- Use `code formatting` for technical terms, commands, or code

**Quotes:**
- Direct quotes within speech: "And I thought, 'This is amazing.'"
- Extended quotes: Use blockquotes if needed

**Lists:**
- Use when speaker lists items systematically
- Don't force lists where they don't naturally exist

**Paragraph breaks:**
- Break when speaker changes topics
- Break when there's a natural pause or shift
- Keep related thoughts together
- Don't over-break into tiny paragraphs
