#!/usr/bin/env python3
import fcntl
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
try:
    from jev_flutter import config, hookio, jev, paths, policy, project, rules
except Exception:
    sys.exit(0)

TOOLS = {"Edit", "Write", "MultiEdit"}
DEBOUNCE_S = 2.0
MAX_DEBOUNCE_S = 5.0
MAX_DEFER_S = 12.0
DEADLINE_S = 25.0
MAX_RULE_LINES = 4
LOG = jev.STATE_DIR / "guard.jsonl"


@contextmanager
def locked(path):
    with open(path, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def log(record):
    try:
        with open(LOG, "a") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return None


def debounce(settings):
    try:
        return min(max(float(settings["guard"].get("debounce_s", DEBOUNCE_S)), 0.0), MAX_DEBOUNCE_S)
    except (TypeError, ValueError):
        return DEBOUNCE_S


def steps_of(name, tool_input, response):
    # How the tool changed the file, oldest first: the runs of Claude Code's diff, else the replaced strings.
    response = response if isinstance(response, dict) else {}
    patch = response.get("structuredPatch")
    if name == "Write":
        if response.get("type") != "update":
            return [{"create": True}]
        if not isinstance(patch, list):
            return [{"unknown": True}]
    elif not (isinstance(patch, list) and patch):
        edits = tool_input.get("edits") if name == "MultiEdit" else [tool_input]
        return [{"edit": [e["old_string"], e["new_string"]]} for e in (edits if isinstance(edits, list) else [])
                if isinstance(e, dict) and isinstance(e.get("old_string"), str) and isinstance(e.get("new_string"), str)]
    if not patch:
        return []
    runs = rules.patch_runs(patch)
    return [{"runs": runs} if runs else {"unknown": True}]


def _queue(queue):
    data = hookio.read_json(queue, {})
    data = data if isinstance(data, dict) else {}
    return int(data.get("seq") or 0), [e for e in data.get("pending") or [] if isinstance(e, dict)]


def enqueue(queue, lock, entry):
    with locked(lock):
        seq, pending = _queue(queue)
        entry["seq"] = seq + 1
        hookio.write_json(queue, {"seq": entry["seq"], "pending": pending + [entry]})
    return entry["seq"]


def claim(queue, lock, seq):
    # The newest process takes every pending edit of the file; older ones step aside unless the batch waited too long.
    with locked(lock):
        newest, pending = _queue(queue)
        oldest = min((e.get("ts", 0) for e in pending), default=time.time())
        if newest > seq and time.time() - oldest < MAX_DEFER_S:
            return []
        hookio.write_json(queue, {"seq": newest, "pending": []})
        return sorted(pending, key=lambda e: e.get("seq", 0))


def hand_over(queue, lock, batch):
    # Newer edits of the same file are waiting: give the batch back so their process judges everything at once.
    with locked(lock):
        newest, pending = _queue(queue)
        if not pending:
            return False
        hookio.write_json(queue, {"seq": newest, "pending": batch + pending})
        return True


def report(rel, stamp, hits, gaps):
    head = "jev-for-flutter · conventions à vérifier dans %s (édition de %s)" % (rel, time.strftime("%H:%M:%S", time.localtime(stamp)))
    if gaps:
        head += " (évaluation partielle : %s)" % ", ".join(gaps)
    lines = [head + " :"]
    shown = hits if len(hits) <= MAX_RULE_LINES else hits[:MAX_RULE_LINES - 1]
    for rule, p, _ in shown:
        lines.append("- [%s] %s (p=%.2f)" % (rule["id"], " ".join(rule["message"].split()), p))
    if len(hits) > len(shown):
        names = ", ".join(r["id"] for r, _, _ in hits[len(shown):])
        if len(names) > 100:
            names = names[:100].rsplit(", ", 1)[0] + ", …"
        lines.append("- (+%d autres : %s)" % (len(hits) - len(shown), names))
    lines.append("Corrige si c'est avéré, sinon ignore (avis probabiliste, non bloquant).")
    return "\n".join(lines)


def wake(text):
    sys.stderr.write(text + "\n")
    sys.stderr.flush()
    os._exit(2)


def main(payload):
    started = time.time()
    name = payload.get("tool_name")
    tool_input = payload.get("tool_input") if isinstance(payload.get("tool_input"), dict) else {}
    target = tool_input.get("file_path")
    if name not in TOOLS or not isinstance(target, str) or not target:
        return None
    root = project.project_root(payload.get("cwd") or None)
    settings = config.load(root)
    rules_file = rules.path(root, settings)
    if not settings["guard"].get("enabled") or not rules_file.is_file():
        return None
    real = os.path.realpath(target)
    rel = os.path.relpath(real, os.path.realpath(str(root))).replace(os.sep, "/")
    if rel == ".." or rel.startswith("../"):
        return None
    ruleset = rules.read(rules_file)
    selected = rules.select(ruleset, rel)
    if not selected or not policy.jev_allowed(root, settings, "guard")[0]:
        return None
    if not policy.sendable(real, root) or not policy.sendable(str(rules_file), root) or paths.is_generated(real, settings, root):
        return None
    steps = steps_of(name, tool_input, payload.get("tool_response"))
    if not steps:
        return None

    session = payload.get("session_id") or "default"
    directory = hookio.state_file("guard", session)
    directory.mkdir(exist_ok=True)
    key = hashlib.sha1(real.encode("utf-8")).hexdigest()
    queue, lock = directory / (key + ".json"), directory / (key + ".lock")
    # Deletions are queued too: older edits can only be traced back through every later edit of the file.
    seq = enqueue(queue, lock, {"ts": started, "tool": name, "steps": steps})
    time.sleep(debounce(settings))
    batch = claim(queue, lock, seq)
    if not batch:
        return None

    record = {"ts": None, "session": session, "file": key, "edits": len(batch), "changes": 0, "lost": 0, "requests": 0,
              "unjudged": 0, "rules": {}, "fired": [], "jev_ms": None, "wait_ms": None, "partial": False, "outcome": "stale"}
    last_edit = max(e.get("ts", started) for e in batch)

    def done(outcome):
        record.update(outcome=outcome, ts=round(time.time(), 3), wait_ms=int((time.time() - last_edit) * 1000))
        log(record)

    text = read_text(real)
    if text is None:
        return done("stale")
    # Each change is tied to its exact lines: an edit that no longer matches the file is counted lost, never judged.
    changes, lost = rules.net_changes(text, [step for entry in batch for step in entry.get("steps") or []])
    record.update(changes=len(changes), lost=lost, partial=lost > 0)
    if lost and hand_over(queue, lock, batch):
        return done("handed")
    if not changes:
        return done("stale" if lost else "noop")
    states, unjudged = rules.build_states(rel, changes, text, reserve=rules.longest_question(selected))
    client = jev.Client(settings, "guard", timeout=settings["jev"]["hook_timeout_s"], use_breaker=True)
    record.update(requests=len(states) * -(-len(selected) // rules.PER_REQUEST), unjudged=unjudged)
    asked = time.monotonic()
    try:
        answers, failed, record["requests"] = rules.ask(client, states, selected)
    except jev.JevError as error:
        record.update(jev_ms=int((time.monotonic() - asked) * 1000), error=type(error).__name__, status=error.status)
        return done("error")
    record.update(jev_ms=int((time.monotonic() - asked) * 1000), failed=failed, partial=bool(lost or unjudged or failed))
    verdicts = rules.scored(answers, selected, ruleset, settings)
    record["rules"] = {rule["id"]: round(p, 4) for rule, p, _ in verdicts}
    hits = sorted((v for v in verdicts if v[1] >= v[2]), key=lambda v: -v[1])
    if read_text(real) != text:
        return done("handed" if hand_over(queue, lock, batch) else "stale")
    record["fired"] = [rule["id"] for rule, _, _ in hits]
    if not hits:
        return done("partial" if record["partial"] else "quiet")
    done("fired")
    gaps = [label % count for label, count in (("lignes non jugées : %d", unjudged), ("requêtes Jev en échec : %d", failed),
                                                 ("éditions non retrouvées dans le fichier : %d", lost)) if count]
    wake(report(rel, last_edit, hits, gaps))


if __name__ == "__main__":
    hookio.run(main, DEADLINE_S)
