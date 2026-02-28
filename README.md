# OpenClaw Custom Skills

A collection of custom skills for [OpenClaw](https://github.com/openclaw/openclaw).

## Skills

| Skill | Description |
|---|---|
| [codex-search](./codex-search/) | Deep web search using Codex CLI for complex queries needing multi-source synthesis |
| [codex-deep-search](./codex-deep-search/) | Extended deep search with data persistence |
| [github-tech-watch-daily](./github-tech-watch-daily/) | Daily GitHub trending report with rolling deduplication → Telegram delivery |
| [leap-screener](./leap-screener/) | Screen US stocks for LEAP Call opportunities (3-layer funnel → xlsx report → Telegram) |
| [socratic-learning-coach](./socratic-learning-coach/) | Socratic questioning method for active recall and understanding gap diagnosis |
| [x-brand-operator](./x-brand-operator/) | Operate a personal X/Twitter account with human-like AI hot-topic engagement |

## Installation

Add the skill directory to your OpenClaw config:

```json
{
  "skills": {
    "load": {
      "extraDirs": ["~/work/openclaw-skills"]
    }
  }
}
```

Or copy individual skill folders into your OpenClaw skills directory.

## License

MIT
