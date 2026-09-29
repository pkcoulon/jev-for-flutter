import argparse
import json
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import config, jev, policy, project, rules

USAGE = "jev-flutter eval guard [--from-rules | cas.jsonl] [--sweep] [--rules FICHIER]"
THRESHOLDS = [round(0.5 + 0.05 * i, 2) for i in range(10)]
TARGET_PRECISION = 0.9
SMALL_SAMPLE = 20


def cases_from_rules(ruleset):
    cases = []
    for rule in ruleset["rules"]:
        for example in rule.get("examples") or []:
            if isinstance(example, dict) and isinstance(example.get("after"), str) and isinstance(example.get("violation"), bool):
                cases.append({"rule": rule["id"], "file": rules.example_path(rule, ruleset), "before": "",
                              "after": example["after"], "context": example.get("context") or "", "violation": example["violation"]})
    return cases


def cases_from_file(file, ruleset):
    known = {rule["id"]: rule for rule in ruleset["rules"]}
    cases, rejected = [], 0
    for line in Path(file).read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except ValueError:
            rejected += 1
            continue
        if (not isinstance(case, dict) or case.get("rule") not in known or not isinstance(case.get("after"), str)
                or not isinstance(case.get("violation"), bool)):
            rejected += 1
            continue
        rule = known[case["rule"]]
        cases.append({"rule": rule["id"], "file": case.get("file") or rules.example_path(rule, ruleset),
                      "before": case.get("before") or "", "after": case["after"], "context": case.get("context") or "",
                      "violation": case["violation"]})
    return cases, rejected


def counts(pairs, limit):
    tp = sum(1 for p, v in pairs if p >= limit and v)
    fp = sum(1 for p, v in pairs if p >= limit and not v)
    fn = sum(1 for p, v in pairs if p < limit and v)
    return tp, fp, fn, len(pairs) - tp - fp - fn


def ratio(a, b):
    return a / b if b else None


def fmt(value):
    return "  -  " if value is None else "%.2f" % value


def suggest(pairs):
    positives = sum(1 for _, v in pairs if v)
    if not positives or positives == len(pairs):
        return None
    best = None
    for limit in THRESHOLDS:
        tp, fp, fn, _ = counts(pairs, limit)
        if not tp:
            continue
        precision, recall = tp / (tp + fp), tp / (tp + fn)
        f_half = 1.25 * precision * recall / (0.25 * precision + recall)
        key = (precision >= TARGET_PRECISION, recall if precision >= TARGET_PRECISION else f_half, limit)
        best = max(best, key) if best else key
    return best[2] if best else None


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))] if ordered else None


