import math
import re

MAX_DECL = 80
MAX_BLOCK = 120
WINDOW = 60
OVERLAP = 5
MIN_TAIL = 20
SMALL_MEMBER = 12
MERGED_MEMBERS = 30
SHARED_GAP = 6
TEXT_MIN, TEXT_MAX = 20, 60
OUTPUT_BLOCK = 40
OUTPUT_HEAD, OUTPUT_TAIL, OUTPUT_CONTEXT = 5, 30, 2
ERROR_HEAD, ERROR_TAIL = 40, 20
PIECE_CHARS = 4000
BLOCK_CHARS = 16000
ERROR_RE = re.compile(r"(?i:\b(?:errors?|exceptions?|failed|failures?|fatal|panic(?:ked)?|warnings?)\b)|✗|\bFAIL\b|Traceback")
SETUP_CALLS = {"setUp", "setUpAll", "tearDown", "tearDownAll"}
CLASS_KINDS = {"class", "mixin", "enum", "extension", "extension type"}
OWN_LABEL_KINDS = {"text", "output", "always"}


def split_lines(text):
    # Same numbering as sed, wc -l and cat -n: only \n ends a line (str.splitlines also splits on \r, \f, U+2028…).
    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def clip(text, limit=60):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _label(text, secrets=None, limit=60):
    return clip(secrets.sub("[REDACTED]", text) if secrets and text else text, limit)


def decl_label(decl, secrets=None):
    kind, name = decl.get("kind", ""), decl.get("name", "")
    if kind in CLASS_KINDS:
        return "%s %s" % (kind, name)
    if kind == "function":
        return "%s()" % name
    if kind in ("getter", "setter"):
        return "%s %s" % ("get" if kind == "getter" else "set", name)
    return _label(decl.get("signature") or name, secrets)


def member_label(owner, member):
    kind, name = member.get("kind", ""), member.get("name", "")
    if kind == "constructor":
        return "%s.%s()" % (owner, name) if name else "%s()" % owner
    if kind in ("method", "operator"):
        return "%s.%s()" % (owner, name)
    if kind == "setter":
        return "%s.%s=" % (owner, name)
    if kind == "constants":
        return "%s : %s" % (owner, name)
    return "%s.%s" % (owner, name)


def test_label(node, secrets=None):
    return "%s '%s'" % (node["kind"], _label(node["name"], secrets)) if node.get("name") else node["kind"]


def windows(start, end):
    spans, a = [], start
    while True:
        b = min(a + WINDOW - 1, end)
        spans.append([a, b])
        if b >= end:
            break
        a = b - OVERLAP + 1
    if len(spans) > 1 and spans[-1][1] - spans[-1][0] + 1 < MIN_TAIL:
        spans.pop()
        spans[-1][1] = end
    return spans


def _pieces(line, secrets):
    count = math.ceil(len(line) / PIECE_CHARS)
    step = math.ceil(len(line) / count)
    protected = [m.span() for m in secrets.finditer(line)] if secrets else []
    out, begin = [], 0
    while begin < len(line):
        end = min(begin + step, len(line))
        for a, b in protected:
            if a < end < b:
                end = b
        out.append((begin + 1, end))
        begin = end
    return out


def _by_chars(a, b, lines, secrets):
    parts, start, size = [], None, 0
    for number in range(a, b + 1):
        length = len(lines[number - 1])
        if length > PIECE_CHARS:
            if start is not None:
                parts.append((start, number - 1, None))
                start, size = None, 0
            parts += [(number, number, cols) for cols in _pieces(lines[number - 1], secrets)]
            continue
        if start is not None and size + length > BLOCK_CHARS:
            parts.append((start, number - 1, None))
            start, size = None, 0
        if start is None:
            start = number
        size += length + 1
    if start is not None:
        parts.append((start, b, None))
    return parts


def _seg(segs, start, end, label, kind, parent=None, context=False, line=None):
    if end < start:
        return None
    segs.append({"start": start, "end": end, "label": label, "kind": kind, "parent": parent, "context": context,
                 "line": line or start})
    return len(segs) - 1


