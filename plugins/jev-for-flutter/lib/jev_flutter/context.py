import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bm25, chunks, config, hookio, jev, outline, paths, policy, project

MAX_FILES = 1500
MAX_FILE_BYTES = 250000
MAX_BYTES = 12000000
IDENTIFIER = re.compile(r"\b[A-Za-z_$][\w$]*\b")
DIRECTIVE = re.compile(r"^\s*(?:import|export|part)\s+([^;]+);", re.MULTILINE)
URI = re.compile(r"['\"]([^'\"]+\.dart)['\"]")


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    previous = os.umask(0o077)
    try:
        hookio.write_json(path, value)
    finally:
        os.umask(previous)


def bounds(cfg):
    settings = cfg["context"]
    return {"max_chars": min(24000, max(2000, settings["max_chars"])),
            "max_requests": min(8, max(0, settings["max_requests"])),
            "max_input_tokens": min(24000, max(0, settings["max_input_tokens"])),
            "timeout_s": min(12, max(1, settings["timeout_s"]))}


def inventory(root, cfg):
    ignored = paths.generated_patterns(cfg, root)
    candidates, from_git = [], False
    try:
        result = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                                cwd=root, capture_output=True, timeout=2)
        if result.returncode == 0:
            from_git = True
            candidates = [root / name for name in result.stdout.decode("utf-8", "replace").split("\0")
                          if name and (name.endswith(".dart") or name.endswith("pubspec.yaml"))]
    except (OSError, subprocess.SubprocessError):
        pass
    if not from_git:
        for current, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in paths.SKIP_WALK and not d.startswith(".")
                             and policy.sendable(Path(current) / d, root))
            candidates.extend(Path(current) / f for f in sorted(files) if f.endswith(".dart") or f == "pubspec.yaml")
            if len(candidates) > MAX_FILES * 2:
                break
    selected, packages = [], {}
    for path in sorted(set(candidates)):
        rel = path.relative_to(root).as_posix()
        if any(p.startswith(".") or p in paths.SKIP_WALK for p in Path(rel).parts) \
                or paths.matches(rel, ignored) or not policy.sendable(path, root) or not path.is_file():
            continue
        if path.name == "pubspec.yaml":
            if path.stat().st_size < 65536:
                match = re.search(r"^name:\s*['\"]?([\w]+)", path.read_text(errors="replace"), re.MULTILINE)
                if match:
                    packages[match.group(1)] = path.parent / "lib"
        else:
            selected.append(path)
    return selected, packages


