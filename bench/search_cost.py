#!/usr/bin/env python3
import argparse
import collections
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from adoption import EDITS, MCP_FIND_TOOLS, SHELL_READS, lens_kind, load, pipelines, result_text  # noqa: E402
from score import load_cc_usage, result_event  # noqa: E402

SEARCHES = {"grep", "rg", "find", "ls", "fd", "ag"}
EMPTY = re.compile(r"^(No (files|matches) found|\(Bash completed with no output\))?$")
LISTED = re.compile(r"^\S+\.(?:dart|md|arb|yaml)$")
NOT_FILE = re.compile(r"^(-|<|\d*>|\+?\d+$|[\d,$]+p$)")
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")
PLUGIN_ARMS = ("all", "all_refuse")


def money(value):
    return ("%.2f $" % value).replace(".", ",")


def per(part, whole):
    return ("%.1f %%" % (100.0 * part / whole if whole else 0)).replace(".", ",")


def commands(block):
    command = (block.get("input") or {}).get("command")
    if block.get("name") != "Bash" or not isinstance(command, str):
        return []
    return [[w for w in p[0] if not ASSIGNMENT.match(w)] for p in pipelines(command) if p and p[0]]


def is_search(block):
    if block.get("name") in ("Grep", "Glob") or block.get("name") in MCP_FIND_TOOLS:
        return True
    return any(w and (Path(w[0]).name in SEARCHES or w[:2] == ["git", "grep"]) for w in commands(block))


def read_files(block):
    if block.get("name") == "Read":
        return [(block.get("input") or {}).get("file_path") or ""]
    return [w for words in commands(block) if words and words[0] in SHELL_READS
            for w in words[1:] if not NOT_FILE.match(w)]


def named(path, text):
    return bool(re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(os.path.basename(path)), text))


