import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import bm25, hookio, jev, memory, policy, project

CACHE_VERSION = 2
SKILL_NAME_MAX = 64
DESC_WIDTH = 240
REQUEST_CHARS = 3000
HEAD_CHARS, TAIL_CHARS = 1990, 1000
CHUNK_NOTES = 150
MAX_SKILLS = 120
OUTPUT_CHARS = 700
LINE_DESC_WIDTH = 160
SKILL_MIN_P = 0.7
TICKET_NOTES = 3
# The hook's deadline is 4 s; Jev gets what is left of this, so selecting, rendering and logging still fit.
JEV_BUDGET_S = 3.5
# ASCII on purpose: transcripts store the hook's JSON escaped once more, and "·" does not survive that verbatim.
ROUTED_MARK = "probablement utile pour cette demande"
HEADER = "jev-for-flutter · %s :" % ROUTED_MARK
FOOTER = "Lis ou charge-les si c'est pertinent ; d'autres fiches peuvent compter."
NOTE_QUESTION = "Would reading `notes.%s` help handle `request`?"
NOTE_FOCUS = "Only notes with directly relevant facts, decisions or rules for this request."
SKILL_QUESTION = "Which listed skill, if any, should be loaded to handle `request`?"
SKILL_FOCUS = "Pick none unless one listed skill clearly fits this request."
NONE_OPTION = "No listed skill fits this request."
KEY_LINE = re.compile(r"^([A-Za-z0-9_-]+):(?:[ \t]+(.*?))?[ \t]*$")
BLOCK_SCALAR = re.compile(r"^[|>][0-9+-]*$")
PASTE_MARKER = re.compile(r"(?m)^</?pasted_content id=\"[^\"]*\">[ \t]*$")


def clean(text, width=None):
    text = " ".join(str(text or "").split())
    if width and len(text) > width:
        text = text[: max(1, width - 1)].rstrip() + "…"
    return text


