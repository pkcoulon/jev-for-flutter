import json
import re
from pathlib import Path

from . import jev, outline, paths, policy

VERSION = 1
PER_REQUEST = 40
CONTEXT_RADII = (12, 5, 0)
FOLD_LINES = 40
OVERLAP_LINES = 3
MAX_STATES = 6
MAX_ENCLOSING = 8
NEW = -1
DEFAULT_THRESHOLD = 0.85
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
YES_NO_RE = re.compile(r"^(does|do|did|is|are|was|were|has|have|can|could|should|would|will)\b", re.I)
CODE_RE = re.compile(r"`[^`]*`|\"[^\"]*\"|(?<![A-Za-z])'[^']*'")
ACCENTS = re.compile(r"[àâçéèêëîïôûùüÿœæ]", re.I)
FRENCH = frozenset(
    "le la les des du est une dans pour avec sur qui que pas ne ce cette ces au aux et ou il elle sont "
    "fichier modification utilise ajoute plutôt sans".split()
)
ENGLISH = frozenset(
    "the a an does do is are this that any of to in change changes introduce introduces use uses using "
    "with without instead or it its add adds".split()
)
LINT_HINTS = re.compile(
    r"trailing comma|single quotes?|double quotes?|const constructor|prefer[_ ]const|unused (?:import|variable|parameter)"
    r"|import order|sort(?:ed)? imports|line length|longer than \d+|avoid_print|\bprint\(|type annotation"
    r"|camel ?case|snake ?case|lower ?case|upper ?case|naming convention|missing return type|dynamic type"
    r"|\bprint\b|relative imports?|\bunawaited\b|\bawait(?:s|ed|ing)?\b|\blate\b",
    re.I,
)
REFERENCE = (("after_context", "`after_context` is surrounding code"),
             ("enclosing", "`enclosing` lists the declarations containing the change"))


class RulesError(Exception):
    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def path(root, config):
    return Path(root) / config["guard"]["rules_file"]


def read(file, strict=False):
    try:
        data = json.loads(Path(file).read_text())
    except OSError as error:
        raise RulesError(["lecture impossible : %s" % (error.strerror or error)])
    except ValueError as error:
        raise RulesError(["JSON invalide : %s" % error])
    errors, _ = validate(data, strict)
    if errors:
        raise RulesError(errors)
    return data


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def looks_english(text):
    prose = CODE_RE.sub(" ", text)
    if ACCENTS.search(prose):
        return False
    words = re.findall(r"[a-z]+", prose.lower())
    english = sum(w in ENGLISH for w in words)
    return english > 0 and english >= sum(w in FRENCH for w in words)


def _globs(value, where, errors):
    if not isinstance(value, list) or not value or not all(isinstance(g, str) for g in value):
        errors.append("%s : applies_to doit être une liste non vide de globs" % where)
        return
    for glob in value:
        if not glob.strip() or glob.startswith(("/", "~", "./")) or "\\" in glob or ".." in glob.split("/"):
            errors.append("%s : glob invalide « %s » (relatif à la racine, séparateur /)" % (where, glob))


def _threshold(value, where, errors):
    if value is not None and (not _number(value) or not 0 < value < 1):
        errors.append("%s : threshold doit être un nombre entre 0 et 1" % where)


def _examples(value, where, errors, warnings):
    if not isinstance(value, list) or not value:
        errors.append("%s : examples absents (2 à 4, au moins une violation et un cas conforme)" % where)
        return
    labels = []
    for index, example in enumerate(value, 1):
        if not isinstance(example, dict) or not _text(example.get("after")) or not isinstance(example.get("violation"), bool):
            errors.append("%s : exemple %d invalide ({after, violation: true|false, context?})" % (where, index))
            continue
        if "context" in example and not isinstance(example["context"], str):
            errors.append("%s : exemple %d, context doit être une chaîne" % (where, index))
        labels.append(example["violation"])
    if labels and (True not in labels or False not in labels):
        warnings.append("%s : il faut au moins une violation et un cas conforme dans examples" % where)
    if not 2 <= len(value) <= 4:
        warnings.append("%s : %d exemple%s, 2 à 4 attendus" % (where, len(value), "s" if len(value) > 1 else ""))


