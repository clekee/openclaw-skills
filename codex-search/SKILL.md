---
name: codex-search
description: Deep web search using Codex CLI for complex queries that need multi-source synthesis. Use when web_search (Brave) returns insufficient results, when the user asks for in-depth research, comprehensive analysis, or says "deep search", "详细搜索", "帮我查一下", or when a topic needs following multiple links and cross-referencing sources.
---

# Codex Search

Use Codex CLI's web search capability for research tasks needing more depth than Brave API snippets.

## When to Prefer Over web_search

- Complex/niche topics needing multi-source synthesis
- User explicitly asks for thorough/deep research
- Brave results are too shallow or missing context

## Usage

### Dispatch Mode (recommended — background + callback)

```bash
nohup bash ~/work/openclaw-skills/codex-search/scripts/search.sh \
  --prompt "Your research query" \
  --task-name "my-research" \
  --telegram-group "957022683" \
  --timeout 120 > /tmp/codex-search.log 2>&1 &
```

After dispatch: tell user search is running, results will be sent to chat when done. Do NOT poll.

**IMPORTANT:** Always include `--telegram-group` so results are delivered directly to chat. Do NOT just give the user a file path.

### Synchronous Mode (short queries only)

```bash
bash ~/work/openclaw-skills/codex-search/scripts/search.sh \
  --prompt "Quick factual query" \
  --output "/tmp/search-result.md" \
  --timeout 60
```

Then **read the output file and send the content to the user in chat**.

## Post-Search Rule

**Read the result file, extract the "Brief Summary" section, and send a clean synthesized answer in chat.** Do NOT dump the raw per-search-round notes (Search 1, Search 2...) — the user wants the final conclusion, not the research process. Never just give a file path.

## Parameters

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--prompt` | Yes | — | Research query |
| `--output` | No | `/tmp/codex-search-results/<task>.md` | Output file path |
| `--task-name` | No | `search-<timestamp>` | Task identifier |
| `--telegram-group` | No | — | Telegram chat ID for callback (send full results) |
| `--model` | No | `gpt-5.3-codex` | Model override |
| `--timeout` | No | `120` | Seconds before auto-stop |

## Result Files

| File | Content |
|------|---------|
| `/tmp/codex-search-results/<task>.md` | Search report (incremental) |
| `/tmp/codex-search-results/latest-meta.json` | Task metadata + status |
| `/tmp/codex-search-results/task-output.txt` | Raw Codex output |
