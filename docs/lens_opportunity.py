#!/usr/bin/env python3
import collections
import json
import re
import sys
from pathlib import Path

CHARS_PER_TOKEN = 2.3
FILE_MIN_LINES = 150
OUTPUT_MIN_LINES = 80
READERS = {"cat", "bat", "less", "nl"}
SEARCHERS = {"grep", "rg", "find", "ls", "tree", "fd", "git"}
BUILDERS = {"flutter", "dart", "very_good", "dcm", "gradle", "xcodebuild", "pod", "npm", "fvm"}
SKIP = {"time", "rtk", "proxy", "env", "sudo", "nice", "command", "exec", "do", "then", "if", "while", "until", "!", "{"}
SKIP_SEGMENT = {"cd", "export", "set", "echo", "printf", "sleep", "mkdir", "true", "false", "for", "done", "fi", "local"}


def head_command(command):
    for segment in re.split(r"&&|\|\||;|\n", command or ""):
        words = segment.replace("(", " ").replace(")", " ").split()
        while words and (words[0] in SKIP or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0])):
            words.pop(0)
        if words and words[0] in SKIP_SEGMENT:
            continue
        if words:
            return words[0].rsplit("/", 1)[-1], segment
    return "", ""


def result_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
    return ""


def file_kind(path):
    path = (path or "").strip("'\"")
    if path.endswith(".dart"):
        return "lecture de code Dart entier (≥ 150 lignes)"
    if path.endswith(".md"):
        return "lecture de docs .md entières (≥ 150 lignes)"
    return "relecture de sorties sauvegardées, autres fichiers (≥ 150 lignes)"


def classify(name, tool_input, text, tool_result_meta):
    lines = text.count("\n") + 1 if text else 0
    if name == "Read":
        ranged = "offset" in tool_input or "limit" in tool_input
        total = (tool_result_meta or {}).get("file", {}).get("totalLines") or lines
        if not ranged and total >= FILE_MIN_LINES:
            return file_kind(tool_input.get("file_path")), tool_input.get("file_path")
        return None, None
    if name != "Bash":
        return None, None
    command = tool_input.get("command") or ""
    head, segment = head_command(command)
    piped = "|" in segment
    if head in READERS and lines >= FILE_MIN_LINES:
        if piped and re.search(r"\|\s*(head|tail|sed)\b", segment):
            return None, None
        if piped and re.search(r"\|\s*(grep|rg)\b", segment):
            return "recherche ≥ 80 lignes", None
        targets = [w for w in segment.split()[1:] if not w.startswith("-") and w != "|"]
        return file_kind(targets[-1] if targets else ""), (targets[-1] if targets else None)
    if head in SEARCHERS and lines >= OUTPUT_MIN_LINES:
        return "recherche ≥ 80 lignes", None
    if (head in BUILDERS or "test" in head) and lines >= OUTPUT_MIN_LINES:
        return "tests / analyse / build ≥ 80 lignes", None
    if lines >= OUTPUT_MIN_LINES and head not in ("sed", "head", "tail", "awk"):
        return "autre sortie ≥ 80 lignes", None
    return None, None


