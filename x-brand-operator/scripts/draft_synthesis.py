#!/usr/bin/env python3
"""
draft_synthesis.py — Prepare context for synthesis posts.

Outputs topic distribution + guidelines. The agent writes the actual post.
"""
import argparse, json, collections

TOPICS = {
    "model": ["model", "release", "gpt", "claude", "gemini", "llama", "llm"],
    "benchmark": ["benchmark", "eval", "score", "sota"],
    "agent": ["agent", "workflow", "tool", "automation", "coding"],
    "infra": ["inference", "latency", "throughput", "gpu", "npu", "cost", "serving"],
    "policy": ["regulation", "policy", "safety", "governance"],
    "product": ["launch", "ship", "release", "feature", "product", "api"],
}

SYNTHESIS_STYLES = [
    {
        "style": "hot_take",
        "description": "One spicy opinion based on today's threads. Not a summary.",
        "example": "everyone's shipping agent IDEs but nobody's solved agent debugging. logs ≠ explanations. we're building cockpits without flight recorders.",
        "rules": ["Max 2-3 sentences", "Have an actual opinion", "No bullet points"],
    },
    {
        "style": "pattern_notice",
        "description": "You noticed something across multiple threads today.",
        "example": "3 separate threads today about eval quality > model quality. feels like the industry is finally learning what we figured out in compilers 20 years ago: the test suite IS the product.",
        "rules": ["Reference the pattern, not individual posts", "Connect to your experience", "Max 3 sentences"],
    },
    {
        "style": "question_post",
        "description": "Ask your followers something genuine based on what you're seeing.",
        "example": "real question: how many of you are actually running evals on production traffic vs synthetic? because the gap between those two is massive and nobody talks about it.",
        "rules": ["Ask something you genuinely want to know", "Keep it conversational", "Max 2 sentences"],
    },
]

ANTI_PATTERNS = [
    "Don't write 'Today in AI:' followed by bullet points — that's a newsletter, not a tweet.",
    "Don't use 'Implication:' or 'Takeaway:' labels.",
    "Don't try to cover more than one idea per post.",
    "Write like you're texting a smart friend, not writing a report.",
    "If there's no genuine pattern worth calling out, DON'T POST. Silence > filler.",
]


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

    items = data.get("items", [])
    c = collections.Counter(classify(i.get("text")) for i in items)
    top = c.most_common(3)

    # Pick a random style
    import random
    style = random.choice(SYNTHESIS_STYLES)

    output = {
        "topic_distribution": dict(c),
        "top_topics": [{"topic": k, "count": v} for k, v in top],
        "top_thread_excerpts": [
            {"author": i.get("author", {}).get("username", "?"), "text": (i.get("text") or "")[:200]}
            for i in sorted(items, key=lambda x: x.get("heat", 0), reverse=True)[:5]
        ],
        "assigned_style": style,
        "anti_patterns": ANTI_PATTERNS,
        "persona_reminder": (
            "You are William Zhang — Staff Engineer at AMD working on LLM inference. "
            "Write like yourself on Twitter. Casual, opinionated, grounded in real work. "
            "Not an industry analyst. Not a newsletter."
        ),
    }

    text = json.dumps(output, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