def validate(data, strict=False):
    errors, warnings = [], []
    if not isinstance(data, dict):
        return ["la racine doit être un objet JSON"], warnings
    if data.get("version") != VERSION:
        errors.append("version doit valoir %d" % VERSION)
    defaults = data.get("defaults", {})
    if not isinstance(defaults, dict):
        errors.append("defaults doit être un objet")
        defaults = {}
    _threshold(defaults.get("threshold"), "defaults", errors)
    if "applies_to" in defaults:
        _globs(defaults["applies_to"], "defaults", errors)
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("rules doit être une liste non vide")
        return errors, warnings
    if len(rules) > 30:
        warnings.append("%d règles : 10 à 30 visées ; au-delà de %d, plusieurs requêtes par fichier" % (len(rules), PER_REQUEST))
    seen = set()
    for index, rule in enumerate(rules, 1):
        where = "règle %d" % index
        if not isinstance(rule, dict):
            errors.append("%s : objet attendu" % where)
            continue
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not ID_RE.match(rule_id):
            errors.append("%s : id invalide (minuscules, chiffres, - _ .)" % where)
        else:
            where = "[%s]" % rule_id
            if rule_id in seen:
                errors.append("%s : id en double" % where)
            seen.add(rule_id)
        question = rule.get("question")
        if not _text(question):
            errors.append("%s : question manquante" % where)
        elif strict:
            if not looks_english(question):
                errors.append("%s : question à formuler en anglais" % where)
            if not question.rstrip().endswith("?") or not YES_NO_RE.match(question.strip()):
                warnings.append("%s : question oui/non attendue (Does…? Is…?), OUI = violation" % where)
            if LINT_HINTS.search(question):
                warnings.append("%s : semble décidable par un lint ; à retirer si un lint la couvre" % where)
        for key in ("true", "false"):
            value = rule.get(key)
            if not (_text(value) or (isinstance(value, (dict, list)) and value)):
                errors.append("%s : critère « %s » manquant" % (where, key))
        message = rule.get("message")
        if not _text(message) or "\n" in message:
            errors.append("%s : message manquant ou sur plusieurs lignes" % where)
        elif strict and len(message) > 160:
            warnings.append("%s : message long (%d caractères), une ligne courte attendue" % (where, len(message)))
        if "applies_to" in rule:
            _globs(rule["applies_to"], where, errors)
        elif "applies_to" not in defaults:
            errors.append("%s : applies_to absent (ni dans la règle ni dans defaults)" % where)
        _threshold(rule.get("threshold"), where, errors)
        if strict:
            _examples(rule.get("examples"), where, errors, warnings)
    return errors, warnings


def patterns(rule, ruleset):
    return rule.get("applies_to") or (ruleset.get("defaults") or {}).get("applies_to") or []


def select(ruleset, rel_path):
    return [rule for rule in ruleset["rules"] if paths.matches(rel_path, patterns(rule, ruleset))]


def threshold(rule, ruleset, config):
    for value in (rule.get("threshold"), (ruleset.get("defaults") or {}).get("threshold"), config["guard"].get("threshold")):
        if _number(value):
            return float(value)
    return DEFAULT_THRESHOLD


def question(rule, state=None):
    # Names only the reference fields the state carries; without a state, all of them (longest variant).
    shown = [note for key, note in REFERENCE if state is None or state.get(key)]
    instructions = {"question": rule["question"], "inspect": "`change`"}
    if shown:
        instructions["context"] = "%s, for reference only; judge only what the change introduces" % " and ".join(shown)
    return jev.noul(_redacted(instructions), _redacted(rule["true"]), _redacted(rule["false"]))


def _start(value):
    return max(0, value - 1) if isinstance(value, int) and not isinstance(value, bool) else 0


def patch_runs(patch):
    # Changed runs of a structuredPatch: the 0-based line where each starts after the edit, its lines before and after.
    runs = []
    for hunk in patch if isinstance(patch, list) else []:
        if not isinstance(hunk, dict) or not isinstance(hunk.get("lines"), list):
            continue
        at, run = _start(hunk.get("newStart")), None
        for line in hunk["lines"] + [" "]:
            kind = line[:1] if isinstance(line, str) else " "
            if kind == "\\":
                continue
            if kind in ("-", "+"):
                run = run or {"at": at, "before": [], "after": []}
                run["before" if kind == "-" else "after"].append(line[1:])
                at += kind == "+"
                continue
            if run:
                runs.append(run)
                run = None
            at += 1
    return runs


def _common(before, after):
    head = 0
    while head < min(len(before), len(after)) and before[head] == after[head]:
        head += 1
    tail = 0
    while tail < min(len(before), len(after)) - head and before[-1 - tail] == after[-1 - tail]:
        tail += 1
    return head, tail


def replaced_run(text, index, old, new):
    # The lines that differ around `new`, found at `index` in the text after an edit that put it in place of `old`.
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index + len(new))
    end = len(text) if end < 0 else end
    prefix, suffix = text[start:index], text[index + len(new):end]
    before, after = (prefix + old + suffix).split("\n"), (prefix + new + suffix).split("\n")
    head, tail = _common(before, after)
    return {"at": text.count("\n", 0, start) + head, "before": before[head:len(before) - tail],
            "after": after[head:len(after) - tail]}


