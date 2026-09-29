#!/usr/bin/env python3
import argparse
import collections
import json
import re
import sys
from pathlib import Path

MIN_LINES = 300
NOT_READ = re.compile(r"has not been read|must read|Read it first", re.I)


def load(path):
    rows = []
    for line in open(path, errors="replace"):
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def result_text(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict))


def trial_metrics(directory):
    meta = json.loads((directory / "meta.json").read_text())
    uses, stats = {}, collections.Counter()
    lensed, order = set(), []
    for entry in load(directory / "transcript.jsonl"):
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                uses[block["id"]] = block
                name, data = block.get("name"), block.get("input") or {}
                if name == "Bash":
                    command = data.get("command") or ""
                    for segment in re.split(r"&&|\|\||;|\n", command):
                        head = segment.split()[:2]
                        if head and head[0] == "lens":
                            stats["lens_find" if head[1:] == ["find"] else "lens_which" if head[1:] == ["which"] else "lens"] += 1
                            lensed.update(w.strip("'\"") for w in segment.split() if w.strip("'\"").endswith(".dart"))
                        elif head and head[0] == "dart-outline":
                            stats["dart_outline"] += 1
                elif name == "Skill" and "dartlens" in json.dumps(data):
                    stats["skill"] += 1
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in uses:
                use = uses[block["tool_use_id"]]
                data = use.get("input") or {}
                text = result_text(block.get("content"))
                if use.get("name") == "Read":
                    path = data.get("file_path") or ""
                    full = data.get("offset") is None and data.get("limit") is None
                    lines = text.count("\n") + 1
                    if block.get("is_error") and "dartlens" in text:
                        stats["read_refused"] += 1
                        continue
                    if full and path.endswith(".dart") and lines >= MIN_LINES:
                        stats["big_full_reads"] += 1
                        stats["big_full_read_tokens"] += round(len(text) / 2.3)
                        if any(path.endswith(t.lstrip("./")) for t in lensed):
                            stats["full_read_after_lens"] += 1
                    elif not full:
                        stats["ranged_reads"] += 1
                elif use.get("name") in ("Edit", "MultiEdit", "Write") and block.get("is_error") and NOT_READ.search(text):
                    stats["edit_refused_not_read"] += 1
    nudges = collections.Counter()
    logs = directory / "dartlens_logs.jsonl"
    for record in load(logs) if logs.exists() else []:
        if record.get("_file", "").endswith("nudge.jsonl"):
            nudges[record.get("event")] += 1
    return {"trial": meta["trial"], "task": meta["task"], "arm": meta["arm"], "status": meta.get("status"),
            "nudges": dict(nudges), **stats}


def main():
    parser = argparse.ArgumentParser(description="Parcours d'adoption de lens, essai par essai, puis par bras.")
    parser.add_argument("results")
    parser.add_argument("--json")
    args = parser.parse_args()
    trials = [trial_metrics(d) for d in sorted(Path(args.results).expanduser().iterdir())
              if (d / "meta.json").exists() and (d / "transcript.jsonl").exists()]
    keys = ("big_full_reads", "big_full_read_tokens", "ranged_reads", "lens", "lens_find", "dart_outline", "skill",
            "read_refused", "full_read_after_lens", "edit_refused_not_read")
    print("%-44s %s" % ("essai", " ".join("%s" % k for k in ("occas.", "tok", "cibl.", "lens", "find", "plan", "skill", "refus", "relu", "edit!", "rappels"))))
    for t in trials:
        print("%-44s %s  %s" % (t["trial"][:44], " ".join("%5s" % t.get(k, 0) for k in keys), t["nudges"]))
    by_arm = collections.defaultdict(collections.Counter)
    for t in trials:
        by_arm[t["arm"]].update({k: t.get(k, 0) for k in keys})
        by_arm[t["arm"]].update({"nudge_" + k: v for k, v in t["nudges"].items()})
        by_arm[t["arm"]]["trials"] += 1
    print()
    for arm, total in sorted(by_arm.items()):
        print(arm, dict(total))
    if args.json:
        Path(args.json).write_text(json.dumps({"trials": trials, "by_arm": by_arm}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
