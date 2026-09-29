#!/usr/bin/env python3
import argparse
import collections
import glob
import json
from pathlib import Path

from adoption import MIN_LINES, result_text
from score import entries, load_cc_usage


def attributed_cost(cc, call, tokens):
    classes = list(zip(cc.rates_for(call.model)[:4], call.tokens[:4]))
    estimates = []
    for reverse in (False, True):
        remaining, cost = tokens, 0
        for rate, count in sorted(classes, reverse=reverse):
            taken = min(remaining, count)
            cost += taken * rate / 1e6
            remaining -= taken
        estimates.append(cost)
    return estimates


def estimate(cc, events, chars_per_token):
    live = collections.defaultdict(int)
    low, high, inconsistent = 0, 0, 0
    for kind, scope, value in events:
        if kind == "read":
            live[scope] += value
        elif kind == "compact":
            live[scope] = 0
        elif kind == "call":
            tokens = live[scope] / chars_per_token
            inconsistent += tokens > sum(value.tokens[:4])
            lower, upper = attributed_cost(cc, value, tokens)
            low += lower
            high += upper
    return {"chars_per_token": chars_per_token, "attributed_usd": [low, high],
            "inconsistent_calls": inconsistent}


def inspect_trial(cc, directory):
    calls, pending, events = {}, {}, []
    read_ids, contexts = set(), set()
    for index, entry in enumerate(entries(directory / "transcript.jsonl")):
        scope = entry.get("parent_tool_use_id") or "main"
        if entry.get("type") == "system" and entry.get("subtype") == "compact_boundary":
            events.append(("compact", scope, None))
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if entry.get("type") == "assistant" and usage and message.get("model") != "<synthetic>" \
                and not entry.get("isApiErrorMessage"):
            key = message.get("id") or entry.get("requestId") or str(index)
            if key in calls:
                calls[key].merge(usage)
            else:
                call = calls[key] = cc.Call(directory / "transcript.jsonl", scope,
                                            cc.epoch(entry.get("timestamp")), message.get("model"), usage, True)
                if cc.rates_for(call.model) is None:
                    raise ValueError("%s : modèle sans tarif : %s" % (directory.name, call.model))
                contexts.add(scope)
                events.append(("call", scope, call))
        content = message.get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            data = block.get("input") or {}
            if block.get("type") == "tool_use" and block.get("name") == "Read" \
                    and data.get("offset") is None and data.get("limit") is None \
                    and str(data.get("file_path", "")).endswith(".dart"):
                pending[block["id"]] = scope
            key = block.get("tool_use_id")
            if block.get("type") == "tool_result" and key in pending and key not in read_ids:
                read_ids.add(key)
                text = result_text(block.get("content"))
                if not block.get("is_error") and text.count("\n") + 1 >= MIN_LINES:
                    events.append(("read", pending[key], len(text)))
    streamed_calls = len(calls)
    for path in sorted((directory / "session").rglob("*.jsonl")):
        cc.scan(path, str(directory), calls, collections.defaultdict(lambda: [0, 0.0, 0.0]),
                lambda stamp: True, set(), True, {})
    if not calls:
        raise ValueError("%s : aucun appel facturable dans le transcript" % directory.name)
    missing = sum(not call.split_ok for call in calls.values())
    if missing:
        raise ValueError("%s : durée du cache manquante ou incohérente pour %d appels" % (directory.name, missing))
    return {"trial": str(directory), "calls": len(calls), "contexts": len(contexts),
            "calls_without_stream_position": len(calls) - streamed_calls,
            "reads": sum(kind == "read" for kind, _, _ in events),
            "read_chars": sum(value for kind, _, value in events if kind == "read"),
            "compactions": sum(kind == "compact" for kind, _, _ in events),
            "usage": {name: sum(call.tokens[i] for call in calls.values()) for i, name in enumerate(cc.CLASSES)},
            "recorded_cost_usd": sum(sum(call.cost(False)) for call in calls.values()),
            "estimates": [estimate(cc, events, cpt) for cpt in (2.3, 3.5)]}


def main():
    parser = argparse.ArgumentParser(description="Estimer le coût attribuable aux grandes lectures Dart enregistrées.")
    parser.add_argument("patterns", nargs="+", help="dossiers d'essais, ou motifs glob entre guillemets")
    parser.add_argument("--json", type=Path, help="écrire le détail des hypothèses et résultats")
    args = parser.parse_args()
    directories = sorted({Path(p).resolve() for pattern in args.patterns
                          for p in glob.glob(str(Path(pattern).expanduser()))
                          if (Path(p) / "meta.json").is_file() and (Path(p) / "transcript.jsonl").is_file()})
    if not directories:
        parser.error("aucun essai avec meta.json et transcript.jsonl")
    cc = load_cc_usage()
    try:
        trials = [inspect_trial(cc, directory) for directory in directories]
    except (OSError, ValueError) as error:
        parser.error(str(error))
    cost = sum(t["recorded_cost_usd"] for t in trials)
    totals = []
    for i, cpt in enumerate((2.3, 3.5)):
        totals.append({"chars_per_token": cpt,
                       "attributed_usd": [sum(t["estimates"][i]["attributed_usd"][j] for t in trials) for j in (0, 1)],
                       "inconsistent_calls": sum(t["estimates"][i]["inconsistent_calls"] for t in trials)})
    result = {"scope": "Read complet de Dart, au moins %d lignes reçues, parcours inchangé" % MIN_LINES,
              "pricing": cc.PRICING_VERSION, "recorded_cost_usd": cost, "estimates": totals, "trials": trials,
              "assumptions": ["Le texte reste dans le contexte de l'agent lecteur jusqu'à sa compaction ou sa fin.",
                              "La conversion caractères/tokens est hypothétique.",
                              "L'attribution aux classes de facturation est inconnue : deux allocations extrêmes sont affichées.",
                              "Les contextes distincts et les usages répétés d'un message sont séparés.",
                              "Les usages sont complétés depuis les sessions persistées ; le parcours vient de transcript.jsonl."],
              "excluded": ["parcours différents, appels évités ou ajoutés", "find, which, Bash et sorties de commande",
                           "coût Jev, qualité, temps, facture et quota d'abonnement"],
              "interpretation": "Simulation conditionnelle : ni économie mesurée ni plafond global du plugin."}
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("Grandes lectures Dart : %d essais, %d lectures, %d caractères." % (
        len(trials), sum(t["reads"] for t in trials), sum(t["read_chars"] for t in trials)))
    print("Appels enregistrés : %.2f $ au tarif API (%s)." % (cost, cc.PRICING_VERSION))
    for item in totals:
        if item["inconsistent_calls"]:
            print("%.1f car./token : hypothèse incohérente avec le contexte de %d appels ; montant non interprétable." % (
                item["chars_per_token"], item["inconsistent_calls"]))
        else:
            print("%.1f car./token : coût attribuable estimé entre %.2f $ et %.2f $." % (
                item["chars_per_token"], *item["attributed_usd"]))
    print(result["interpretation"])
    print("Contexte supposé conservé jusqu'à la compaction ou la fin de l'agent ; attribution du cache inconnue.")
    print("Ne mesure pas find/which, les appels évités, le détour par lens, la qualité ni le nombre d'essais nécessaire.")


if __name__ == "__main__":
    main()
