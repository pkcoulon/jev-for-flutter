import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

from .. import config, jev, paths, policy, project, rules

USAGE = "dartlens rules check [fichier] | list [fichier] | test <fichier.dart> [--change ANCIEN NOUVEAU] [--state]"
MAX_WALK = 50000
MAX_INCLUDES = 8
LINT_NAME = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")
# Lints a rule author tends to rephrase as a question; matched against the question when the lint is active.
LINT_TOPICS = {name: re.compile(pattern, re.I) for name, pattern in {
    "avoid_print": r"\bprint|console|debug(?:ging)? output",
    "use_build_context_synchronously": r"context\b.*\b(?:async|await|asynchronous|mounted)|\b(?:async|await|asynchronous|mounted)\b.*\bcontext\b",
    "unawaited_futures": r"\bunawaited\b|not awaited|without awaiting|fire[- ]and[- ]forget",
    "discarded_futures": r"\bunawaited\b|not awaited|discard(?:s|ed)? (?:a |the )?futures?",
    "avoid_dynamic_calls": r"\bdynamic\b",
    "prefer_const_constructors": r"\bconst\b",
    "prefer_single_quotes": r"\bquotes?\b",
    "require_trailing_commas": r"trailing comma",
    "always_use_package_imports": r"relative imports?|package imports?",
    "prefer_relative_imports": r"relative imports?|package imports?",
    "directives_ordering": r"import order|sort(?:ed)? imports",
    "lines_longer_than_80_chars": r"line length|long lines|longer than",
    "cancel_subscriptions": r"subscriptions?\b.*\bcancel|\bcancel.*\bsubscriptions?",
    "close_sinks": r"\bclose[sd]?\b.*(?:sink|stream ?controller)|(?:sink|stream ?controller).*\bclose",
    "avoid_catches_without_on_clauses": r"\bcatch(?:es)?\b",
    "empty_catches": r"empty catch|swallow",
    "use_key_in_widget_constructors": r"\bkey\b.*\bconstructor|constructor.*\bkey\b",
    "sized_box_for_whitespace": r"sized ?box|whitespace",
    "public_member_api_docs": r"doc(?:umentation)? comments?|dartdoc",
    "always_declare_return_types": r"return types?",
}.items()}


def _rules_file(root, settings, explicit):
    return Path(explicit).resolve() if explicit else rules.path(root, settings)


def _load_json(file):
    try:
        return json.loads(file.read_text()), None
    except OSError as error:
        return None, "lecture impossible : %s" % (error.strerror or error)
    except ValueError as error:
        return None, "JSON invalide : %s" % error


def _project_files(root):
    found = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in paths.SKIP_WALK and not d.startswith(".")]
        base = os.path.relpath(current, root)
        found.extend(f if base == "." else base.replace(os.sep, "/") + "/" + f for f in files)
        if len(found) > MAX_WALK:
            break
    return found


def _yaml_entries(text):
    # Just enough YAML for analysis_options: (path, value) for each scalar, (parent path, item) for each list item.
    stack, out = [], []
    for raw in text.splitlines():
        line = "" if raw.lstrip().startswith("#") else re.sub(r"\s+#.*$", "", raw).rstrip()
        if not line.strip():
            continue
        indent, body = len(line) - len(line.lstrip()), line.strip()
        if body.startswith("- "):
            while stack and stack[-1][0] > indent:
                stack.pop()
            out.append((tuple(k for _, k in stack), body[2:].strip().strip("'\"")))
            continue
        key, sep, value = body.partition(":")
        if not sep:
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        value = value.strip().strip("'\"")
        if value:
            out.append((tuple(k for _, k in stack) + (key.strip(),), value))
        else:
            stack.append((indent, key.strip()))
    return out


def _version(path):
    return tuple(int(n) for n in re.findall(r"\d+", os.path.basename(path).rsplit("-", 1)[-1]))