def _members(segs, cursor, decl, secrets):
    children = sorted(decl.get("children") or [], key=lambda c: c["start"])
    first = next((c for c in children if c["kind"] not in ("field", "constants")), None)
    if first is None or first["start"] - 1 < max(cursor, decl.get("line", decl["start"])):
        _seg(segs, cursor, decl["end"], decl_label(decl, secrets), "decl", line=decl.get("line"))
        return decl["end"] + 1
    owner = decl.get("name", "")
    header = _seg(segs, cursor, first["start"] - 1, "%s (en-tête)" % decl_label(decl, secrets), "header", line=decl.get("line"))
    current, group = first["start"], []

    def flush():
        if group:
            names = [member_label(owner, c) for c in group]
            label = names[0] if len(names) == 1 else "%s … %s (%d membres)" % (names[0], names[-1], len(names))
            _seg(segs, group[0]["_from"], group[-1]["end"], label, "member", parent=header, line=group[0].get("line"))
            group.clear()

    for child in children:
        if child["start"] < current or child["end"] > decl["end"]:
            continue
        size = child["end"] - current + 1
        if group and (size > SMALL_MEMBER or child["end"] - group[0]["_from"] + 1 > MERGED_MEMBERS):
            flush()
        group.append(dict(child, _from=current))
        if size > SMALL_MEMBER:
            flush()
        current = child["end"] + 1
    flush()
    segs[-1]["end"] = decl["end"]
    return decl["end"] + 1


def _tests(segs, cursor, decl, tests, secrets):
    def walk(nodes, current, parent):
        for node in sorted(nodes, key=lambda n: n["start"]):
            if node["start"] < current:
                continue
            if node["start"] - current > SHARED_GAP:
                _seg(segs, current, node["start"] - 1, "code partagé entre tests", "group", parent=parent)
                current = node["start"]
            children = [c for c in node.get("children") or [] if c["start"] >= node["start"] and c["end"] <= node["end"]]
            if node["kind"].startswith("group") and children:
                first = min(c["start"] for c in children)
                group = _seg(segs, current, first - 1, test_label(node, secrets), "group", parent=parent, line=node["start"])
                walk(children, first, group if group is not None else parent)
                segs[-1]["end"] = max(segs[-1]["end"], node["end"])
            else:
                kind = "setup" if node["kind"] in SETUP_CALLS else "test"
                _seg(segs, current, node["end"], test_label(node, secrets), kind, parent=parent, line=node["start"])
            current = node["end"] + 1
        return current

    first = min(t["start"] for t in tests)
    head = _seg(segs, cursor, first - 1, "%s (en-tête)" % decl_label(decl, secrets), "group", line=decl.get("line"))
    walk(tests, first, head)
    segs[-1]["end"] = max(segs[-1]["end"], decl["end"])
    return decl["end"] + 1


def _finish(segs, lines, secrets=None):
    blocks, first_id = [], {}
    for index, seg in enumerate(segs):
        spans = windows(seg["start"], seg["end"]) if seg["end"] - seg["start"] + 1 > MAX_BLOCK else [[seg["start"], seg["end"]]]
        parts = [part for a, b in spans for part in _by_chars(a, b, lines, secrets)]
        for k, (a, b, cols) in enumerate(parts):
            text = "\n".join(lines[a - 1:b]) if cols is None else lines[a - 1][cols[0] - 1:cols[1]]
            block = dict(seg, id="b%d" % (len(blocks) + 1), start=a, end=b, text=text)
            if len(parts) > 1:
                base = seg["label"]
                if cols and seg["kind"] in OWN_LABEL_KINDS:
                    base = _label(text, secrets) or "(vide)"
                block["label"] = "%s [%d/%d]" % (base, k + 1, len(parts))
                block["line"] = seg["line"] if a <= seg["line"] <= b and k == 0 else a
            if cols:
                block["cols"] = cols
                if seg["kind"] == "always" and cols[0] > 1:
                    block.update(kind="output", context=False)
            first_id.setdefault(index, block["id"])
            blocks.append(block)
    for block in blocks:
        block["parent"] = first_id.get(block["parent"]) if block["parent"] is not None else None
    return blocks