def _unit(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1


def _scalar(value, rest):
    if BLOCK_SCALAR.match(value):
        return " ".join(line.strip() for line in rest)
    joined = " ".join([value] + [line.strip() for line in rest])
    if value[:1] == '"':
        match = re.match(r'"((?:[^"\\]|\\.)*)"', joined)
        if not match:
            return joined.strip('"')
        try:
            return json.loads('"%s"' % match.group(1))
        except ValueError:
            return match.group(1)
    if value[:1] == "'":
        match = re.match(r"'((?:[^']|'')*)'", joined)
        return match.group(1).replace("''", "'") if match else joined.strip("'")
    return joined


def frontmatter(path, limit=16384):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as handle:
            lines = handle.read(limit).splitlines()
    except OSError:
        return {}, ""
    if not lines or lines[0].strip() != "---":
        return {}, "\n".join(lines[:20])
    end = next((i for i in range(1, len(lines)) if lines[i].rstrip() in ("---", "...")), None)
    if end is None:
        return {}, ""
    groups = []
    for line in lines[1:end]:
        match = KEY_LINE.match(line)
        if match:
            groups.append((match.group(1), match.group(2) or "", []))
        elif groups:
            groups[-1][2].append(line)
    fields = {}
    for key, value, rest in groups:
        filled = [line for line in rest if line.strip()]
        nested = [KEY_LINE.match(line.strip()) for line in filled]
        if not value and filled and all(nested) and all(line[:1] in " \t" for line in filled):
            fields[key] = {m.group(1): clean(_scalar(m.group(2) or "", [])) for m in nested}
        else:
            fields[key] = clean(_scalar(value, rest))
    return fields, "\n".join(lines[end + 1:end + 20])


def _text(fields, key):
    value = fields.get(key)
    return value if isinstance(value, str) else ""


def _note(path):
    fields, body = frontmatter(path)
    meta = fields.get("metadata") if isinstance(fields.get("metadata"), dict) else {}
    description = _text(fields, "description")
    if not description:
        description = next((line.strip("# \t") for line in body.splitlines() if line.strip("# \t")), "")
    return {
        "name": _text(fields, "name") or path.stem,
        "description": clean(description),
        "type": _text(fields, "type") or meta.get("type", ""),
    }


def _skill(path):
    fields, _ = frontmatter(path)
    return {
        "name": _text(fields, "name") or path.parent.name,
        "description": _text(fields, "description"),
        "invocable": _text(fields, "disable-model-invocation").lower() != "true",
    }


class _Cache:
    def __init__(self, path):
        self.path = path
        data = hookio.read_json(path, {})
        self.files = data.get("files", {}) if isinstance(data, dict) and data.get("version") == CACHE_VERSION else {}
        self.used = set()
        self.dirty = False

    def get(self, path, parse):
        key = str(path)
        try:
            stat = path.stat()
        except OSError:
            return None
        stamp = [stat.st_mtime_ns, stat.st_size]
        self.used.add(key)
        entry = self.files.get(key)
        if isinstance(entry, dict) and entry.get("stamp") == stamp:
            return entry["value"]
        value = parse(path)
        self.files[key] = {"stamp": stamp, "value": value}
        self.dirty = True
        return value

    def save(self):
        stale = set(self.files) - self.used
        if not (self.dirty or stale):
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            hookio.write_json(self.path, {"version": CACHE_VERSION, "files": {k: v for k, v in self.files.items() if k in self.used}})
        except OSError:
            pass


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def _enabled_plugins(root):
    enabled = {}
    for path in (claude_home() / "settings.json", root / ".claude" / "settings.json", root / ".claude" / "settings.local.json"):
        data = hookio.read_json(path, {})
        if isinstance(data, dict) and isinstance(data.get("enabledPlugins"), dict):
            enabled.update(data["enabledPlugins"])
    return enabled


def _skill_sources(root):
    home = claude_home()
    sources = [("", home / "skills"), ("", root / ".claude" / "skills")]
    installed = hookio.read_json(home / "plugins" / "installed_plugins.json", {})
    plugins = installed.get("plugins") if isinstance(installed, dict) else None
    enabled = _enabled_plugins(root)
    for key, entries in sorted((plugins or {}).items()):
        if enabled.get(key) is False or not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("installPath"):
                continue
            scoped = entry.get("projectPath")
            if entry.get("scope") in ("project", "local") and scoped and os.path.realpath(scoped) != str(root):
                continue
            sources.append((key.split("@")[0], Path(entry["installPath"]) / "skills"))
    return sources


def build(root, memory_dir):
    root = Path(root).resolve()
    real = Path(os.path.realpath(os.path.expanduser(str(memory_dir)))) if memory_dir else None
    digest = hashlib.sha1(("%s\0%s" % (root, real or "")).encode()).hexdigest()
    cache = _Cache(jev.STATE_DIR / ("catalog-%s.json" % digest))
    refused = bool(real) and policy.path_refused(real)
    notes, notes_refused = [], 0
    # The refusal is checked before listing the directory: nothing of a refused memory is read.
    if real and not refused and real.is_dir():
        for path in sorted(real.glob("*.md")):
            if path.name.lower() == "memory.md" or not path.is_file():
                continue
            if not policy.sendable(path, root, [real]):
                notes_refused += 1
                continue
            note = cache.get(path, _note)
            if note:
                notes.append(dict(note, file=path.name, path=str(path)))
    skills, names, skills_refused = [], set(), 0
    for prefix, base in _skill_sources(root):
        for path in sorted(base.glob("*/SKILL.md")):
            if not path.is_file():
                continue
            if not policy.sendable(path, root, [os.path.dirname(os.path.realpath(path))]):
                skills_refused += 1
                continue
            skill = cache.get(path, _skill)
            # A name over the skill spec limit cannot be invoked; truncating it would name a skill that does not exist.
            if not skill or not skill["invocable"] or len(skill["name"]) > SKILL_NAME_MAX:
                continue
            name = re.sub(r"[^\w:.-]", "", "%s:%s" % (prefix, skill["name"]) if prefix else skill["name"])
            if name and name not in names:
                names.add(name)
                skills.append(dict(skill, name=name, path=str(path)))
    cache.save()
    return {
        "root": str(root),
        "memory_dir": str(real) if real and not refused and real.is_dir() else None,
        "memory_refused": refused,
        "notes": notes,
        "notes_refused": notes_refused,
        "skills": skills,
        "skills_refused": skills_refused,
    }


def root_of(cwd):
    # Not project.project_root: CLAUDE_PROJECT_DIR stays where the session started, the payload cwd follows cd and worktrees.
    here = Path(cwd).resolve()
    return next((c for c in (here, *here.parents) if any((c / m).exists() for m in project.ROOT_MARKERS)), here)


def hook_client(settings, tool, started):
    left = JEV_BUDGET_S - (time.monotonic() - started)
    return jev.Client(settings, tool, timeout=min(settings["jev"]["hook_timeout_s"], max(0.2, left)), retries=0)


def transcripts_dir(root):
    base = claude_home() / "projects"
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(Path(root).resolve()))
    if (base / slug).is_dir():
        return base / slug
    try:
        return next((entry for entry in base.iterdir() if entry.name.lower() == slug.lower()), None)
    except OSError:
        return None


