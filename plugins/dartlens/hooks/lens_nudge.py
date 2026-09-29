#!/usr/bin/env python3
import fcntl
import hashlib
import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
try:
    from dartlens import catalog, config, hookio, jev, narrow, paths, policy
except Exception:
    sys.exit(0)

MAX_BYTES = 4 * 1024 * 1024
MODES = ("narrow", "hint", "refuse_once", "start", "off")

START = ("Jev for Flutter : les grandes lectures Dart peuvent être ciblées sur ta question, avec une indication des lignes omises. "
         "Un second Read ou un offset explicite reste libre. Pour trouver un comportement sans connaître son nom, "
         "utilise `jev-flutter find \"description\" dossier` ; pour un symbole connu, Grep. "
         "Vérifie les branches et conversions nécessaires avant de conclure.")

FIND_CODE = (" L'outil MCP `find_code` prépare le même contexte que `lens context` ; "
             "ses résultats sont des pistes : suis le parcours complet et vérifie chaque partie avant de conclure.")

HINT = ("dartlens : %(name)s fait %(lines)d lignes. Pour une question précise sur un fichier de cette taille, "
        "`lens \"ta question\" %(rel)s` ne montre que les passages concernés ; `dart-outline %(rel)s` en donne le plan.")

REFUSE = ("dartlens : %(name)s fait %(lines)d lignes. Lu en entier, il resterait dans la conversation et serait relu à chaque échange suivant. "
          "Si tu cherches quelque chose de précis, demande-le : `lens \"ta question\" %(rel)s`. "
          "Tu verras les passages concernés et la liste de ce qui est omis. Pour son plan : `dart-outline %(rel)s`. "
          "S'il te faut tout le fichier, relance le même Read : dartlens ne l'arrêtera plus.")


def log(record):
    record.update(ts=round(time.time(), 3), run=os.environ.get("DARTLENS_BENCH_RUN"))
    try:
        jev.STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(jev.STATE_DIR / "nudge.jsonl", "a") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


def settings(cwd):
    root = catalog.root_of(cwd)
    cfg = config.load(root)
    allowed, _ = policy.jev_allowed(root, cfg, "lens")
    mode = os.environ.get("DARTLENS_LENS_NUDGE") or cfg["lens"].get("nudge")
    return root, cfg, allowed, mode if mode in MODES else "narrow"


def count_lines(path):
    with open(path, "rb") as handle:
        data = handle.read(MAX_BYTES)
    if b"\0" in data[:8192]:
        return 0
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def claim(session_id, key, limit):
    # One marker per file: only the first of two parallel Reads wins, and a lost state never means refusing again.
    directory = hookio.state_file("nudge", session_id)
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory.parent / (directory.name + ".lock"), "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if len(os.listdir(directory)) >= limit:
            return False
        try:
            os.close(os.open(str(directory / key), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
        except FileExistsError:
            return False
    return True


def start(payload):
    cwd = payload.get("cwd") or os.getcwd()
    if policy.refusal(catalog.root_of(cwd)):
        return None
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if env_file:
        directory = str(Path(__file__).resolve().parents[1] / "bin")
        with open(env_file, "a") as handle:
            handle.write("export PATH=%s:\"$PATH\"\n" % shlex.quote(directory))
    _, _, allowed, mode = settings(cwd)
    if not allowed or mode == "off":
        return None
    log({"session": payload.get("session_id"), "event": "start", "mode": mode, "source": payload.get("source")})
    offered = config.load(os.environ.get("CLAUDE_PROJECT_DIR") or catalog.root_of(cwd))["find"].get("mcp") is True
    return hookio.context("SessionStart", START + (FIND_CODE if offered else ""))


def read(payload):
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path")
    if not isinstance(path, str) or not path.endswith(".dart"):
        return None
    if tool_input.get("offset") is not None or tool_input.get("limit") is not None:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    if policy.path_refused(cwd) or policy.path_refused(path):
        return None
    root, cfg, allowed, mode = settings(cwd)
    if allowed and mode == "narrow":
        return narrow.read(payload, Path(root).resolve(), cfg)
    if not allowed or mode not in ("hint", "refuse_once"):
        return None
    file = Path(path).resolve()
    if Path(root).resolve() not in file.parents or not file.is_file() or paths.is_generated(str(file), cfg, root):
        return None
    lines = count_lines(file)
    if lines < cfg["lens"].get("nudge_min_lines", 300):
        return None
    session = payload.get("session_id")
    key = hashlib.sha1(str(file).encode()).hexdigest()[:16]
    record = {"session": session, "file": key, "lines": lines, "mode": mode}
    refuse = mode == "refuse_once" and not jev.Breaker(jev.STATE_DIR / "breaker.json").is_open()
    if not claim(session, key, cfg["lens"].get("nudge_max", 3 if mode == "hint" else 5)):
        log(dict(record, event="read_again" if refuse else "quiet"))
        return None
    rel = os.path.relpath(file, cwd)
    words = {"name": file.name, "lines": lines, "rel": shlex.quote(rel)}
    log(dict(record, event="refuse" if refuse else "hint"))
    if refuse:
        return hookio.permission("deny", REFUSE % words)
    return hookio.context("PreToolUse", HINT % words)


def prepare(payload):
    prompt = narrow.clean_goal(payload.get("prompt"))
    if not prompt or not payload.get("session_id"):
        return None
    names = set(re.findall(r"(?<![\w./:-])(?:\./|/)?(?:[\w.-]+/)*[\w.-]+\.dart(?![\w/-]|\.\w)", prompt))
    if len(names) != 1:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    if policy.path_refused(cwd):
        return None
    root, cfg, allowed, mode = settings(cwd)
    if not allowed or mode != "narrow" or not cfg["read"]["prefetch"]:
        return None
    request = dict(payload, tool_name="Read", tool_input={"file_path": names.pop()})
    return narrow.read(request, Path(root).resolve(), cfg, prepare=True)


if __name__ == "__main__":
    os.umask(0o077)
    hookio.run({"start": start, "read": read, "prepare": prepare}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda payload: None), deadline=4.0)
