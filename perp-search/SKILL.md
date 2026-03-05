---
name: perp-search
description: Deep web search via self-hosted Perplexica (SearxNG + LLM). Use when web_search returns insufficient results, when the user asks for in-depth research with cited sources, comprehensive analysis, or says "deep search", "详细搜索", "帮我查一下", or when a topic needs multi-source synthesis with citations. Supports speed/balanced/quality modes. Requires Docker + Perplexica running locally.
---

# Perp Search — Perplexica Deep Research

Local Perplexica instance (SearxNG meta-search + LLM synthesis) for deep research with cited sources.

## Prerequisites

- Docker with `perplexica` container running on port 3000
- LLM provider configured (OpenRouter/OpenAI-compatible)

First-time setup:
```bash
bash scripts/setup.sh
bash scripts/configure.sh --provider openrouter --api-key $OPENROUTER_API_KEY --model minimax/minimax-m2.5
```

## Usage

### Synchronous (short queries, <2min)

```bash
bash scripts/search.sh \
  --prompt "Your research query" \
  --mode balanced \
  --timeout 120
```

Read output file and send content to user in chat.

### Background dispatch (long research)

```bash
nohup bash scripts/search.sh \
  --prompt "Deep research query" \
  --mode quality \
  --task-name "my-research" \
  --discord-channel "CHANNEL_ID" \
  --timeout 180 > /tmp/perp-search.log 2>&1 &
```

Tell user search is running; results deliver to chat when done.

### Modes

| Mode | Searches | Best for |
|------|----------|----------|
| `speed` | 1 round, 3 queries | Quick facts |
| `balanced` | 2-3 rounds | General research |
| `quality` | 5-6 rounds, 2000+ word output | Deep analysis |

### Parameters

| Flag | Default | Description |
|------|---------|-------------|
| `--prompt` | required | Research query |
| `--mode` | `balanced` | speed/balanced/quality |
| `--model` | `minimax/minimax-m2.5` | LLM model via OpenRouter |
| `--provider` | `openrouter-minimax` | Perplexica provider id |
| `--timeout` | `120` | Max seconds |
| `--task-name` | `search-<ts>` | Task identifier |
| `--output` | auto | Output file path |
| `--telegram-group` | — | Telegram chat for callback |
| `--discord-channel` | — | Discord channel for callback |
| `--sources` | `["web"]` | JSON array of sources |
| `--url` | `http://localhost:3000` | Perplexica URL |

### Output

Results saved to `/tmp/perp-search-results/<task>.md` with:
- Full LLM-synthesized answer with inline citations
- Source list with titles and URLs
- Metadata in `latest-meta.json`

## Post-Search Rules

1. Read the output file, restructure logically, output in user's language
2. Do not dump raw file — synthesize and present with key data preserved
3. Keep source citations; consolidate at end
4. Never just give a file path — send the content