def _undo(lines, step):
    # The lines before `step` given the lines just after it, with its runs (`old`: where each started before);
    # None when the lines are not exactly what the step wrote.
    if "edit" in step:
        old, new = step["edit"]
        text = "\n".join(lines)
        if not new or text.count(new) != 1:
            return None
        runs = [replaced_run(text, text.index(new), old, new)]
    else:
        runs = step.get("runs")
        if not runs:
            return None
    placed, shift = [], 0
    for run in sorted(runs, key=lambda r: r["at"]):
        placed.append(dict(run, old=run["at"] - shift))
        shift += len(run["after"]) - len(run["before"])
    out = list(lines)
    for run in reversed(placed):
        at, after = run["at"], run["after"]
        if at > len(out) or out[at:at + len(after)] != after:
            return None
        out[at:at + len(after)] = run["before"]
    return out, placed


def _trimmed(before, after, at):
    head, tail = _common(before, after)
    after = after[head:len(after) - tail]
    first, last = 0, len(after)
    while first < last and not after[first].strip():
        first += 1
    while last > first and not after[last - 1].strip():
        last -= 1
    if first == last:
        return None
    return {"before": "\n".join(before[head:len(before) - tail]), "after": "\n".join(after[first:last]),
            "span": [at + head + first, last - first]}


def net_changes(text, steps):
    # What a batch of steps (oldest first) changed in the file: runs of the current text, each with the lines it
    # replaced before the batch. Also returns how many of the oldest steps could not be traced through the text.
    current = text.split("\n")
    lines, replay, lost = current, [], 0
    for index in range(len(steps) - 1, -1, -1):
        if steps[index].get("create"):
            replay.append([{"old": 0, "before": [], "after": lines}])
            lines = []
            break
        undone = _undo(lines, steps[index])
        if undone is None:
            lost = index + 1
            break
        lines, runs = undone
        replay.append(runs)
    # Replays the traced steps on line numbers: an untouched line keeps its number, a written one becomes NEW.
    marks = list(range(len(lines)))
    for runs in reversed(replay):
        for run in sorted(runs, key=lambda r: -r["old"]):
            marks[run["old"]:run["old"] + len(run["before"])] = [NEW] * len(run["after"])
    if len(marks) != len(current):
        return [], len(steps)
    changes, previous, i = [], -1, 0
    while i < len(marks):
        if marks[i] != NEW:
            previous, i = marks[i], i + 1
            continue
        j = i
        while j < len(marks) and marks[j] == NEW:
            j += 1
        change = _trimmed(lines[previous + 1:marks[j] if j < len(marks) else len(lines)], current[i:j], i)
        if change:
            changes.append(change)
        i = j
    return changes, lost


def windows(text, spans, radius):
    if radius <= 0 or not spans:
        return []
    lines = text.split("\n")
    ranges = sorted([max(0, s - radius), min(len(lines) - 1, s + max(n, 1) - 1 + radius), [(s, s + max(n, 1) - 1)]]
                    for s, n in spans)
    merged = []
    for span in ranges:
        if merged and span[0] <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], span[1])
            merged[-1][2].extend(span[2])
        else:
            merged.append(span)
    out = []
    for first, last, blocks in merged:
        folded = [(s, e) for s, e in blocks if e - s + 1 > FOLD_LINES]
        code = []
        number = first
        while number <= last:
            fold = next(((s, e) for s, e in folded if s <= number <= e), None)
            if fold:
                code.append("// … lines %d-%d: see `change` …" % (fold[0] + 1, fold[1] + 1))
                number = fold[1] + 1
            else:
                code.append(lines[number])
                number += 1
        out.append({"lines": "%d-%d" % (first + 1, last + 1), "code": "\n".join(code)})
    return out


def enclosing(text, spans):
    try:
        decls = outline.regex_outline(text)["decls"]
    except Exception:
        return []
    found = []
    for start, _ in spans:
        line = start + 1
        decl = next((d for d in decls if d["start"] <= line <= d["end"]), None)
        chain = [decl] + [c for c in decl.get("children") or [] if c["start"] <= line <= c["end"]][:1] if decl else []
        for node in chain:
            entry = {"lines": "%d-%d" % (node["start"], node["end"]), "signature": node.get("signature") or node.get("name") or ""}
            if entry not in found:
                found.append(entry)
    return found[:MAX_ENCLOSING]


