#!/usr/bin/env python3
import argparse, json, difflib


def sim(a, b):
    return difflib.SequenceMatcher(a=(a or "").lower(), b=(b or "").lower()).ratio()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drafts", required=True, help="json file with drafts list")
    ap.add_argument("--recent", required=True, help="json file with recent texts list")
    ap.add_argument("--threshold", type=float, default=0.80)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    with open(args.drafts, "r", encoding="utf-8") as f:
        drafts_obj = json.load(f)
    with open(args.recent, "r", encoding="utf-8") as f:
        recent_obj = json.load(f)

    drafts = drafts_obj.get("drafts", drafts_obj if isinstance(drafts_obj, list) else [])
    recent = recent_obj.get("texts", recent_obj if isinstance(recent_obj, list) else [])

    reviewed = []
    for d in drafts:
        txt = d.get("reply_draft") or d.get("text") or ""
        best = 0.0
        best_src = ""
        for r in recent:
            s = sim(txt, r)
            if s > best:
                best = s
                best_src = r
        reviewed.append({
            **d,
            "max_similarity": round(best, 3),
            "status": "reject" if best >= args.threshold else "pass",
            "similar_to": best_src[:120],
        })

    out = {"threshold": args.threshold, "count": len(reviewed), "items": reviewed}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
