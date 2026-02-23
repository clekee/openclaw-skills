---
name: github-tech-watch-daily
description: Generate and send a daily GitHub tech watch report with two sections - (1) GitHub Trending daily hot repos and (2) hot new repos created in the last 7 days - with rolling deduplication. Use when scheduling or running daily GitHub discovery pushes to Telegram groups/channels. Triggers on daily GitHub report, GitHub trending push, tech watch daily, GitHub热门推送.
---

# GitHub Tech Watch Daily

Two-section daily GitHub report with dedup.

## Pipeline

```bash
# Step 1: Fetch data (outputs JSON to stdout)
python3 scripts/github_daily_report.py \
  --state-file <path/to/github_shared.json> \
  --max-trending 10 --max-new 10

# Step 2: Format for Telegram (reads JSON from stdin)
python3 scripts/format_report.py [--template references/format-template.txt]
```

Pipe together:
```bash
python3 scripts/github_daily_report.py --state-file STATE_FILE | python3 scripts/format_report.py
```

## Send rules

- Use `message` tool (action=send) to push formatted text
- Plain text only: no HTML tags, no Markdown link syntax
- URLs as raw text
- If a section has 0 repos, print `今天没有新内容`

## State file

- JSON with `shared[]` array of `{repo, ts}`
- 30-day rolling window, auto-pruned on each run
- Dedup by `owner/repo`

## Cron setup

```
session: isolated
schedule: cron 0 11 * * * (exact)
delivery: none (agent sends via message tool directly)
```

Agent task: run pipeline, send output via message tool, reply `已推送`.
