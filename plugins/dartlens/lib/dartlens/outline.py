import bisect
import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import chunks, project

SOURCES = Path(__file__).resolve().parents[2] / "outline"
CACHE = Path.home() / ".cache" / "dartlens" / "outline"
BUILD_LOG = CACHE / "build.log"
FAILED_RETRY_S = 3600
LOCK_WAIT_S = 180
NOT_BUILT = "outline non compilé"
TEST_CALLS = {"group", "test", "testWidgets", "blocTest", "testGoldens", "goldenTest", "patrolTest", "patrolWidgetTest",
              "setUp", "setUpAll", "tearDown", "tearDownAll"}


def _log(message):
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        with open(BUILD_LOG, "a") as handle:
            handle.write("%s %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), message))
    except OSError:
        pass


def dart_command(root=None):
    dart = project.dart_executable(root)
    if not dart:
        return None
    # Flutter's bin/dart is a shell wrapper; the bundled SDK binary starts faster and skips tool updates.
    bundled = Path(dart).resolve().parent / "cache" / "dart-sdk" / "bin" / "dart"
    return str(bundled) if bundled.exists() else dart


def sdk_version(dart):
    real = Path(dart).resolve()
    for candidate in (real.parent.parent / "version", real.parent / "cache" / "dart-sdk" / "version"):
        try:
            return candidate.read_text().strip()
        except OSError:
            continue
    try:
        result = subprocess.run([dart, "--version"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    match = re.search(r"version:\s*(\S+)", result.stdout + result.stderr)
    return match.group(1) if match else None


def cache_dir(dart):
    digest = hashlib.sha1()
    for name in ("pubspec.yaml", "bin/outline.dart"):
        digest.update((SOURCES / name).read_bytes())
    digest.update(("%s|%s|%s" % (sdk_version(dart), platform.system(), platform.machine())).encode())
    return CACHE / digest.hexdigest()[:16]


def _run(command, cwd, timeout):
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        ok, output = result.returncode == 0, (result.stdout + result.stderr).strip()
    except (OSError, subprocess.SubprocessError) as error:
        ok, output = False, str(error)
    _log("%s %s (%.1f s)%s" % ("ok" if ok else "ÉCHEC", " ".join(command[1:3]), time.monotonic() - started,
                               "" if ok else " : " + output[-400:].replace("\n", " | ")))
    return ok, output


def _build(dart, directory):
    started = time.monotonic()
    src = directory / "src"
    (src / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCES / "pubspec.yaml", src / "pubspec.yaml")
    shutil.copyfile(SOURCES / "bin" / "outline.dart", src / "bin" / "outline.dart")
    ok, output = _run([dart, "pub", "get", "--offline"], src, 180)
    if not ok:
        ok, output = _run([dart, "pub", "get"], src, 600)
    if ok:
        target = directory / ("outline.%d.tmp" % os.getpid())
        ok, output = _run([dart, "compile", "exe", "bin/outline.dart", "-o", str(target)], src, 900)
        if ok:
            os.replace(str(target), str(directory / "outline"))
    seconds = time.monotonic() - started
    _log("compilation %s en %.1f s -> %s" % ("réussie" if ok else "échouée", seconds, directory))
    return ok, output, seconds


def binary(root=None, build=True, force=False, wait=LOCK_WAIT_S):
    dart = dart_command(root)
    if not dart:
        return None, "SDK Dart introuvable"
    try:
        directory = cache_dir(dart)
    except OSError as error:
        return None, "sources de l'outline illisibles : %s" % error
    exe = directory / "outline"
    if exe.exists() and not force:
        return str(exe), ""
    failed = directory / "failed"
    if not force and failed.exists() and time.time() - failed.stat().st_mtime < FAILED_RETRY_S:
        return None, "compilation échouée récemment (voir %s)" % BUILD_LOG
    if not build:
        return None, NOT_BUILT
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / ".lock", "w") as lock:
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() > deadline:
                    return None, "compilation en cours dans un autre processus"
                time.sleep(0.2)
        if exe.exists() and not force:
            return str(exe), ""
        ok, output, seconds = _build(dart, directory)
        if not ok:
            failed.write_text(output[-2000:])
            return None, "compilation échouée (voir %s)" % BUILD_LOG
        failed.unlink(missing_ok=True)
        return str(exe), "outline compilé en %.1f s" % seconds


def _building(root):
    dart = dart_command(root)
    try:
        lock_path = cache_dir(dart) / ".lock" if dart else None
    except OSError:
        return False
    if not lock_path or not lock_path.exists():
        return False
    try:
        with open(lock_path, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(lock, fcntl.LOCK_UN)
        return False
    except OSError:
        return True


def build_in_background(root=None):
    if _building(root):
        return "compilation de l'outline en cours en arrière-plan"
    lib = str(Path(__file__).resolve().parents[1])
    code = "import sys; sys.path.insert(0, %r); from dartlens import outline; outline.binary(%r)" % (lib, str(root) if root else None)
    try:
        subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError as error:
        return "compilation impossible : %s" % error
    return "compilation de l'outline lancée en arrière-plan (%s)" % BUILD_LOG


def outline(files, root=None, approx=False, build=True):
    files = [str(f) for f in files]
    if not files:
        return {}, False, ""
    note = ""
    if not approx:
        if build == "background":
            exe, note = binary(root, build=False)
            if not exe and note == NOT_BUILT:
                note = build_in_background(root)
        else:
            exe, note = binary(root, build=build)
        if exe:
            try:
                result = subprocess.run([exe, "--json", "--stdin"], input="\n".join(files), capture_output=True, text=True,
                                        timeout=10 + 0.2 * len(files))
                data = json.loads(result.stdout)
                if isinstance(data, dict) and all(f in data for f in files):
                    return data, False, note
                note = "sortie de l'outline incomplète"
            except (OSError, subprocess.SubprocessError, ValueError) as error:
                note = "outline en échec : %s" % error
    data = {}
    for path in files:
        try:
            data[path] = regex_outline(Path(path).read_bytes().decode("utf-8", "replace"))
        except OSError as error:
            data[path] = {"error": str(error)}
    return data, True, note


def _skip_string(text, i):
    n = len(text)
    raw = text[i] in "rR"
    if raw:
        i += 1
    quote = text[i]
    delimiter = quote * 3 if text.startswith(quote * 3, i) else quote
    j = i + len(delimiter)
    while j < n:
        if not raw and text[j] == "\\":
            j += 2
            continue
        if text.startswith(delimiter, j):
            return j + len(delimiter)
        if len(delimiter) == 1 and text[j] == "\n":
            return j
        if not raw and text.startswith("${", j):
            j = _skip_interpolation(text, j + 2)
            continue
        j += 1
    return n


def _string_start(text, i):
    c = text[i]
    if c in "'\"":
        return True
    return c in "rR" and i + 1 < len(text) and text[i + 1] in "'\"" and not (i and (text[i - 1].isalnum() or text[i - 1] == "_"))


def _skip_interpolation(text, j):
    depth, n = 1, len(text)
    while j < n:
        if _string_start(text, j):
            j = _skip_string(text, j)
            continue
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def mask(text):
    out = list(text)
    i, n = 0, len(text)

    def blank(a, b, keep=None):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "
        if keep is not None:
            out[a] = keep

    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif text.startswith("/*", i):
            depth, j = 1, i + 2
            while j < n and depth:
                if text.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif text.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            blank(i, j)
            i = j
        elif _string_start(text, i):
            j = _skip_string(text, i)
            blank(i, j, keep='"')
            i = j
        else:
            i += 1
    return "".join(out)


def _items(masked, start, end):
    items = []
    depth, i = 0, start
    item_start = body = None
    assigned = False
    while i < end:
        c = masked[i]
        if item_start is None:
            if c.isspace() or (c == ";" and depth == 0):
                i += 1
                continue
            item_start, body, assigned = i, None, False
        if c in "([{":
            if c == "{" and depth == 0 and body is None and not assigned:
                body = i
            depth += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
            if c == "}" and depth == 0 and body is not None and not assigned:
                items.append((item_start, i + 1, body))
                item_start = None
        elif depth == 0 and c == "=" and masked[i + 1:i + 2] != "=" and masked[i - 1:i] not in ("=", "!", "<", ">"):
            if body is None:
                assigned = True
        elif depth == 0 and c == ";":
            items.append((item_start, i + 1, None))
            item_start = None
        i += 1
    if item_start is not None:
        items.append((item_start, end, body))
    return items


ANNOTATION = re.compile(r"@\w+(?:\.\w+)*(?:\s*\([^()]*(?:\([^()]*\)[^()]*)*\))?")
ID = r"[A-Za-z_$][\w$]*"
CLASS_RE = re.compile(r"^(?:(?:abstract|sealed|base|final|interface|mixin|macro|augment)\s+)*class\s+(%s)" % ID)
MIXIN_RE = re.compile(r"^(?:base\s+)?mixin\s+(%s)" % ID)
EXT_TYPE_RE = re.compile(r"^extension\s+type\s+(?:const\s+)?(%s)" % ID)
EXT_RE = re.compile(r"^extension\s*(%s)?\s*(?:<[^>]*>)?\s*on\b" % ID)
ENUM_RE = re.compile(r"^enum\s+(%s)" % ID)
TYPEDEF_RE = re.compile(r"^typedef\s+(%s)\s*(?:<[^=]*>)?\s*=" % ID)
OLD_TYPEDEF_RE = re.compile(r"^typedef\s+.*?(%s)\s*(?:<[^()]*>)?\s*\(" % ID)
CALL_RE = re.compile(r"(%s)\s*(?:<[^()]*>)?\s*\(" % ID)
ACCESSOR_RE = re.compile(r"\b(get|set)\s+(%s)" % ID)
VAR_RE = re.compile(r"(%s)\s*(?:=|$)" % ID)


def _header(text, masked, a, stop):
    pos = a
    while True:
        while pos < stop and masked[pos].isspace():
            pos += 1
        match = ANNOTATION.match(masked, pos) if pos < stop and masked[pos] == "@" else None
        if not match:
            break
        pos = match.end()
    cut = re.search(r"(?<![=!<>])=(?!=)", masked[pos:stop])
    end = pos + cut.start() if cut and not _in_brackets(masked[pos:pos + cut.start()]) else stop
    arrow = " =>" if end < stop and masked[end:end + 2] == "=>" else ""
    return pos, re.sub(r"\s+", " ", masked[pos:stop]).strip(), re.sub(r"\s+", " ", text[pos:end]).strip() + arrow


def _in_brackets(prefix):
    depth = 0
    for c in prefix:
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
    return depth > 0


def _signature(source, limit=160):
    source = re.sub(r"\s*(\{|;)\s*$", "", source).strip()
    return source if len(source) <= limit else source[:limit - 1] + "…"


def _classify(flat):
    for kind, regex in (("class", CLASS_RE), ("mixin", MIXIN_RE), ("extension type", EXT_TYPE_RE), ("enum", ENUM_RE)):
        match = regex.match(flat)
        if match:
            return kind, match.group(1)
    match = EXT_RE.match(flat)
    if match:
        return "extension", match.group(1) or "<unnamed>"
    match = TYPEDEF_RE.match(flat) or OLD_TYPEDEF_RE.match(flat)
    if match:
        return "typedef", match.group(1)
    return None, None


def _callable(flat, owner=None):
    before = re.split(r"=>|=(?!=)", flat, 1)[0]
    accessor = ACCESSOR_RE.search(before)
    paren = before.find("(")
    if accessor and (paren < 0 or accessor.start() < paren):
        return ("getter" if accessor.group(1) == "get" else "setter"), accessor.group(2)
    if re.search(r"\boperator\b", before):
        return "operator", "operator"
    call = CALL_RE.search(before)
    if call:
        name = call.group(1)
        if owner and (name == owner or re.search(r"\b%s\s*\.\s*\w+\s*\($" % re.escape(owner), before[:call.end()])
                      or before.startswith(("factory ", "const " + owner))):
            dotted = re.search(r"\b%s\s*\.\s*(\w+)" % re.escape(owner), before)
            return "constructor", dotted.group(1) if dotted else ""
        return ("method" if owner else "function"), name
    variable = VAR_RE.search(before.rstrip(";").strip())
    return ("field" if owner else "variable"), (variable.group(1) if variable else before.strip()[:40])


def regex_outline(text):
    masked = mask(text)
    starts = [0] + [m.end() for m in re.finditer("\n", text)]
    source_lines = chunks.split_lines(text)

    def line(offset):
        return bisect.bisect_right(starts, offset)

    def first_line(offset):
        number = line(offset)
        while number > 1 and source_lines[number - 2].lstrip().startswith("///"):
            number -= 1
        return number

    def entry(kind, name, a, b, sig, children=None, name_at=None):
        return {"kind": kind, "name": name, "signature": sig, "start": first_line(a), "end": line(max(a, b - 1)),
                "line": line(name_at if name_at is not None else a), "children": children or []}

    def members(owner, body_start, body_end, enum=False):
        out = []
        for index, (a, b, body) in enumerate(_items(masked, body_start + 1, body_end - 1)):
            stop = body if body is not None else b
            offset, flat, source = _header(text, masked, a, stop)
            if enum and index == 0:
                names = [n.strip().split("(")[0] for n in re.split(r",", flat.rstrip(";")) if n.strip()]
                out.append(entry("constants", "%d values" % len(names), offset, b, _signature(", ".join(names), 120)))
                continue
            kind, name = _callable(flat, owner)
            out.append(entry(kind, name, a, b, _signature(source), name_at=offset))
        return out

    decls, directives = [], []
    for a, b, body in _items(masked, 0, len(text)):
        stop = body if body is not None else b
        offset, flat, source = _header(text, masked, a, stop)
        if re.match(r"^(import|export|part|library)\b", flat):
            directives.append((a, b))
            continue
        kind, name = _classify(flat)
        if kind and kind != "typedef" and body is not None:
            sig = _signature(source)
            children = members(name, body, b, enum=kind == "enum")
            decls.append(entry(kind, name, a, b, sig, children, name_at=offset))
        elif kind == "typedef":
            decls.append(entry(kind, name, a, b, _signature(re.sub(r"\s+", " ", text[offset:b])), name_at=offset))
        else:
            kind, name = _callable(flat)
            decls.append(entry(kind, name, a, b, _signature(source), name_at=offset))
    tests = _regex_tests(text, masked, line)
    lines = text.count("\n") + (0 if text.endswith("\n") or not text else 1)
    return {
        "lines": lines,
        "directives": [line(directives[0][0]), line(directives[-1][1] - 1), len(directives)] if directives else None,
        "decls": decls,
        "tests": tests,
        "errors": 0,
        "approx": True,
    }


TEST_CALL_RE = re.compile(r"(?<![\w.$])(%s)\s*(?:<[^()]*>)?\s*\(" % "|".join(sorted(TEST_CALLS, key=len, reverse=True)))


def _regex_tests(text, masked, line):
    found = []
    for match in TEST_CALL_RE.finditer(masked):
        open_at = match.end() - 1
        depth, j = 0, open_at
        while j < len(masked):
            if masked[j] in "([{":
                depth += 1
            elif masked[j] in ")]}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        label = ""
        literal = re.match(r"\s*(r?)('''|\"\"\"|'|\")", text[open_at + 1:open_at + 400])
        if literal:
            quote = literal.group(2)
            begin = open_at + 1 + literal.end()
            close = text.find(quote, begin)
            label = re.sub(r"\s+", " ", text[begin:close if close > 0 else begin + 120])[:120]
        found.append({"kind": match.group(1), "name": label, "start": line(match.start()), "end": line(j),
                      "children": [], "_span": (match.start(), j)})
    roots, stack = [], []
    for node in found:
        while stack and node["_span"][0] > stack[-1]["_span"][1]:
            stack.pop()
        (stack[-1]["children"] if stack else roots).append(node)
        stack.append(node)
    for node in found:
        node.pop("_span")
    return roots


def _render_nodes(out, nodes, depth, tests=False):
    for node in nodes:
        if tests:
            label = node["kind"] + (" '%s'" % node["name"] if node.get("name") else "")
        else:
            label = node.get("signature") or node.get("name", "")
        out.append("%s%d-%d %s" % ("  " * depth, node["start"], node["end"], label))
        _render_nodes(out, node.get("children") or [], depth + 1, tests)


def render(path, entry):
    if entry.get("error"):
        return "== %s : %s\n" % (path, entry["error"])
    extra = " · approx (repli regex)" if entry.get("approx") else ""
    errors = entry.get("errors") or 0
    out = ["== %s (%d lignes%s%s)" % (path, entry.get("lines", 0), " · %d erreurs de syntaxe" % errors if errors else "", extra)]
    directives = entry.get("directives")
    if directives:
        out.append("%d-%d directives (%d)" % tuple(directives))
    _render_nodes(out, entry.get("decls") or [], 0)
    if entry.get("tests"):
        out.append("tests :")
        _render_nodes(out, entry["tests"], 1, tests=True)
    return "\n".join(out) + "\n"
