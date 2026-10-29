#!/usr/bin/env python3
"""How much of your traffic (and bandwidth bill) is AI crawlers?

Reads web server access logs in Combined Log Format (nginx, Apache default)
and reports requests and bytes per AI crawler. Plain or .gz files, or stdin.

    python3 botcheck.py /var/log/nginx/access.log*
    zcat access.log.*.gz | python3 botcheck.py -

Nothing leaves your machine. Stdlib only.
"""

import argparse
import gzip
import json
import re
import sys
from datetime import datetime

SITE_URL = "https://crawlbill.anas.link"

# (user-agent substring, name, operator, kind). Matched case-insensitively, first hit wins.
BOTS = [
    ("GPTBot", "GPTBot", "OpenAI", "ai"),
    ("OAI-SearchBot", "OAI-SearchBot", "OpenAI", "ai"),
    ("ChatGPT-User", "ChatGPT-User", "OpenAI", "ai"),
    ("ClaudeBot", "ClaudeBot", "Anthropic", "ai"),
    ("Claude-User", "Claude-User", "Anthropic", "ai"),
    ("Claude-SearchBot", "Claude-SearchBot", "Anthropic", "ai"),
    ("anthropic-ai", "anthropic-ai", "Anthropic", "ai"),
    ("PerplexityBot", "PerplexityBot", "Perplexity", "ai"),
    ("Perplexity-User", "Perplexity-User", "Perplexity", "ai"),
    ("CCBot", "CCBot", "Common Crawl", "ai"),
    ("Bytespider", "Bytespider", "ByteDance", "ai"),
    ("Amazonbot", "Amazonbot", "Amazon", "ai"),
    ("meta-externalagent", "meta-externalagent", "Meta", "ai"),
    ("meta-externalfetcher", "meta-externalfetcher", "Meta", "ai"),
    ("FacebookBot", "FacebookBot", "Meta", "ai"),
    ("Google-CloudVertexBot", "Google-CloudVertexBot", "Google", "ai"),
    ("cohere-ai", "cohere-ai", "Cohere", "ai"),
    ("Diffbot", "Diffbot", "Diffbot", "ai"),
    ("YouBot", "YouBot", "You.com", "ai"),
    ("Timpibot", "Timpibot", "Timpi", "ai"),
    ("ImagesiftBot", "ImagesiftBot", "ImageSift", "ai"),
    ("omgili", "omgili", "Webz.io", "ai"),
    ("Googlebot", "Googlebot", "Google", "search"),
    ("bingbot", "bingbot", "Microsoft", "search"),
    ("Applebot", "Applebot", "Apple", "search"),
    ("DuckDuckBot", "DuckDuckBot", "DuckDuckGo", "search"),
    ("YandexBot", "YandexBot", "Yandex", "search"),
    ("Baiduspider", "Baiduspider", "Baidu", "search"),
    ("PetalBot", "PetalBot", "Huawei", "search"),
]
_BOTS_LOWER = [(sub.lower(), name, op, kind) for sub, name, op, kind in BOTS]

LINE_RE = re.compile(
    r'^\S+ \S+ \S+ \[(?P<time>[^\]]+)\] "(?:[^"\\]|\\.)*" \d{3} (?P<bytes>\d+|-)'
    r' "(?:[^"\\]|\\.)*" "(?P<ua>(?:[^"\\]|\\.)*)"'
)
KINDS = ("ai", "search", "other")


def parse_line(line):
    m = LINE_RE.match(line)
    if not m:
        return None
    try:
        time = datetime.strptime(m["time"], "%d/%b/%Y:%H:%M:%S %z")
    except ValueError:
        time = None
    size = m["bytes"]
    return {"time": time, "bytes": 0 if size == "-" else int(size), "ua": m["ua"]}


def classify(ua):
    lowered = ua.lower()
    for sub, name, op, kind in _BOTS_LOWER:
        if sub in lowered:
            return kind, name, op
    return "other", None, None


