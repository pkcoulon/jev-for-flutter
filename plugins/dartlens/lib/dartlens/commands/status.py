import argparse
import collections
import json
import math
import os
import time
from pathlib import Path

from .. import config, hookio, jev, memory, policy, project
from .log import error_kind, is_number, name, read_records

# TypeSafe rate shown in its cookbooks (jev-1.12, 2026-09); not confirmed for the pinned model.
PRICE_PER_MTOK = 0.042
PRICE_NOTE = "0,042 $/MTok d'entrée, sortie gratuite (tarif des cookbooks TypeSafe, jev-1.12, 2026-09 ; non confirmé pour %s)"
WINDOWS = (("24 h", 86400), ("7 j", 7 * 86400))
BREAKERS = {"breaker.json": "garde", "breaker-router.json": "routeur"}
MAX_PROBLEMS = 3


def fr(value, digits=1):
    return ("%.*f" % (digits, value)).replace(".", ",")


def num(value):
    return "{:,}".format(int(value)).replace(",", " ")


def finite(value):
    return value if is_number(value) and math.isfinite(value) and value >= 0 else None


def config_line(root, problems):
    found = next((n for n in config.CONFIG_FILES if (Path(root) / n).is_file()), None)
    if not found:
        return "aucune (valeurs par défaut ; activer Jev dans .claude/dartlens.json)"
    if not problems:
        return found
    more = " ; +%d" % (len(problems) - MAX_PROBLEMS) if len(problems) > MAX_PROBLEMS else ""
    return "%s, %d problème(s) : %s%s" % (found, len(problems), " ; ".join(problems[:MAX_PROBLEMS]), more)


def key_line():
    for var in jev.KEY_ENV:
        if os.environ.get(var, "").strip():
            return "présente (variable %s)" % var
    try:
        if jev.KEY_FILE.read_text().strip():
            mode = jev.KEY_FILE.stat().st_mode & 0o777
            loose = " ; droits %o, chmod 600 conseillé" % mode if mode & 0o077 else ""
            return "présente (fichier %s%s)" % (memory.display(jev.KEY_FILE), loose)
    except OSError:
        pass
    return "absente (%s ou %s)" % (", ".join(jev.KEY_ENV), memory.display(jev.KEY_FILE))


def policy_line(root):
    rules = policy.user_policy()
    source = memory.display(policy.USER_POLICY) if policy.USER_POLICY.is_file() else "aucune politique utilisateur"
    counts = "%d dépôt(s), %d chemin(s) exclus" % (len(rules["deny_remotes"]), len(rules["deny_paths"]))
    refused = policy.refusal(root)
    return "%s, %s ; ce projet : %s" % (source, counts, "EXCLU (%s)" % refused if refused else "non exclu")


def breaker_state(file):
    if not file.exists():
        return "fermé"
    data = hookio.read_json(file, None)
    failures, last = (data.get("failures"), data.get("last")) if isinstance(data, dict) else (None, None)
    if finite(failures) is None or finite(last) is None:
        return "fichier illisible (%s, à supprimer)" % memory.display(file)
    elapsed = time.time() - last
    if jev.Breaker(file).is_open():
        return "OUVERT, %d échecs, Jev sauté encore %d s" % (failures, max(0, int(jev.BREAKER_COOLDOWN - elapsed)))
    if failures:
        return "fermé (%d échec(s) consécutif(s), dernier il y a %d s)" % (failures, int(elapsed))
    return "fermé"


def breaker_line():
    extra = sorted(f.name for f in jev.STATE_DIR.glob("breaker*.json") if f.name not in BREAKERS)
    return " ; ".join("%s %s" % (BREAKERS.get(n, n), breaker_state(jev.STATE_DIR / n)) for n in [*BREAKERS, *extra])


