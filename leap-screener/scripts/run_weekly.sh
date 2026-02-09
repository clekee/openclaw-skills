#!/usr/bin/env bash
# LEAP Screener 每周全量扫描
# 用法: ./run_weekly.sh [top_n]
set -euo pipefail

WORKSPACE="${WORKSPACE:-/Users/clekee/stock_watch}"
VENV="$WORKSPACE/.venv/bin/python"
SCREENER="$WORKSPACE/leap_screener.py"
REPORTS="$WORKSPACE/reports"
DATE=$(date +%Y-%m-%d)
TOP_N="${1:-15}"

mkdir -p "$REPORTS"

echo "▶ 开始 LEAP 全量扫描 (top $TOP_N)..."
MD_OUT="$REPORTS/leap-fullscan-$DATE.md"
XLSX_OUT="$REPORTS/LEAP_Screener_$DATE.xlsx"

# 1. 跑 screener
$VENV "$SCREENER" --top "$TOP_N" 2>"$REPORTS/leap_stderr_$DATE.log" | tee "$MD_OUT"

# 2. 生成 xlsx
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
$VENV "$SCRIPT_DIR/generate_xlsx.py" "$MD_OUT" "$XLSX_OUT"

echo "✅ 完成: $MD_OUT + $XLSX_OUT"