def default_memory(root):
    directory = transcripts_dir(root)
    return directory / "memory" if directory and (directory / "memory").is_dir() else None


def git_branch(root):
    git = Path(root) / ".git"
    try:
        if git.is_file():
            git = (Path(root) / re.search(r"gitdir:\s*(.+)", git.read_text()).group(1).strip()).resolve()
        head = (git / "HEAD").read_text().strip()
    except (OSError, AttributeError):
        return ""
    return head[len("ref: refs/heads/"):] if head.startswith("ref: refs/heads/") else ""


def eligible(prompt):
    text = (prompt or "").strip()
    if len(text) < 8:
        return False
    first = text.split(None, 1)[0]
    # A slash command is skipped; an absolute path at the start of a prompt is not one.
    return not (first.startswith("/") and "/" not in first[1:])


def _cut(text, gap):
    return text if len(text) <= REQUEST_CHARS else text[:HEAD_CHARS] + gap + text[-TAIL_CHARS:]


def ticket_notes(prompt, branch, cat, settings):
    if not cat["notes"] or not settings["router"].get("memory", True):
        return []
    # Branch first, then only what Jev would see of the prompt: a pasted log must not cost seconds.
    keys = [key for key in memory.ticket_keys("%s\n%s" % (branch or "", _cut(prompt, "\n")), settings.get("ticket_regex")) if key]
    if not keys:
        return []
    rank = {}
    for r, key in enumerate(keys):
        rank.setdefault(_key_form(key), r)
    # memory._key_regex's form in a single pattern: one compile and one pass over the catalog, whatever the number of keys.
    bodies = ("[-_]".join(re.escape(part) for part in re.split(r"[-_]", key.lower())) for key in keys)
    combined = re.compile(r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % "|".join(bodies), re.IGNORECASE)
    best = []
    for i, note in enumerate(cat["notes"]):
        # As memory.find, over the notes the policy let into the catalog: file name first, then name and description.
        fields = (note["file"][:-3], "%s\n%s" % (note["name"], note["description"]))
        hits = [(rank[_key_form(m)], f) for f, text in enumerate(fields) for m in combined.findall(text) if _key_form(m) in rank]
        if hits:
            best.append(min(hits) + (i,))
    return [(i, keys[r]) for r, _, i in sorted(best)[:TICKET_NOTES]]


def _key_form(text):
    return re.sub(r"[-_]", "-", text.upper())


def note_index(cat):
    return bm25.BM25(["%s %s %s" % (n["file"][:-3], n["name"], n["description"]) for n in cat["notes"]])


def skill_index(cat):
    return bm25.BM25(["%s %s" % (s["name"], s["description"]) for s in cat["skills"]])


def _sendable_text(text):
    # A lone surrogate (truncated emoji in the hook JSON) cannot be encoded to UTF-8 for the request body.
    return policy.redact(str(text or "").encode("utf-8", "replace").decode("utf-8"))


def _request_text(prompt):
    # Redact before cutting: a cut inside a token would drop its prefix and let the rest through unrecognised.
    text = _cut(PASTE_MARKER.sub("", _sendable_text(prompt)).strip(), " […] ")
    return policy.redact(text)


