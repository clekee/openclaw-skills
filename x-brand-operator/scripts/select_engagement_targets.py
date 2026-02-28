#!/usr/bin/env python3
import argparse, json

KEYWORDS = [
    "benchmark", "latency", "throughput", "memory", "cost", "hallucination",
    "agent", "safety", "open-source", "inference", "distillation", "eval"
]

def value_score(item):
    txt = (item.get("text") or "").lower()
    k = sum(1 for w in KEYWORDS if w in txt)
    q = txt.count("?")
    heat = item.get("heat", 0)
    return heat + k * 8 + q * 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="-")
    ap.add_argument("-k", "--count", type=int, default=5)
    args = ap.parse_args()

    with open(args.inp, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    for it in items:
        it["value_score"] = round(value_score(it), 2)

    items.sort(key=lambda x: x["value_score"], reverse=True)
    chosen = items[: args.count]

    out = {
        "source_count": len(items),
        "selected_count": len(chosen),
        "selected": [
            {
                "id": i.get("id"),
                "url": i.get("url"),
                "author": i.get("author", {}).get("username"),
                "heat": i.get("heat"),
                "value_score": i.get("value_score"),
                "text": i.get("text"),
            }
            for i in chosen
        ],
    }

    text = json.dumps(out, ensure_ascii=False, indent=2)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)


if __name__ == "__main__":
    main()
