#!/usr/bin/env python3
import collections
import glob
import os
import re
import statistics
import sys

sys.dont_write_bytecode = True
from score import entries, load_cc_usage  # noqa: E402

CC = load_cc_usage()
DEFAULT = ("~/.cache/dartlens-bench/results/adoption-2026-09-29/*.control.*",
           "~/.cache/dartlens-bench/results/pilot-2026-09-29/*.control.*")
BIG_LINES = 300
TTL = (3600, 300)
SHELL = {"cat", "head", "tail", "sed"}
DRIFT = (0.25, 1000)
SCOPES = (("big", "Read complets .dart >= 300 lignes (périmètre annoncé)"),
          ("read", "Read complets .dart, toutes tailles"),
          ("shell", "lectures shell .dart (cat, sed -n, head, tail)"))


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join(b.get("text") or "" for b in content or [] if isinstance(b, dict))


def size(block):
    return len(text_of(block.get("content")) if block.get("type") == "tool_result" else block.get("text") or "")


def shell_read(command):
    flat = CC.QUOTED.sub(lambda m: re.sub(r"[;&|`\n]", " ", m.group(0)), command or "")
    for segment in CC.SEGMENT.split(flat):
        words = [w for w in segment.split() if w not in CC.PREFIXES and not CC.ASSIGNMENT.match(w)]
        if words and os.path.basename(words[0]) in SHELL and ".dart" in segment \
                and (os.path.basename(words[0]) != "sed" or any(w.startswith("-n") for w in words)):
            return True
    return False


def scopes(use, block):
    data = use.get("input") or {}
    if block.get("type") != "tool_result" or block.get("is_error"):
        return set()
    if use.get("name") == "Read" and str(data.get("file_path", "")).endswith(".dart") \
            and data.get("offset") is None and data.get("limit") is None:
        return {"read", "big"} if text_of(block.get("content")).count("\n") + 1 >= BIG_LINES else {"read"}
    return {"shell"} if use.get("name") == "Bash" and shell_read(data.get("command")) else set()


def split(events):
    calls, blocks, compacts = [], collections.defaultdict(list), set()
    for kind, item in events:
        if kind == "call":
            calls.append(item)
        elif kind == "compact":
            compacts.add(len(calls))
        elif calls:
            blocks[len(calls) - 1].append(item)
    shrinks = {i for i in range(1, len(calls)) if calls[i].context < calls[i - 1].context}
    return calls, blocks, compacts, shrinks


def load(directory):
    outputs = collections.Counter()
    for path in glob.glob(os.path.join(directory, "session", "**", "*.jsonl"), recursive=True):
        for entry in entries(path):
            message = entry.get("message")
            if entry.get("type") == "assistant" and isinstance(message, dict) and message.get("usage"):
                outputs[message.get("id")] = max(outputs[message.get("id")], message["usage"].get("output_tokens") or 0)
    events, calls, uses, cost = collections.defaultdict(list), {}, {}, None
    for entry in entries(os.path.join(directory, "transcript.jsonl")):
        kind, message, context = entry.get("type"), entry.get("message"), entry.get("parent_tool_use_id") or "main"
        if kind == "result":
            cost = entry.get("total_cost_usd", cost)
        elif kind == "system" and entry.get("subtype") == "compact_boundary":
            events[context].append(("compact", None))
        elif kind == "assistant" and isinstance(message, dict):
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    uses[block.get("id")] = block
            key, usage = message.get("id"), message.get("usage")
            if not usage or message.get("model") == "<synthetic>":
                continue
            if key in calls:
                calls[key].merge(usage)
            else:
                calls[key] = CC.Call(directory, context, CC.epoch(entry.get("timestamp")), message.get("model"), usage,
                                     True)
                events[context].append(("call", calls[key]))
        elif kind == "user" and isinstance(message, dict):
            content = message.get("content")
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content or []
            events[context] += [("block", b) for b in blocks if isinstance(b, dict)]
    for key, call in calls.items():
        call.tokens[4] = max(call.tokens[4], outputs[key])
    return {c: split(e) for c, e in events.items()}, uses, cost


