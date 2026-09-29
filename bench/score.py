#!/usr/bin/env python3
import argparse
import collections
import hashlib
import hmac
import importlib.machinery
import importlib.util
import inspect
import json
import os
import random
import re
import secrets
import statistics
import sys
from pathlib import Path

BENCH = Path(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "plugins", "jev-for-flutter", "lib"))
from jev_flutter import paths  # noqa: E402
from jev_flutter.commands.status import PRICE_PER_MTOK as JEV_USD_PER_MTOK  # noqa: E402

CC_USAGE = BENCH.parent / "plugins" / "jev-for-flutter" / "bin" / "cc-usage"
LENS_WORDS = ("lens", "dartlens", "jev-flutter")
TOOLING_WORDS = (r"dartlens", r"jev[-_]for[-_]flutter", r"jev_flutter", r"\blens\b", r"\bjev\b", r"typesafe", r"system ?one", r"convention_guard", r"context_router",
                 r"dart-outline", r"\bgarde\b.{0,30}\bconventions?\b", r"conventions? à vérifier", r"avis probabiliste",
                 r"\bp\s?=\s?[01][.,]\d+", r"\brout(?:eur|er)\b.{0,30}\b(?:mémoire|memory|skill)")
NOTICE = ("_Dans tous les paquets, quel que soit le bras, les phrases et lignes qui mentionnent l'outillage de l'essai "
          "sont retirées._")
GIT_COMMAND = re.compile(r"(?:^|[\s;&|(])((?:/\S*/)?git\s.*?)(?=$|[;&|)]|\n)")
GIT_SUSPECT = re.compile(r"--all\b|--branches|--remotes|--glob\b|\brefs/|\breflog\b|--walk-reflogs|\s-g\b|FETCH_HEAD"
                         r"|ORIG_HEAD|\bstash\b|\bfsck\b|--lost-found|\bcat-file\b|\brev-list\b|--reflog")
PATH_SUSPECT = re.compile(r"dartlens-bench|/results/[^/\s]+/[^/\s]+\.r\d+|\.claude/projects|/dl[bs]-|\.\./\.\.|\.cache/dartlens\b")
PATH_KEYS = ("file_path", "path", "pattern", "notebook_path")
JEV_ARMS = ("lens", "guard", "router", "all")
GATE_MARK = re.compile(r"run\.py'? --gate")
EXPLORATORY = "exploratoire : pas de verdict de qualité"