def _redacted(value):
    if isinstance(value, str):
        return policy.redact(value)
    if isinstance(value, list):
        return [_redacted(v) for v in value]
    if isinstance(value, dict):
        return {k: _redacted(v) for k, v in value.items()}
    return value


def _clip(value, limit):
    return value if len(value) <= limit else value[:limit] + "\n// …[truncated]"


def _lines(start, count):
    return "%d-%d" % (start + 1, start + max(count, 1))


def build_states(rel, changes, text, reserve=0):
    # States covering every change (each with its span, when known), and the number of changed lines left unjudged.
    budget = jev.STATE_TOKEN_BUDGET - reserve
    items, starts, spans = [], [], []
    for c in changes:
        span = c.get("span")
        # Redact before any split so a secret cut in half cannot slip past the patterns.
        item = _redacted(dict({"lines": _lines(*span)} if span else {}, before=c.get("before") or "", after=c["after"]))
        if item not in items:
            items.append(item)
            starts.append(span[0] if span else None)
            spans.extend([span] if span else [])
    found = enclosing(text, spans) if spans and text else []
    extra = {"enclosing": _redacted(found)} if found else {}
    for radius in CONTEXT_RADII:
        around = windows(text, spans, radius) if text else []
        state = dict({"file": rel, "change": items, "after_context": _redacted(around)}, **extra)
        if jev.estimate_tokens(state) <= budget:
            return [state], 0
    return _split(rel, items, starts, extra, budget)


def _size(value):
    return len(json.dumps(value, ensure_ascii=False))


def _split(rel, items, starts, extra, budget):
    room = int((budget - jev.estimate_tokens(dict({"file": rel, "change": [], "after_context": []}, **extra)))
               * jev.CHARS_PER_TOKEN) - 64
    pieces, clipped, total = [], set(), 0
    for index, (item, start) in enumerate(zip(items, starts)):
        before = _clip(item["before"], room // 4)
        lines = item["after"].split("\n")
        total += len(lines)
        first = 0
        while first < len(lines):
            size, end = _size(before) + 48, first
            while end < len(lines) and size + _size(lines[end]) <= room:
                size += _size(lines[end])
                end += 1
            if end == first:
                lines[first] = _clip(lines[first], room // 2)
                clipped.add((index, first))
                end = first + 1
            piece = {"before": before, "after": "\n".join(lines[first:end])}
            if start is not None:
                piece = dict({"lines": _lines(start + first, end - first)}, **piece)
            pieces.append((piece, {(index, n) for n in range(first, end)}))
            if end >= len(lines):
                break
            first, before = max(first + 1, end - OVERLAP_LINES), ""
    states = []
    for piece, covered in pieces:
        if states and jev.estimate_tokens(dict(states[-1][0], change=states[-1][0]["change"] + [piece])) <= budget:
            states[-1][0]["change"].append(piece)
            states[-1][1].update(covered)
        else:
            states.append((dict({"file": rel, "change": [piece], "after_context": []}, **extra), set(covered)))
    if len(states) > MAX_STATES:
        # Head and tail: the end of a large write matters as much as its start.
        states = states[:MAX_STATES - 1] + states[-1:]
    judged = set().union(*(covered for _, covered in states))
    return [state for state, _ in states], total - len(judged) + len(clipped & judged)


def ask(client, states, selected):
    # Every state is asked every rule; a rule keeps its highest probability over the states.
    groups = [selected[i:i + PER_REQUEST] for i in range(0, len(selected), PER_REQUEST)]
    jobs = [(state, {rule["id"]: question(rule, state) for rule in group}) for state in states for group in groups]
    if not jobs:
        return {}, 0, 0
    results = client.ask_many(jobs, workers=min(8, len(jobs)))
    failures = [r for r in results if isinstance(r, Exception)]
    if len(failures) == len(results):
        raise failures[0]
    answers = {}
    for result in results:
        for key, answer in (result.items() if isinstance(result, dict) else ()):
            p = jev.probability(answer)
            if _number(p) and (key not in answers or p > jev.probability(answers[key])):
                answers[key] = answer
    return answers, len(failures), len(jobs)


def scored(answers, selected, ruleset, config):
    out = []
    for rule in selected:
        p = jev.probability(answers.get(rule["id"]))
        if _number(p):
            out.append((rule, float(p), threshold(rule, ruleset, config)))
    return out


def longest_question(selected):
    return max((jev.estimate_tokens(question(rule)) for rule in selected), default=0)


def example_path(rule, ruleset):
    for glob in patterns(rule, ruleset):
        candidate = glob.replace("**/", "").replace("**", "example").replace("*", "example").replace("?", "x")
        if candidate:
            return candidate
    return "lib/example.dart"
