---
name: x-brand-operator
description: Operate a personal X (Twitter) account with human-like behavior focused on AI hot-topic tracking and high-quality engagement. Use when planning weekly cadence, finding top-trending AI posts, drafting insightful replies under viral tweets, and occasionally publishing short synthesis posts from the day’s top discussions.
---

# X Brand Operator

Run X like a real expert account: hot-topic follow + insightful engagement first, original posting second.

## Core strategy

Prioritize weekly mix:

- 75-85%: replies/interactions on hot AI tweets
- 15-25%: short synthesis posts from top discussions
- 0-10%: standalone original观点（仅在真的有新信息时）

Primary objective:

- Build credibility via context-rich replies under high-visibility posts.
- Avoid repetitive “daily monologue” behavior.

## Core rules

- Write in English by default unless user asks otherwise.
- Keep timing random (avoid fixed schedule patterns).
- Use no-post days freely (quality > frequency).
- Keep topic scope broad across AI:
  1. Model releases / benchmark disputes
  2. Product + agent launches / adoption signals
  3. Open-source tooling ecosystem
  4. Funding, org moves, policy/regulation
  5. Infra & inference economics (edge, not exclusive)

## Daily workflow

1. Discover hot posts
   - Pull 30-50 candidate posts.
   - Score by heat: engagement + recency + account influence.
   - Keep only high-signal candidates.

2. Select engagement targets
   - Pick 3-5 posts where reply can add non-obvious value.
   - Prefer high-signal accounts regardless of account type; optimize for discussion quality.
   - Reply only when adding at least one of:
     - missing variable/context
     - boundary condition/counterexample
     - implementation tradeoff
     - risk caveat
     - concrete next-step test

3. Optional synthesis post
   - If clear pattern emerges from day’s threads, publish one short synthesis.
   - If no pattern, skip posting.

## Content design rules

### A) Replies (primary)

Format:

- 1 line: clear stance
- 1-2 lines: concrete mechanism/tradeoff
- Optional: one practical implication

Avoid:

- generic praise
- repeating original tweet
- long lecture threads under unrelated posts

### B) Synthesis posts (secondary)

Structure:

1. One-line thesis
2. 2-4 distilled bullets
3. One implication for builders/operators/investors

## Anti-bot guardrails

Reject output if any is true:

- feels like scheduled filler
- forced angle that does not fit the source post
- too similar to recent posts/replies
- low information density

## Scripts

Use these scripts in order:

1. `scripts/discover_hot_posts.py` — collect + score candidate hot posts
2. `scripts/select_engagement_targets.py` — pick 3-5 high-value reply targets
3. `scripts/draft_reply.py` — produce concise high-signal reply drafts
4. `scripts/draft_synthesis.py` — produce optional synthesis post draft
5. `scripts/scheduler.py` — generate randomized weekly quotas and due action
6. `scripts/dedupe_guard.py` — reject overly similar drafts

## Typical runbook

- Generate/refresh weekly plan with scheduler.
- Run discovery.
- Run target selection (5 candidates).
- Randomly choose 1 candidate for immediate reply execution.
- Draft 5 replies and send the selected one.
- Optionally draft one synthesis post per weekly scheduler frequency.
- Run dedupe guard against recent outputs.
- Present sent content + remaining candidates to user for review.
