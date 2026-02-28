#!/usr/bin/env python3
import argparse, json, textwrap

TEMPLATES = [
    "Strong point. The hidden variable here is {var}; without controlling it, the headline result may not transfer.",
    "I mostly agree, but boundary conditions matter: {var}. That’s where many prod rollouts break.",
    "Useful thread. The practical tradeoff is {var} vs {var2}—teams should decide based on serving constraints, not benchmark screenshots.",
]

VARS = [
    "data distribution shift", "latency tail (p95/p99)", "memory bandwidth", "evaluation leakage",
    "token budget", "context length", "throughput under concurrency", "operational reliability"
]


def build(text, idx):
    v1 = VARS[idx % len(VARS)]
    v2 = VARS[(idx + 3) % len(VARS)]
    t = TEMPLATES[idx % len(TEMPLATES)].format(var=v1, var2=v2)
    implication = "If I were testing this, I’d run one ablation on real traffic slices before drawing broad conclusions."
    out = t + " " + implication
    return textwrap.shorten(out, width=500, placeholder="...")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for i, t in enumerate(data.get("selected", [])):
        rows.append({
            "target_url": t.get("url"),
            "target_id": t.get("id"),
            "author": t.get("author"),
            "source_excerpt": (t.get("text") or "")[:180],
            "reply_draft": build(t.get("text") or "", i),
        })

    text = json.dumps({"count": len(rows), "drafts": rows}, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