def load_cc_usage():
    loader = importlib.machinery.SourceFileLoader("cc_usage", str(CC_USAGE))
    spec = importlib.util.spec_from_loader("cc_usage", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def entries(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    yield entry
    except OSError:
        return


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    low = int(position)
    high = min(low + 1, len(values) - 1)
    return values[low] + (values[high] - values[low]) * (position - low)


def median(values):
    return statistics.median(values) if values else None


# ---------------------------------------------------------------- one trial


def usage(cc, trial_dir, meta):
    session_files = sorted((trial_dir / "session").glob("*.jsonl"))
    session_files += sorted((trial_dir / "session" / "subagents").rglob("*.jsonl"))
    stream = trial_dir / "transcript.jsonl"
    primary = session_files or ([stream] if stream.is_file() else [])
    everything = primary + ([stream] if session_files and stream.is_file() else [])
    # Shared calls and results: message ids and tool_use ids dedupe the persisted and streamed copies.
    calls, tools, results = {}, collections.defaultdict(lambda: [0, 0.0, 0.0]), set()
    session = meta.get("session_id") or meta["trial"]
    extra = [{}] if "compactions" in inspect.signature(cc.scan).parameters else []
    for path in everything:
        cc.scan(path, session, calls, tools, lambda stamp: True, results, True, *extra)
    kept = list(calls.values())
    api, flat = cc.valuation(kept, False), cc.valuation(kept, True)
    totals = {k: sum(c.tokens[i] for c in kept) for i, k in enumerate(cc.CLASSES)}
    totals.update(calls=len(kept), usage_blocks=sum(c.blocks for c in kept), usd=api["total"],
                  flat=flat["total"], ttl_split_missing=sum(not c.split_ok for c in kept))
    tool_counts = {k: v[0] for k, v in tools.items() if ":" not in k}
    bash_words = {k[5:]: v[0] for k, v in tools.items() if k.startswith("Bash:")}
    return totals, api["unpriced_calls"], tool_counts, bash_words, primary


def suspicious(text, repo, home):
    # The trial's own repository and session (its memory) are legitimate; the bench and other trials are not.
    if repo:
        text = text.replace(".claude/projects/" + re.sub(r"[^A-Za-z0-9]", "-", repo), "<session>")
        for variant in (repo, repo[len("/private"):] if repo.startswith("/private/") else repo):
            text = text.replace(variant, "<repo>")
    return bool(PATH_SUSPECT.search(text) or (home and home in text))


def activity(paths_, repo, home):
    seen, lens, git_cmds, hooks, hook_chars, dartlens_hooks = set(), 0, [], 0, 0, 0
    flagged = []
    for path in paths_:
        for entry in entries(path):
            kind = entry.get("type")
            if kind == "assistant":
                for block in (entry.get("message") or {}).get("content") or []:
                    if not isinstance(block, dict) or block.get("type") != "tool_use" or block.get("id") in seen:
                        continue
                    seen.add(block.get("id"))
                    name, data = block.get("name") or "", block.get("input") or {}
                    command = data.get("command") if isinstance(data.get("command"), str) else ""
                    if ("lens" in name.lower() or (name == "Skill" and "lens" in json.dumps(data).lower())
                            or re.search(r"(^|[\s/;&|(])(%s)(\s|$)" % "|".join(LENS_WORDS), command)):
                        lens += 1
                    for match in GIT_COMMAND.finditer(command):
                        git_cmds.append(match.group(1).strip())
                        if GIT_SUSPECT.search(match.group(1)):
                            flagged.append(match.group(1).strip())
                    targets = [command] + [str(data[k]) for k in PATH_KEYS if isinstance(data.get(k), str)]
                    if any(suspicious(t, repo, home) for t in targets if t):
                        flagged.append("%s %s" % (name, " ".join(t for t in targets if t)[:300]))
            text = hook_text(entry)
            if text is not None:
                hooks += 1
                hook_chars += len(text)
                dartlens_hooks += bool(re.search(r"dartlens|convention_guard|context_router", text, re.I))
    return {"lens_calls": lens, "git_cmds": git_cmds, "suspects": list(dict.fromkeys(flagged)),
            "hook_injections": hooks, "hook_chars": hook_chars, "dartlens_injections": dartlens_hooks}


def hook_text(entry):
    kind, sub = entry.get("type"), str(entry.get("subtype") or "")
    attachment = entry.get("attachment") if isinstance(entry.get("attachment"), dict) else None
    if kind == "attachment" and attachment and "hook" in str(attachment.get("type") or ""):
        # The bench's own permission gate runs in every arm and injects nothing.
        if GATE_MARK.search(str(attachment.get("command") or "")):
            return None
        return json.dumps(attachment, ensure_ascii=False)
    if kind == "system" and "hook" in sub:
        return json.dumps(entry, ensure_ascii=False)
    return None


def result_event(stream):
    found = None
    for entry in entries(stream):
        if entry.get("type") == "result":
            found = entry
    return found or {}


def last_text(paths_):
    text = ""
    for path in paths_:
        for entry in entries(path):
            if entry.get("type") != "assistant" or entry.get("isSidechain") or entry.get("parent_tool_use_id"):
                continue
            parts = [b.get("text", "") for b in (entry.get("message") or {}).get("content") or []
                     if isinstance(b, dict) and b.get("type") == "text"]
            if any(p.strip() for p in parts):
                text = "\n".join(parts)
    return text


def jev_stats(trial_dir):
    calls, errors, unavailable, latencies, questions, tokens, models, files = 0, 0, 0, [], 0, 0, set(), collections.Counter()
    output_tokens, missing_output = 0, 0
    window = 0
    for record in entries(trial_dir / "dartlens_logs.jsonl"):
        files[record.get("_file", "?")] += 1
        window += record.get("_attribution") == "window"
        if not str(record.get("_file", "")).endswith("usage.jsonl"):
            continue
        if record.get("error"):
            errors += 1
            unavailable += record.get("error") == "indisponible"
            continue
        calls += 1
        if isinstance(record.get("ms"), (int, float)):
            latencies.append(record["ms"])
        questions += record.get("questions") or 0
        tokens += record.get("input_tokens") or 0
        output = record.get("output_tokens")
        if type(output) is int and output >= 0:
            output_tokens += output
        else:
            missing_output += 1
        if record.get("model"):
            models.add(record["model"])
    return {"jev_calls": calls, "jev_errors": errors, "jev_unavailable": unavailable, "jev_ms": latencies,
            "jev_questions": questions, "jev_input_tokens": tokens, "jev_models": sorted(models),
            "jev_output_tokens": output_tokens if not missing_output else None,
            "jev_output_known_tokens": output_tokens, "jev_output_missing_calls": missing_output,
            "dartlens_logs": dict(files), "window_attributed": window}


def added_lines(diff):
    current, added = None, collections.defaultdict(list)
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[4:].strip()
            current = current[2:] if current.startswith("b/") else current
        elif line.startswith("+") and current and current != "/dev/null":
            added[current].append(line[1:])
    return added


def evaluate(check, answer, changes, diff):
    kind = check["kind"]
    changed = [c["path"] for c in changes]
    if kind == "answer":
        flags = re.IGNORECASE | re.MULTILINE
        ok = (all(re.search(p, answer, flags) for p in check.get("all", []))
              and (not check.get("any") or any(re.search(p, answer, flags) for p in check["any"]))
              and not any(re.search(p, answer, flags) for p in check.get("none", [])))
        return {"ok": ok}
    if kind == "touched":
        hits = [any(paths.matches(p, [g]) for p in changed) for g in check["paths"]]
        return {"ok": all(hits) if check.get("mode", "all") == "all" else any(hits)}
    if kind == "untouched":
        statuses = ("M", "D", "R", "C", "T") if check.get("existing_only") else ("M", "D", "R", "C", "T", "A")
        bad = [c["path"] for c in changes if c["status"] in statuses and paths.matches(c["path"], check["paths"])]
        return {"ok": not bad, "files": bad}
    if kind == "no_diff":
        ignore = check.get("ignore", ["pubspec.lock", "**/pubspec.lock", ".dart_tool/**", "build/**"])
        bad = [p for p in changed if not paths.matches(p, ignore)]
        return {"ok": not bad, "files": bad}
    if kind == "diff_added":
        regex = re.compile(check["regex"])
        scope = check.get("paths")
        count = sum(1 for path, lines in added_lines(diff).items() if not scope or paths.matches(path, scope)
                    for line in lines if regex.search(line))
        return {"ok": count > 0 if check.get("expect", True) else count == 0, "count": count}
    return {"ok": False, "detail": "type non évalué ici"}


def infra_attempts(cc, trial_dir):
    usd, count = 0.0, 0
    for attempt in sorted(trial_dir.glob("infra-*")):
        meta = read_json(attempt / "meta.json", None)
        if not meta:
            continue
        count += 1
        usd += usage(cc, attempt, meta)[0].get("usd", 0.0)
    return count, usd


def score_trial(cc, trial_dir, tasks, reviews, home):
    meta = read_json(trial_dir / "meta.json", None)
    if not meta:
        return None
    task = tasks.get(meta["task"]) or read_json(trial_dir / "task.json", {})
    row = {k: meta.get(k) for k in ("trial", "task", "project", "type", "arm", "lang", "rep", "position", "status",
                                    "duration_s", "returncode", "timeout", "jev_backend", "conditions", "conditions_id")}
    row["jev_expected"] = meta.get("jev_expected", meta.get("arm") in JEV_ARMS)
    row["infra_count"], row["infra_usd"] = infra_attempts(cc, trial_dir)
    if meta.get("status") != "done":
        row.update(valid=False, exec_ok=False, accepted=False, infra=meta.get("status") == "infra_failed")
        return row
    stream = trial_dir / "transcript.jsonl"
    result = result_event(stream)
    totals, unpriced, tools, bash, primary = usage(cc, trial_dir, meta)
    answer = result.get("result") if isinstance(result.get("result"), str) else last_text(primary)
    changes = read_json(trial_dir / "changes.json", [])
    diff = (trial_dir / "diff.patch").read_text(errors="replace") if (trial_dir / "diff.patch").is_file() else ""
    ran = {c["id"]: c for c in read_json(trial_dir / "checks.json", [])}
    checks = []
    for check in task.get("checks", []):
        outcome = ran.get(check["id"]) if check["kind"] in ("command", "grep") else evaluate(check, answer, changes, diff)
        outcome = dict(outcome or {"ok": False, "detail": "non exécuté"})
        outcome.update(id=check["id"], role=check.get("role", "success"))
        checks.append(outcome)
    completed = meta.get("returncode") == 0 and not meta.get("timeout") and result and not result.get("is_error")
    exec_ok = bool(completed) and all(c["ok"] for c in checks)
    review = reviews.get(meta["trial"])
    # A review counts only once both verdicts are given: a regression rejects the trial.
    accepted = None if review is None else bool(exec_ok and review["accepted"] and review["regression"] is False)
    mentioned = [f for f in task.get("expected_files", []) if f in answer or any(c["path"] == f for c in changes)]
    jev = jev_stats(trial_dir)
    row.update(valid=True, infra=False, completed=bool(completed), exec_ok=exec_ok, accepted=accepted, checks=checks,
               usage=totals, unpriced=unpriced, tools=tools, bash=bash, changes=len(changes),
               expected_hit="%d/%d" % (len(mentioned), len(task.get("expected_files", []))),
               num_turns=result.get("num_turns"), api_ms=result.get("duration_api_ms"),
               cc_cost_usd=result.get("total_cost_usd"), denials=len(result.get("permission_denials") or []),
               session_found=(meta.get("session") or {}).get("found"),
               memory_dir_matched=(meta.get("session") or {}).get("memory_dir_matched"),
               answer=answer, **activity(primary, meta.get("repo") or meta.get("worktree"), home), **jev)
    row["fake"] = meta.get("jev_backend") == "fake" or any(m.endswith("-fake") for m in jev["jev_models"])
    return row


# ---------------------------------------------------------------- aggregation


def cell(rows):
    valid = [r for r in rows if r["valid"]]
    success = [r for r in valid if (r["accepted"] if r["accepted"] is not None else r["exec_ok"])]
    usd = sum(r["usage"].get("usd", 0.0) for r in valid)
    flat = sum(r["usage"].get("flat", 0.0) for r in valid)
    ms = [m for r in valid for m in r["jev_ms"]]
    jev_tokens = sum(r["jev_input_tokens"] for r in valid)
    return {
        "trials": len(rows), "valid": len(valid), "exec_ok": sum(r["exec_ok"] for r in valid),
        "reviewed": sum(r["accepted"] is not None for r in valid), "successes": len(success),
        "rate": len(success) / len(valid) if valid else None, "usd": usd, "flat": flat,
        "unpriced": sum(sum(r["unpriced"].values()) for r in valid),
        "usd_per_success": usd / len(success) if success else None,
        "duration_success_median": median([r["duration_s"] for r in success if r.get("duration_s") is not None]),
        "duration_total": sum(r.get("duration_s") or 0 for r in valid),
        "api_calls_median": median([r["usage"].get("calls", 0) for r in valid]),
        "tool_results_median": median([sum(r["tools"].values()) for r in valid]),
        "lens_calls": sum(r["lens_calls"] for r in valid), "git_cmds": sum(len(r["git_cmds"]) for r in valid),
        "suspects": sum(len(r["suspects"]) for r in valid),
        "jev_calls": sum(r["jev_calls"] for r in valid), "jev_errors": sum(r["jev_errors"] for r in valid),
        "jev_unavailable": sum(r["jev_unavailable"] for r in valid),
        "jev_tokens": jev_tokens, "jev_usd": jev_tokens / 1e6 * JEV_USD_PER_MTOK,
        "jev_expected": any(r["jev_expected"] for r in rows),
        "jev_p50": percentile(ms, 0.5), "jev_p95": percentile(ms, 0.95),
        "injections": sum(r["dartlens_injections"] for r in valid), "hook_chars": sum(r["hook_chars"] for r in valid),
        "denials": sum(r["denials"] for r in valid),
        "infra": sum(r["infra_count"] for r in rows), "infra_usd": sum(r["infra_usd"] for r in rows),
    }


def jev_problem(c, max_error):
    # An arm meant to use Jev but that never reached it compares the control with itself.
    if not c["jev_expected"] or not c["valid"]:
        return None
    if c["jev_calls"] == 0:
        return "Jev indisponible : aucun appel réussi (%d erreur(s), dont %d sans requête)" % (c["jev_errors"], c["jev_unavailable"])
    share = c["jev_errors"] / (c["jev_calls"] + c["jev_errors"])
    if share > max_error:
        return "Jev indisponible : %.0f %% des requêtes en erreur (seuil %.0f %%)" % (100 * share, 100 * max_error)
    return None


def heterogeneity(rows):
    valid = [r for r in rows if r["valid"]]
    unknown = [r["trial"] for r in valid if not r.get("conditions")]
    if unknown:
        return "conditions inconnues pour %d essai(s) (méta sans conditions)" % len(unknown)
    ids = {r["conditions_id"] for r in valid}
    if len(ids) <= 1:
        return None
    keys = sorted({k for r in valid for k in r["conditions"]})
    differing = [k for k in keys if len({json.dumps(r["conditions"].get(k), sort_keys=True) for r in valid}) > 1]
    return "conditions hétérogènes entre essais (%s)" % ", ".join(differing)


def compare(by_task, arm, args):
    deltas, reps, cost_ratios, time_ratios, arm_usd, base_usd = [], [], [], [], 0.0, 0.0
    for task, arms in sorted(by_task.items()):
        a, b = arms.get(arm), arms.get(args.baseline)
        if not a or not b or a["rate"] is None or b["rate"] is None:
            continue
        deltas.append(a["rate"] - b["rate"])
        reps.append(min(a["valid"], b["valid"]))
        arm_usd += a["usd"]
        base_usd += b["usd"]
        if b["usd"] > 0:
            cost_ratios.append(a["usd"] / b["usd"])
        if a["duration_success_median"] and b["duration_success_median"]:
            time_ratios.append(a["duration_success_median"] / b["duration_success_median"])
    if not deltas:
        return None
    comp = {"tasks": len(deltas), "min_reps": min(reps), "delta": sum(deltas) / len(deltas), "ci": None,
            "non_inferior": None, "exploratory": len(deltas) < args.min_tasks or min(reps) < args.min_reps,
            "cost_total_ratio": arm_usd / base_usd if base_usd else None,
            "cost_ratio_dist": distribution(cost_ratios), "time_ratio_dist": distribution(time_ratios)}
    if not comp["exploratory"]:
        rng = random.Random(args.seed)
        means = sorted(sum(rng.choice(deltas) for _ in deltas) / len(deltas) for _ in range(args.boot))
        comp["ci"] = [means[int(0.025 * args.boot)], means[max(0, int(0.975 * args.boot) - 1)]]
        comp["non_inferior"] = comp["ci"][0] > -args.margin
    return comp


def distribution(values):
    if not values:
        return None
    return {"n": len(values), "min": min(values), "q1": percentile(values, 0.25), "median": percentile(values, 0.5),
            "q3": percentile(values, 0.75), "max": max(values)}


# ---------------------------------------------------------------- output


def fmt(value, kind="n"):
    if value is None:
        return "—"
    if kind == "pct":
        return ("%.0f %%" % (100 * value)).replace(".", ",")
    if kind == "usd":
        return ("%.2f $" % value).replace(".", ",")
    if kind == "usd4":
        return ("%.4f $" % value).replace(".", ",")
    if kind == "int":
        return "{:,}".format(value).replace(",", " ")
    if kind == "s":
        return "%.0f s" % value
    if kind == "ratio":
        return ("%.2f" % value).replace(".", ",")
    return str(round(value, 1)).replace(".", ",") if isinstance(value, float) else str(value)


def dist_text(d):
    if not d:
        return "—"
    return "médiane %s [q1 %s, q3 %s] min %s max %s (n=%d)" % (
        fmt(d["median"], "ratio"), fmt(d["q1"], "ratio"), fmt(d["q3"], "ratio"), fmt(d["min"], "ratio"),
        fmt(d["max"], "ratio"), d["n"])


def render(rows, by_task, by_arm, comparisons, args, blockers, cc):
    lines = list(blockers["global"])
    invalid = [r for r in rows if not r["valid"] and not r.get("infra")]
    if invalid:
        lines.append("Essais invalides (mise en situation échouée ou non terminés) : %s" % ", ".join(r["trial"] for r in invalid))
    infra = [r for r in rows if r.get("infra")]
    if infra:
        lines.append("Pannes d'infrastructure à relancer (hors comparaison) : %s" % ", ".join(r["trial"] for r in infra))
    lines.append("Valorisation API au tarif standard %s (bin/cc-usage), usages dédoublonnés par message. Facture réelle : %s."
                 % (cc.PRICING_VERSION, cc.BILL))
    lines.append("Coût Jev à part : tokens d'entrée de usage.jsonl à %s $/Mtok pour jev-1.13.0, sortie gratuite "
                 "(docs.typesafe.ai/models, vérifié le 29/09/2026 ; autre modèle à vérifier). Ni facture ni quota d'abonnement."
                 % ("%g" % JEV_USD_PER_MTOK).replace(".", ","))
    unpriced = sum(c["unpriced"] for c in by_arm.values())
    if unpriced:
        lines.append("Attention : %d appels sans tarif connu, exclus de la valorisation." % unpriced)
    header = "%-34s %-10s %6s %8s %9s %10s %9s %6s %6s %9s %6s" % (
        "tâche", "bras", "essais", "réussis", "taux", "$ Claude", "$/réussi", "t méd", "lens", "Jev p50", "injec")
    lines += ["", "Par tâche et par bras", header, "-" * len(header)]
    for task in sorted(by_task):
        for arm in args.arm_order:
            c = by_task[task].get(arm)
            if not c:
                continue
            lines.append("%-34s %-10s %6d %8s %9s %10s %9s %6s %6d %9s %6d" % (
                task[:34], arm, c["trials"], "%d/%d" % (c["successes"], c["valid"]), fmt(c["rate"], "pct"),
                fmt(c["usd"], "usd"), fmt(c["usd_per_success"], "usd"), fmt(c["duration_success_median"], "s"),
                c["lens_calls"], fmt(c["jev_p50"]), c["injections"]))
    lines += ["", "Totaux par bras (coût par réussite = coût Claude total / nombre de réussites, échecs compris)"]
    for arm in args.arm_order:
        c = by_arm.get(arm)
        if not c:
            continue
        lines.append("  %-10s essais %d, réussis %d/%d (%s), $ Claude %s, $/réussite %s, durée totale %s, "
                     "Jev %d appels (%d erreurs dont %d sans requête, p50 %s ms, p95 %s ms), "
                     "Jev %s tokens d'entrée soit %s (valorisation), Claude + Jev %s, injections %d (%d car.), "
                     "refus %d, git %d, signalements %d, pannes infra %d (%s, hors totaux)"
                     % (arm, c["trials"], c["successes"], c["valid"], fmt(c["rate"], "pct"), fmt(c["usd"], "usd4"),
                        fmt(c["usd_per_success"], "usd"), fmt(c["duration_total"], "s"), c["jev_calls"],
                        c["jev_errors"], c["jev_unavailable"], fmt(c["jev_p50"]), fmt(c["jev_p95"]),
                        fmt(c["jev_tokens"], "int"), fmt(c["jev_usd"], "usd4"), fmt(c["usd"] + c["jev_usd"], "usd4"),
                        c["injections"], c["hook_chars"], c["denials"], c["git_cmds"], c["suspects"], c["infra"],
                        fmt(c["infra_usd"], "usd")))
        if blockers["arms"].get(arm):
            lines.append("  %-10s %s" % ("", blockers["arms"][arm]))
    flagged = [r for r in rows if r["valid"] and r["suspects"]]
    if flagged:
        lines += ["", "Signalements (état d'origine, banc ou autres essais visés) : à trancher en revue"]
        for r in flagged:
            lines.append("  %s : %s" % (r["trial"], " | ".join(s[:120] for s in r["suspects"][:5])))
    if comparisons:
        method = ("exploratoire, sans rééchantillonnage" if all(c.get("exploratory") for c in comparisons.values())
                  else "bootstrap sur les tâches, %d tirages" % args.boot)
        lines += ["", "Comparaison au bras %s, répétitions regroupées par tâche (%s)" % (args.baseline, method),
                  "  Verdict de qualité à partir de %d tâches et %d répétitions par tâche et par bras (seuils du pilote, "
                  "PROTOCOL.md) ; en deçà, campagne exploratoire : ni IC ni verdict, l'écart est descriptif."
                  % (args.min_tasks, args.min_reps)]
        for arm, comp in comparisons.items():
            if not comp:
                continue
            ci = (", IC95 [%+.0f ; %+.0f], marge %.0f pts" % (100 * comp["ci"][0], 100 * comp["ci"][1], 100 * args.margin)
                  if comp["ci"] else "")
            lines.append("  %-10s %d tâches, au moins %d répétition(s) par tâche, écart de taux %+.0f pts%s : %s" % (
                arm, comp["tasks"], comp["min_reps"], 100 * comp["delta"], ci, comp["verdict"]))
            lines.append("  %-10s coût Claude : rapport des totaux %s ; par tâche %s" % (
                "", fmt(comp["cost_total_ratio"], "ratio"), dist_text(comp["cost_ratio_dist"])))
            lines.append("  %-10s temps médian des réussites, par tâche : %s" % ("", dist_text(comp["time_ratio_dist"])))
    return "\n".join(lines)


# ---------------------------------------------------------------- blind review


def tooling_pattern(tasks_dir):
    ids = set()
    projects = read_json(tasks_dir / "_projects.json", {})
    for settings in projects.values() if isinstance(projects, dict) else []:
        ruleset = ((settings or {}).get("plugin_files") or {}).get(".claude/dartlens/rules.json") or {}
        ids |= {r["id"] for r in ruleset.get("rules") or [] if isinstance(r, dict) and isinstance(r.get("id"), str)}
    words = list(TOOLING_WORDS) + [r"\[%s\]" % re.escape(i) for i in sorted(ids)]
    words += [r"(?<![\w-])%s(?![\w-])" % re.escape(i) for i in sorted(ids) if re.search(r"[-_.]", i)]
    return re.compile("|".join(words), re.IGNORECASE)


def strip_tooling(text, pattern):
    # Whole sentences go, never single words: a placeholder would itself betray the arm.
    kept, removed = [], 0
    for line in text.split("\n"):
        if not pattern.search(line):
            kept.append(line)
            continue
        sentences = re.split(r"(?<=[.!?;])\s+", line)
        rest = [s for s in sentences if not pattern.search(s)]
        removed += len(sentences) - len(rest)
        if any(re.search(r"\w", s) for s in rest):
            kept.append(" ".join(rest))
    return "\n".join(kept), removed


def strip_diff(diff, pattern):
    kept = [line for line in diff.split("\n") if not pattern.search(line)]
    return "\n".join(kept), len(diff.split("\n")) - len(kept)


def neutral(text):
    # Bench and plugin cache paths are named the same way whatever the arm, so a flagged command stays readable.
    text = re.sub(r"[^\s'\"]*dartlens-bench[^\s'\"]*", "<banc>", text)
    return re.sub(r"[^\s'\"]*\.cache/dartlens\b[^\s'\"]*", "<cache>", text)


def review_code(salt, trial):
    return hmac.new(salt.encode(), trial.encode(), hashlib.sha256).hexdigest()[:8]


def export_review(rows, tasks, directory, key_path, pattern):
    directory, key_path = directory.resolve(), key_path.resolve()
    if directory == key_path.parent or directory in key_path.parents:
        sys.exit("--key doit être hors du dossier remis au relecteur (%s)" % directory)
    if (directory / "key.json").exists():
        sys.exit("%s contient key.json (ancien format) : sors-le du dossier avant tout nouvel export" % directory)
    key = read_json(key_path, None) if key_path.exists() else {"salt": secrets.token_hex(16), "codes": {}}
    if not isinstance(key, dict) or not isinstance(key.get("salt"), str) or not isinstance(key.get("codes"), dict):
        sys.exit("clé illisible : %s" % key_path)
    directory.mkdir(parents=True, exist_ok=True)
    reviews_file = directory / "reviews.json"
    template = read_json(reviews_file, {}) if reviews_file.exists() else {}
    added, modified = 0, collections.defaultdict(lambda: [0, 0])
    for row in sorted((r for r in rows if r["valid"]), key=lambda r: review_code(key["salt"], r["trial"])):
        code = review_code(key["salt"], row["trial"])
        if key["codes"].get(code, row["trial"]) != row["trial"]:
            sys.exit("collision de code %s : exporte dans un nouveau dossier avec une nouvelle clé" % code)
        answer, cut_answer = strip_tooling(row.get("answer") or "", pattern)
        trial_dir = Path(row["_dir"])
        diff = (trial_dir / "diff.patch").read_text(errors="replace") if (trial_dir / "diff.patch").is_file() else ""
        diff, cut_diff = strip_diff(diff, pattern)
        git_lines = [strip_tooling(neutral(g), pattern)[0] for g in row["git_cmds"]]
        flagged = [strip_tooling(neutral(s), pattern)[0] for s in row["suspects"]]
        modified[row["arm"]][0] += 1
        modified[row["arm"]][1] += bool(cut_answer or cut_diff)
        key["codes"][code] = row["trial"]
        template.setdefault(code, {"accepted": None, "regression": None, "notes": ""})
        packet = directory / (code + ".md")
        if packet.exists():
            continue
        task = tasks.get(row["task"], {})
        prompt = task.get("prompt_" + (row.get("lang") or "fr"), "")
        grid = "\n".join("- [ ] " + item for item in task.get("review", []))
        commands = "\n".join("- `%s`" % g for g in git_lines if g.strip()) or "(aucune)"
        alerts = "\n".join("- `%s`" % s for s in flagged if s.strip()) or "(aucun)"
        packet.write_text(
            "# Essai %s\n\nTâche : %s (%s)\n\n%s\n\n## Demande\n\n%s\n\n## Grille\n\n%s\n\n## Réponse finale\n\n%s\n\n"
            "## Commandes git\n\n%s\n\n## Signalements (état d'origine, banc ou autres essais visés)\n\n%s\n\n"
            "## Diff\n\n```diff\n%s\n```\n" % (code, row["task"], task.get("type", ""), NOTICE, prompt, grid, answer,
                                              commands, alerts, diff))
        added += 1
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(json.dumps(key, indent=1))
    reviews_file.write_text(json.dumps(template, indent=1, ensure_ascii=False))
    return added, len(template), modified


def load_reviews(path, key_path):
    if not path:
        return {}, 0
    if not key_path:
        sys.exit("--reviews demande --key (la correspondance code → essai, gardée hors du dossier du relecteur)")
    reviews, key = read_json(path, {}), read_json(key_path, {})
    codes = key.get("codes") if isinstance(key, dict) else None
    if not isinstance(codes, dict):
        sys.exit("clé illisible : %s" % key_path)
    complete, incomplete = {}, 0
    for code, value in reviews.items():
        if code not in codes or not isinstance(value, dict):
            continue
        if isinstance(value.get("accepted"), bool) and isinstance(value.get("regression"), bool):
            complete[codes[code]] = value
        elif value.get("accepted") is not None or value.get("regression") is not None:
            incomplete += 1
    return complete, incomplete


# ---------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser(prog="score.py", description="Note une campagne du banc dartlens : critères, "
                                     "usages dédoublonnés et valorisés, appels Jev, tableau par tâche et par bras.")
    parser.add_argument("results", type=Path, help="dossier de la campagne (sortie de run.py)")
    parser.add_argument("--tasks", type=Path, default=BENCH / "tasks")
    parser.add_argument("--reviews", type=Path, help="reviews.json rempli par le relecteur")
    parser.add_argument("--key", type=Path, help="clé code → essai, hors du dossier du relecteur (créée ou complétée par l'export)")
    parser.add_argument("--export-review", type=Path, help="écrit ou complète un paquet de revue aveugle dans ce dossier")
    parser.add_argument("--baseline", default="control")
    parser.add_argument("--margin", type=float, default=0.10, help="marge de non-infériorité sur le taux de réussite")
    parser.add_argument("--min-tasks", type=int, default=20, help="tâches comparées sous lesquelles la campagne est "
                        "exploratoire, sans verdict de qualité")
    parser.add_argument("--min-reps", type=int, default=3, help="répétitions par tâche et par bras sous lesquelles la "
                        "campagne est exploratoire, sans verdict de qualité")
    parser.add_argument("--max-jev-errors", type=float, default=0.10,
                        help="part d'erreurs Jev au-delà de laquelle un bras est déclaré sans Jev")
    parser.add_argument("--boot", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--prices", type=Path, help="JSON {version, rates_usd_per_mtok: {modèle: [entrée, écriture 5 min, "
                        "écriture 1 h, lecture, sortie]}} qui remplace la grille de cc-usage")
    parser.add_argument("--json", type=Path, help="écrit aussi le détail en JSON")
    args = parser.parse_args()

    cc = load_cc_usage()
    if args.prices:
        grid = read_json(args.prices, None)
        if not isinstance(grid, dict) or not isinstance(grid.get("rates_usd_per_mtok"), dict):
            sys.exit("grille illisible : %s" % args.prices)
        cc.RATES = {m: tuple(r) for m, r in grid["rates_usd_per_mtok"].items()}
        cc.PRICING_VERSION = grid.get("version", str(args.prices))
    tasks = {}
    for path in sorted(args.tasks.glob("*.json")):
        task = read_json(path, None)
        if isinstance(task, dict) and task.get("id"):
            tasks[task["id"]] = task
    reviews, incomplete = load_reviews(args.reviews, args.key)
    results = args.results.resolve()
    home = str(results.parent.parent) if results.parent.name == "results" else None
    rows = []
    for trial_dir in sorted(p for p in results.iterdir() if p.is_dir() and not p.name.startswith("_")):
        row = score_trial(cc, trial_dir, tasks, reviews, home)
        if row:
            row["_dir"] = str(trial_dir)
            rows.append(row)
    if not rows:
        sys.exit("aucun essai dans %s" % args.results)
    if args.export_review:
        if not args.key:
            sys.exit("--export-review demande --key FICHIER, hors du dossier remis au relecteur")
        added, total, modified = export_review(rows, tasks, args.export_review, args.key, tooling_pattern(args.tasks))
        print("%d paquet(s) ajouté(s), %d au total dans %s ; clé : %s (à garder hors de vue du relecteur)"
              % (added, total, args.export_review, args.key))
        shares = {arm: m / n for arm, (n, m) in modified.items() if n}
        print("Paquets retouchés par le masquage : %s" % ", ".join("%s %.0f %%" % (a, 100 * s) for a, s in sorted(shares.items())))
        if shares and max(shares.values()) - min(shares.values()) > 0.25:
            print("Attention : le masquage touche les bras de façon inégale, l'aveugle est fragile ; relis quelques "
                  "paquets avant de les remettre.")
        return
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        grouped[row["task"]][row["arm"]].append(row)
    by_task = {task: {arm: cell(items) for arm, items in arms.items()} for task, arms in grouped.items()}
    arms_seen = sorted({r["arm"] for r in rows}, key=lambda a: (a != args.baseline, a))
    args.arm_order = arms_seen
    by_arm = {arm: cell([r for r in rows if r["arm"] == arm]) for arm in arms_seen}
    comparisons = {arm: compare(by_task, arm, args) for arm in arms_seen if arm != args.baseline}
    comparisons = {arm: comp for arm, comp in comparisons.items() if comp is not None}
    fake = any(r.get("fake") for r in rows)
    pending = sum(1 for r in rows if r["valid"] and r["accepted"] is None)
    mixed = heterogeneity(rows)
    blockers = {"global": [], "arms": {arm: jev_problem(c, args.max_jev_errors) for arm, c in by_arm.items()},
                "verdict": None}
    if fake:
        blockers["global"].append("FAUX SERVEUR JEV : essais de plomberie. Aucune conclusion de qualité ni d'économie.")
    if mixed:
        blockers["global"].append("CAMPAGNE HÉTÉROGÈNE : %s. Aucun verdict." % mixed)
    if pending:
        blockers["global"].append("Revue aveugle manquante ou incomplète pour %d essais%s : succès = critères exécutables "
                                  "seuls (provisoire)." % (pending, " (%d revues à moitié remplies)" % incomplete if incomplete else ""))
    blockers["verdict"] = ("faux serveur" if fake else "campagne hétérogène" if mixed else
                           "revue incomplète" if pending else None)
    for arm, comp in comparisons.items():
        if not comp:
            continue
        reason = blockers["verdict"] or blockers["arms"].get(arm) or blockers["arms"].get(args.baseline)
        if reason:
            comp["non_inferior"] = None
        comp["verdict"] = (EXPLORATORY if comp["exploratory"] else "— (%s)" % reason if reason else
                           "non-infériorité établie" if comp["non_inferior"] else "non établie")
    print(render(rows, by_task, by_arm, comparisons, args, blockers, cc))
    if args.json:
        detail = [{k: v for k, v in r.items() if k != "answer"} for r in rows]
        args.json.write_text(json.dumps({"pricing": cc.PRICING_VERSION, "fake": fake, "pending_reviews": pending,
                                         "jev_usd_per_mtok": JEV_USD_PER_MTOK,
                                         "jev_price_hypothetical": any(row.get("jev_calls") and row.get("jev_models") != ["jev-1.13.0"] for row in rows),
                                         "verdict_min": {"tasks": args.min_tasks, "reps": args.min_reps},
                                         "heterogeneous": mixed, "jev_blocked": blockers["arms"],
                                         "trials": detail, "by_task": by_task, "by_arm": by_arm,
                                         "comparisons": comparisons}, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main()