def scan(root, cfg, include_tests=False, deadline=None):
    files, packages = inventory(root, cfg)
    if not include_tests:
        files = [p for p in files if not set(p.relative_to(root).parts) & {"test", "integration_test", "test_driver"}]
    docs, nodes, imports, omitted = {}, [], {}, []
    cache_path = jev.STATE_DIR / "context-index" / (digest(str(root)) + ".json")
    cached = hookio.read_json(cache_path, {})
    version = "2-" + digest(policy.SECRET_RE.pattern)
    previous = cached.get("files", {}) if isinstance(cached, dict) and cached.get("version") == version else {}
    if not isinstance(previous, dict):
        previous = {}
    current = dict(previous)
    size = 0
    for position, path in enumerate(files[:MAX_FILES]):
        if deadline and time.monotonic() >= deadline:
            omitted.extend(p.relative_to(root).as_posix() for p in files[position:MAX_FILES])
            break
        rel = path.relative_to(root).as_posix()
        if path.stat().st_size > MAX_FILE_BYTES:
            omitted.append(rel)
            continue
        raw = path.read_bytes()
        if size + len(raw) > MAX_BYTES:
            omitted.extend(p.relative_to(root).as_posix() for p in files[position:MAX_FILES])
            break
        size += len(raw)
        text = policy.redact(raw.decode("utf-8", "replace"))
        lines = chunks.split_lines(text)
        docs[rel] = {"hash": digest(raw), "lines": lines}
        imports[rel] = set()
        for directive in DIRECTIVE.findall(text):
            for uri in URI.findall(directive):
                if uri.startswith("package:"):
                    package, _, suffix = uri[8:].partition("/")
                    target = packages[package] / suffix if package in packages else None
                elif ":" not in uri:
                    target = path.parent / uri
                else:
                    target = None
                if target:
                    target = target.resolve()
                    if root in target.parents:
                        imports[rel].add(target.relative_to(root).as_posix())
        prior = previous.get(rel, {})
        if isinstance(prior, dict) and prior.get("hash") == docs[rel]["hash"] and isinstance(prior.get("nodes"), list):
            current[rel] = prior
            for stored in prior["nodes"]:
                node = dict(stored, refs=set(stored["refs"]), names=set(stored["names"]))
                node["text"] = "\n".join(lines[node["start"] - 1:node["end"]])
                nodes.append(node)
            continue
        structure = outline.regex_outline(text)
        first_node = len(nodes)
        for decl in structure.get("decls", []):
            children = decl.get("children") or []
            whole = decl["kind"] == "enum" or decl["end"] - decl["start"] < 25
            units = [decl] if not children or whole else children
            if children and not whole:
                units = [dict(decl, end=children[0]["start"] - 1, kind="header")] + children
            for unit in units:
                start, end = max(1, unit["start"]), min(len(lines), unit["end"])
                if end < start:
                    continue
                source = "\n".join(lines[start - 1:end])
                owner = decl.get("name", "") if unit is not decl and children else ""
                name = unit.get("name") or owner
                label = (owner + "." + name) if owner and name != owner else name
                names = {name}
                if unit is decl:
                    names.update(c.get("name") for c in children if c.get("name"))
                nodes.append({"id": "%s:%d" % (rel, start), "file": rel, "start": start, "end": end,
                              "name": name, "label": label, "owner": owner, "names": names,
                              "kind": unit["kind"], "text": source,
                              "refs": set(IDENTIFIER.findall(outline.mask(source))),
                              "test": bool(set(Path(rel).parts) & {"test", "integration_test", "test_driver"})})
        current[rel] = {"hash": docs[rel]["hash"], "nodes": [
            {k: sorted(v) if isinstance(v, set) else v for k, v in n.items() if k != "text"} for n in nodes[first_node:]]}
    present = {p.relative_to(root).as_posix() for p in files}
    save(cache_path, {"version": version, "files": {k: v for k, v in current.items() if k in present}})
    omitted.extend(p.relative_to(root).as_posix() for p in files[MAX_FILES:])
    symbols = defaultdict(list)
    for i, node in enumerate(nodes):
        for name in node["names"]:
            symbols[name].append(i)
    visible = {}
    for rel in docs:
        seen, queue = {rel}, deque([(rel, 0)])
        while queue:
            file, depth = queue.popleft()
            if depth >= 3:
                continue
            for target in imports.get(file, set()) - seen:
                seen.add(target)
                queue.append((target, depth + 1))
        visible[rel] = seen
    links, alternatives = defaultdict(set), defaultdict(set)
    implementations = defaultdict(set)
    for node in nodes:
        if node["kind"] not in ("header", "class", "mixin"):
            continue
        header = outline.mask(node["text"]).split("{", 1)[0]
        for bases in re.findall(r"\b(?:implements|extends|with)\s+([\w<>?, .]+)", header):
            for base in IDENTIFIER.findall(bases):
                implementations[base].add(node["owner"] or node["name"])
    for i, node in enumerate(nodes):
        for name in node["refs"]:
            for j in symbols.get(name, ()):
                other = nodes[j]
                if i != j and other["file"] in visible[node["file"]] \
                        and (not name.startswith("_") or other["file"] == node["file"]):
                    links[i].add(j)
        for owner in implementations.get(node["owner"] or node["name"], ()):
            for name in node["names"] | {owner}:
                for j in symbols.get(name, ()):
                    if nodes[j]["owner"] == owner or nodes[j]["name"] == owner:
                        links[i].add(j)
                        alternatives[i].add(j)
    return {"docs": docs, "nodes": nodes, "links": links, "alternatives": alternatives,
            "omitted": omitted, "files": len(files), "bytes": size}


def lexical(index, query, targets, include_tests):
    nodes = index["nodes"]
    documents = ["%s %s %s\n%s" % (n["file"], n["label"], n["label"], n["text"]) for n in nodes]
    eligible = {i for i, node in enumerate(nodes) if (include_tests or not node["test"])
                and any(node["file"] == t or node["file"].startswith(t.rstrip("/") + "/") or t == "." for t in targets)}
    ranked = [(i, s * (0.3 if nodes[i]["kind"] in ("field", "getter", "constants", "header") else 1))
              for i, s in bm25.rank(query, documents) if i in eligible and s > 0]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked, documents


