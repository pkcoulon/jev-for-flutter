import fcntl
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

from . import hookio, jev, outline, paths, policy


def clean_goal(content):
    if not isinstance(content, str):
        return ""
    for marker in ("<system-reminder>", "<command-name>", "<local-command-stdout>"):
        content = content.split(marker, 1)[0]
    content = content.strip()
    return policy.redact(content) if 12 <= len(content) <= 2000 else ""


def goal_from_transcript(path):
    if not path:
        return ""
    with open(path, "rb") as handle:
        size = handle.seek(0, os.SEEK_END)
        handle.seek(max(0, size - 1024 * 1024))
        if size > 1024 * 1024:
            handle.readline()
        records = handle.read().splitlines()
    for raw in reversed(records):
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeError):
            continue
        if record.get("type") != "user" or record.get("isMeta"):
            continue
        content = (record.get("message") or {}).get("content")
        if isinstance(content, list):
            if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                continue
            content = "\n".join(b.get("text", "") for b in content
                                if isinstance(b, dict) and b.get("type") == "text")
        if not isinstance(content, str) or not content.strip():
            continue
        return clean_goal(content)
    return ""


def probability(answer, key):
    value = answer.get(key) if isinstance(answer, dict) else None
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1 else None


def reserve(session, key, maximum, kind="read-windows"):
    if not session:
        return False
    directory = hookio.state_file(kind, session)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with open(directory.parent / (directory.name + ".lock"), "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        if len(list(directory.iterdir())) >= maximum:
            return False
        try:
            os.close(os.open(directory / key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        except FileExistsError:
            return False
    return True


def judge(payload, cfg, key, state, questions, prepare):
    directory = hookio.state_file("read-prepared", payload.get("session_id"))
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    cached = directory / (key + ".json")
    timeout = min(3, max(0.1, cfg["read"]["timeout_s"]))
    deadline = time.monotonic() + timeout
    requested = False
    while True:
        result = hookio.read_json(cached, {})
        if isinstance(result, dict) and type(result.get("time")) in (int, float) \
                and 0 <= time.time() - result["time"] <= 90:
            return result.get("answers"), True
        if not requested:
            requested = True
            maximum = min(24, max(0, cfg["read"]["max_calls"]))
            if reserve(payload.get("session_id"), key, maximum, "read-requests"):
                client = jev.Client(cfg, "read", timeout=timeout, retries=0, use_breaker=True)
                try:
                    answers = client.ask(state, questions)
                except jev.JevError:
                    answers = None
                hookio.write_json(cached, {"time": time.time(), "answers": answers})
                return answers, False
            marker = hookio.state_file("read-requests", payload.get("session_id")) / key
            if prepare or not marker.is_file() or time.time() - marker.stat().st_mtime > timeout + 1:
                return None, False
        if time.monotonic() >= deadline:
            return None, False
        time.sleep(min(0.025, max(0, deadline - time.monotonic())))


def window(text, line, last=None, goal=""):
    lines = text.splitlines()
    total = len(lines)
    width = max(150, total // 5)
    start = max(1, min(line - width // 2, total - width + 1))
    end = start + width - 1
    tree = outline.regex_outline(text)
    declarations = list(tree.get("decls") or [])
    flat, candidates = [], []
    while declarations:
        node = declarations.pop()
        flat.append(node)
        declarations.extend(node.get("children") or [])
        if node.get("kind") not in ("function", "method", "constructor", "getter", "setter"):
            continue
        a, b = node.get("start"), node.get("end")
        if isinstance(a, int) and isinstance(b, int) and a <= (last or line) and b >= line:
            start, end = min(start, a), max(end, b)
            candidates.append(node)
    explicit_targets = []
    for target in candidates:
        name = target.get("name", "")
        explicit = name and re.search(r"`" + re.escape(name) + r"`|(?<![\w$])" + re.escape(name) + r"\s*\(", goal)
        unique = name and sum(n.get("name") == name for n in flat) == 1
        if explicit and unique:
            explicit_targets.append(target)
    if len(explicit_targets) == 1:
        needed, pending = set(), [flat.index(explicit_targets[0])]
        while pending and len(needed) <= 32:
            i = pending.pop()
            if i in needed:
                continue
            needed.add(i)
            node = flat[i]
            body = outline.mask("\n".join(lines[node["start"] - 1:node["end"]]))
            names = set(re.findall(outline.ID, body))
            pending.extend(j for j, n in enumerate(flat) if j not in needed and n.get("name") in names)
        if not pending and len(needed) <= 32:
            first = min(flat[i]["start"] for i in needed)
            final = max(flat[i]["end"] for i in needed)
            width = max(64, final - first + 25)
            a = max(1, min((first + final - width) // 2, total - width + 1))
            b = min(total, a + width - 1)
            if a <= first and b >= final and start <= a <= b <= end:
                start, end = a, b
    return (start, end) if end - start + 1 <= total * 0.6 else None


def read(payload, root, cfg, prepare=False):
    began = time.monotonic()
    tool_input = payload.get("tool_input") or {}
    if not payload.get("session_id") or payload.get("tool_name") != "Read" \
            or "offset" in tool_input or "limit" in tool_input:
        return None
    name = tool_input.get("file_path")
    if not isinstance(name, str) or not name.endswith(".dart"):
        return None
    file = (Path(payload.get("cwd") or root) / name).resolve()
    if not policy.sendable(file, root) or paths.is_generated(str(file), cfg, root) or not file.is_file():
        return None
    limits = cfg["read"]
    if file.stat().st_size > min(64000, max(1, limits["max_bytes"])):
        return None
    raw = file.read_bytes()
    if b"\0" in raw or len(raw) > min(64000, max(1, limits["max_bytes"])):
        return None
    text = raw.decode("utf-8")
    lines = policy.redact(text).splitlines()
    if len(lines) < max(400, limits["min_lines"]):
        return None
    goal = clean_goal(payload.get("prompt")) if prepare else goal_from_transcript(payload.get("transcript_path"))
    if not goal:
        return None
    step = max(10, math.ceil(len(lines) / 200))
    blocks = {"c%d" % (i // step): {"start_line": i + 1, "text": "\n".join(lines[i:i + step])}
              for i in range(0, len(lines), step)}
    state = {"goal": goal, "file": {"path": str(file.relative_to(root)), "chunks": blocks}}
    questions = {
        "where": jev.choice("Which chunk contains the implementation most directly needed for `goal`? "
                            "Use the source, regardless of the language of the goal.",
                            {key: "lines %d-%d" % (b["start_line"], min(len(lines), b["start_line"] + step - 1))
                             for key, b in blocks.items()}),
        "focused": jev.noul("Is `goal` a focused question about ONE localized behaviour in this file, "
                            "so a single region with surrounding code is enough to investigate it? "
                            "Answer no for a whole-file review, a rewrite, multiple independent questions, "
                            "comparison of separate paths or tracing an end-to-end flow."),
    }
    if jev.estimate_tokens(state) + jev.estimate_tokens(questions) > jev.STATE_TOKEN_BUDGET:
        return None
    stamp = hashlib.sha256(raw).hexdigest()
    key = hashlib.sha256(json.dumps([str(file), stamp, goal, jev.model_name(cfg), jev.base_url(), questions],
                                   sort_keys=True).encode()).hexdigest()[:32]
    if not prepare and not reserve(payload.get("session_id"), key, min(24, max(0, limits["max_calls"]))):
        return None
    answers, reused = judge(payload, cfg, key, state, questions, prepare)
    if prepare:
        jev._log("read.jsonl", {"ts": time.time(), "session": payload.get("session_id"), "event": "prepared",
                               "ready": isinstance(answers, dict), "ms": round((time.monotonic() - began) * 1000)})
        return None
    if not isinstance(answers, dict):
        return None
    where = answers.get("where")
    confidence = probability(where, "confidence")
    focused = probability(answers.get("focused"), "noul")
    choice = where.get("choice") if isinstance(where, dict) else None
    record = {"ts": time.time(), "session": payload.get("session_id"), "file": hashlib.sha256(str(file).encode()).hexdigest()[:16],
              "lines": len(lines), "confidence": confidence, "focused": focused, "event": "unchanged", "prepared": reused}
    selected = None
    if isinstance(choice, str) and choice in blocks and confidence is not None and confidence >= max(0.6, limits["confidence"]) \
            and focused is not None and focused >= max(0.85, limits["focused"]):
        selected = window(text, blocks[choice]["start_line"], min(len(lines), blocks[choice]["start_line"] + step - 1), goal)
    if selected and (hashlib.sha256(file.read_bytes()).hexdigest() != stamp
                     or not policy.sendable(file, root) or not policy.jev_allowed(root, cfg, "lens")[0]):
        selected = None
    output = None
    if selected:
        start, end = selected
        record.update(event="narrowed", offset=start, limit=end - start + 1,
                      full_chars=len(text), shown_chars=len("\n".join(text.splitlines()[start - 1:end])))
        note = ("Jev for Flutter: Read narrowed to lines %d-%d of %d. This is a selected region, not the whole file. "
                "Follow other calls/branches needed for the answer. Repeat Read for the whole file, or set an explicit "
                "offset/limit for another region. Source on disk is unchanged.") % (start, end, len(lines))
        output = hookio.context("PreToolUse", note)
        output["hookSpecificOutput"]["updatedInput"] = dict(tool_input, offset=start, limit=end - start + 1)
    record["ms"] = round((time.monotonic() - began) * 1000)
    jev._log("read.jsonl", record)
    return output