def fit(trials):
    xs, ys, outs = [], [], []
    for contexts, uses, _ in trials.values():
        for calls, blocks, compacts, shrinks in contexts.values():
            for s in range(len(calls) - 1):
                step = blocks.get(s, [])
                if len(step) == 1 and step[0].get("type") == "tool_result" and s + 1 not in compacts | shrinks \
                        and (uses.get(step[0].get("tool_use_id")) or {}).get("name") == "Read":
                    xs.append(size(step[0]))
                    ys.append(calls[s + 1].context - calls[s].context - calls[s].tokens[4])
                    outs.append(calls[s].tokens[4])
    slope, intercept = statistics.linear_regression(xs, ys)
    residuals = [y - intercept - slope * x for x, y in zip(xs, ys)]
    ratios = [y / x for x, y in zip(xs, ys) if x >= 2000]

    def partial(values):
        s, i = statistics.linear_regression(xs, values)
        return [v - i - s * x for x, v in zip(xs, values)]

    out_coef = statistics.linear_regression(partial(outs), partial([y + o for y, o in zip(ys, outs)])).slope
    return dict(n=len(xs), a=intercept, b=slope, resid=max(map(abs, residuals)), out=out_coef,
                lo=min(ratios), hi=max(ratios))


def weight(calls, s, lo, hi, stops):
    usd = 0.0
    for j in range(s + 1, len(calls)):
        if j > s + 1 and j in stops:
            break
        call = calls[j]
        rates = CC.rates_for(call.model) or sys.exit("modèle sans tarif dans cc-usage : %s" % call.model)
        _, five, hour, read, _ = call.tokens
        edges = (0, read, read + hour, read + hour + five, call.context)
        part = [max(0, min(hi, edges[i + 1]) - max(lo, edges[i])) / (hi - lo) for i in range(4)]
        usd += (part[0] * rates[3] + part[1] * rates[2] + part[2] * rates[1] + part[3] * rates[0]) / 1e6
    return usd


def analyse(contexts, uses, model):
    acc, notes = {k: collections.Counter() for k, _ in SCOPES}, collections.Counter()
    for name, (calls, blocks, compacts, shrinks) in contexts.items():
        stops = compacts | shrinks
        notes["compactions"] += len(compacts)
        notes["shrinks"] += len(shrinks)
        notes["main" if name == "main" else "sub"] += len(calls)
        ttl = TTL[0] if any(c.tokens[2] for c in calls) else TTL[1]
        gaps = [b.first - a.first for a, b in zip(calls, calls[1:]) if a.first and b.first]
        notes["over_ttl"] += sum(g > ttl for g in gaps)
        notes["max_gap"] = max([notes["max_gap"]] + gaps)
        for s, step in blocks.items():
            tagged = [(b, scopes(uses.get(b.get("tool_use_id")) or {}, b)) for b in step]
            if not any(t for _, t in tagged):
                continue
            chars = sum(size(b) for b in step) or 1
            unused = s + 1 >= len(calls) or s + 1 in stops
            if not unused:
                before, after = calls[s], calls[s + 1]
                net = after.context - before.context - before.tokens[4]
                expected = model["a"] + model["b"] * chars
                measured = abs(net - expected) <= max(DRIFT[1], DRIFT[0] * expected)
                lo = before.context + before.tokens[4] if measured else before.context
                per_token = weight(calls, s, lo, max(after.context, lo + 1), stops)
            for tag, _ in SCOPES:
                mine = [b for b, t in tagged if tag in t]
                if not mine:
                    continue
                row, own = acc[tag], sum(map(size, mine))
                row["n"] += len(mine)
                if unused:
                    row["unused"] += len(mine)
                    continue
                if measured:
                    mid, other = net * own / chars, chars - own
                    low = max(0, min(mid, net - max(0, model["a"]) - other * model["hi"]))
                    high = max(mid, net - other * model["lo"])
                else:
                    row["range"] += len(mine)
                    mid, low, high = (model[k] * own for k in ("b", "lo", "hi"))
                row["tokens"] += mid
                row["usd"] += mid * per_token
                row["low"] += low * per_token
                row["high"] += high * per_token
    return acc, notes


def fr(value, digits=2):
    return ("%.*f" % (digits, value)).replace(".", ",")


