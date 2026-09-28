import argparse
import json
import math
import re
import time

from .. import jev, transcript

COMPONENTS = ("lens", "guard", "router")
FIRST = ("run", "outcome", "mode", "backend", "status", "p", "p_max", "fired", "kept", "rules", "top", "skill")
HIDDEN = {"ts", "session", "tool", "component"}
TEXT_KEYS = {"outcome", "mode", "backend", "status", "model", "file", "verdict", "decision", "kind"}
# Collections of rule ids, note files, skill names, paths or line ranges; anything else shows numbers only.
NAME_KEYS = {"rules", "fired", "kept", "top", "skill", "skills", "notes", "selected", "ranges", "files", "omitted",
             "candidates", "errors"}
LABEL_KEYS = ("id", "name", "rule", "note", "skill", "file", "path", "lines", "range")
# Only identifier-like strings of up to four words are printed, never prose or code; the rest is masked in place.
IDENT = re.compile(r"[\w.:/@+#~-]+(?: [\w.:/@+#~-]+){0,3}")
MASK = "‹masqué›"
# Error details may echo request fragments: keep the kind only.
ERROR_KIND = re.compile(r"(HTTP \d{3}|réseau|[A-Z]\w*(?:Error|Unavailable|Exception))\b")
MAX_ITEMS = 6
MAX_NAME = 48
STALE_TAIL = 200


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def valid_ts(value):
    return is_number(value) and math.isfinite(value) and 0 < value < 4e9


def error_kind(value):
    match = ERROR_KIND.match(value) if isinstance(value, str) else None
    if not match:
        return "autre"
    if match.group(1) == "réseau" and ("timed out" in value or "délai dépassé" in value):
        return "réseau (délai dépassé)"
    return match.group(1)


def read_records(file, since=0, limit=None):
    found, skipped, older = [], 0, 0
    try:
        for line in transcript.reverse_lines(file):
            try:
                entry = json.loads(line)
            except ValueError:
                entry = None
            if not isinstance(entry, dict) or not valid_ts(entry.get("ts")):
                skipped += 1
                continue
            if entry["ts"] < since:
                # Several processes append: tolerate some out-of-order lines before stopping.
                older += 1
                if older > STALE_TAIL:
                    break
                continue
            older = 0
            found.append(entry)
            if limit and len(found) >= limit:
                break
    except OSError:
        skipped += 1
    return found, skipped


def number(value):
    return ("%.3f" % value).rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def name(value):
    if not isinstance(value, str) or len(value) > 120 or not IDENT.fullmatch(value):
        return None
    return value if len(value) <= MAX_NAME else value[:MAX_NAME - 1] + "…"


def joined(parts):
    parts = [p for p in parts if p]
    more = len(parts) - MAX_ITEMS
    return ", ".join(parts[:MAX_ITEMS]) + (" +%d" % more if more > 0 else "")


def item(value):
    if is_number(value):
        return number(value)
    if isinstance(value, str):
        return name(value) or MASK
    if isinstance(value, (list, tuple)):
        parts = [item(v) for v in value if not isinstance(v, (list, tuple, dict))]
        return " ".join(p for p in parts if p) or None
    if isinstance(value, dict):
        key = next((k for k in LABEL_KEYS if k in value), None)
        p = next((value[k] for k in ("p", "probability", "confidence") if is_number(value.get(k))), None)
        return ((name(value[key]) if key else None) or MASK) + (" " + number(p) if p is not None else "")
    return None


def field(key, value):
    if value is None or value == [] or value == {}:
        return None
    if isinstance(value, bool):
        return key if value else None
    if is_number(value):
        return "%s=%s" % (key, number(value))
    if key == "error":
        return "error=" + error_kind(value)
    if isinstance(value, str):
        if key == "run":
            return "run=" + (name(value) or MASK)
        return "%s=%s" % (key, value[:80]) if key in TEXT_KEYS else None
    if key not in NAME_KEYS:
        return None
    if isinstance(value, dict):
        pairs = sorted(((k, v) for k, v in value.items() if is_number(v)), key=lambda kv: -kv[1])
        rows = joined("%s %s" % (name(k) or MASK, number(v)) for k, v in pairs)
        return rows and "%s : %s" % (key, rows)
    if isinstance(value, list):
        rows = joined(item(v) for v in value)
        return rows and "%s : %s" % (key, rows)
    return None


def render(component, record):
    keys = [k for k in FIRST if k in record] + [k for k in record if k not in FIRST and k not in HIDDEN]
    head = "%s  %-6s" % (time.strftime("%m-%d %H:%M:%S", time.localtime(record["ts"])), component)
    session = name(record.get("session"))
    if session:
        head += "  s:" + session[:8]
    return head + "  " + " · ".join(f for f in (field(k, record[k]) for k in keys) if f)


def recent(component, count):
    found, skipped = [], 0
    for file in sorted(jev.STATE_DIR.glob(component + "*.jsonl")):
        # Margin for lines appended slightly out of order by concurrent hooks.
        records, bad = read_records(file, limit=2 * count + 50)
        found += [(r["ts"], component, r) for r in records]
        skipped += bad
    return found, skipped


def main(argv):
    parser = argparse.ArgumentParser(prog="dartlens log", description="Dernières décisions de lens, de la garde et du "
                                     "routeur : probabilités, règles ou fiches retenues, sans contenu.")
    parser.add_argument("component", nargs="?", choices=COMPONENTS, help="composant (défaut : tous)")
    parser.add_argument("-n", type=int, default=20, help="nombre de décisions (défaut 20)")
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("-n doit être positif")
    components = [args.component] if args.component else list(COMPONENTS)
    rows, skipped = [], 0
    for component in components:
        found, bad = recent(component, args.n)
        rows += found
        skipped += bad
    rows = sorted(rows, key=lambda row: row[0])[-args.n:]
    if not rows:
        print("Aucune décision journalisée (%s dans %s)." % (", ".join(c + "*.jsonl" for c in components), jev.STATE_DIR))
    for _, component, record in rows:
        print(render(component, record))
    if skipped:
        print("%d ligne(s) illisible(s) ignorée(s)." % skipped)
    return 0