def _candidate(item):
    return _sendable_text("%s — %s" % (item["name"], clean(_sendable_text(item["description"]), DESC_WIDTH)))


def _fits(state, questions):
    longest = max(jev.estimate_tokens(q) for q in questions.values())
    return jev.estimate_tokens(state) + longest <= jev.STATE_TOKEN_BUDGET


def requests(prompt, branch, cat, settings, skip_notes=()):
    router = settings["router"]
    base = {"request": _request_text(prompt), "branch": _sendable_text(branch)}
    notes = {}
    if router.get("memory", True):
        for i, note in enumerate(cat["notes"]):
            if i not in skip_notes:
                notes["n%d" % i] = _candidate(note)
    skills = {}
    if router.get("skills", True) and cat["skills"]:
        order = list(range(len(cat["skills"])))
        if len(order) > MAX_SKILLS:
            ranked = skill_index(cat).scores(prompt)
            order = sorted(sorted(order, key=lambda i: -ranked[i])[:MAX_SKILLS])
        for i in order:
            skills["s%d" % i] = _candidate(cat["skills"][i])
    note_questions = {key: jev.noul({"question": NOTE_QUESTION % key, "focus": NOTE_FOCUS}) for key in notes}
    skill_question = jev.choice({"question": SKILL_QUESTION, "focus": SKILL_FOCUS}, dict(skills, none=NONE_OPTION)) if skills else None
    questions = dict(note_questions)
    if skill_question:
        questions["skill"] = skill_question
    if not questions:
        return []
    whole = dict(base, notes=notes, skills=skills)
    if len(notes) <= CHUNK_NOTES and _fits(whole, questions):
        return [(whole, questions)]
    jobs = [(dict(base, skills=skills), {"skill": skill_question})] if skill_question else []
    keys, size = list(notes), CHUNK_NOTES
    while keys:
        chunk = keys[:size]
        state, chunk_questions = dict(base, notes={k: notes[k] for k in chunk}), {k: note_questions[k] for k in chunk}
        if size > 1 and not _fits(state, chunk_questions):
            size = max(1, size // 2)
            continue
        jobs.append((state, chunk_questions))
        keys = keys[size:]
    return jobs


def judge(client, jobs, workers=8):
    # Any failure, not only JevError, becomes that request's result: the caller decides, nothing escapes.
    def one(job):
        try:
            return client.ask(*job)
        except hookio.Deadline:
            raise
        except Exception as error:
            return error
    if len(jobs) == 1:
        return [one(jobs[0])]
    pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(jobs))))
    try:
        return list(pool.map(one, jobs))
    finally:
        # Never wait for a request still in flight: on a deadline the hook must exit now.
        pool.shutdown(wait=False, cancel_futures=True)


def _skill_answer(answer, options):
    if not isinstance(answer, dict):
        return None
    choice, probabilities, confidence = answer.get("choice"), answer.get("probabilities"), answer.get("confidence")
    if choice not in options or not isinstance(probabilities, dict) or not _unit(probabilities.get(choice)) or not _unit(confidence):
        return None
    return {
        "choice": choice,
        "p": float(probabilities[choice]),
        "confidence": float(confidence),
        "probabilities": {k: float(v) for k, v in probabilities.items() if k in options and _unit(v)},
    }


def interpret(jobs, results):
    note_p, skill, errors, asked = {}, None, [], 0
    for (_, questions), answers in zip(jobs, results):
        asked += sum(1 for key in questions if key != "skill")
        if isinstance(answers, Exception):
            errors.append(getattr(answers, "status", 0) or type(answers).__name__)
            continue
        if not isinstance(answers, dict):
            errors.append("invalid")
            continue
        for key, question in questions.items():
            answer = answers.get(key)
            if key == "skill":
                skill = _skill_answer(answer, question["criteria"])
            elif isinstance(answer, dict) and answer.get("type", "noul") == "noul" and _unit(jev.probability(answer)):
                note_p[int(key[1:])] = float(jev.probability(answer))
    # Partial note answers: the abstention rule and the top picks would rest on part of the catalog, so abstain.
    if len(note_p) < asked:
        if not errors:
            errors.append("missing")
        note_p = {}
    return note_p, skill, errors


