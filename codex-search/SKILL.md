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

## Post-Search Rule (必须遵守)

搜索完成后，读取结果文件，然后按以下规则输出：

1. **用中文输出**
2. **不要 dump 原始搜索笔记**（Search 1, Search 2... 这种逐轮记录不要发）
3. **有条理地重组内容** — 把多轮搜索的 raw 结果串起来，按逻辑分层整理
4. **保持细节浓度** — 不要压缩成几句话的 brief，关键数据、分析师观点、时间线、来源都要保留
5. **绝不只给文件路径** — 用户不会去打开 md 文件
6. 数据来源在末尾统一标注即可，不需要每句话都带链接

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