def _package_lib(package, root):
    try:
        data = json.loads((Path(root) / ".dart_tool" / "package_config.json").read_text())
        for entry in data.get("packages") or []:
            if entry.get("name") == package:
                uri = entry.get("rootUri") or ""
                base = urllib.parse.unquote(uri[7:]) if uri.startswith("file://") else os.path.join(root, ".dart_tool", uri)
                return os.path.normpath(os.path.join(base, entry.get("packageUri") or "lib/"))
    except (OSError, ValueError, AttributeError, TypeError):
        pass
    cache = os.path.join(os.environ.get("PUB_CACHE") or os.path.expanduser("~/.pub-cache"), "hosted", "pub.dev")
    try:
        locked = re.search(r"^  %s:\n(?:    .*\n)*?    version: \"([^\"]+)\"" % re.escape(package),
                           (Path(root) / "pubspec.lock").read_text(), re.MULTILINE)
    except OSError:
        locked = None
    if locked and os.path.isdir(os.path.join(cache, "%s-%s" % (package, locked.group(1)))):
        return os.path.join(cache, "%s-%s" % (package, locked.group(1)), "lib")
    found = [d for d in glob.glob(os.path.join(cache, package + "-*")) if re.fullmatch(r"[\d.]+(?:[-+].*)?", d.rsplit(package + "-", 1)[-1])]
    return os.path.join(max(found, key=_version), "lib") if found else None


def active_lints(file, root, seen=None, missing=None):
    # Lints enabled by analysis_options.yaml and its includes, minus those set to false or ignored.
    seen = set() if seen is None else seen
    missing = [] if missing is None else missing
    real = os.path.realpath(str(file))
    if real in seen or len(seen) >= MAX_INCLUDES:
        return set(), missing
    seen.add(real)
    try:
        entries = _yaml_entries(Path(real).read_text())
    except OSError:
        return set(), missing
    active = set()
    for path, value in entries:
        if path == ("include",):
            if value.startswith("package:"):
                package, _, rest = value[len("package:"):].partition("/")
                lib = _package_lib(package, root)
                target = os.path.join(lib, rest) if lib else None
            else:
                target = os.path.join(os.path.dirname(real), value)
            if target and os.path.isfile(target):
                active |= active_lints(target, root, seen, missing)[0]
            else:
                missing.append(value)
    for path, value in entries:
        if path == ("linter", "rules") and LINT_NAME.match(value):
            active.add(value)
        elif len(path) == 3 and path[:2] == ("linter", "rules"):
            (active.add if value.lower() == "true" else active.discard)(path[2])
        elif len(path) == 3 and path[:2] == ("analyzer", "errors") and value.lower() == "ignore":
            active.discard(path[2])
    return active, missing


def check(root, settings, file):
    shown = project.rel(file, root)
    data, problem = _load_json(file)
    if problem:
        print("%s : %s" % (shown, problem))
        return 1
    errors, warnings = rules.validate(data, strict=True)
    if not errors:
        files = _project_files(root)
        used = set()
        for rule in data["rules"]:
            for glob in rules.patterns(rule, data):
                used.add(glob)
        for glob in sorted(used):
            if not any(paths.matches(f, [glob]) for f in files):
                warnings.append("applies_to « %s » ne correspond à aucun fichier du projet" % glob)
        lints, missing = active_lints(Path(root) / "analysis_options.yaml", root)
        for value in missing:
            warnings.append("include « %s » introuvable (.dart_tool/package_config.json, ~/.pub-cache) : ses lints ne sont pas comparés" % value)
        for rule in data["rules"]:
            named = sorted(n for n in lints if n in rule["question"] or n == rule["id"].replace("-", "_")
                           or (n in LINT_TOPICS and LINT_TOPICS[n].search(rule["question"])))
            if named:
                warnings.append("[%s] recoupe le lint actif %s (analysis_options.yaml ou un include) : à retirer si le lint la décide" % (
                    rule["id"], ", ".join(named)))
    count = len(data.get("rules") or []) if isinstance(data, dict) else 0
    print("%s : %d règle%s, %d erreur%s, %d avertissement%s" % (
        shown, count, "s" if count > 1 else "", len(errors), "s" if len(errors) > 1 else "", len(warnings), "s" if len(warnings) > 1 else ""))
    for line in errors:
        print("erreur  " + line)
    for line in warnings:
        print("avert.  " + line)
    return 1 if errors else 0


def listing(root, settings, file):
    try:
        data = rules.read(file)
    except rules.RulesError as error:
        print("%s : %s" % (project.rel(file, root), "; ".join(error.problems)))
        return 1
    print("%s : %d règles" % (project.rel(file, root), len(data["rules"])))
    for rule in data["rules"]:
        print("- [%s] seuil %.2f · %s · %d ex. · %s" % (
            rule["id"], rules.threshold(rule, data, settings), ", ".join(rules.patterns(rule, data)),
            len(rule.get("examples") or []), rule["message"]))
    return 0