def line(label, row, cost):
    detail = "%d lecture(s)" % row["n"]
    extra = [text % row[k] for k, text in (("range", "%d hors mesure"), ("unused", "%d sans appel suivant")) if row[k]]
    detail += " (dont %s)" % ", ".join(extra) if extra else ""
    if not row["n"]:
        return "  %s : aucune" % label
    text = "  %s : %s, %s tokens ; %s $ = %s %%" % (label, detail, format(round(row["tokens"]), ",").replace(",", " "),
                                                    fr(row["usd"], 3), fr(100 * row["usd"] / cost, 1))
    return text + " [%s à %s %%]" % (fr(100 * row["low"] / cost, 1), fr(100 * row["high"] / cost, 1))


trials = {}
for pattern in sys.argv[1:] or DEFAULT:
    for directory in sorted(glob.glob(os.path.expanduser(pattern))):
        if os.path.exists(os.path.join(directory, "meta.json")):
            contexts, uses, cost = load(directory)
            if cost:
                trials[directory] = (contexts, uses, cost)
if not trials:
    sys.exit("aucun essai avec meta.json et coût final")
model = fit(trials)
print("Coût attribuable aux lectures, même parcours sans elles ; %d essais ; tarifs cc-usage %s"
      % (len(trials), CC.PRICING_VERSION))
print("Taille mesurée : %d pas à un seul Read, tokens ajoutés - sortie précédente = %s + car. / %s "
      "(écart max %d tokens ; coefficient libre de la sortie précédente %s, 1 : compatible avec une sortie renvoyée en entier)"
      % (model["n"], fr(model["a"], 0), fr(1 / model["b"]), model["resid"], fr(model["out"])))
total, notes_total = {k: collections.Counter() for k, _ in SCOPES}, collections.Counter()
cost_total = recomputed_total = 0.0
for directory, (contexts, uses, cost) in trials.items():
    acc, notes = analyse(contexts, uses, model)
    calls = [c for calls, _, _, _ in contexts.values() for c in calls]
    recomputed = sum(sum(c.cost(False)) for c in calls)
    cost_total += cost
    recomputed_total += recomputed
    notes_total.update({k: v for k, v in notes.items() if k != "max_gap"})
    notes_total["max_gap"] = max(notes_total["max_gap"], notes["max_gap"])
    print("\n%s (%s) : %d appels principaux, %d de sous-agents ; coût final %s $ (recalculé %s $) ; "
          "compactions %d, baisses de contexte %d, écarts > durée du cache %d (max %d s)"
          % (os.path.relpath(directory, os.path.dirname(os.path.dirname(directory))),
             ", ".join(sorted({c.model for c in calls})), notes["main"], notes["sub"], fr(cost, 3), fr(recomputed, 3),
             notes["compactions"], notes["shrinks"], notes["over_ttl"], notes["max_gap"]))
    for key, label in SCOPES:
        print(line(label, acc[key], cost))
        total[key].update(acc[key])
print("\nTOTAL %d essais : coût final %s $ (recalculé %s $) ; compactions %d, baisses de contexte %d, "
      "écarts > durée du cache %d (max %d s)"
      % (len(trials), fr(cost_total, 3), fr(recomputed_total, 3), notes_total["compactions"], notes_total["shrinks"],
         notes_total["over_ttl"], notes_total["max_gap"]))
for key, label in SCOPES:
    print(line(label, total[key], cost_total))
print("\nMesure : tokens ajoutés entre deux appels successifs du même contexte, moins la sortie finale du premier ;"
      " partagés au prorata des caractères quand le pas contient plusieurs contenus.")
print("Classe : position de la lecture dans la partie lue, écrite 1 h, écrite 5 min ou non cachée de chaque appel"
      " suivant du même contexte .")
print("Fourchette : bas sans l'enveloppe du pas (%s tokens) ; dans un pas mixte, les autres contenus comptés de"
      " %s à %s car./token (ratios mesurés sur des lectures, supposés pour les autres contenus) ; même plage pour une lecture hors mesure."
      % (fr(max(0, model["a"]), 0), fr(1 / model["hi"]), fr(1 / model["lo"])))
print("Hypothèse non mesurée : mêmes appels et même contenu sans ces lectures ; ni l'extrait qui les remplacerait,"
      " ni les tours de recherche évités ne sont comptés.")