def analyze(lines):
    kinds = {k: {"requests": 0, "bytes": 0} for k in KINDS}
    bots = {}
    skipped = 0
    first = last = None
    for line in lines:
        rec = parse_line(line.rstrip("\n"))
        if rec is None:
            skipped += 1
            continue
        kind, name, op = classify(rec["ua"])
        kinds[kind]["requests"] += 1
        kinds[kind]["bytes"] += rec["bytes"]
        if kind == "ai":
            b = bots.setdefault(name, {"bot": name, "operator": op, "requests": 0, "bytes": 0})
            b["requests"] += 1
            b["bytes"] += rec["bytes"]
        t = rec["time"]
        if t is not None:
            first = t if first is None or t < first else first
            last = t if last is None or t > last else last
    span = (last - first).total_seconds() / 86400 if first else 0.0
    return {
        "total": {
            "requests": sum(k["requests"] for k in kinds.values()),
            "bytes": sum(k["bytes"] for k in kinds.values()),
        },
        "kinds": kinds,
        "bots": sorted(bots.values(), key=lambda b: (-b["bytes"], -b["requests"])),
        "skipped": skipped,
        "first": first.isoformat() if first else None,
        "last": last.isoformat() if last else None,
        "span_days": span,
    }


def estimate_cost(report, price_per_gb):
    period = report["kinds"]["ai"]["bytes"] / 1e9 * price_per_gb
    # Under a day of logs extrapolates too wildly to be useful.
    monthly = period / report["span_days"] * 30 if report["span_days"] >= 1 else None
    return {"price_per_gb": price_per_gb, "period": period, "monthly": monthly}


def _open(path):
    if path == "-":
        return sys.stdin
    if path.endswith(".gz"):
        return gzip.open(path, "rt", errors="replace")
    return open(path, errors="replace")


def _read(paths):
    for path in paths:
        f = _open(path)
        try:
            yield from f
        finally:
            if f is not sys.stdin:
                f.close()


def _size(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000


def _pct(part, whole):
    return f"{100 * part / whole:.1f}%" if whole else "-"


def render(report, cost):
    total = report["total"]
    out = []
    span = f", {report['span_days']:.1f} days" if report["first"] else ""
    out.append(
        f"botcheck: {total['requests']:,} requests, {_size(total['bytes'])}{span}"
        f" ({report['skipped']:,} unparsed skipped)"
    )
    if not total["requests"]:
        out.append("No Combined Log Format lines found.")
        return "\n".join(out)
    out.append("")
    row = "{:<24} {:<13} {:>10} {:>7} {:>10} {:>7}"
    out.append(row.format("AI crawler", "operator", "requests", "%req", "bytes", "%bytes"))
    for b in report["bots"]:
        out.append(row.format(
            b["bot"], b["operator"], f"{b['requests']:,}", _pct(b["requests"], total["requests"]),
            _size(b["bytes"]), _pct(b["bytes"], total["bytes"]),
        ))
    out.append("")
    for kind, label in (("ai", "AI crawlers total"), ("search", "Search crawlers"), ("other", "Everything else")):
        k = report["kinds"][kind]
        out.append(row.format(
            label, "", f"{k['requests']:,}", _pct(k["requests"], total["requests"]),
            _size(k["bytes"]), _pct(k["bytes"], total["bytes"]),
        ))
    out.append("")
    out.append(
        f"AI crawler egress: ${cost['period']:,.2f} over this log"
        + (f", about ${cost['monthly']:,.2f}/month" if cost["monthly"] is not None else "")
        + f" at ${cost['price_per_gb']:.2f}/GB (an assumption: pass --price-per-gb with your host's rate)."
    )
    out.append("Bytes are response bodies only; compute and function invocations come on top.")
    out.append("")
    out.append(f"Want this cut? Send this output to {SITE_URL}")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("logs", nargs="+", help="access log files (.gz ok), or - for stdin")
    parser.add_argument("--price-per-gb", type=float, default=0.15, help="your host's egress price in USD (default 0.15)")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    report = analyze(_read(args.logs))
    cost = estimate_cost(report, args.price_per_gb)
    if args.json:
        print(json.dumps({**report, "cost": cost}, indent=2))
    else:
        print(render(report, cost))


if __name__ == "__main__":
    main()
