import re
from pathlib import Path

from . import hookio

HEAD_LINES = 15
FIELD = re.compile(r"^(name|description)\s*:\s*(.*?)\s*$")


def directory(transcript_path):
    if not transcript_path:
        return None
    path = Path(transcript_path).expanduser().parent / "memory"
    return path if path.is_dir() else None


def display(memory_dir):
    home = str(Path.home())
    text = str(memory_dir)
    return "~" + text[len(home):] if text.startswith(home + "/") else text


def ticket_keys(text, pattern):
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except (re.error, TypeError):
        return []
    keys = []
    for match in regex.finditer(text or ""):
        key = match.group(0).upper()
        if key not in keys:
            keys.append(key)
    return keys


def _key_regex(key):
    body = "[-_]".join(re.escape(part) for part in re.split(r"[-_]", key.lower()))
    return re.compile(r"(?<![a-z0-9])" + body + r"(?![a-z0-9])", re.IGNORECASE)


def _head(path):
    fields = {}
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle):
                if index >= HEAD_LINES:
                    break
                match = FIELD.match(line)
                if match and match.group(1) not in fields:
                    fields[match.group(1)] = match.group(2).strip("\"'")
    except OSError:
        pass
    return fields


def find(memory_dir, key, limit=5):
    regex = _key_regex(key)
    by_name, by_head = [], []
    for path in sorted(Path(memory_dir).resolve().glob("*.md")):
        if path.name.lower() == "memory.md":
            continue
        fields = _head(path)
        note = (path, fields.get("description") or fields.get("name") or "")
        if regex.search(path.stem):
            by_name.append(note)
        elif regex.search(fields.get("name", "") + "\n" + fields.get("description", "")):
            by_head.append(note)
    return (by_name + by_head)[:limit]


def listing(notes, width=160):
    items = []
    for path, description in notes:
        if len(description) > width:
            description = description[: width - 1].rstrip() + "…"
        items.append("memory/%s — %s" % (path.name, description) if description else "memory/%s" % path.name)
    return " ; ".join(items)


def _state(session_id):
    return hookio.state_file("tickets", session_id, ".json")


def seen(session_id):
    known = hookio.read_json(_state(session_id), [])
    return set(known) if isinstance(known, list) else set()


def remember(session_id, keys):
    hookio.write_json(_state(session_id), sorted(seen(session_id) | set(keys)))
