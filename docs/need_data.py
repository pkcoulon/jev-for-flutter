#!/usr/bin/env python3
import collections
import json
import re
import sys
from pathlib import Path

PRICING_DATE = "2026-09-28"
# USD per million tokens: input, 5m cache write, 1h cache write, cache read, output.
PRICES = {
    "claude-fable-5-1": (10, 12.5, 20, 0.25, 50),
    "claude-fable-5": (10, 12.5, 20, 1, 50),
    "claude-opus-5-5": (4, 5, 8, 0.20, 20),
    "claude-opus-5": (5, 6.25, 10, 0.5, 25),
    "claude-opus-4-8": (5, 6.25, 10, 0.5, 25),
    "claude-opus-4-7": (5, 6.25, 10, 0.5, 25),
    "claude-opus-4-6": (5, 6.25, 10, 0.5, 25),
    "claude-sonnet-5": (2, 2.5, 4, 0.2, 10),
    "claude-sonnet-4-6": (3, 3.75, 6, 0.3, 15),
    "claude-haiku-4-5": (1, 1.25, 2, 0.1, 5),
}
CHARS_PER_TOKEN = 2.3
SKIP_SEGMENT = {"cd", "export", "set", "unset", "echo", "printf", "sleep", "mkdir", "true", "false", "for", "done", "fi",
                "else", "local", "trap", "wait", "rm", "touch", "cp", "mv", "ln", "chmod"}
SKIP = {"time", "rtk", "proxy", "fvm", "env", "sudo", "nice", "then", "do", "if", "while", "until", "!", "{", "}",
        "command", "exec"}
BUCKETS = [(0, 100_000, "< 100 k"), (100_000, 200_000, "100–200 k"), (200_000, 400_000, "200–400 k"), (400_000, 10**12, "> 400 k")]


def price(model):
    for key in sorted(PRICES, key=len, reverse=True):
        if (model or "").startswith(key):
            return PRICES[key]
    return None