def main(argv):
    argv = list(argv)
    if argv[:1] == ["guard"]:
        argv = argv[1:]
    parser = argparse.ArgumentParser(prog="jev-flutter eval guard", usage=USAGE)
    parser.add_argument("cases", nargs="?")
    parser.add_argument("--from-rules", action="store_true")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--rules")
    args = parser.parse_args(argv)
    if args.cases and args.from_rules:
        print("usage : " + USAGE)
        return 1
    root = project.project_root()
    settings = config.load(root)
    rules_file = Path(args.rules).resolve() if args.rules else rules.path(root, settings)
    try:
        ruleset = rules.read(rules_file)
    except rules.RulesError as error:
        print("règles invalides ou absentes : %s" % "; ".join(error.problems))
        return 1
    allowed, reason = policy.jev_allowed(root, settings, "guard")
    if not allowed:
        print("Jev indisponible : %s" % reason)
        return 2
    if not policy.sendable(str(rules_file), root) or (args.cases and not policy.sendable(args.cases, root)):
        print("envoi refusé : les fichiers de règles et de cas doivent être dans le projet et non sensibles")
        return 2
    rejected = 0
    if args.cases:
        try:
            cases, rejected = cases_from_file(args.cases, ruleset)
        except OSError as error:
            print("lecture impossible : %s" % (error.strerror or error))
            return 1
    else:
        cases = cases_from_rules(ruleset)
    if not cases:
        print("aucun cas à évaluer")
        return 1
    by_id = {rule["id"]: rule for rule in ruleset["rules"]}
    # Production conditions: the hook's timeout and no retry, so what the hook would lose is counted as lost here.
    timeout = settings["jev"]["hook_timeout_s"]
    client = jev.Client(settings, "eval-guard", timeout=timeout, retries=0)

    def run(case):
        # Same path as the hook: the example sits after its context in a synthetic file, with its span.
        rule, context = by_id[case["rule"]], case["context"]
        text = context + "\n" + case["after"] if context else case["after"]
        change = {"before": case["before"], "after": case["after"],
                  "span": [context.count("\n") + 1 if context else 0, case["after"].count("\n") + 1]}
        states, _ = rules.build_states(case["file"], [change], text, reserve=rules.longest_question([rule]))
        started = time.monotonic()
        try:
            answers, _, jobs = rules.ask(client, states, [rule])
        except jev.JevError as error:
            return None, None, len(states), error.kind
        p = jev.probability(answers.get(rule["id"]))
        return p, int((time.monotonic() - started) * 1000), jobs, None if p is not None else "sans réponse"

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run, cases))
    latencies = [ms for _, ms, _, _ in results if ms is not None]
    lost = Counter(kind for _, _, _, kind in results if kind)
    pairs = {}
    for case, (p, _, _, _) in zip(cases, results):
        if isinstance(p, (int, float)):
            pairs.setdefault(case["rule"], []).append((float(p), case["violation"]))

    print("Évaluation de la garde · %d cas, %d règles, %d requêtes Jev%s" % (
        len(cases), len(pairs), sum(jobs for _, _, jobs, _ in results), ", %d lignes rejetées" % rejected if rejected else ""))
    print("Conditions de production : délai %.1f s par requête, sans nouvelle tentative." % timeout)
    if lost:
        print("Attention : %d cas perdus, silencieux en production (%s), exclus des chiffres." % (
            sum(lost.values()), ", ".join("%s : %d" % item for item in sorted(lost.items()))))
    if not pairs:
        print("Aucun cas évalué : Jev a échoué sur tous les cas.")
        return 2
    if jev.base_url() != jev.DEFAULT_URL:
        print("Attention : serveur Jev non officiel (%s). Réponses simulées : ces chiffres ne valent rien pour la qualité." % jev.base_url())
    if not args.cases:
        print("Attention : exemples écrits avec les règles, donc estimation optimiste.")
    if any(len(v) < SMALL_SAMPLE for v in pairs.values()):
        print("Attention : moins de %d cas par règle, précision et rappel indicatifs seulement." % SMALL_SAMPLE)
    print()
    print("%-28s %3s %5s %6s %6s %6s %3s %3s %3s %3s  %s" % ("règle", "n", "viol.", "seuil", "préc.", "rappel", "VP", "FP", "FN", "VN", "seuil suggéré"))
    everything = []
    for rule in ruleset["rules"]:
        rule_pairs = pairs.get(rule["id"])
        if not rule_pairs:
            continue
        everything.extend(rule_pairs)
        limit = rules.threshold(rule, ruleset, settings)
        tp, fp, fn, tn = counts(rule_pairs, limit)
        suggested = suggest(rule_pairs)
        print("%-28s %3d %5d %6.2f %6s %6s %3d %3d %3d %3d  %s" % (
            rule["id"][:28], len(rule_pairs), sum(v for _, v in rule_pairs), limit, fmt(ratio(tp, tp + fp)),
            fmt(ratio(tp, tp + fn)), tp, fp, fn, tn, "%.2f" % suggested if suggested else "n/a"))
    if args.sweep:
        print()
        print("%-28s %s" % ("précision / rappel par seuil", " ".join("%9.2f" % t for t in THRESHOLDS)))
        for rule in ruleset["rules"]:
            rule_pairs = pairs.get(rule["id"])
            if not rule_pairs:
                continue
            cells = []
            for limit in THRESHOLDS:
                tp, fp, fn, _ = counts(rule_pairs, limit)
                cells.append("%4s/%-4s" % (fmt(ratio(tp, tp + fp)).strip(), fmt(ratio(tp, tp + fn)).strip()))
            print("%-28s %s" % (rule["id"][:28], " ".join(cells)))
        cells = []
        for limit in THRESHOLDS:
            tp, fp, fn, _ = counts(everything, limit)
            cells.append("%4s/%-4s" % (fmt(ratio(tp, tp + fp)).strip(), fmt(ratio(tp, tp + fn)).strip()))
        print("%-28s %s" % ("ensemble", " ".join(cells)))
    print()
    if latencies:
        print("latence Jev : médiane %d ms, p95 %d ms, max %d ms (%d requêtes)" % (
            percentile(latencies, 0.5), percentile(latencies, 0.95), max(latencies), len(latencies)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