def trial(cc, directory):
    meta = json.loads((directory / "meta.json").read_text())
    repo = meta["repo"].rstrip("/") + "/"

    def rel(path):
        return path[len(repo):] if path.startswith(repo) else re.sub(r"^\./", "", path)

    session, stream = directory / "session", directory / "transcript.jsonl"
    files = sorted(session.glob("*.jsonl")) + sorted(session.glob("subagents/**/*.jsonl"))
    calls = {}
    for path in files + [stream]:
        cc.scan(path, meta["session_id"], calls, collections.defaultdict(lambda: [0, 0.0, 0.0]), lambda s: True, set(),
                True, {})
    uses, results, first, thread, received = {}, {}, {}, collections.defaultdict(list), []
    for path in files:
        context = "main" if path.parent == session else "sub"
        for row in load(path):
            message, stamp = row.get("message"), cc.epoch(row.get("timestamp"))
            attachment = row.get("attachment") if isinstance(row.get("attachment"), dict) else {}
            if attachment.get("type") == "instructions":
                received.append((stamp, json.dumps(attachment, ensure_ascii=False)))
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if row.get("type") == "assistant":
                key = message.get("id")
                if key in calls and key not in first:
                    first[key] = stamp
                    thread[path].append((key, context))
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in uses:
                        uses[block["id"]] = {"block": block, "call": key, "stamp": stamp, "context": context}
            elif row.get("type") == "user":
                received.append((stamp, content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)))
                for block in content if isinstance(content, list) else []:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        results[block.get("tool_use_id")] = {"text": result_text(block.get("content")),
                                                             "error": bool(block.get("is_error")), "stamp": stamp}
    context_of = {key: context for keys in thread.values() for key, context in keys}
    cost = {key: sum(call.cost(False) or [0.0]) for key, call in calls.items()}
    main = next(keys for path, keys in thread.items() if path.parent == session)
    total = sum(cost.values())

    added = {}
    for keys in thread.values():
        for i, (key, _) in enumerate(keys[:-1]):
            now, nxt = calls[key], calls[keys[i + 1][0]]
            ids = [t for t, u in uses.items() if u["call"] == key and t in results]
            if not ids:
                continue
            gained = max(0, nxt.context - now.context - now.tokens[4])
            chars = sum(len(results[t]["text"]) for t in ids)
            rates = cc.rates_for(nxt.model)
            write = (nxt.tokens[1] * rates[1] + nxt.tokens[2] * rates[2]) / nxt.written if nxt.written else rates[1]
            carry = (write + rates[3] * (len(keys) - i - 2)) / 1e6
            for t in ids:
                tokens = gained * (len(results[t]["text"]) / chars if chars else 1 / len(ids))
                added[t] = (tokens, tokens * carry)

    edits = [(u["stamp"], u["call"], rel((u["block"].get("input") or {}).get("file_path") or "")) for u in uses.values()
             if u["block"].get("name") in EDITS]
    edits = sorted(e for e in edits if e[2] and not e[2].startswith("/"))
    edited = {e[2] for e in edits}
    cutoff_key = edits[0][1] if edits else main[-1][0]
    explore = {key for key in first if first[key] < first[cutoff_key]}
    phase = {c: [0, 0.0] for c in ("main", "sub")}
    for key in explore:
        phase[context_of[key]][0] += 1
        phase[context_of[key]][1] += cost[key]
    tools, content = collections.Counter(), collections.Counter()
    for t, u in uses.items():
        if u["call"] in explore:
            name, word = cc.tool_key(u["block"])
            tools[(name + " " + word if word else name) + (" (sous-agent)" if u["context"] == "sub" else "")] += 1
            kind = ("recherche" if is_search(u["block"]) else "lecture" if read_files(u["block"]) else
                    "skill" if name == "Skill" else "autre")
            tokens, usd = added.get(t, (0.0, 0.0))
            content.update({kind: tokens, kind + "$": usd})

    changes = json.loads((directory / "changes.json").read_text()) if (directory / "changes.json").is_file() else []
    diff = (directory / "diff.patch").read_text(errors="replace") if (directory / "diff.patch").is_file() else ""
    final = result_event(stream)
    answer = final.get("result") or ""
    modified = edited | {c["path"] for c in changes} | set(re.findall(r"^diff --git a/\S+ b/(\S+)", diff, re.M))
    reports = "\n".join(results[t]["text"] for t, u in uses.items()
                        if u["block"].get("name") in ("Task", "Agent") and t in results)
    reads, candidates = [], set()
    for t, u in uses.items():
        result = results.get(t)
        if not result or result["error"]:
            continue
        if u["block"].get("name") in ("Glob", "Grep"):
            candidates.update(rel(line.strip()) for line in result["text"].splitlines() if LISTED.match(line.strip()))
        paths = [rel(p) for p in read_files(u["block"]) if p]
        if not paths:
            continue
        candidates.update(paths)
        kept = any(p in modified or any(named(p, text) for text in (answer, meta["prompt"], diff, reports)) for p in paths)
        tokens, usd = added.get(t, (0.0, 0.0))
        reads.append({"context": u["context"], "paths": paths, "kept": kept, "tokens": tokens, "usd": usd})

    existing = [c["path"] for c in changes if c.get("status") != "A"]
    targets = existing or sorted(p for p in candidates if not p.startswith("/") and named(p, answer))
    seen = {}
    for target in targets:
        stamps = [s for s, text in received if named(target, text)]
        stamps += [u["stamp"] for u in uses.values()
                   if named(target, json.dumps(u["block"].get("input"), ensure_ascii=False))]
        seen[target] = min(stamps, default=float("inf"))
    searches = sorted((u["stamp"], t) for t, u in uses.items() if is_search(u["block"]))
    keys = collections.Counter()
    repeats = empty = refused = 0
    for _, t in searches:
        block = uses[t]["block"]
        data = block.get("input") or {}
        key = (uses[t]["context"], block.get("name"),
               json.dumps({k: v for k, v in data.items() if k != "description"}, sort_keys=True, ensure_ascii=False))
        repeats += keys[key] > 0
        keys[key] += 1
        result = results.get(t) or {"error": True}
        refused += bool(result["error"])
        empty += not result["error"] and bool(EMPTY.match(result["text"].strip()))
    cut = first[cutoff_key]
    before_first = min(seen.values(), default=float("inf"))
    before_all = max(seen.values(), default=float("inf"))
    return {
        "trial": "%s/%s" % (meta.get("campaign", directory.parent.name).split("-")[0], meta["trial"]),
        "total": total, "reported": final.get("total_cost_usd"), "orphans": len(set(calls) - set(first)),
        "calls": {c: sum(1 for k in first if context_of[k] == c) for c in ("main", "sub")},
        "phase": phase, "start": cost[main[0][0]] if main[0][0] in explore else 0.0,
        "tools": tools, "content": content, "reads": reads, "targets": targets,
        "unseen": [t for t, s in seen.items() if s == float("inf")],
        "searches": {"explore": sum(1 for s, _ in searches if s < cut), "all": len(searches),
                     "before_first": sum(1 for s, _ in searches if s < before_first),
                     "before_all": sum(1 for s, _ in searches if s < before_all),
                     "after_all": sum(1 for s, _ in searches if before_all < s < cut),
                     "repeats": repeats, "empty": empty, "refused": refused},
    }


