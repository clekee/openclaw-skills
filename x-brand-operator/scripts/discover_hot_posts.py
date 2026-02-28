#!/usr/bin/env python3
import argparse, json, math, subprocess, time
from datetime import datetime, timezone


def run(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout + "\n" + p.stderr)
    return p.stdout.strip()


def parse_ts(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def recency_score(created_at):
    dt = parse_ts(created_at)
    if not dt:
        return 0.5
    age_hours = max((datetime.now(timezone.utc) - dt).total_seconds() / 3600.0, 0.0)
    return math.exp(-age_hours / 18.0)


def heat(tweet):
    m = tweet.get("public_metrics", {})
    likes = m.get("like_count", 0)
    rts = m.get("retweet_count", 0)
    reps = m.get("reply_count", 0)
    quote = m.get("quote_count", 0)
    followers = tweet.get("author", {}).get("public_metrics", {}).get("followers_count", 0)
    return (
        likes * 1.0
        + rts * 1.5
        + reps * 1.2
        + quote * 1.0
        + math.log10(max(followers, 1)) * 20
        + recency_score(tweet.get("created_at")) * 50
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", default="(AI OR LLM OR agent OR benchmark OR inference OR open-source) lang:en -is:retweet")
    ap.add_argument("-n", "--limit", type=int, default=30)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    raw = run(f"xurl search {json.dumps(args.query)} -n {args.limit}")
    obj = json.loads(raw)

    data = obj.get("data", [])
    includes = obj.get("includes", {})
    users = {u.get("id"): u for u in includes.get("users", [])}

    rows = []
    for t in data:
        a = users.get(t.get("author_id"), {})
        item = {
            "id": t.get("id"),
            "text": t.get("text", ""),
            "created_at": t.get("created_at"),
            "public_metrics": t.get("public_metrics", {}),
            "author": {
                "id": a.get("id"),
                "name": a.get("name"),
                "username": a.get("username"),
                "public_metrics": a.get("public_metrics", {}),
            },
            "url": f"https://x.com/{a.get('username','i')}/status/{t.get('id')}"
        }
        item["heat"] = round(heat(item), 2)
        rows.append(item)

    rows.sort(key=lambda x: x["heat"], reverse=True)
    out = {"generated_at": int(time.time()), "query": args.query, "count": len(rows), "items": rows}

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