def dart_blocks(path, text, structure, secrets=None):
    lines = split_lines(text)
    total = len(lines)
    if not total:
        return []
    if not structure or structure.get("error") or not structure.get("decls"):
        return text_blocks(text, secrets=secrets)
    segs, cursor = [], 1
    directives = structure.get("directives")
    if directives and directives[1] >= 1:
        _seg(segs, 1, min(directives[1], total), "imports (%d)" % directives[2], "directives", context=True)
        cursor = directives[1] + 1
    tests = structure.get("tests") or []
    for decl in sorted(structure.get("decls") or [], key=lambda d: d["start"]):
        if decl["end"] < cursor:
            continue
        end = min(decl["end"], total)
        decl = dict(decl, end=end)
        inner = [t for t in tests if decl["start"] <= t["start"] and t["end"] <= end]
        if inner and decl.get("kind") == "function":
            cursor = _tests(segs, cursor, decl, inner, secrets)
        elif end - cursor + 1 > MAX_DECL and decl.get("children"):
            cursor = _members(segs, cursor, decl, secrets)
        else:
            _seg(segs, cursor, end, decl_label(decl, secrets), "decl", line=decl.get("line"))
            cursor = end + 1
    if cursor <= total:
        if segs and not segs[-1]["context"]:
            segs[-1]["end"] = total
        else:
            _seg(segs, cursor, total, _label(next((l for l in lines[cursor - 1:] if l.strip()), "fin du fichier"), secrets), "text")
    return _finish(segs, lines, secrets)


def text_blocks(text, kind="text", secrets=None):
    lines = split_lines(text)
    total = len(lines)
    if not total:
        return []
    paragraphs, start = [], 1
    for number in range(1, total + 1):
        blank = not lines[number - 1].strip()
        following = number < total and lines[number].strip()
        if number == total or (blank and following):
            paragraphs.append((start, number))
            start = number + 1
    segs, current, size = [], 1, 0

    def close(end):
        label = _label(next((l for l in lines[current - 1:end] if l.strip()), "(vide)"), secrets)
        _seg(segs, current, end, label, kind)

    for a, b in paragraphs:
        heading = lines[a - 1].lstrip().startswith("#")
        if size and ((size + b - a + 1 > TEXT_MAX and size >= TEXT_MIN) or (heading and size >= TEXT_MIN // 2)):
            close(a - 1)
            current, size = a, 0
        size += b - a + 1
        while size > TEXT_MAX:
            close(current + TEXT_MAX - 1)
            current += TEXT_MAX
            size -= TEXT_MAX
    if size:
        if segs and size < TEXT_MIN // 2 and segs[-1]["end"] - segs[-1]["start"] + 1 + size <= TEXT_MAX + 10:
            segs[-1]["end"] = total
        else:
            close(total)
    return _finish(segs, lines, secrets)


def _error_key(line):
    return re.sub(r"\d+", "#", re.sub(r"\S*/\S*", "/", line)).strip()


def always_kept(lines):
    total = len(lines)
    keep = set(range(1, min(total, OUTPUT_HEAD) + 1)) | set(range(max(1, total - OUTPUT_TAIL + 1), total + 1))
    hits = [n for n, line in enumerate(lines, 1) if ERROR_RE.search(line)]
    seen, picked = set(), []
    for number in hits:
        key = _error_key(lines[number - 1])
        if key not in seen:
            seen.add(key)
            picked.append(number)
    if len(picked) > ERROR_HEAD + ERROR_TAIL:
        picked = picked[:ERROR_HEAD] + picked[-ERROR_TAIL:]
    for number in picked:
        keep.update(range(max(1, number - OUTPUT_CONTEXT), min(total, number + OUTPUT_CONTEXT) + 1))
    return keep, {"error_lines": len(hits), "error_kept": len(picked)}


def output_blocks(text, secrets=None):
    lines = split_lines(text)
    total = len(lines)
    if not total:
        return [], {"error_lines": 0, "error_kept": 0}
    keep, info = always_kept(lines)
    segs, start = [], 1
    for number in range(1, total + 2):
        if number <= total and (number in keep) == (start in keep):
            continue
        end = number - 1
        if start in keep:
            _seg(segs, start, end, _label(lines[start - 1], secrets) or "(vide)", "always", context=True)
        else:
            size = end - start + 1
            count = max(1, round(size / OUTPUT_BLOCK))
            step = math.ceil(size / count)
            for a in range(start, end + 1, step):
                b = min(a + step - 1, end)
                _seg(segs, a, b, _label(next((l for l in lines[a - 1:b] if l.strip()), "(vide)"), secrets), "output")
        start = number
    return _finish(segs, lines, secrets), info