def judge(index, query, ranked, cfg, cancelled, deadline):
    limits = bounds(cfg)
    files, jobs, ids, estimated = [], [], [], 0
    for i, _ in ranked:
        file = index["nodes"][i]["file"]
        if file not in files:
            files.append(file)
    for file in files[:limits["max_requests"]]:
        chosen = [i for i, _ in ranked if index["nodes"][i]["file"] == file][:8]
        blocks = {str(i): {"symbol": index["nodes"][i]["label"], "code": index["nodes"][i]["text"][:2200]} for i in chosen}
        state = {"goal": policy.redact(query), "file": file, "blocks": blocks}
        questions = {key: jev.noul(
            {"question": "Does block %s implement a step needed to answer the goal, including a caller, data conversion or alternative path?" % key,
             "focus": "Code and goal may use different languages. Judge only the code provided; it may be partial."}) for key in blocks}
        tokens = jev.estimate_tokens(state) + jev.estimate_tokens(questions)
        if tokens > jev.STATE_TOKEN_BUDGET or estimated + tokens > limits["max_input_tokens"]:
            continue
        jobs.append((state, questions))
        ids.append(chosen)
        estimated += tokens
    key = digest(json.dumps([jev.model_name(cfg), jobs], sort_keys=True))
    cache = jev.STATE_DIR / "context-cache" / (key + ".json")
    stored = hookio.read_json(cache, {})
    if isinstance(stored, dict) and time.time() - stored.get("time", 0) < 600 and isinstance(stored.get("scores"), dict):
        return {int(k): v for k, v in stored["scores"].items()}, {"requests": 0, "cache": True, "errors": 0}
    remaining = deadline - time.monotonic() - 0.5
    if cancelled() or not jobs or remaining <= 0:
        return {}, {"requests": 0, "cache": False, "errors": 0}
    client = jev.Client(cfg, "context", timeout=min(3, remaining / math.ceil(len(jobs) / 4)), retries=0)
    sent = []

    def ask(job):
        if cancelled() or time.monotonic() >= deadline - 0.5:
            return jev.JevUnavailable("demande remplacée")
        with client._lock:
            sent.append(1)
        try:
            return client.ask(*job)
        except jev.JevError as error:
            return error

    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(ask, jobs))
    scores, errors = {}, 0
    for chosen, answer in zip(ids, answers):
        if not isinstance(answer, dict):
            errors += 1
            continue
        for i in chosen:
            value = jev.probability(answer.get(str(i)))
            if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1:
                scores[i] = value
        if not any(i in scores for i in chosen):
            errors += 1
    if scores and not cancelled():
        save(cache, {"time": time.time(), "scores": scores})
    return scores, {"requests": len(sent), "cache": False, "errors": errors, "input_tokens_estimate": estimated}