def family(name, command):
    if name != "Bash":
        known = {"Read": "Read · files", "Grep": "Grep / Glob", "Glob": "Grep / Glob", "Agent": "Subagent results",
                 "Task": "Subagent results", "WebFetch": "Web pages", "WebSearch": "Web pages", "Skill": "Loaded skills"}
        return known.get(name) or ("MCP (Figma, Jira…)" if name.startswith("mcp__") else "Other tools")
    head = ""
    for segment in re.split(r"&&|\|\||;|\n|\|", command or ""):
        words = segment.replace("(", " ").replace(")", " ").split()
        while words and (words[0] in SKIP or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words.pop(0)
        if words and words[0] in SKIP_SEGMENT:
            continue
        if words:
            head = words[0].rsplit("/", 1)[-1]
            break
    if head in ("cat", "sed", "head", "tail", "less", "nl", "awk"):
        return "Bash · file reads"
    if head in ("grep", "rg", "find", "ls", "tree", "fd", "wc"):
        return "Bash · search / list"
    if head in ("flutter", "dart", "very_good", "dcm") or "test" in head:
        return "Bash · tests / analysis"
    if head in ("git", "gh"):
        return "Bash · git / GitHub"
    if head in ("python3", "python", "node", "bash", "sh", "jq"):
        return "Bash · scripts"
    return "Bash · other"


def result_chars(content):
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(len(b.get("text", "")) if isinstance(b, dict) else 0 for b in content)
    return 0


def scan(path):
    calls, results, seen, names = [], [], {}, {}
    for line in open(path, errors="replace"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            results.append(("boundary", len(calls)))
        message = entry.get("message") or {}
        if entry.get("type") == "assistant":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    names[block.get("id")] = (block.get("name"), (block.get("input") or {}).get("command"))
            usage = message.get("usage")
            mid = message.get("id")
            if not usage or not mid or message.get("model") == "<synthetic>" or entry.get("isApiErrorMessage"):
                continue
            if mid in seen:
                calls[seen[mid]]["output"] = max(calls[seen[mid]]["output"], usage.get("output_tokens") or 0)
                continue
            creation = usage.get("cache_creation") or {}
            w1 = creation.get("ephemeral_1h_input_tokens") or 0
            w5 = creation.get("ephemeral_5m_input_tokens")
            w5 = (usage.get("cache_creation_input_tokens") or 0) - w1 if w5 is None else w5
            seen[mid] = len(calls)
            calls.append({
                "model": message.get("model"), "input": usage.get("input_tokens") or 0, "w5": w5, "w1": w1,
                "read": usage.get("cache_read_input_tokens") or 0, "output": usage.get("output_tokens") or 0,
            })
        elif entry.get("type") == "user":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    name, command = names.get(block.get("tool_use_id"), ("?", None))
                    results.append((family(name or "?", command), len(calls), result_chars(block.get("content"))))
    return calls, results


def cost(call):
    grid = price(call["model"])
    if not grid:
        return None
    i, w5, w1, r, o = grid
    return (call["input"] * i + call["w5"] * w5 + call["w1"] * w1 + call["read"] * r + call["output"] * o) / 1e6


def main(out_path, *args):
    excluded = {a.split("=", 1)[1] for a in args if a.startswith("--exclude=")}
    project_dirs = [a for a in args if not a.startswith("--")]
    files = [f for d in project_dirs for f in Path(d).expanduser().glob("**/*.jsonl")
             if "journal" not in f.name and not any(x in str(f) for x in excluded)]
    all_calls, residency, sessions = [], collections.Counter(), []
    reread_weights = []
    for path in files:
        calls, results = scan(path)
        if not calls:
            continue
        all_calls.extend(calls)
        if "subagents" not in path.parts:
            sessions.append((len(calls), path.name, calls, results))
        boundary_after = sorted(pos for kind, pos, *_ in results if kind == "boundary")
        for item in results:
            if item[0] == "boundary":
                continue
            label, pos, chars = item
            end = next((b for b in boundary_after if b > pos), len(calls))
            turns = max(0, end - pos)
            tokens = chars / CHARS_PER_TOKEN
            residency[label] += tokens * turns
            if tokens >= 200:
                reread_weights.append(turns)
    context = [c["input"] + c["w5"] + c["w1"] + c["read"] for c in all_calls]
    total_turns = sum(context)
    priced = [(ctx, cost(c)) for ctx, c in zip(context, all_calls) if cost(c) is not None]
    total_cost = sum(v for _, v in priced)
    by_bucket_calls = [sum(1 for ctx, _ in priced if lo <= ctx < hi) for lo, hi, _ in BUCKETS]
    by_bucket_cost = [sum(v for ctx, v in priced if lo <= ctx < hi) for lo, hi, _ in BUCKETS]

    sessions.sort(key=lambda s: s[0])
    candidates = [s for s in sessions if 80 <= s[0] <= 260] or sessions
    _, _, calls, results = candidates[len(candidates) // 2]
    series = [c["input"] + c["w5"] + c["w1"] + c["read"] for c in calls]
    # Claude Code's first call of a session can be a tiny warm-up; the conversation starts at the first real context.
    start = next((i for i, v in enumerate(series) if v >= 10_000), 0)
    series = series[start:]
    results = [(r[0], r[1] - start, *r[2:]) for r in results]
    entered = collections.defaultdict(list)
    for item in results:
        if item[0] != "boundary":
            entered[item[1]].append((item[2], item[0]))
    notes = [{"index": 0, "label": "%dk before the first question: instructions, tools, memory" % round(series[0] / 1000), "dx": 12, "dy": 20}]
    code_sources = {"Bash · file reads", "Read · files", "Bash · search / list", "Bash · tests / analysis"}
    jumps = sorted(((series[i] - series[i - 1], i) for i in range(2, len(series))
                    if any(src in code_sources for _, src in entered.get(i, []))), reverse=True)
    if jumps and jumps[0][0] > 5000:
        delta, i = jumps[0]
        source = max(item for item in entered[i] if item[1] in code_sources)[1]
        phrase = {"Bash · file reads": "one file read (cat, sed)", "Read · files": "one file read (Read)",
                  "Bash · search / list": "one search (grep, find)", "Bash · tests / analysis": "test output"}[source]
        notes.append({"index": i, "label": "+%dk from %s\nreused in each later call" % (round(delta / 1000), phrase),
                      "dx": -12 if i > len(series) / 4 else 12, "dy": -26 if i > len(series) / 4 else 22,
                      "anchor": "end" if i > len(series) / 4 else "start"})

    rows = sorted(({"label": k, "value": 100 * v / total_turns} for k, v in residency.items()), key=lambda r: -r["value"])
    rereads = sorted(reread_weights)
    charts = {
        "context-growth": {
            "kind": "line", "unit": "k", "values": series, "notes": notes, "x_label": "API call",
            "title": "Context grows and is supplied on every call",
            "subtitle": "Context tokens per call in one real Flutter session with %d calls" % len(series),
        },
        "tool-residency": {
            "kind": "hbar", "unit": "%", "rows": rows[:7],
            "title": "Tool results remain in later context",
            "subtitle": "Tool-result share of repeated context by source · %d sessions, %d Flutter projects" % (len(sessions), len(project_dirs)),
        },
        "cost-by-context": {
            "kind": "grouped", "unit": "%", "groups": [b[2] for b in BUCKETS], "label_groups": [len(BUCKETS) - 1],
            "series": [
                {"label": "Share of calls", "values": [100 * n / max(1, len(priced)) for n in by_bucket_calls]},
                {"label": "Share of API-equivalent cost", "values": [100 * v / max(1e-9, total_cost) for v in by_bucket_cost]},
            ],
            "title": "Long contexts account for most cost",
            "subtitle": "Calls and API-equivalent cost by context size · prices as of %s" % PRICING_DATE,
        },
    }
    summary = {
        "pricing_date": PRICING_DATE, "sessions": len(sessions), "files": len(files), "calls": len(all_calls),
        "mean_context": round(total_turns / max(1, len(all_calls))),
        "valued_cost_usd": round(total_cost, 2),
        "tool_results_share_of_context_pct": round(100 * sum(residency.values()) / total_turns, 1),
        "median_rereads_of_tool_result": rereads[len(rereads) // 2] if rereads else 0,
        "calls_over_200k_pct": round(100 * sum(by_bucket_calls[2:]) / max(1, len(priced)), 1),
        "cost_over_200k_pct": round(100 * sum(by_bucket_cost[2:]) / max(1e-9, total_cost), 1),
        "unpriced_models": sorted({c["model"] for c in all_calls if cost(c) is None}),
        "rows": rows,
    }
    Path(out_path).write_text(json.dumps(charts, ensure_ascii=False, indent=1))
    Path(out_path).with_name("need_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