def dry_run(root, settings, file, target, change, show_state):
    try:
        ruleset = rules.read(file)
    except rules.RulesError as error:
        print("règles invalides : %s (lance dartlens rules check)" % "; ".join(error.problems))
        return 1
    real = os.path.realpath(target)
    rel = os.path.relpath(real, os.path.realpath(str(root))).replace(os.sep, "/")
    if rel == ".." or rel.startswith("../"):
        print("%s est hors du projet (%s)" % (target, root))
        return 1
    selected = rules.select(ruleset, rel)
    if not selected:
        print("aucune règle ne s'applique à %s (applies_to) : la garde ne ferait rien" % rel)
        return 0
    allowed, reason = policy.jev_allowed(root, settings)
    if not allowed:
        print("Jev indisponible : %s" % reason)
        return 2
    if not policy.sendable(real, root) or not policy.sendable(str(file), root):
        print("envoi refusé par la politique de données (fichier sensible ou exclu)")
        return 2
    if paths.is_generated(real, settings, root):
        print("%s est un fichier généré : la garde l'ignore" % rel)
        return 0
    try:
        text = Path(real).read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        print("lecture impossible : %s" % (error.strerror or error))
        return 1
    if change:
        old, new = change
        if old not in text:
            print("--change : ANCIEN introuvable dans %s" % rel)
            return 1
        index = text.index(old)
        text = text[:index] + new + text[index + len(old):]
        steps = [{"runs": [rules.replaced_run(text, index, old, new)]}]
    else:
        steps = [{"create": True}]
    changes, _ = rules.net_changes(text, steps)
    if not changes:
        print("modification vide : la garde ne ferait rien")
        return 0
    states, unjudged = rules.build_states(rel, changes, text, reserve=rules.longest_question(selected))
    if show_state:
        print(json.dumps(states, ensure_ascii=False, indent=2))
    # Same client as the hook: its timeout, no retry, so a slow answer shows up as the silence it would cause.
    timeout = settings["jev"]["hook_timeout_s"]
    client = jev.Client(settings, "rules-test", timeout=timeout, retries=0)
    started = time.monotonic()
    try:
        answers, failed, requests = rules.ask(client, states, selected)
    except jev.JevError as error:
        print("Jev en échec (délai du hook %.1f s, sans nouvelle tentative) : %s ; la garde resterait silencieuse" % (timeout, error))
        return 2
    elapsed = int((time.monotonic() - started) * 1000)
    verdicts = sorted(rules.scored(answers, selected, ruleset, settings), key=lambda v: -v[1])
    print("%s · %d règle%s applicable%s · %d requête%s Jev, %d ms%s%s" % (
        rel, len(selected), "s" * (len(selected) > 1), "s" * (len(selected) > 1), requests, "s" * (requests > 1),
        elapsed, " · lignes non jugées : %d" % unjudged if unjudged else "", " · requêtes en échec : %d" % failed if failed else ""))
    if jev.base_url() != jev.DEFAULT_URL:
        print("serveur Jev non officiel (%s) : réponses simulées, sans valeur sur la qualité" % jev.base_url())
    print("p     seuil  verdict  règle")
    for rule, p, limit in verdicts:
        print("%.2f  %.2f   %-7s  [%s] %s" % (p, limit, "ALERTE" if p >= limit else "ok", rule["id"], rule["message"]))
    missing = [r["id"] for r in selected if r["id"] not in answers]
    if missing:
        print("sans réponse : %s" % ", ".join(missing))
    return 0


def main(argv):
    parser = argparse.ArgumentParser(prog="dartlens rules", usage=USAGE, add_help=True)
    parser.add_argument("action", choices=("check", "list", "test"))
    parser.add_argument("path", nargs="?")
    parser.add_argument("--rules", help="fichier de règles à utiliser (défaut : guard.rules_file)")
    parser.add_argument("--change", nargs=2, metavar=("ANCIEN", "NOUVEAU"))
    parser.add_argument("--state", action="store_true", help="affiche l'état envoyé à Jev")
    args = parser.parse_args(argv)
    root = project.project_root()
    settings = config.load(root)
    if args.action == "test":
        if not args.path:
            print("usage : " + USAGE)
            return 1
        return dry_run(root, settings, _rules_file(root, settings, args.rules), args.path, args.change, args.state)
    file = _rules_file(root, settings, args.path or args.rules)
    if not file.is_file():
        print("%s absent : lance /dartlens:rules pour le générer" % project.rel(file, root))
        return 1
    return check(root, settings, file) if args.action == "check" else listing(root, settings, file)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