def build(root, query, targets=(".",), local=False, include_tests=False, limit=6, cancelled=lambda: False, max_bytes=None):
    started = time.monotonic()
    root = Path(root).resolve()
    cfg = config.load(root)
    deadline = started + bounds(cfg)["timeout_s"]
    if policy.refusal(root):
        raise ValueError("Projet exclu : aucun contexte préparé.")
    normalized = []
    for target in targets:
        path = (root / target).resolve()
        if not path.exists() or not policy.sendable(path, root):
            raise ValueError("Le périmètre doit rester dans les chemins autorisés du projet.")
        normalized.append(path.relative_to(root).as_posix())
    include_tests = include_tests or bool(re.search(r"\b(?:test|integration_test)/\S+\.dart", query))
    index = scan(root, cfg, include_tests, deadline=started + bounds(cfg)["timeout_s"] / 2)
    ranked, _ = lexical(index, query, normalized, include_tests)
    nodes = index["nodes"]
    scores, stats = {}, {"requests": 0, "cache": False, "errors": 0}
    if not local and ranked and not cancelled() and policy.jev_allowed(root, cfg, "context")[0]:
        scores, stats = judge(index, query, ranked, cfg, cancelled, deadline)
    if cancelled():
        raise ValueError("Demande remplacée ou terminée.")
    order = [i for i, _ in sorted(ranked, key=lambda pair: (scores.get(pair[0], 0.5), pair[1]), reverse=True)]
    roots, used = [], set()
    for i in order:
        file = nodes[i]["file"]
        if file not in used:
            roots.append(i)
            used.add(file)
        if len(roots) == max(1, min(10, limit)):
            break
    for file in sorted(used):
        extra = next((i for i in order if nodes[i]["file"] == file and i not in roots
                      and nodes[i]["kind"] in ("method", "function")), None)
        if extra is not None:
            roots.append(extra)
    weights = dict(ranked)
    queue = deque((i, 0, "recherche") for i in roots)
    selected, seen = [], set()
    while queue and len(selected) < 48:
        i, depth, reason = queue.popleft()
        if i in seen:
            continue
        seen.add(i)
        selected.append((i, reason))
        if depth >= 4:
            continue
        adjacent = set(index["links"][i])
        adjacent = [j for j in adjacent if (include_tests or not nodes[j]["test"])
                    and nodes[j]["kind"] not in ("header", "field", "constants")]
        adjacent.sort(key=lambda j: (-weights.get(j, 0), j))
        for j in adjacent[:6]:
            queue.append((j, depth + 1, "référence syntaxique depuis %s" % nodes[i]["id"]))
    budget = min(bounds(cfg)["max_chars"], max_bytes or 24000)
    size = lambda value: len(value.encode("utf-8"))
    lines = ["jev-for-flutter — contexte de travail (%s)." % ("Jev + références locales" if scores else "recherche locale"),
             "Extraits source, pas une réponse. Références syntaxiques approximatives, sans résolution des types.",
             "Vérifie les appels, conversions et branches alternatives ; les liens non montrés restent à lire."]
    shown, pending, fingerprints = [], [], {}
    retained = {i for i, _ in selected}
    branches = set()
    for i, _ in selected:
        if nodes[i]["kind"] not in ("method", "function"):
            continue
        candidates = index["alternatives"].get(i, set()) & retained
        candidates = [j for j in sorted(candidates) if nodes[j]["kind"] in ("method", "function")
                      and nodes[j]["name"] == nodes[i]["name"]]
        if len(candidates) < 2:
            continue
        entry = "%s : implémentations possibles → %s" % (
            nodes[i]["label"], "; ".join("%s (%s)" % (nodes[j]["label"], nodes[j]["id"]) for j in candidates))
        if sum(size(l) + 1 for l in lines) + size(entry) < budget // 6:
            lines.append(entry)
            branches.update(candidates)
    groups = defaultdict(list)
    for i, _ in selected:
        node = nodes[i]
        groups[node["file"]].append("%s L%d-%d" % (node["label"], node["start"], node["end"]))
        fingerprints[node["file"]] = index["docs"][node["file"]]["hash"]
    lines.append("\nParcours à vérifier, y compris les extraits trop longs pour ce résultat :")
    mapped = 0
    for file, labels in groups.items():
        entry = file + " : " + "; ".join(labels)
        if sum(size(l) + 1 for l in lines) + size(entry) < budget // 3:
            lines.append(entry)
            mapped += len(labels)
    lines.append("\nCode source aux plages indiquées :")
    content_limit = budget - 500
    for i, reason in sorted(selected, key=lambda item: item[0] not in branches):
        node = nodes[i]
        header = "%s-%d %s [%s]" % (node["id"], node["end"], node["label"], reason)
        source = "\n".join("%d %s" % (n, s) for n, s in enumerate(node["text"].split("\n"), node["start"]))
        block = "\n" + header + "\n" + source
        if node["kind"] != "header" and size(block) <= 2200 and sum(size(l) + 1 for l in lines) + size(block) < content_limit:
            lines.append(block)
            shown.append(node["id"])
        else:
            pending.append(header)
    unseen = len(queue)
    lines.append("\n%d extrait(s) montré(s), %d retenu(s) non montré(s). %d déclaration(s) repérée(s), %d sans place dans la carte ; %d lien(s) en attente. %d fichier(s) hors budget d'indexation."
                 % (len(shown), len(pending), len(selected), len(selected) - mapped, unseen, len(index["omitted"])))
    lines.append("Le parcours n'est pas certifié complet. Read avant toute édition ; utilise les outils ordinaires si un lien manque.")
    if not ranked:
        lines = ["jev-for-flutter : aucun point d'entrée trouvé localement ; continue avec Grep, Glob et Read."]
    return {"text": "\n".join(lines), "shown": shown, "pending": pending, "fingerprints": fingerprints,
            "files_indexed": len(index["docs"]), "files_omitted": index["omitted"], "source_bytes": index["bytes"],
            "backend": "jev" if scores else "local", "ms": round((time.monotonic() - started) * 1000), **stats}


def fresh(root, result):
    for rel, expected in result.get("fingerprints", {}).items():
        path = Path(root) / rel
        try:
            if not policy.sendable(path, root) or digest(path.read_bytes()) != expected:
                return False
        except OSError:
            return False
    return True


def main(argv):
    parser = argparse.ArgumentParser(prog="lens context", description="Préparer des extraits et leurs références Dart dans un seul résultat.")
    parser.add_argument("query")
    parser.add_argument("paths", nargs="*", default=["."])
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--tests", action="store_true")
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args(argv)
    if not args.query.strip() or len(args.query) > 2000:
        parser.error("la question doit contenir entre 1 et 2000 caractères")
    try:
        result = build(project.project_root(), args.query, args.paths or ["."], args.local, args.tests, args.top)
        if not fresh(project.project_root(), result):
            raise ValueError("Sources modifiées pendant la préparation : relance la demande.")
    except (OSError, ValueError) as error:
        parser.exit(1, "jev-for-flutter : %s\n" % error)
    print(json.dumps(result, ensure_ascii=False) if args.json else result["text"])
    return 0