def lens_use(directory):
    counts, done = collections.Counter(), set()
    for row in load(directory / "transcript.jsonl"):
        message = row.get("message")
        for block in (message.get("content") or []) if isinstance(message, dict) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("id") in done:
                continue
            done.add(block.get("id"))
            command = (block.get("input") or {}).get("command")
            if block.get("name") == "Bash" and isinstance(command, str):
                counts.update(k for k in (lens_kind(w) for p in pipelines(command) for w in p) if k)
            elif block.get("name") in MCP_FIND_TOOLS:
                counts.update(find=1, find_mcp=1)
    logs = directory / "dartlens_logs.jsonl"
    modes = collections.Counter(r.get("mode") for r in (load(logs) if logs.is_file() else [])
                                if str(r.get("_file", "")).endswith("lens.jsonl"))
    return counts, modes


def render(rows, plugin, cc):
    total = sum(r["total"] for r in rows)
    out = ["Coût de la recherche dans les %d témoins sans plugin" % len(rows),
           "Mesuré : usage de chaque appel (dédoublonné par message) × tarifs cc-usage %s, classes de cache comprises. "
           "« p » = conversation principale, « s » = sous-agents." % cc.PRICING_VERSION,
           "Coût de l'essai = somme de ces appels (entre parenthèses : total_cost_usd de claude -p).", ""]
    out.append("1. Phase d'exploration : appels commencés avant le premier appel qui modifie un fichier du projet "
               "(sans modification : avant la réponse finale)")
    out.append("%-52s %-17s %-14s %-19s %-9s %s" % ("essai", "coût essai", "appels p/s", "coût explo p / s",
                                                   "% essai", "hors 1er"))
    sums = collections.Counter()
    for r in rows:
        (mc, mu), (sc, su) = r["phase"]["main"], r["phase"]["sub"]
        explo = mu + su
        sums.update(total=r["total"], explo=explo, start=r["start"], main=mu, sub=su, mc=mc, sc=sc,
                    calls_main=r["calls"]["main"], calls_sub=r["calls"]["sub"])
        out.append("%-52s %-17s %-14s %-19s %-9s %s" % (
            r["trial"][:52], "%s (%s)" % (money(r["total"]), money(r["reported"] or 0)),
            "%d/%d sur %d/%d" % (mc, sc, r["calls"]["main"], r["calls"]["sub"]), "%s / %s" % (money(mu), money(su)),
            per(explo, r["total"]), per(explo - r["start"], r["total"])))
    out.append("%-52s %-17s %-14s %-19s %-9s %s" % (
        "= ensemble", money(total), "%d/%d sur %d/%d" % (sums["mc"], sums["sc"], sums["calls_main"], sums["calls_sub"]),
        "%s / %s" % (money(sums["main"]), money(sums["sub"])),
        per(sums["explo"], total), per(sums["explo"] - sums["start"], total)))
    out.append("« hors 1er » retire le premier appel principal (écriture du prompt système : payée quelle que soit la "
               "recherche).")
    out.append("Outils appelés pendant l'exploration :")
    for r in rows:
        out.append("  %s : %s" % (r["trial"], " · ".join("%s %d" % kv for kv in r["tools"].most_common()) or "aucun"))
    out.append("Résultats d'outils reçus pendant l'exploration : tokens par écart d'usage (méthode de la section 2) et coût "
               "estimé de leur présence jusqu'à la fin de leur contexte")
    kinds = ("recherche", "lecture", "skill", "autre")
    out.append("%-52s " % "essai" + " ".join("%-20s" % k for k in kinds))
    whole = collections.Counter()
    for r in rows:
        whole.update(r["content"])
        out.append("%-52s " % r["trial"][:52] + " ".join(
            "%-20s" % ("%d tk %s" % (r["content"][k], money(r["content"][k + "$"]))) for k in kinds))
    out.append("%-52s " % "= ensemble" + " ".join(
        "%-20s" % ("%d tk %s" % (whole[k], money(whole[k + "$"]))) for k in kinds)
        + " (%s de l'ensemble)" % per(sum(whole[k + "$"] for k in kinds), total))
    out.append("")
    out.append("2. Lectures sans suite visible : fichiers lus (Read, cat/sed/head/tail) ni modifiés dans l'essai, "
               "ni cités dans le diff, la réponse finale, la demande ou un rapport de sous-agent.")
    out.append("   Ce repérage par nom de fichier ne démontre pas qu'une lecture était inutile : elle peut avoir "
               "servi à comprendre le code ou à écarter une piste.")
    out.append("   Tokens mesurés par écart d'usage entre l'appel qui demande la lecture et le suivant du même contexte "
               "(sortie retirée, partage au prorata des caractères si plusieurs résultats arrivent ensemble).")
    out.append("   Coût estimé : ces tokens écrits une fois en cache à la classe (5 min / 1 h) de l'appel suivant, puis "
               "relus à chaque appel suivant du même contexte ; ni expiration ni compaction modélisées.")
    out.append("%-52s %-15s %-15s %-21s %-12s %s" % ("essai", "sans suite p/s", "toutes p/s", "tokens sans suite p/s",
                                                   "coût estimé", "% essai"))
    lost = collections.Counter()
    for r in rows:
        bad = [x for x in r["reads"] if not x["kept"]]
        by = {c: [x for x in bad if x["context"] == c] for c in ("main", "sub")}
        usd = sum(x["usd"] for x in bad)
        lost.update(n=len(bad), all=len(r["reads"]), tokens=sum(x["tokens"] for x in bad),
                    read_tokens=sum(x["tokens"] for x in r["reads"]), usd=usd)
        out.append("%-52s %-15s %-15s %-21s %-12s %s" % (
            r["trial"][:52], "%d/%d" % (len(by["main"]), len(by["sub"])),
            "%d/%d" % tuple(sum(1 for x in r["reads"] if x["context"] == c) for c in ("main", "sub")),
            "%d / %d" % tuple(round(sum(x["tokens"] for x in by[c])) for c in ("main", "sub")),
            money(usd), per(usd, r["total"])))
        names = collections.Counter(p for x in bad for p in x["paths"])
        if names:
            out.append("    " + " · ".join(("%s ×%d" % (p, n) if n > 1 else p) for p, n in sorted(names.items())))
    out.append("%-52s %-15s %-15s %-21s %-12s %s" % (
        "= ensemble", "%d lectures" % lost["n"], "%d lectures" % lost["all"],
        "%d sur %d" % (lost["tokens"], lost["read_tokens"]), money(lost["usd"]), per(lost["usd"], total)))
    out.append("")
    out.append("3. Recherches (Grep, Glob, Bash grep/rg/find/ls) avant d'avoir vu le nom des fichiers cibles")
    out.append("   Cibles : fichiers existants modifiés ; sans modification, fichiers lus ou listés cités dans la réponse. "
               "« Vu » : nom du fichier présent dans le prompt, les instructions, un résultat ou une commande, "
               "tous contextes confondus.")
    out.append("%-52s %-7s %-12s %-10s %-10s %-11s %-10s %-6s %s" % ("essai", "cibles", "explo/total", "avant 1re",
                                                             "avant tte", "après tte", "identiques", "vides", "refusées"))
    for r in rows:
        s = r["searches"]
        out.append("%-52s %-7d %-12s %-10d %-10d %-11d %-10d %-6d %d" % (
            r["trial"][:52], len(r["targets"]), "%d/%d" % (s["explore"], s["all"]), s["before_first"], s["before_all"],
            s["after_all"], s["repeats"], s["empty"], s["refused"]))
        if r["unseen"]:
            out.append("    jamais vus avant usage : " + ", ".join(r["unseen"]))
    out.append("« après tte » : recherches lancées après l'apparition de tous les noms cibles et avant la phase de "
               "modification. « identiques » : même outil, motif, chemin et filtre (ou même commande) qu'une recherche "
               "précédente du même contexte (tous paramètres). « refusées » : erreur ou permission refusée.")
    if any(r["orphans"] for r in rows):
        out.append("Appels absents des fichiers de session, exclus des phases : "
                   + ", ".join("%s %d" % (r["trial"], r["orphans"]) for r in rows if r["orphans"]))
    out.append("")
    out.append("Lecture : ces montants sont une CIBLE, la taille de ce qu'une meilleure recherche pourrait viser, pas une "
               "économie. On ne sait pas quelle part lens find ou lens which en supprimerait : aucun essai ne les a vus "
               "appelés spontanément, et la phase d'exploration contient aussi du travail qu'aucun outil de recherche "
               "ne remplace (chargement de skill, compréhension du code, lancement des tests).")
    out.append("")
    out.append("4. Essais avec plugin : appels à lens par sorte (Bash ou MCP / journal lens.jsonl)")
    found, logged = collections.Counter(), collections.Counter()
    for name, (counts, modes) in plugin:
        found.update({k: counts[k] for k in ("find", "which")})
        logged.update({k: modes[k] for k in ("find", "which")})
        out.append("  %-52s appels : fichier %d · commande %d · find %d (MCP %d) · which %d   journal : %s" % (
            name[:52], counts["fichier"], counts["commande"], counts["find"], counts["find_mcp"], counts["which"],
            " · ".join("%s %d" % kv for kv in sorted(modes.items(), key=lambda kv: str(kv[0]))) or "vide"))
    out.append("  => sur %d essais : find %d appel(s), %d entrée(s) de journal ; "
               "which %d appel(s), %d entrée(s) de journal." % (
                   len(plugin), found["find"], logged["find"], found["which"], logged["which"]))
    out.append("  Les appels et les journaux peuvent décrire la même exécution ; ces nombres ne s'additionnent pas.")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Coût de la recherche du bon code dans les témoins, et usage de "
                                                 "lens find / which dans les essais avec plugin. Lecture seule.")
    parser.add_argument("results", nargs="?", default="~/.cache/dartlens-bench/results")
    parser.add_argument("--json")
    args = parser.parse_args()
    root = Path(args.results).expanduser()
    cc = load_cc_usage()
    rows = [trial(cc, d) for d in sorted(root.glob("*/*.control.*")) if (d / "meta.json").is_file()]
    plugin = [("%s/%s" % (d.parent.name.split("-")[0], d.name), lens_use(d)) for d in sorted(root.glob("*/*"))
              if d.name.split(".")[1:2] and d.name.split(".")[1] in PLUGIN_ARMS and (d / "transcript.jsonl").is_file()]
    print(render(rows, plugin, cc))
    if args.json:
        Path(args.json).write_text(json.dumps({"trials": rows}, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