def scan(path):
    calls, events, seen, uses = 0, [], set(), {}
    for line in open(path, errors="replace"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            events.append(("boundary", calls))
        message = entry.get("message") or {}
        if entry.get("type") == "assistant":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    uses[block.get("id")] = (block.get("name"), block.get("input") or {})
            mid = message.get("id")
            if message.get("usage") and mid and mid not in seen and message.get("model") != "<synthetic>":
                seen.add(mid)
                calls += 1
        elif entry.get("type") == "user":
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    name, tool_input = uses.get(block.get("tool_use_id"), ("?", {}))
                    text = result_text(block.get("content"))
                    kind, target = classify(name, tool_input, text, entry.get("toolUseResult") if isinstance(entry.get("toolUseResult"), dict) else None)
                    if kind:
                        events.append((kind, calls, len(text), target))
    return calls, events, seen


def context_total(path):
    total, seen = 0, set()
    for line in open(path, errors="replace"):
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        message = entry.get("message") or {}
        usage = message.get("usage")
        mid = message.get("id")
        if entry.get("type") == "assistant" and usage and mid and mid not in seen and message.get("model") != "<synthetic>":
            seen.add(mid)
            total += sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return total


def analyse(project_dirs, excluded):
    files = [f for d in project_dirs for f in Path(d).expanduser().glob("**/*.jsonl")
             if "journal" not in f.name and not any(x in str(f) for x in excluded)]
    stats = collections.defaultdict(lambda: {"count": 0, "tokens": 0.0, "token_turns": 0.0, "rereads": 0})
    total_turns = 0
    for path in files:
        calls, events, _ = scan(path)
        if not calls:
            continue
        total_turns += context_total(path)
        boundaries = sorted(pos for kind, pos, *_ in events if kind == "boundary")
        read_targets = collections.Counter()
        for kind, pos, *rest in events:
            if kind == "boundary":
                continue
            chars, target = rest
            end = next((b for b in boundaries if b > pos), calls)
            tokens = chars / CHARS_PER_TOKEN
            s = stats[kind]
            s["count"] += 1
            s["tokens"] += tokens
            s["token_turns"] += tokens * max(0, end - pos)
            if target:
                if read_targets[target]:
                    s["rereads"] += 1
                read_targets[target] += 1
    out = {"files": len(files), "context_token_turns": total_turns, "categories": {}}
    for kind, s in stats.items():
        out["categories"][kind] = {
            "count": s["count"], "tokens": round(s["tokens"]), "share_of_context_pct": round(100 * s["token_turns"] / max(1, total_turns), 2),
            "median_tokens": None, "rereads": s["rereads"],
        }
    addressable = sum(s["token_turns"] for s in stats.values())
    out["addressable_share_pct"] = round(100 * addressable / max(1, total_turns), 2)
    out["counterfactual_saved_pct"] = {str(f): round(100 * addressable * (1 - f) / max(1, total_turns), 2) for f in (0.2, 0.35, 0.5)}
    return out


def main(out_path, *args):
    excluded = [a.split("=", 1)[1] for a in args if a.startswith("--exclude=")]
    groups = {}
    for arg in args:
        if arg.startswith("--group="):
            name, dirs = arg.split("=", 1)[1].split(":", 1)
            groups[name] = dirs.split(",")
    result = {name: analyse(dirs, excluded) for name, dirs in groups.items()}
    Path(out_path).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    names = list(result)
    order = sorted({k for r in result.values() for k in r["categories"]},
                   key=lambda k: -sum(r["categories"].get(k, {}).get("share_of_context_pct", 0) for r in result.values()))
    labels = {"recherche ≥ 80 lignes": "recherches longues", "lecture de code Dart entier (≥ 150 lignes)": "code Dart lu en entier",
              "relecture de sorties sauvegardées, autres fichiers (≥ 150 lignes)": "sorties sauvegardées relues",
              "autre sortie ≥ 80 lignes": "autres sorties longues", "lecture de docs .md entières (≥ 150 lignes)": "docs .md lues en entier",
              "tests / analyse / build ≥ 80 lignes": "tests / analyse / build"}
    legend = {"pro": "projet pro (le plus utilisé)", "perso": "projets perso"}
    spec = {"lens-target": {
        "kind": "grouped", "unit": "%", "groups": [labels.get(k, k) for k in order],
        "series": [{"label": "%s : %s %% au total" % (legend.get(n, n), ("%.1f" % result[n]["addressable_share_pct"]).replace(".", ",")),
                    "values": [result[n]["categories"].get(k, {}).get("share_of_context_pct", 0) for k in order]} for n in names],
        "title": "Ce que lens peut viser dans des sessions réelles",
        "subtitle": "Part du contexte relu occupée par des sorties que lens sait cibler (fichiers ≥ 150 lignes, sorties ≥ 80 lignes)",
        "label_groups": [0, 1],
    }}
    Path(out_path).with_name("lens_target_chart.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
