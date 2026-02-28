#!/usr/bin/env python3
import argparse, json, collections, textwrap

TOPICS = {
    "model": ["model", "release", "gpt", "claude", "gemini", "llama"],
    "benchmark": ["benchmark", "eval", "score", "sota"],
    "agent": ["agent", "workflow", "tool", "automation"],
    "infra": ["inference", "latency", "throughput", "gpu", "npu", "cost"],
    "policy": ["regulation", "policy", "safety", "governance"],
}


def classify(text):
    t = (text or "").lower()
    for k, ws in TOPICS.items():
        if any(w in t for w in ws):
            return k
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    c = collections.Counter(classify(i.get("text")) for i in data.get("items", []))
    top = c.most_common(3)

    thesis = "Today’s AI timeline looked noisy, but three production-relevant signals stood out."
    bullets = [f"- {k}: {v} high-signal threads dominated discussion" for k, v in top]
    tail = "Implication: prioritize experiments that survive real-traffic constraints, not just leaderboard optics."
    post = "\n".join([thesis] + bullets + [tail])
    post = textwrap.shorten(post, width=800, placeholder="...")

    out = {"topic_counts": dict(c), "synthesis_draft": post}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