def abstains(settings, note_p):
    router = settings["router"]
    threshold, limit = float(router.get("memory_threshold", 0.8)), int(router.get("max_notes", 3))
    # An answer that flags a large share of the catalog does not discriminate: abstain rather than pick arbitrarily.
    return sum(1 for p in note_p.values() if p >= threshold) > max(2 * limit, len(note_p) / 2)


def select(settings, cat, note_p, skill, tickets, seen):
    router = settings["router"]
    seen_notes, seen_skills = set(seen.get("notes") or []), set(seen.get("skills") or [])
    chosen = [(i, "ticket") for i, _ in tickets if cat["notes"][i]["file"] not in seen_notes]
    picked = {i for i, _ in chosen}
    threshold, limit, count = float(router.get("memory_threshold", 0.8)), int(router.get("max_notes", 3)), 0
    passing = sorted(((p, i) for i, p in note_p.items() if p >= threshold), key=lambda item: (-item[0], item[1]))
    if abstains(settings, note_p):
        passing = []
    for p, i in passing:
        if count >= limit:
            break
        if i not in picked and cat["notes"][i]["file"] not in seen_notes:
            chosen.append((i, p))
            picked.add(i)
            count += 1
    pick = None
    if (skill and skill["choice"] != "none" and skill["p"] >= SKILL_MIN_P
            and skill["confidence"] >= float(router.get("skill_confidence", 0.8))):
        index = int(skill["choice"][1:])
        if cat["skills"][index]["name"] not in seen_skills:
            pick = (index, skill["p"])
    return chosen, pick


def _shares(lengths, available):
    if sum(lengths) <= available:
        return lengths
    limits, remaining = [0] * len(lengths), available
    order = sorted(range(len(lengths)), key=lambda i: lengths[i])
    for rank, i in enumerate(order):
        limits[i] = max(0, min(lengths[i], remaining // (len(order) - rank)))
        remaining -= limits[i]
    return limits


def render(cat, chosen, pick):
    # Returns what is actually shown: only that may be remembered as seen or logged as kept.
    notes = []
    for entry in chosen:
        note = cat["notes"][entry[0]]
        label = "ticket" if entry[1] == "ticket" else "p=%.2f" % entry[1]
        # Redacted before any cut, as for Jev: the output lands in the transcript.
        notes.append((entry, "- memory/%s" % policy.redact(clean(note["file"])),
                      clean(policy.redact(note["description"]), LINE_DESC_WIDTH), " (%s)" % label))
    skill_line = "- skill `%s` (p=%.2f)" % (policy.redact(clean(cat["skills"][pick[0]]["name"])), pick[1]) if pick else None
    while notes or skill_line:
        extra = [skill_line] if skill_line else []
        fixed = len(HEADER) + len(FOOTER) + sum(len(p) + len(t) + 4 for _, p, _, t in notes) + sum(len(e) + 1 for e in extra) + 1
        limits = _shares([len(d) for _, _, d, _ in notes], OUTPUT_CHARS - fixed)
        lines = [HEADER]
        for (_, prefix, description, tail), limit in zip(notes, limits):
            text = clean(description, limit) if limit >= 12 else ""
            lines.append(prefix + (" — " + text if text else "") + tail)
        text = "\n".join(lines + extra + [FOOTER])
        if len(text) <= OUTPUT_CHARS:
            return text, [entry for entry, _, _, _ in notes], pick if skill_line else None
        # The skill goes first, then Jev notes from the lowest p; ticket notes (listed first) go last.
        if skill_line:
            skill_line = None
        else:
            notes.pop()
    return "", [], None


def remember(state_path, seen, cat, chosen, pick):
    notes = set(seen.get("notes") or []) | {cat["notes"][i]["file"] for i, _ in chosen}
    skills = set(seen.get("skills") or []) | ({cat["skills"][pick[0]]["name"]} if pick else set())
    try:
        hookio.write_json(state_path, {"notes": sorted(notes), "skills": sorted(skills)})
    except OSError:
        pass


def log(record):
    jev._log("router.jsonl", dict(record, ts=round(time.time(), 3)))
