#!/usr/bin/env python3
import glob
import json
import os
import sys

WRITE_5M, CACHE_READ = 2.5, 0.2


def ceiling(directory, chars_per_token):
    calls, seen, reads, pending, cost = 0, set(), [], set(), None
    for line in open(os.path.join(directory, "transcript.jsonl")):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "result":
            cost = entry.get("total_cost_usd")
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            data = block.get("input") or {}
            if block.get("type") == "tool_use" and block.get("name") == "Read" and data.get("offset") is None \
                    and data.get("limit") is None and data.get("file_path", "").endswith(".dart"):
                pending.add(block["id"])
            if block.get("type") == "tool_result" and block.get("tool_use_id") in pending:
                content = block.get("content")
                text = content if isinstance(content, str) else "".join(
                    b.get("text", "") for b in content or [] if isinstance(b, dict))
                if text.count("\n") + 1 >= 300:
                    reads.append((calls, len(text)))
        if entry.get("type") == "assistant" and message.get("usage") and message.get("id") not in seen:
            seen.add(message.get("id"))
            calls += 1
    saved = sum(chars / chars_per_token * (WRITE_5M + CACHE_READ * max(0, calls - pos - 1)) / 1e6 for pos, chars in reads)
    return cost, saved


total = {2.3: [0, 0], 3.5: [0, 0]}
for pattern in sys.argv[1:]:
    for directory in sorted(glob.glob(os.path.expanduser(pattern))):
        if not os.path.exists(os.path.join(directory, "meta.json")):
            continue
        for cpt in total:
            cost, saved = ceiling(directory, cpt)
            if cost:
                total[cpt][0] += cost
                total[cpt][1] += saved
for cpt, (cost, saved) in total.items():
    print("%.1f car./token : coût %.2f $, plafond %.2f $ (%.0f %%)" % (cpt, cost, saved, 100 * saved / cost))