def rules_line(root, settings):
    file = Path(root) / settings["guard"]["rules_file"]
    shown = project.rel(file, root)
    if not file.is_file():
        return "absent (%s)" % shown
    try:
        data = json.loads(file.read_text())
    except (OSError, ValueError) as error:
        return "%s illisible : %s" % (shown, error)
    count = len(data["rules"]) if isinstance(data, dict) and isinstance(data.get("rules"), list) else 0
    try:
        from .. import rules
    except Exception:
        verdict = "validité non vérifiée (module rules indisponible)"
    else:
        errors, _ = rules.validate(data)
        verdict = "valides" if not errors else "%d erreur(s), dont : %s" % (len(errors), errors[0])
    sendable = "" if policy.sendable(str(file), root) else " ; NON envoyable à Jev (hors projet ou fichier sensible)"
    return "%s : %d règle(s), %s%s (détail : dartlens rules check)" % (shown, count, verdict, sendable)


def settings_lines(settings):
    guard, router, lens, find = settings["guard"], settings["router"], settings["lens"], settings["find"]
    onoff = {True: "oui", False: "non"}
    return [
        "Garde : %s, seuil %s" % ("activée" if guard.get("enabled") else "désactivée", guard.get("threshold")),
        "Routeur : %s ; mémoire %s (seuil %s, %s fiches max) ; skills %s (confiance %s)" % (
            "activé" if router.get("enabled") else "désactivé", onoff[bool(router.get("memory"))],
            router.get("memory_threshold"), router.get("max_notes"), onoff[bool(router.get("skills"))],
            router.get("skill_confidence")),
        "Lens : seuil %s, %s fichiers max ; find : %s, top %s, min %s, tests %s" % (
            lens.get("threshold"), lens.get("max_files"), " ".join(find.get("extensions") or []), find.get("top"),
            find.get("min"), "inclus" if find.get("include_tests") else "exclus"),
    ]


def usage_records(since):
    file = jev.STATE_DIR / "usage.jsonl"
    if not file.is_file():
        return None, 0
    found, skipped = read_records(file, since)
    records = []
    for r in found:
        total = finite(r.get("total_ms"))
        records.append({
            "ts": r["ts"], "tool": name(r.get("tool")) or "?", "model": name(r.get("model")),
            "questions": finite(r.get("questions")), "input_tokens": finite(r.get("input_tokens")),
            "attempts": finite(r.get("attempts")), "call_ms": finite(r.get("ms")),
            # Older lines have no total_ms: their last attempt is all there is.
            "total_ms": finite(r.get("ms")) if total is None else total,
            "error": error_kind(r["error"]) if "error" in r else None,
        })
    return records, skipped


def percentile(values, q):
    return values[min(len(values), max(1, math.ceil(q * len(values)))) - 1] if values else 0


def spread(values):
    values = sorted(values)
    return "p50 %d ms, p95 %d ms" % (percentile(values, 0.5), percentile(values, 0.95))


