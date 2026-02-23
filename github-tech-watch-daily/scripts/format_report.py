#!/usr/bin/env python3
"""
Read JSON from github_daily_report.py (stdin or --input),
output formatted plain-text report ready for Telegram.
"""
import argparse, json, sys, os
from datetime import datetime, timezone, timedelta

def format_trending(repo):
    lang = f" · {repo['language']}" if repo.get('language','N/A') != 'N/A' else ''
    today = f" (+{repo['stars_today']:,} today)" if repo.get('stars_today') else ''
    desc = repo.get('description','').strip()
    lines = [f"⭐ {repo['stars']:,}{today}{lang} · {repo['name']}"]
    if desc:
        lines.append(desc)
    lines.append(repo['url'])
    return '\n'.join(lines)

def format_new(repo):
    lang = f" · {repo['language']}" if repo.get('language','N/A') != 'N/A' else ''
    desc = repo.get('description','').strip()
    lines = [f"⭐ {repo['stars']:,}{lang} · {repo['name']}"]
    if desc:
        lines.append(desc)
    lines.append(repo['url'])
    return '\n'.join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', help='JSON file (default: stdin)')
    ap.add_argument('--template', help='Template file path')
    args = ap.parse_args()

    if args.input:
        with open(args.input) as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    pst = timezone(timedelta(hours=-8))
    date_str = datetime.now(pst).strftime('%-m/%d')

    tr = data.get('trending', {}).get('repos', [])
    nw = data.get('new', {}).get('repos', [])

    trending_section = '\n\n'.join(format_trending(r) for r in tr) if tr else '今天没有新内容'
    new_section = '\n\n'.join(format_new(r) for r in nw) if nw else '今天没有新内容'

    if args.template and os.path.exists(args.template):
        with open(args.template) as f:
            tpl = f.read()
    else:
        tpl = (
            "🔥 GitHub 每日报告 — {date}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "📈 今日 Trending Top {trending_count}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "{trending_section}\n\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "🆕 一周内新项目 Top {new_count}\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "{new_section}\n\n"
            "📊 共 {total} 个项目 · 明天只推新面孔"
        )

    print(tpl.format(
        date=date_str,
        trending_count=len(tr),
        new_count=len(nw),
        trending_section=trending_section,
        new_section=new_section,
        total=len(tr) + len(nw),
    ))

if __name__ == '__main__':
    main()
