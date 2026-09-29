#!/usr/bin/env python3
import argparse
import collections
import json
import re
import shlex
import sys
from pathlib import Path

MIN_LINES = 300
NOT_READ = re.compile(r"has not been read|must read|Read it first", re.I)
EDITS = ("Edit", "MultiEdit", "Write", "NotebookEdit")
SHELL_READS = ("cat", "sed", "head", "tail")
LENS_FILE = re.compile(r"^== (?!\$ )(.+?) \((\d+) lignes\) · (?:intégral|\d+/\d+ blocs · (\d+)/(\d+) lignes)", re.M)
LENS_KINDS = {"focus": "fichier", "command": "commande", "find": "find", "which": "which"}
LENS_LABELS = {"fichier": "lens", "commande": "lens cmd", "find": "lens find", "which": "lens which"}
MCP_FIND_TOOLS = {"mcp__plugin_dartlens_dartlens__find_code", "mcp__dartlens__find_code"}


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


def words_of(text):
    try:
        return shlex.split(text)
    except ValueError:
        return text.split()


def pipelines(command):
    return [[words_of(part) for part in s.split("|")] for s in re.split(r"&&|\|\||;|\n", command) if s.strip()]


def lens_kind(words):
    if not words or Path(words[0]).name != "lens":
        return None
    return words[1] if words[1:2] in (["find"], ["which"]) else "commande" if "--" in words else "fichier"


def span(words):
    tool, args = words[0], words[1:]
    if tool == "cat":
        return 1, None
    if tool == "sed":
        script = next((a for a in args if re.fullmatch(r"(\d+|\$)(,(\d+|\$))?p", a)), None)
        if "-n" not in args or not script:
            return None
        first, _, last = script[:-1].partition(",")
        last = last or first
        return (float("inf") if first == "$" else int(first)), (None if last == "$" else int(last))
    found = re.search(r"(?:^|\s)(?:-n\s*|--lines=|-)(\+?\d+)\b", " ".join(args))
    value = found.group(1) if found else "10"
    if tool == "head":
        return 1, int(value)
    return (int(value), None) if value.startswith("+") else (-int(value), None)


def covers(start, end, size, got):
    if start < 0:
        return got < -start or size is not None and -start >= size
    return start <= 1 and (end is None or got < end - start + 1 or size is not None and end >= size)


def shell_reads(command):
    reads = []
    for pipeline in pipelines(command):
        words = pipeline[0]
        if not words or words[0] not in SHELL_READS or any(p[:1] and p[0] not in SHELL_READS for p in pipeline[1:]):
            continue
        if any(w.startswith((">", "<<")) for w in words):
            continue
        files = [w for w in words[1:] if w.endswith(".dart")]
        bounds = span(words) if files else None
        if bounds:
            reads.append((words[0], files, bounds, len(pipeline) == 1))
    return reads