def usage_lines(pinned):
    now = time.time()
    source = memory.display(jev.STATE_DIR / "usage.jsonl")
    records, skipped = usage_records(now - WINDOWS[-1][1])
    if records is None:
        return ["Usage Jev : aucun appel journalisé (%s absent)" % source]
    lines = ["Usage Jev (%s, tous projets confondus) :" % source]
    for label, seconds in WINDOWS:
        rows = [r for r in records if r["ts"] >= now - seconds]
        ok = [r for r in rows if r["error"] is None]
        tokens = sum(r["input_tokens"] or 0 for r in ok)
        unknown = sum(1 for r in ok if r["input_tokens"] is None)
        lines.append("  %s : %d requête(s) (%d réussie(s), %d en erreur ; %d tentative(s)), %d question(s), "
                     "%s tokens d'entrée%s, ≈ %s $" % (
                         label, len(rows), len(ok), len(rows) - len(ok), sum(r["attempts"] or 1 for r in rows),
                         sum(r["questions"] or 0 for r in ok), num(tokens),
                         " (%d sans décompte)" % unknown if unknown else "", fr(tokens / 1e6 * PRICE_PER_MTOK, 6)))
        total = [r["total_ms"] for r in rows if r["total_ms"] is not None]
        if total:
            missing = " ; %d sans mesure" % (len(rows) - len(total)) if len(total) < len(rows) else ""
            line = "    latence par requête, reprises et erreurs comprises : %s%s" % (spread(total), missing)
            single = [r["call_ms"] for r in ok if r["call_ms"] is not None]
            if single:
                line += " ; tentative réussie seule : %s" % spread(single)
            lines.append(line)
        tools = collections.Counter(r["tool"] for r in rows)
        if tools:
            lines.append("    par outil : " + ", ".join("%s %d" % item for item in tools.most_common()))
    models = collections.Counter(r["model"] for r in records if r["error"] is None)
    if models:
        lines.append("  modèle effectif (7 j) : " + ", ".join(
            "%s ×%d%s" % (m, n, "" if m == pinned else " ≠ épinglé") if m else "non renvoyé ×%d" % n
            for m, n in models.most_common()))
    failed = [r for r in records if r["error"] is not None]
    if failed:
        last = max(failed, key=lambda r: r["ts"])
        lines.append("  dernière erreur : %s, %s : %s" % (
            time.strftime("%Y-%m-%d %H:%M", time.localtime(last["ts"])), last["tool"], last["error"]))
    if skipped:
        lines.append("  %d ligne(s) illisible(s) ignorée(s)" % skipped)
    lines.append("  latence : appel Jev seul (réseau, reprises, délais dépassés), hors préparation dans les hooks "
                 "(durées complètes : dartlens log)")
    lines.append("  coût estimé au tarif affiché : " + PRICE_NOTE % pinned)
    return lines


def main(argv):
    parser = argparse.ArgumentParser(prog="dartlens status", description="État de dartlens et de Jev pour le projet courant.")
    parser.add_argument("--project", help="dossier du projet, dont la racine est cherchée comme pour les hooks "
                                          "(défaut : dossier courant)")
    args = parser.parse_args(argv)
    if args.project:
        start = Path(args.project).expanduser().resolve()
        if not start.is_dir():
            parser.error("--project : %s : %s" % ("dossier attendu" if start.exists() else "dossier introuvable", args.project))
        # Not project_root(): it prefers CLAUDE_PROJECT_DIR over an explicit argument.
        root = next((c for c in (start, *start.parents) if any((c / m).exists() for m in project.ROOT_MARKERS)), start)
    else:
        start = root = project.project_root()
    problems = []
    settings = config.load(root, problems)
    allowed, reason = policy.jev_allowed(root, settings)
    pinned = jev.model_name(settings)
    model = "%s (%s)" % (pinned, "surchargé par DARTLENS_JEV_MODEL" if os.environ.get("DARTLENS_JEV_MODEL") else "config")
    lines = [
        "dartlens · %s%s" % (memory.display(root), "" if root == start else " (racine trouvée depuis %s)" % memory.display(start)),
        "Config : %s" % config_line(root, problems),
        "Jev pour ce projet : %s" % ("activé" if settings["jev"].get("enabled") else "non activé (jev.enabled)"),
        "Envoi à Jev : %s" % ("autorisé" if allowed else "refusé : " + reason),
        "Politique : %s" % policy_line(root),
        "Clé TypeSafe : %s" % key_line(),
        "Modèle : %s ; délais hook %s s, CLI %s s" % (model, settings["jev"]["hook_timeout_s"], settings["jev"]["cli_timeout_s"]),
    ]
    if jev.base_url() != jev.DEFAULT_URL:
        lines.append("URL : %s (surchargée par DARTLENS_JEV_URL : aucun résultat n'y mesure la qualité de Jev)" % jev.base_url())
    lines.append("Disjoncteurs : %s" % breaker_line())
    lines.append("Règles : %s" % rules_line(root, settings))
    lines += settings_lines(settings)
    try:
        lines += usage_lines(pinned)
    except Exception as error:
        lines.append("Usage Jev : journal illisible (%s)" % type(error).__name__)
    print("\n".join(lines))
    return 0
