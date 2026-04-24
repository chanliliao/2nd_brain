# Skill: learning-log

Captures Henry's AI study sessions with enough structure for the reflection agent to promote key facts to MEMORY.md.

---

## Trigger

User says "log what I learned", "add to my study notes", "I just finished studying \<topic\>", or invokes `/learning-log`.

---

## Context about Henry's current learning focus

Henry is actively studying AI engineering. Primary topics:
- Claude Agent SDK (tool use, multi-agent orchestration, session management)
- FastEmbed and agentic RAG patterns
- Agentic memory architectures
- LLM cost optimization (context compression, caching)
- Practical Python patterns for AI agents

When guessing tags or category routing, use this focus as a prior.

---

## Steps

### Step 1 — Gather study session details

Ask Henry (or accept inline if he provided it):

- **What did you study?** Topic name.
- **Key concepts?** Main things learned — bullet points OK.
- **Time spent?** Approximate hours.
- **Code, commands, or snippets?** Anything to preserve exactly.
- **Questions or next steps?** What to explore next.
- **Links?** References, docs, papers.

If Henry gives you a quick brain dump, extract these fields from it rather than asking follow-up questions.

### Step 2 — Compose the learning entry

Format:

```markdown
## [Topic Name] — YYYY-MM-DD

**Time:** ~Xh
**Tags:** #ai-learning #<topic-slug>

**Summary:** 2–3 sentence overview of what was studied and the key insight or takeaway.

**Key concepts:**
- Concept 1: brief explanation
- Concept 2: brief explanation
- Concept 3: brief explanation

**Code / commands:**
\`\`\`<language>
# paste Henry's code or commands here
\`\`\`

**Questions / next steps:**
- What to explore next
- Open questions

**Links:**
- [Title](url)
```

Rules:
- Always include `#ai-learning` tag so reflection agent can find it
- Add a second tag for the topic slug: e.g., `#claude-agent-sdk`, `#fastembed`, `#rag-patterns`
- Omit sections (Code, Links) if Henry provided nothing for them
- Summary must be ≥ 2 sentences
- The entry overall should be ≥ 300 words; aim for completeness, not brevity

### Step 3 — Append to today's daily log

Path: `vault/daily/YYYY-MM-DD.md` (use today's actual date).

If today's daily log does not exist, create it first:
```markdown
# YYYY-MM-DD

## Today's Focus

```

Then append the learning entry under a `## Learning` heading if one doesn't already exist, or just append it if the heading is already there.

### Step 4 — Write standalone note (conditional)

Write a standalone note to `vault/Memory/agent-designs/YYYY-MM-DD_<topic-slug>.md` if **either** condition is true:
- The entry is ≥ 500 words, **or**
- The topic directly covers an agent architecture (multi-agent orchestration, memory systems, RAG, tool use, LLM eval)

Standalone note format:
```markdown
---
tags: [ai-learning, <topic-slug>]
date: YYYY-MM-DD
---

# <Topic Name>

<full learning entry content>
```

### Step 5 — Confirm

> "Logged '\<topic\>' to vault/daily/YYYY-MM-DD.md. [If standalone: Also saved to vault/Memory/agent-designs/\<filename\>.md.] Reflection agent will promote key facts to MEMORY.md tomorrow at 8 AM."

---

## Hard constraints

- Always include `#ai-learning` tag — reflection agent depends on it for categorization
- Never write to paths outside `vault/`
- Never post or share the entry anywhere
- If Henry asks to log something unrelated to AI/tech study, still log it — don't filter topics