def session_results(directory):
    found = {}
    for path in (directory / "session").glob("**/*.jsonl"):
        for row in load(path):
            message = row.get("message")
            if not isinstance(row.get("toolUseResult"), dict) or not isinstance(message, dict):
                continue
            for block in message.get("content") if isinstance(message.get("content"), list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    found[block.get("tool_use_id")] = row["toolUseResult"]
    return found


def collapse(labels):
    out = []
    for label in labels:
        if out and out[-1][0] == label:
            out[-1][1] += 1
        else:
            out.append([label, 1])
    return " → ".join(label if count == 1 else "%s ×%d" % (label, count) for label, count in out)


def trial_metrics(directory):
    meta = json.loads((directory / "meta.json").read_text())
    repo = (meta.get("repo") or "").rstrip("/") + "/"

    def rel(path):
        return path[len(repo):] if path.startswith(repo) else re.sub(r"^\./", "", path)

    extra = session_results(directory)
    uses, stats, events, whole, sizes, lensed = {}, collections.Counter(), [], [], {}, set()

    def send(tool, path, lines, ts):
        whole.append({"tool": tool, "file": path, "lines": lines, "ts": ts, "at": len(events)})

    for entry in load(directory / "transcript.jsonl"):
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        for block in message.get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                uses[block["id"]] = block
                if block.get("name") == "Skill" and "dartlens" in json.dumps(block.get("input")):
                    stats["skill"] += 1
                continue
            if block.get("type") != "tool_result" or block.get("tool_use_id") not in uses:
                continue
            use = uses[block["tool_use_id"]]
            name, data = use.get("name"), use.get("input") or {}
            text, error = result_text(block.get("content")), bool(block.get("is_error"))
            ts = (entry.get("timestamp") or "")[11:19]
            event = {"ts": ts, "parent": entry.get("parent_tool_use_id"), "label": name, "files": set(),
                     "refused": None, "modified": name in EDITS and not error}
            if name == "Read":
                path = rel(data.get("file_path") or "")
                event["files"].add(path)
                ranged = data.get("offset") is not None or data.get("limit") is not None
                if error and "dartlens" in text:
                    stats["read_refused"] += 1
                    size = re.search(r"fait (\d+) lignes", text)
                    event.update(label="Read(refus)", refused=path, size=int(size[1]) if size else 0)
                elif not error:
                    result = entry.get("tool_use_result")
                    result = result if isinstance(result, dict) else extra.get(block["tool_use_id"]) or {}
                    info = result.get("file") or {}
                    numbers = re.findall(r"^\s*(\d+)\t", text, re.M)
                    start = info.get("startLine") or (int(numbers[0]) if numbers else 1)
                    lines, total, limit = info.get("numLines", len(numbers)), info.get("totalLines"), data.get("limit")
                    full = not ranged or start <= 1 and (lines >= total if total is not None else bool(limit) and lines < limit)
                    event["label"] = "Read(plage=tout)" if ranged and full else "Read(plage)" if ranged else "Read"
                    if not path.endswith(".dart"):
                        event["label"] = event["label"].replace("Read", "Read " + (Path(path).suffix or "?"), 1)
                    if not path.endswith(".dart"):
                        stats["other_chars"] += len(text)
                    else:
                        bucket = "read_range" if ranged else "read_full"
                        stats[bucket + "_n"] += 1
                        stats[bucket + "_lines"] += lines
                        stats[bucket + "_chars"] += len(text)
                        if total:
                            sizes[path] = total - 1
                        if full:
                            stats["read_range_whole"] += ranged
                            stats["full_read_after_lens"] += path in lensed
                            send(event["label"], path, lines, ts)
            elif name in MCP_FIND_TOOLS:
                event["label"] = "lens find (MCP)"
                if not error:
                    stats["lens_n"] += 1
                    stats["find_mcp_n"] += 1
                    stats["search_result_chars"] += len(text)
            elif name == "Bash":
                command = data.get("command") or ""
                segments = [p for pipeline in pipelines(command) for p in pipeline]
                kinds = [k for k in map(lens_kind, segments) if k]
                stats["dart_outline"] += sum(1 for w in segments if w and Path(w[0]).name == "dart-outline")
                reads = [] if kinds else shell_reads(command)
                head = next((w for w in segments if w and "=" not in w[0]), None) or ["Bash"]
                event["label"] = LENS_LABELS[kinds[0]] if kinds else reads[0][0] if reads else Path(head[0]).name
                if kinds:
                    for words in segments:
                        if lens_kind(words):
                            event["files"].update(rel(w) for w in words if w.endswith(".dart"))
                    lensed.update(event["files"])
                    if not error:
                        stats["lens_n"] += 1
                        stats["search_result_chars" if all(k in ("find", "which") for k in kinds) else "lens_chars"] += len(text)
                        for match in LENS_FILE.finditer(text):
                            path, total = rel(match[1]), int(match[4] or match[2])
                            sizes[path] = total
                            if path.endswith(".dart") and int(match[3] or match[2]) >= total:
                                send("lens", path, total, ts)
                elif reads:
                    for _, files, _, _ in reads:
                        event["files"].update(rel(f) for f in files)
                    if not error:
                        single = len(reads) == 1 and len(reads[0][1]) == 1
                        got = len(text.splitlines()) if single else float("inf")
                        stats["shell_n"] += 1
                        stats["shell_lines"] += len(text.splitlines())
                        stats["shell_chars"] += len(text)
                        for tool, files, (start, end), alone in reads:
                            for path in map(rel, files):
                                if alone and covers(start, end, sizes.get(path), got):
                                    stats["shell_whole"] += 1
                                    send(tool, path, sizes.get(path) or (got if single else None), ts)
            elif name in EDITS:
                event["files"].add(rel(data.get("file_path") or ""))
                stats["edit_refused_not_read"] += error and bool(NOT_READ.search(text))
            if error and not event["refused"]:
                event["label"] += "✗"
            events.append(event)
    nudges = collections.Counter()
    logs = directory / "dartlens_logs.jsonl"
    for record in load(logs) if logs.exists() else []:
        source = record.get("_file", "")
        if source.endswith("nudge.jsonl"):
            nudges[record.get("event")] += 1
        elif source.endswith("lens.jsonl"):
            stats["lens_" + LENS_KINDS.get(record.get("mode"), str(record.get("mode")))] += 1
            stats["lens_shown"] += record.get("shown_lines") or 0
            stats["lens_total"] += record.get("total_lines") or 0
    refusals = []
    for index, event in enumerate(events):
        if not event["refused"]:
            continue
        steps, until = [], None
        for later in events[index + 1:]:
            if later["parent"] != event["parent"]:
                continue
            steps.append(later["label"] + ("*" if event["refused"] in later["files"] else ""))
            if later["modified"]:
                until = later["ts"]
                break
        else:
            steps.append("fin")
        then = next((w for w in whole if w["at"] > index and w["file"] == event["refused"]), None)
        refusals.append({"ts": event["ts"], "file": event["refused"], "lines": event["size"], "path": collapse(steps),
                         "modified_at": until, "whole_after": then})
    big = {w["file"] for w in whole if (w["lines"] or 0) >= MIN_LINES}
    stats.update(whole_sends=len(whole), whole_files=len({w["file"] for w in whole}), whole_big_files=len(big))
    return {"trial": meta["trial"], "task": meta["task"], "arm": meta["arm"], "status": meta.get("status"),
            "nudges": dict(nudges), "whole": whole, "refusals": refusals, **stats}


def received(label, s):
    return "%-44s %-23s %-30s %-27s %-26s %12d" % (
        label[:44],
        "%d: %d l / %d c" % (s["read_full_n"], s["read_full_lines"], s["read_full_chars"]),
        "%d (%d tout): %d l / %d c" % (s["read_range_n"], s["read_range_whole"], s["read_range_lines"],
                                       s["read_range_chars"]),
        "%d: %d/%d l / %d c" % (s["lens_n"], s["lens_shown"], s["lens_total"], s["lens_chars"]),
        "%d (%d tout): %d l / %d c" % (s["shell_n"], s["shell_whole"], s["shell_lines"], s["shell_chars"]),
        s["other_chars"])


def adoption(label, s, nudges):
    return "%-44s %6d %4d %4d  %-10s %5d %5d %5d %5d %5d  %s" % (
        label[:44], s["whole_sends"], s["whole_files"], s["whole_big_files"],
        "%d/%d/%d/%d" % (s["lens_fichier"], s["lens_commande"], s["lens_find"], s["lens_which"]),
        s["dart_outline"], s["skill"], s["read_refused"], s["full_read_after_lens"], s["edit_refused_not_read"], nudges)


def main():
    parser = argparse.ArgumentParser(description="Code Dart reçu par Claude et parcours après refus, par essai et par variante.")
    parser.add_argument("results")
    parser.add_argument("--json")
    args = parser.parse_args()
    trials = [trial_metrics(d) for d in sorted(Path(args.results).expanduser().iterdir())
              if (d / "meta.json").exists() and (d / "transcript.jsonl").exists()]
    by_arm = collections.defaultdict(collections.Counter)
    for t in trials:
        by_arm[t["arm"]].update({k: v for k, v in t.items() if type(v) is int})
        by_arm[t["arm"]].update({"nudge_" + k: v for k, v in t["nudges"].items()})
        by_arm[t["arm"]]["trials"] += 1
    rows = [(t["trial"], collections.Counter(t), t["nudges"]) for t in trials]
    rows += [("= %s (%d essais)" % (arm, s["trials"]), s, {k[6:]: v for k, v in s.items() if k.startswith("nudge_")})
             for arm, s in sorted(by_arm.items())]
    print("Code Dart reçu (appels : lignes / caractères ; « tout » = plage couvrant le fichier entier)")
    print("%-44s %-23s %-30s %-27s %-26s %12s" % ("essai", "Read complet", "Read plage", "lens montrées/totales",
                                                 "shell cat/sed/head/tail", "hors .dart c"))
    for label, s, _ in rows:
        print(received(label, s))
    print()
    print("Fichiers Dart transmis entiers (tous outils) ; appels lens par sorte d'après lens.jsonl")
    print("%-44s %6s %4s %4s  %-10s %5s %5s %5s %5s %5s  %s" % ("essai", "envois", "fich", "gros", "f/c/find/w", "plan", "skill",
                                                             "refus", "relu", "edit!", "rappels"))
    for label, s, nudges in rows:
        print(adoption(label, s, nudges))
    print()
    print("Gros fichiers Dart (≥ %d lignes) transmis entiers" % MIN_LINES)
    if not any(t["whole_big_files"] for t in trials):
        print("  aucun")
    for t in trials:
        big = [w for w in t["whole"] if (w["lines"] or 0) >= MIN_LINES]
        if big:
            print("  %s : %s" % (t["trial"], " ; ".join("%s %s l. par %s à %sZ" % (w["file"], w["lines"], w["tool"], w["ts"])
                                                         for w in big)))
    print()
    print("Après chaque lecture refusée, jusqu'à la modification suivante ou la fin (* = même fichier)")
    if not any(t["refusals"] for t in trials):
        print("  aucune lecture refusée")
    for t in trials:
        for r in t["refusals"]:
            after = r["whole_after"]
            print("  %s %sZ %s (%d l.) : %s%s%s" % (
                t["trial"], r["ts"], r["file"], r["lines"], r["path"],
                " [modif. %sZ]" % r["modified_at"] if r["modified_at"] else "",
                " ; reçu entier ensuite par %s à %sZ" % (after["tool"], after["ts"]) if after else ""))
    if args.json:
        Path(args.json).write_text(json.dumps({"trials": trials, "by_arm": by_arm}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
