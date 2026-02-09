---
name: leap-screener
description: Screen US stocks for LEAP Call opportunities using a 3-layer funnel (fundamentals, technicals, options), rank candidates, split clean vs flagged results, generate markdown/xlsx reports, and optionally deliver to Telegram. Use when the user asks for LEAP scans, top picks, weekly automation, parameter tuning, or report generation for the stock watch workflow.
---

# LEAP Screener

## Overview

Run the reusable LEAP workflow for William’s stock-watch setup:
1. Full-universe scan (`leap_screener.py`)
2. Clean vs flagged separation
3. Formatted Excel export
4. Optional scheduled automation + Telegram delivery

## Quick Start

From workspace `/Users/clekee/stock_watch`:

```bash
# Run full scan + markdown report
.venv/bin/python leap_screener.py --top 15 \
  2>reports/leap_screener_stderr.log \
  | tee reports/leap-fullscan-$(date +%Y-%m-%d).md

# Build xlsx from markdown
.venv/bin/python skills/leap-screener/scripts/generate_xlsx.py \
  reports/leap-fullscan-$(date +%Y-%m-%d).md \
  reports/LEAP_Screener_$(date +%Y-%m-%d).xlsx
```

## One-Command Weekly Run

Use bundled wrapper:

```bash
skills/leap-screener/scripts/run_weekly.sh 15
```

Outputs:
- `reports/leap-fullscan-YYYY-MM-DD.md`
- `reports/LEAP_Screener_YYYY-MM-DD.xlsx`
- `reports/leap_stderr_YYYY-MM-DD.log`

## Automation Pattern (Cron)

For scheduled runs, create an isolated `agentTurn` cron job that:
1. executes `run_weekly.sh`
2. sends generated xlsx to Telegram target
3. includes short summary (scan count / pass count / top 3)

Current deployment target:
- Telegram group: `-5124166673`

## Tuning Guidance

- Thresholds and history: `references/thresholds.md`
- Prefer conservative changes and compare pass counts before/after.
- If pass count is too low (<10), loosen Layer 1 first, then Layer 2.
- Keep flagged list separate; do not mix into main top list.

## Resources

### scripts/
- `leap_screener.py` — main 3-layer scanner
- `generate_xlsx.py` — formatted workbook generator (Top15 / Flag / Insights)
- `run_weekly.sh` — weekly orchestration wrapper

### references/
- `thresholds.md` — parameter baselines, scoring weights, anomaly rules

### config/
- `defaults.json` — workspace, paths, targets, and default top-n
