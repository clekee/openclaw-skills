#!/usr/bin/env python3
import argparse, json, os, random, time
from datetime import datetime, timedelta, UTC


def week_key(ts=None):
    d = datetime.fromtimestamp(ts or time.time(), UTC)
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=".x_brand_state.json")
    ap.add_argument("--mark-done", choices=["reply", "synthesis", "original"], default=None)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    state = {}
    if os.path.exists(args.state):
        with open(args.state, "r", encoding="utf-8") as f:
            state = json.load(f)

    wk = week_key()
    if state.get("week") != wk:
        replies = random.randint(18, 28)
        synth = random.randint(2, 5)
        original = random.randint(0, 2)
        state = {
            "week": wk,
            "quota": {"reply": replies, "synthesis": synth, "original": original},
            "done": {"reply": 0, "synthesis": 0, "original": 0},
            "next_due_ts": int((datetime.now(UTC) + timedelta(hours=random.randint(3, 8))).timestamp()),
        }

    if args.mark_done:
        state["done"][args.mark_done] = state["done"].get(args.mark_done, 0) + 1

    now = int(time.time())
    due = now >= state.get("next_due_ts", now)
    action = "none"
    if due:
        if state["done"]["reply"] < state["quota"]["reply"]:
            action = "reply"
        elif state["done"]["synthesis"] < state["quota"]["synthesis"]:
            action = "synthesis"
        elif state["done"]["original"] < state["quota"]["original"]:
            action = "original"
        state["next_due_ts"] = int((datetime.now(UTC) + timedelta(hours=random.randint(3, 10))).timestamp())

    with open(args.state, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

    out = {"due": due, "action": action, "state": state}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
