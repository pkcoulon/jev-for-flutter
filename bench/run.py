#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

BENCH = Path(os.path.dirname(os.path.realpath(__file__)))
REPO = BENCH.parent
PLUGIN = REPO / "plugins" / "dartlens"
LIB = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "plugins", "dartlens", "lib")

ARMS = {
    "control": {"plugin": False, "env": {}},
    "lens": {"plugin": True, "env": {"DARTLENS_GUARD_DISABLE": "1", "DARTLENS_ROUTER_DISABLE": "1"}},
    "guard": {"plugin": True, "env": {"DARTLENS_LENS_DISABLE": "1", "DARTLENS_ROUTER_DISABLE": "1"}},
    "router": {"plugin": True, "env": {"DARTLENS_LENS_DISABLE": "1", "DARTLENS_GUARD_DISABLE": "1"}},
    "all": {"plugin": True, "env": {}},
    "all_nojev": {"plugin": True, "env": {"DARTLENS_JEV_DISABLE": "1"}},
    "all_refuse": {"plugin": True, "env": {"DARTLENS_LENS_NUDGE": "refuse_once"}},
}
DEFAULT_ARMS = ("control", "lens", "guard", "router", "all")
TYPES = ("localisation", "correction_multi_fichiers", "ui_i18n", "diagnostic", "convention", "memoire")
RUN_KINDS = ("command", "grep")
SCORE_KINDS = ("answer", "touched", "untouched", "diff_added", "no_diff")
ALLOWED_TOOLS = (
    "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep", "Skill", "TodoWrite",
    "Bash(flutter:*)", "Bash(fvm:*)", "Bash(dart:*)", "Bash(lens:*)", "Bash(dart-outline:*)",
    "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)", "Bash(git grep:*)",
    "Bash(rg:*)", "Bash(grep:*)", "Bash(find:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)",
    "Bash(tail:*)", "Bash(sed -n:*)", "Bash(wc:*)",
    "mcp__plugin_dartlens_dartlens__find_code",
)
# Inherited values that would leak the operator's session into the trial.
STRIPPED_ENV = ("CLAUDE_PROJECT_DIR", "CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT")
PLUGIN_EXCLUDES = ("/.claude/dartlens.json", "/.claude/dartlens/")
RULES_FILE = ".claude/dartlens/rules.json"
SHA = re.compile(r"^[0-9a-f]{40}$")
TAIL = 4000
TAG_SLACK_S = 60
# Claude Code strips these assignments before matching a Bash rule; the gate does the same.
SAFE_ENV = frozenset(("NODE_ENV", "PYTHONUNBUFFERED", "PYTHONDONTWRITEBYTECODE", "LANG", "LANGUAGE", "LC_ALL",
                      "LC_CTYPE", "LC_TIME", "CHARSET", "TERM", "COLORTERM", "NO_COLOR", "FORCE_COLOR", "TZ",
                      "COLUMNS", "LINES", "CI", "GIT_TERMINAL_PROMPT"))
SHELLS = ("sh", "bash", "zsh", "dash")
PUNCTUATION = ";&|<>\n"
QUOTA = re.compile(r"usage limit|hit your (?:usage )?limit|(?:5-hour|weekly|daily|session) limit|credit balance is too low"
                   r"|out of (?:extra )?usage", re.I)
AUTH = re.compile(r"invalid api key|please run /login|not logged in|authentication_error|authentication failed"
                  r"|oauth token (?:has )?expired|api error: 401|\bunauthorized\b", re.I)
TRANSIENT = re.compile(r"overloaded|api error|rate.?limit|\b529\b|\b429\b|internal server error|service unavailable"
                       r"|bad gateway|econnreset|etimedout|socket hang up|network error|connection error"
                       r"|request timed out|fetch failed", re.I)


# ---------------------------------------------------------------- gate
# PreToolUse hook given to every arm: what runs after `lens … --` must pass the same list as a plain Bash call.


def gate_rules():
    try:
        listed = json.loads(os.environ.get("DARTLENS_BENCH_ALLOWED") or "[]")
    except ValueError:
        listed = []
    found = []
    for rule in listed if isinstance(listed, list) else []:
        match = re.fullmatch(r"Bash\((.+?)(:\*)?\)", rule) if isinstance(rule, str) else None
        if match:
            found.append((match.group(1).strip(), bool(match.group(2))))
    return found


def split_commands(text, strict):
    lexer = shlex.shlex(text, posix=True, punctuation_chars=PUNCTUATION)
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    tokens = list(lexer)
    commands, current, index = [], [], 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not all(c in PUNCTUATION for c in token):
            current.append(token)
            continue
        if "<" not in token and ">" not in token:
            if current:
                commands.append(current)
            current = []
            continue
        target = tokens[index] if index < len(tokens) else ""
        index += 1
        if current and current[-1].isdigit():
            current.pop()
        if strict and (token.startswith("<<") or (">" in token and target != "/dev/null" and not target.isdigit())):
            raise ValueError("redirection %s %s" % (token, target))
    if current:
        commands.append(current)
    return commands


def strip_env(argv):
    while argv and re.match(r"^([A-Za-z_]\w*)=", argv[0]) and argv[0].split("=", 1)[0] in SAFE_ENV:
        argv = argv[1:]
    return argv


def gate_allows(argv, rules_):
    argv = strip_env(argv)
    if not argv:
        return True, None
    head = os.path.basename(argv[0])
    if head == "lens":
        return (True, None) if "--" not in argv else gate_allows(argv[argv.index("--") + 1:], rules_)
    if head in SHELLS and "-c" in argv[1:]:
        script = argv[argv.index("-c") + 1] if argv.index("-c") + 1 < len(argv) else ""
        if not script or "$(" in script or "`" in script:
            return False, "%s -c %s" % (head, script or "(vide)")
        try:
            commands = split_commands(script, True)
        except ValueError as error:
            return False, str(error)
        for command in commands:
            ok, bad = gate_allows(command, rules_)
            if not ok:
                return False, bad
        return True, None
    text = " ".join(argv)
    if any(text == prefix or (wildcard and text.startswith(prefix + " ")) for prefix, wildcard in rules_):
        return True, None
    return False, text


def gate():
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        command = (payload.get("tool_input") or {}).get("command")
    except (ValueError, AttributeError):
        return 0
    if payload.get("tool_name") != "Bash" or not isinstance(command, str) or "lens" not in command:
        return 0
    try:
        listed = gate_rules()
        verdicts = [gate_allows(c, listed) for c in split_commands(command, False)
                    if strip_env(c) and os.path.basename(strip_env(c)[0]) == "lens"]
        bad = next((b for ok, b in verdicts if not ok), None)
    except ValueError:
        bad = "commande illisible"
    if bad:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": "Hors de la liste de commandes du banc, la même pour tous les bras : %s" % bad[:200]}}))
    return 0


# The gate runs before every Bash call of every arm: answer before loading the plugin library.
if __name__ == "__main__" and sys.argv[1:] == ["--gate"]:
    sys.exit(gate())

sys.path.insert(0, LIB)
from dartlens import paths, policy, project, rules  # noqa: E402


def config_dir():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def session_dir(worktree):
    return config_dir() / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(worktree))


def tail(text):
    text = text or ""
    return text[-TAIL:]


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def entries(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    yield entry
    except OSError:
        return


# ---------------------------------------------------------------- tasks


def validate(task, projects):
    problems = []
    for key, kind in (("id", str), ("project", str), ("type", str), ("commit", str), ("prompt_fr", str),
                      ("prompt_en", str), ("setup", dict), ("checks", list), ("review", list),
                      ("expected_files", list)):
        if not isinstance(task.get(key), kind):
            problems.append("champ %s absent ou mal typé" % key)
    if problems:
        return problems
    if not re.match(r"^[a-z0-9][a-z0-9-]*$", task["id"]):
        problems.append("id invalide")
    if task["project"] not in projects:
        problems.append("projet inconnu de _projects.json : %s" % task["project"])
    if task["type"] not in TYPES:
        problems.append("type inconnu : %s" % task["type"])
    if not SHA.match(task["commit"]):
        problems.append("commit : SHA complet attendu")
    if not task["prompt_fr"].strip() or not task["prompt_en"].strip():
        problems.append("prompt vide")
    setup = task["setup"]
    if setup.get("status") not in ("ready", "todo"):
        problems.append("setup.status : ready ou todo")
    if setup.get("history", "keep") not in ("keep", "orphan"):
        problems.append("setup.history : keep ou orphan")
    for key in ("patch", "reference"):
        value = setup.get(key)
        if value is not None and (not isinstance(value, str) or not value.startswith("diff --git ")):
            problems.append("setup.%s : diff git attendu" % key)
    if setup.get("reference_answer") is not None and not isinstance(setup["reference_answer"], str):
        problems.append("setup.reference_answer : texte attendu")
    memory = setup.get("memory")
    if memory is not None:
        if not isinstance(memory, dict) or "MEMORY.md" not in memory:
            problems.append("setup.memory : dictionnaire avec MEMORY.md")
        elif any(not isinstance(v, str) or "/" in k for k, v in memory.items()):
            problems.append("setup.memory : noms de fichiers simples et contenus texte")
    for key in ("prepare", "expect_before"):
        if not isinstance(setup.get(key, []), list):
            problems.append("setup.%s : liste attendue" % key)
    if not task["checks"] and setup.get("status") == "ready":
        problems.append("aucun critère exécutable")
    ids = set()
    for check in list(task["checks"]) + list(setup.get("expect_before", [])):
        problems += ["critère %s : %s" % (check.get("id", "?"), p) for p in validate_check(check)]
        if check.get("id") in ids:
            problems.append("critère en double : %s" % check.get("id"))
        ids.add(check.get("id"))
    if not all(isinstance(r, str) and r.strip() for r in task["review"]) or not task["review"]:
        problems.append("grille de revue vide")
    return problems


def validate_check(check):
    kind = check.get("kind")
    if not isinstance(check.get("id"), str):
        return ["id manquant"]
    if kind not in RUN_KINDS + SCORE_KINDS:
        return ["type inconnu %r" % kind]
    if check.get("role", "success") not in ("success", "regression"):
        return ["role : success ou regression"]
    problems = []
    if kind == "command":
        if not isinstance(check.get("cmd"), str):
            problems.append("cmd manquante")
        if check.get("expect_exit", 0) != "nonzero" and not isinstance(check.get("expect_exit", 0), int):
            problems.append("expect_exit : entier ou \"nonzero\"")
        if not isinstance(check.get("files", {}), dict) or not isinstance(check.get("env", {}), dict):
            problems.append("files et env : dictionnaires")
    if kind in ("grep", "touched", "untouched") and not check.get("paths"):
        problems.append("paths manquant")
    patterns = []
    if kind in ("grep", "diff_added"):
        patterns.append(check.get("regex"))
    if kind == "answer":
        patterns += list(check.get("all", [])) + list(check.get("any", [])) + list(check.get("none", []))
        if not patterns:
            problems.append("aucune expression")
    for pattern in patterns:
        try:
            re.compile(pattern)
        except (re.error, TypeError) as error:
            problems.append("regex invalide %r : %s" % (pattern, error))
    return problems


def validate_project(settings):
    if not isinstance(settings, dict) or not isinstance(settings.get("path"), str):
        return ["path manquant"]
    files = settings.get("plugin_files", {})
    if not isinstance(files, dict):
        return ["plugin_files : dictionnaire attendu"]
    if RULES_FILE not in files:
        return []
    # The guard reads this file as is: anything it would reject makes the guard arm silent.
    errors, _ = rules.validate(files[RULES_FILE], strict=True)
    return ["%s : %s" % (RULES_FILE, e) for e in errors]


def load_tasks(directory):
    projects_file = directory / "_projects.json"
    projects = json.loads(projects_file.read_text()) if projects_file.is_file() else {}
    tasks, problems = [], {}
    found = ["%s : %s" % (name, p) for name, settings in sorted(projects.items()) for p in validate_project(settings)]
    if found:
        problems["_projects.json"] = found
    for path in sorted(directory.glob("*.json")):
        if path.name.startswith("_"):
            continue
        try:
            task = json.loads(path.read_text())
        except ValueError as error:
            problems[path.name] = ["JSON invalide : %s" % error]
            continue
        found = validate(task, projects) if isinstance(task, dict) else ["objet JSON attendu"]
        if isinstance(task, dict) and task.get("id") and task["id"] + ".json" != path.name:
            found.append("le fichier doit s'appeler %s.json" % task["id"])
        if found:
            problems[path.name] = found
        else:
            tasks.append(task)
    return projects, tasks, problems


# ---------------------------------------------------------------- shell


class Shell:
    def __init__(self, dry):
        self.dry = dry

    def show(self, argv, cwd=None, env_extra=None):
        prefix = "".join("%s=%s " % (k, shlex.quote(v)) for k, v in sorted((env_extra or {}).items()))
        line = prefix + " ".join(shlex.quote(str(a)) for a in argv)
        print("    " + ("(cd %s && %s)" % (shlex.quote(str(cwd)), line) if cwd else line))

    def run(self, argv, cwd=None, check=True, env=None, timeout=None, stdin_text=None):
        argv = [str(a) for a in argv]
        if self.dry:
            self.show(argv, cwd)
            return subprocess.CompletedProcess(argv, 0, "", "")
        result = subprocess.run(argv, cwd=cwd, env=env, timeout=timeout, text=True, capture_output=True, input=stdin_text)
        if check and result.returncode:
            raise RuntimeError("%s : %s" % (" ".join(argv[:4]), tail(result.stderr or result.stdout).strip()))
        return result

    def write(self, path, text):
        if self.dry:
            print("    écrire %s (%d octets)" % (path, len(text.encode("utf-8"))))
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def git(sh, *args, cwd=None, check=True, stdin_text=None):
    return sh.run(["git", *args], cwd=cwd, check=check, stdin_text=stdin_text)


# ---------------------------------------------------------------- setup


def ensure_mirror(sh, home, name, source, commit):
    mirror = home / "mirrors" / (name + ".git")
    if sh.dry or not mirror.is_dir():
        git(sh, "init", "-q", "--bare", mirror)
        git(sh, "-C", mirror, "config", "gc.auto", "0")
    known = not sh.dry and git(sh, "-C", mirror, "cat-file", "-e", commit + "^{commit}", check=False).returncode == 0
    if not known:
        # Fetch by SHA only: the mirror must not expose Pierrick's other branches.
        git(sh, "-C", mirror, "fetch", "-q", "--no-tags", source, commit)
        git(sh, "-C", mirror, "update-ref", "refs/bench/pins/" + commit, commit)
    return mirror


def source_remotes(source):
    result = subprocess.run(["git", "-C", str(source), "config", "--get-regexp", r"^remote\..*\.url$"],
                            text=True, capture_output=True)
    found = []
    for line in result.stdout.splitlines():
        key, _, url = line.partition(" ")
        if key.count(".") >= 2 and url:
            found.append((key.split(".", 1)[1].rsplit(".", 1)[0], url))
    return found


def make_repo(sh, mirror, commit, repo, history, remotes):
    # A standalone repository per trial: no reference, pin or path shared with the mirror or other trials.
    git(sh, "init", "-q", "-b", "main", repo)
    if history == "orphan":
        if sh.dry:
            sh.show(["sh", "-c", "git -C %s archive %s | tar -x -C %s" % (mirror, commit, repo)])
        else:
            archive = subprocess.Popen(["git", "-C", str(mirror), "archive", commit], stdout=subprocess.PIPE)
            extract = subprocess.run(["tar", "-x", "-C", str(repo)], stdin=archive.stdout, capture_output=True, text=True)
            archive.stdout.close()
            if archive.wait() or extract.returncode:
                raise RuntimeError("extraction de %s : %s" % (commit[:10], extract.stderr.strip()))
            git(sh, "add", "-A", "-f", cwd=repo)
            tree = git(sh, "write-tree", cwd=repo).stdout.strip()
            if tree != git(sh, "-C", mirror, "rev-parse", commit + "^{tree}").stdout.strip():
                raise RuntimeError("extraction de %s incomplète (arbre différent)" % commit[:10])
    else:
        git(sh, "-C", repo, "fetch", "-q", "--no-tags", mirror, commit)
        git(sh, "-C", repo, "checkout", "-q", "-B", "main", commit)
        if not sh.dry:
            (repo / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
    # The source's remotes keep the policy's deny_remotes effective inside the copy.
    for name, url in remotes:
        git(sh, "-C", repo, "config", "remote.%s.url" % name, url)
    sh.write(repo / ".git" / "info" / "exclude", "\n".join(PLUGIN_EXCLUDES) + "\n")


def expand(text, worktree, base):
    flutter = project.flutter_executable(worktree) if "{flutter}" in text else None
    dart = project.dart_executable(worktree) if "{dart}" in text else None
    if "{flutter}" in text and not flutter:
        raise RuntimeError("SDK Flutter introuvable pour %s" % worktree)
    if "{dart}" in text and not dart:
        raise RuntimeError("dart introuvable pour %s" % worktree)
    return (text.replace("{flutter}", shlex.quote(flutter or "")).replace("{dart}", shlex.quote(dart or ""))
            .replace("{base}", base or "HEAD").replace("{worktree}", shlex.quote(str(worktree))))


def write_plugin_files(sh, repo, settings):
    for rel, content in settings.get("plugin_files", {}).items():
        text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2) + "\n"
        sh.write(repo / rel, text)


def setup_repo(sh, trial, repo, mirror, plugin):
    task, settings = trial["task"], trial["project"]
    setup = task["setup"]
    if plugin:
        write_plugin_files(sh, repo, settings)
    if setup.get("patch"):
        git(sh, "apply", "--whitespace=nowarn", "-", cwd=repo, stdin_text=setup["patch"])
    # Before the base commit: whatever pub get or gen-l10n rewrites must not count as the agent's change.
    for command in list(settings.get("prepare", [])) + list(setup.get("prepare", [])):
        if sh.dry:
            sh.show(["sh", "-c", command], repo)
            continue
        result = subprocess.run(expand(command, repo, None), shell=True, cwd=repo, text=True,
                                capture_output=True, timeout=1800)
        if result.returncode:
            raise RuntimeError("préparation « %s » : %s" % (command, tail(result.stderr or result.stdout).strip()))
    identity = git(sh, "-C", mirror, "log", "-1", "--format=%an%x00%ae%x00%aI", trial["commit"]).stdout.strip().split("\x00")
    name, email, date = identity if len(identity) == 3 else ("bench", "bench@localhost", "")
    commit_env = ["-c", "user.name=" + name, "-c", "user.email=" + email, "-c", "commit.gpgsign=false"]
    message = setup.get("message", "wip")
    if setup.get("history") == "orphan":
        git(sh, "add", "-A", cwd=repo)
        git(sh, *commit_env, "commit", "-q", "--no-verify", "-m", message, "--date", date or "now", cwd=repo)
    elif git(sh, "status", "--porcelain", cwd=repo).stdout.strip():
        git(sh, "add", "-A", cwd=repo)
        git(sh, *commit_env, "commit", "-q", "--no-verify", "-m", message, cwd=repo)
    base = git(sh, "rev-parse", "HEAD", cwd=repo).stdout.strip() or "<base>"
    if setup.get("memory"):
        memory = session_dir(repo) / "memory"
        if not sh.dry and memory.exists():
            raise RuntimeError("dossier mémoire déjà présent : %s" % memory)
        for name_, text in setup["memory"].items():
            sh.write(memory / name_, text)
    return base


# ---------------------------------------------------------------- checks


def run_checks(sh, checks, worktree, base, env):
    results = []
    for check in checks:
        if check["kind"] not in RUN_KINDS:
            continue
        if sh.dry:
            if check["kind"] == "command":
                for rel in check.get("files", {}):
                    print("    poser le fichier caché %s le temps du critère" % rel)
                sh.show(["sh", "-c", check["cmd"]], worktree, check.get("env"))
            else:
                print("    grep %s dans %s" % (check["regex"], ", ".join(check["paths"])))
            continue
        started = time.monotonic()
        if check["kind"] == "command":
            result = run_command_check(check, worktree, base, env)
        else:
            result = run_grep_check(check, worktree)
        result.update(id=check["id"], kind=check["kind"], role=check.get("role", "success"),
                      seconds=round(time.monotonic() - started, 1))
        results.append(result)
    return results


def run_command_check(check, worktree, base, env):
    # Hidden files live only for their own criterion: analyze and format judge the agent's tree alone.
    saved = {}
    for rel, text in check.get("files", {}).items():
        target = worktree / rel
        saved[target] = target.read_bytes() if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    expect = check.get("expect_exit", 0)
    try:
        command = expand(check["cmd"], worktree, base)
        result = subprocess.run(command, shell=True, cwd=worktree, env=dict(env, **check.get("env", {})), text=True,
                                capture_output=True, timeout=check.get("timeout_s", 1200))
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": None, "detail": "délai dépassé"}
    except RuntimeError as error:
        return {"ok": False, "exit": None, "detail": str(error)}
    finally:
        restore(saved, worktree)
    ok = result.returncode != 0 if expect == "nonzero" else result.returncode == expect
    return {"ok": ok, "exit": result.returncode, "expect": expect, "output": tail(result.stdout + result.stderr)}


def restore(saved, worktree):
    for target, content in saved.items():
        if content is not None:
            target.write_bytes(content)
            continue
        target.unlink(missing_ok=True)
        parent = target.parent
        while parent != worktree and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent


def run_grep_check(check, worktree):
    regex = re.compile(check["regex"], re.MULTILINE)
    excluded = check.get("exclude", [])
    count, hits = 0, {}
    for pattern in check["paths"]:
        for path in sorted(worktree.glob(pattern)):
            rel = path.relative_to(worktree).as_posix()
            if not path.is_file() or rel in hits or paths.matches(rel, excluded):
                continue
            found = len(regex.findall(path.read_text(errors="replace")))
            hits[rel] = found
            count += found
    expect = check.get("expect", True)
    low = check.get("min", 1 if expect else 0)
    high = check.get("max", None if expect else 0)
    ok = count >= low and (high is None or count <= high)
    return {"ok": ok, "count": count, "files": {k: v for k, v in hits.items() if v}, "min": low, "max": high}


# ---------------------------------------------------------------- trial


class InfraStop(RuntimeError):
    pass


def allowed_rules(args):
    return list(ALLOWED_TOOLS) + list(args.allow)


def gate_enabled(args):
    return args.permission_mode != "bypassPermissions"


def gate_settings():
    command = "%s %s --gate" % (shlex.quote(sys.executable), shlex.quote(str(BENCH / "run.py")))
    return json.dumps({"hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": command, "timeout": 10}]}]}})


def real_claude():
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        path = os.path.join(directory, "claude")
        if os.access(path, os.X_OK) and "cmux" not in os.path.realpath(path):
            return path
    return "claude"


def claude_argv(args, trial, session_id):
    argv = [args.claude, "-p", trial["prompt"], "--output-format", "stream-json", "--verbose",
            "--permission-mode", args.permission_mode, "--session-id", session_id]
    if not args.user_settings:
        argv += ["--setting-sources", "project,local"]
    if args.model:
        argv += ["--model", args.model]
    if ARMS[trial["arm"]]["plugin"]:
        argv += ["--plugin-dir", str(args.plugin_dir)]
    if args.max_turns:
        argv += ["--max-turns", str(args.max_turns)]
    if gate_enabled(args):
        argv += ["--allowedTools", ",".join(allowed_rules(args)), "--settings", gate_settings()]
    return argv + list(args.extra_arg)


def jev_expected(arm):
    return ARMS[arm]["plugin"] and "DARTLENS_JEV_DISABLE" not in ARMS[arm]["env"]


def trial_env(args, trial, tag, state_dir):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DARTLENS_") and k not in STRIPPED_ENV}
    extra = dict(ARMS[trial["arm"]]["env"], DARTLENS_BENCH_RUN=tag, DARTLENS_STATE_DIR=str(state_dir),
                 DARTLENS_BENCH_ALLOWED=json.dumps(allowed_rules(args)))
    if args.jev_url:
        extra["DARTLENS_JEV_URL"] = args.jev_url
    env.update(extra)
    return env, extra


def jev_backend(args):
    if args.jev_url:
        host = re.sub(r"^https?://", "", args.jev_url).split("/")[0].split(":")[0]
        return "fake" if host in ("127.0.0.1", "localhost", "::1") else "custom"
    return "official"


def plugin_python(code, env, cwd):
    result = subprocess.run([sys.executable, "-c", "import json, sys; sys.path.insert(0, %r)\n%s" % (LIB, code)],
                            env=env, cwd=cwd, text=True, capture_output=True, timeout=120)
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"error": tail(result.stderr).strip()[-300:] or "aucune sortie"}


def jev_preflight(repo, env):
    # The hooks run with this same environment and root: a refusal here means the arm would test nothing.
    found = plugin_python("from dartlens import config, policy\nprint(json.dumps(policy.jev_allowed(%r, config.load(%r))))"
                          % (str(repo), str(repo)), env, repo)
    if isinstance(found, list) and len(found) == 2:
        return bool(found[0]), found[1]
    return False, "vérification impossible : %s" % found.get("error")


def jev_ping(repo, env):
    code = ("from dartlens import config, jev\n"
            "client = jev.Client(config.load(%r), 'bench', retries=0)\n"
            "try:\n"
            "    answers = client.ask({'check': 'dartlens bench connectivity'}, "
            "{'ping': jev.noul('Is `check` a connectivity check?')})\n"
            "    print(json.dumps({'ok': isinstance(answers.get('ping'), dict)}))\n"
            "except jev.JevError as error:\n"
            "    print(json.dumps({'ok': False, 'error': str(error)[:200]}))\n") % str(repo)
    found = plugin_python(code, env, repo)
    return bool(found.get("ok")), found.get("error") or ""


def launch(argv, cwd, env, transcript, stderr, timeout):
    with open(transcript, "w") as out, open(stderr, "w") as err:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                   start_new_session=True)
        try:
            return process.wait(timeout=timeout), False
        except KeyboardInterrupt:
            os.killpg(process.pid, signal.SIGTERM)
            raise
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            return process.returncode, True


def infra_failure(out, code, timed_out):
    # Quota, overload, authentication or a CLI that never answered: not the agent's failure, the trial is retried.
    if timed_out:
        return None
    result, answered, api_errors = None, False, []
    for entry in entries(out / "transcript.jsonl"):
        if entry.get("type") == "result":
            result = entry
        elif entry.get("type") == "assistant":
            texts = [b.get("text", "") for b in (entry.get("message") or {}).get("content") or []
                     if isinstance(b, dict) and b.get("type") == "text"]
            if entry.get("isApiErrorMessage") or entry.get("error"):
                api_errors.append(" ".join(texts) + " " + str(entry.get("error") or ""))
            else:
                answered = True
    if code == 0 and result and not result.get("is_error"):
        return None
    try:
        stderr = (out / "stderr.log").read_text(errors="replace")[-2000:]
    except OSError:
        stderr = ""
    text = "\n".join([str((result or {}).get("result") or "")] + api_errors + [stderr])
    for kind, regex in (("quota", QUOTA), ("auth", AUTH), ("transient", TRANSIENT)):
        match = regex.search(text)
        if match:
            return {"kind": kind, "text": text[max(0, match.start() - 80):match.end() + 120].strip()}
    if not answered:
        return {"kind": "no_output", "text": text.strip()[-300:]}
    return None


def archive_attempt(out, meta):
    target = out / ("infra-%d" % (1 + len(list(out.glob("infra-*")))))
    target.mkdir()
    for path in list(out.iterdir()):
        if path != target and not path.name.startswith("infra-"):
            shutil.move(str(path), str(target / path.name))
    (target / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return target


def collect_session(session_id, worktree, out):
    expected = session_dir(worktree)
    main = expected / (session_id + ".jsonl")
    matched = main.is_file()
    if not matched:
        found = sorted((config_dir() / "projects").glob("*/%s.jsonl" % session_id))
        main = found[0] if found else None
    if not main:
        return {"found": False, "memory_dir_matched": False}
    target = out / "session"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(main, target / main.name)
    subagents = main.parent / session_id / "subagents"
    if subagents.is_dir():
        shutil.copytree(subagents, target / "subagents", dirs_exist_ok=True)
    return {"found": True, "memory_dir_matched": matched, "path": str(main)}


def capture_diff(sh, worktree, base, out):
    git(sh, "add", "-A", cwd=worktree)
    diff = git(sh, "diff", "--cached", "--binary", base, cwd=worktree).stdout
    names = git(sh, "diff", "--cached", "--name-status", base, cwd=worktree).stdout
    changes = []
    for line in names.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            changes.append({"status": parts[0][:1], "path": parts[-1]})
    (out / "diff.patch").write_text(diff)
    (out / "changes.json").write_text(json.dumps(changes, ensure_ascii=False, indent=1))
    return changes


def snapshot_logs(tag, session_id, start, end, state_dir, out):
    rows = []
    # The trial's own state directory holds only its records; the shared cache is attributed record by record.
    for path in sorted(state_dir.rglob("*.jsonl")) if state_dir.is_dir() else []:
        for record in entries(path):
            record.update(_file=path.relative_to(state_dir).as_posix(), _attribution="state")
            rows.append(record)
    cache = Path.home() / ".cache" / "dartlens"
    for path in sorted(cache.rglob("*.jsonl")) if cache.is_dir() else []:
        for record in entries(path):
            run, session, stamp = record.get("run"), record.get("session"), record.get("ts")
            inside = isinstance(stamp, (int, float)) and start - TAG_SLACK_S <= stamp <= end
            if run is not None:
                how = "tag" if run == tag and inside else None
            elif session is not None:
                how = "session" if session == session_id else None
            else:
                how = "window" if inside and start <= stamp else None
            if how:
                record.update(_file="shared/" + path.relative_to(cache).as_posix(), _attribution=how)
                rows.append(record)
    (out / "dartlens_logs.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    for breaker in sorted(state_dir.glob("breaker*.json")) if state_dir.is_dir() else []:
        (out / "state").mkdir(exist_ok=True)
        shutil.copy2(breaker, out / "state" / breaker.name)
    return len(rows)


def trial_dirs(args, sh):
    if sh.dry:
        base = Path(args.trials_dir or tempfile.gettempdir())
        return base / "dlb-XXXX", base / "dls-XXXX"
    root = Path(tempfile.mkdtemp(prefix="dlb-", dir=args.trials_dir)).resolve()
    state = Path(tempfile.mkdtemp(prefix="dls-", dir=args.trials_dir)).resolve()
    return root, state


def run_trial(sh, args, trial, home, results, campaign):
    task = trial["task"]
    out = results / trial["id"]
    previous = read_json(out / "meta.json", {}) if not sh.dry else {}
    if previous.get("finished"):
        print("  déjà fait, ignoré")
        return previous
    root, state = trial_dirs(args, sh)
    repo = root / task["project"]
    session_id = str(uuid.uuid4())
    tag = "%s/%s/%s" % (args.campaign, trial["id"], session_id)
    env, extra = trial_env(args, trial, tag, state)
    argv = claude_argv(args, trial, session_id)
    meta = {
        "trial": trial["id"], "task": task["id"], "project": task["project"], "type": task["type"],
        "arm": trial["arm"], "lang": trial["lang"], "rep": trial["rep"], "block": trial["block"],
        "position": trial["position"], "commit": trial["commit"], "prompt": trial["prompt"],
        "session_id": session_id, "tag": tag, "repo": str(repo), "env": extra, "argv": argv,
        "jev_backend": jev_backend(args), "jev_expected": jev_expected(trial["arm"]), "model": args.model,
        "campaign": args.campaign, "infra_attempts": len(list(out.glob("infra-*"))) if out.is_dir() else 0,
    }
    mirror = ensure_mirror(sh, home, task["project"], trial["source"], trial["commit"])
    try:
        try:
            make_repo(sh, mirror, trial["commit"], repo, task["setup"].get("history"), trial["remotes"])
            base = setup_repo(sh, trial, repo, mirror, ARMS[trial["arm"]]["plugin"])
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            # Not finished: rerunning the campaign retries it.
            meta.update(status="setup_failed", error=str(error), finished=False)
            print("  mise en situation échouée : %s" % error)
            return write_meta(out, meta, sh)
        meta["base"] = base
        if sh.dry:
            sh.show(argv, repo, extra)
            run_checks(sh, task["checks"], repo, base, env)
            scored = [c["id"] for c in task["checks"] if c["kind"] in SCORE_KINDS]
            if scored:
                print("    notés ensuite par score.py : %s" % ", ".join(scored))
            return meta
        check_installed(repo, trial["arm"], args.allow_installed_plugin)
        meta["conditions"] = trial_conditions(args, campaign)
        meta["conditions_id"] = conditions_id(meta["conditions"])
        if meta["jev_expected"]:
            allowed, reason = jev_preflight(repo, env)
            meta["jev_preflight"] = [allowed, reason]
            if not allowed:
                raise RuntimeError("Jev refusé pour le bras %s (%s) : l'essai ne mesurerait rien" % (trial["arm"], reason))
            if not campaign["pinged"] and not args.no_jev_ping:
                ping_env = dict(env, DARTLENS_BENCH_RUN="%s/preflight" % args.campaign,
                                DARTLENS_STATE_DIR=str(results / "_preflight"))
                ok, error = jev_ping(repo, ping_env)
                if not ok:
                    raise RuntimeError("Jev ne répond pas (%s) : campagne arrêtée avant de consommer des essais" % error)
                campaign["pinged"] = True
        out.mkdir(parents=True, exist_ok=True)
        start = time.time()
        code, timed_out = launch(argv, repo, env, out / "transcript.jsonl", out / "stderr.log", args.timeout_min * 60)
        end = time.time()
        meta.update(start=start, end=end, duration_s=round(end - start, 1), returncode=code, timeout=timed_out)
        meta["session"] = collect_session(session_id, repo, out)
        infra = infra_failure(out, code, timed_out)
        if infra:
            meta.update(status="infra_failed", infra=infra, finished=False, infra_attempts=meta["infra_attempts"] + 1)
            archive_attempt(out, meta)
            write_meta(out, meta, sh)
            print("  panne d'infrastructure (%s) : essai à relancer, non compté" % infra["kind"])
            if infra["kind"] in ("quota", "auth"):
                raise InfraStop("%s : %s" % (infra["kind"], infra["text"][:200]))
            return meta
        meta["changes"] = len(capture_diff(sh, repo, base, out))
        checks = run_checks(sh, task["checks"], repo, base, env)
        (out / "checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=1))
        time.sleep(max(0.0, args.grace - (time.time() - end)))
        meta["dartlens_records"] = snapshot_logs(tag, session_id, start, time.time(), state, out)
        # Written only now: nothing in the results directory may hint at the solution while the agent runs.
        (out / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=1))
        meta.update(status="done", finished=True)
        passed = sum(c["ok"] for c in checks)
        print("  code %s%s, %.0f s, critères lancés %d/%d" % (code, " (délai)" if timed_out else "",
                                                            meta["duration_s"], passed, len(checks)))
        return write_meta(out, meta, sh)
    finally:
        cleanup(sh, (root, state), args.keep)


def write_meta(out, meta, sh):
    if not sh.dry:
        out.mkdir(parents=True, exist_ok=True)
        (out / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    return meta


def cleanup(sh, directories, keep):
    if sh.dry:
        return
    if keep:
        print("  conservés : %s" % ", ".join(str(d) for d in directories))
        return
    for directory in directories:
        shutil.rmtree(directory, ignore_errors=True)


def check_installed(worktree, arm, allowed):
    found = []
    for path in (config_dir() / "settings.json", worktree / ".claude" / "settings.json",
                 worktree / ".claude" / "settings.local.json"):
        try:
            enabled = json.loads(path.read_text()).get("enabledPlugins") or {}
        except (OSError, ValueError, AttributeError):
            continue
        found += ["%s (%s)" % (k, path) for k, v in enabled.items() if k.split("@")[0].startswith("dartlens") and v]
    if found and not allowed:
        raise RuntimeError("dartlens est activé hors --plugin-dir (%s) : le bras %s serait contaminé"
                           % (", ".join(found), arm))


def isolation_gaps(arms, plugin_dir):
    text = ""
    for path in plugin_dir.rglob("*"):
        if path.is_file() and path.suffix in (".py", ".json", ".md", ".sh", "") and "__pycache__" not in path.parts:
            try:
                text += path.read_text(errors="replace")
            except OSError:
                pass
    gaps = {}
    for arm in arms:
        missing = [name for name in ARMS[arm]["env"] if name not in text]
        if missing:
            gaps[arm] = missing
    return gaps


def plugin_identity(plugin_dir):
    digest = hashlib.sha256()
    for path in sorted(p for p in plugin_dir.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        digest.update(path.relative_to(plugin_dir).as_posix().encode())
        digest.update(path.read_bytes())
    head = subprocess.run(["git", "-C", str(plugin_dir), "rev-parse", "HEAD"], text=True, capture_output=True)
    dirty = subprocess.run(["git", "-C", str(plugin_dir), "status", "--porcelain", "."], text=True, capture_output=True)
    return {"sha256": digest.hexdigest()[:16], "commit": head.stdout.strip() or None,
            "dirty": bool(dirty.stdout.strip()) or head.returncode != 0}


def claude_version(claude):
    return subprocess.run([claude, "--version"], text=True, capture_output=True).stdout.strip()


# ---------------------------------------------------------------- campaign


def conditions(args, version, plugin):
    # Everything that changes what a trial measures: a resumed campaign must keep all of it.
    return {
        "model": args.model, "permission_mode": args.permission_mode, "allowed_tools": sorted(allowed_rules(args)),
        "extra_args": list(args.extra_arg), "user_settings": args.user_settings, "max_turns": args.max_turns, "timeout_min": args.timeout_min,
        "grace": args.grace, "pause": args.pause, "jev_backend": jev_backend(args), "jev_url": args.jev_url,
        "at": args.at, "projects": sorted(args.project), "gate": gate_enabled(args),
        "plugin": plugin["sha256"], "claude_version": version,
    }


def conditions_id(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:12]


def differences(before, after):
    return {k: [before.get(k), after.get(k)] for k in sorted(set(before) | set(after)) if before.get(k) != after.get(k)}


def trial_conditions(args, campaign):
    current = conditions(args, claude_version(args.claude), plugin_identity(args.plugin_dir))
    changed = differences(campaign["conditions"], current)
    if changed and not args.force:
        raise RuntimeError("conditions changées en cours de campagne (%s) : --force pour continuer malgré tout"
                           % ", ".join(changed))
    return current


def open_campaign(args, results, arms, trials, gaps):
    current = conditions(args, claude_version(args.claude), plugin_identity(args.plugin_dir))
    plan = {"ts": time.time(), "arms": arms, "reps": args.reps, "lang": args.lang, "seed": args.seed,
            "schedule": [t["id"] for t in trials], "unisolated": gaps}
    file = results / "campaign.json"
    saved = read_json(file, None)
    if saved is None:
        results.mkdir(parents=True, exist_ok=True)
        saved = {"campaign": args.campaign, "conditions": current, "conditions_id": conditions_id(current), "runs": [plan]}
    else:
        changed = differences(saved.get("conditions") or {}, current)
        if changed and not args.force:
            sys.exit("reprise refusée, conditions différentes de campaign.json :\n%s\n--force pour reprendre quand même "
                     "(la campagne devient hétérogène et score.py le signalera)"
                     % "\n".join("  %s : %r → %r" % (k, a, b) for k, (a, b) in changed.items()))
        plan["forced_differences"] = changed
        saved.setdefault("runs", []).append(plan)
    file.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
    return {"conditions": saved["conditions"], "pinged": False}


# ---------------------------------------------------------------- schedule


def schedule(tasks, arms, reps, lang, seed):
    langs = {"fr": ["fr"], "en": ["en"], "alternate": ["fr", "en"], "both": ["fr", "en"]}[lang]
    trials, block = [], 0
    for rep in range(reps):
        order = list(range(len(tasks)))
        random.Random(seed * 1000 + rep).shuffle(order)
        for index in order:
            task = tasks[index]
            chosen = langs if lang == "both" else [langs[(index + rep) % len(langs)]]
            for language in chosen:
                shift = block % len(arms)
                for position, arm in enumerate(arms[shift:] + arms[:shift]):
                    trial_id = "%s.%s.%s.r%d" % (task["id"], arm, language, rep + 1)
                    trials.append({"id": trial_id, "task": task, "arm": arm, "lang": language, "rep": rep + 1,
                                   "block": block, "position": position, "prompt": task["prompt_" + language]})
                block += 1
    return trials


# ---------------------------------------------------------------- validation without claude


def base_env(args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("DARTLENS_") and k not in STRIPPED_ENV}
    if args.jev_url:
        env["DARTLENS_JEV_URL"] = args.jev_url
    return env


def guard_probe(args, repo, settings, env):
    # One typical edit through the real hook: the guard must reach Jev and log a verdict.
    ruleset = settings.get("plugin_files", {}).get(RULES_FILE)
    if not ruleset:
        return True, "aucune règle de garde pour ce projet"
    rule = next((r for r in ruleset["rules"] if not (repo / rules.example_path(r, ruleset)).exists()), None)
    if rule is None:
        return False, "aucun chemin libre pour l'édition type"
    rel = rules.example_path(rule, ruleset)
    example = next((e for e in rule["examples"] if e.get("violation")), rule["examples"][0])
    content = "%s\n%s\n" % (example.get("context") or "", example["after"])
    write_plugin_files(Shell(False), repo, settings)
    state = Path(tempfile.mkdtemp(prefix="dls-"))
    session = "bench-probe-" + uuid.uuid4().hex[:8]
    payload = {"session_id": session, "cwd": str(repo), "hook_event_name": "PostToolUse", "tool_name": "Write",
               "tool_input": {"file_path": str(repo / rel), "content": content}, "tool_response": {"type": "create"}}
    try:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(content)
        probe_env = dict(env, DARTLENS_STATE_DIR=str(state), CLAUDE_PROJECT_DIR=str(repo),
                         DARTLENS_BENCH_RUN="%s/guard-probe" % args.campaign)
        allowed, reason = jev_preflight(repo, probe_env)
        if not allowed:
            return False, "Jev refusé (%s)" % reason
        started = time.monotonic()
        result = subprocess.run([sys.executable, str(args.plugin_dir / "hooks" / "convention_guard.py")],
                                input=json.dumps(payload), env=probe_env, cwd=repo, text=True, capture_output=True, timeout=90)
        seconds = time.monotonic() - started
        records = [r for r in entries(state / "guard.jsonl") if r.get("session") == session]
        outcomes = [r.get("outcome") for r in records]
        if any(o in ("quiet", "fired") for o in outcomes):
            judged = records[-1].get("rules") or {}
            return True, "%s en %.1f s, %d règle(s) jugée(s) sur %s" % (outcomes[-1], seconds, len(judged), rel)
        return False, "aucun verdict dans guard.jsonl (%s) %s" % (", ".join(map(str, outcomes)) or "aucun enregistrement",
                                                                 tail(result.stderr).strip()[-300:])
    finally:
        shutil.rmtree(state, ignore_errors=True)


def load_score():
    spec = importlib.util.spec_from_file_location("bench_score", str(BENCH / "score.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_trials(sh, trials, home, args, reference):
    failures, missing, probed = 0, [], set()
    score = load_score() if reference and not sh.dry else None
    for trial in trials:
        task = trial["task"]
        setup = task["setup"]
        print("%s (%s)" % (task["id"], setup["status"]))
        if reference and not setup.get("reference"):
            missing.append(task["id"])
            print("  sans référence : non vérifiée")
            continue
        root, state = trial_dirs(args, sh)
        repo = root / task["project"]
        mirror = ensure_mirror(sh, home, task["project"], trial["source"], trial["commit"])
        env = base_env(args)
        try:
            make_repo(sh, mirror, trial["commit"], repo, setup.get("history"), trial["remotes"])
            base = setup_repo(sh, trial, repo, mirror, False)
            if reference:
                git(sh, "apply", "--whitespace=nowarn", "-", cwd=repo, stdin_text=setup["reference"])
                # Same order as a trial: the diff is taken before the criteria run.
                changes = [] if sh.dry else capture_diff(sh, repo, base, state)
                results = run_checks(sh, task["checks"], repo, base, env)
                if not sh.dry:
                    diff = (state / "diff.patch").read_text(errors="replace")
                    for check in task["checks"]:
                        if check["kind"] in SCORE_KINDS:
                            outcome = score.evaluate(check, setup.get("reference_answer") or "", changes, diff)
                            results.append(dict(outcome, id=check["id"]))
            else:
                before = setup.get("expect_before", [])
                results = run_checks(sh, before, repo, base, env)
                if not before:
                    print("  aucun expect_before : mise en situation seulement")
            for result in results:
                print("  %s %s%s" % ("ok " if result["ok"] else "KO ", result["id"],
                                     "" if result["ok"] else " : " + tail(result.get("output") or result.get("detail") or "")[-300:]))
            failures += sum(not r["ok"] for r in results)
            if not reference and not sh.dry and task["project"] not in probed:
                probed.add(task["project"])
                ok, detail = guard_probe(args, repo, trial["project"], env)
                print("  %s garde (%s) : %s" % ("ok " if ok else "KO ", task["project"], detail))
                failures += not ok
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            print("  KO mise en situation : %s" % error)
            failures += 1
        finally:
            if setup.get("memory") and not sh.dry and not args.keep:
                shutil.rmtree(session_dir(repo), ignore_errors=True)
            cleanup(sh, (root, state), args.keep)
    if missing:
        print("%d tâche(s) sans référence, non vérifiée(s) : %s" % (len(missing), ", ".join(missing)))
    return 1 if failures else 0


# ---------------------------------------------------------------- main


def parse():
    parser = argparse.ArgumentParser(prog="run.py", description="Exécute le banc dartlens : un dépôt jetable et autonome "
                                     "par essai, claude -p avec ou sans le plugin, critères exécutables, journaux. Rien "
                                     "n'est lancé avec --dry-run.")
    parser.add_argument("--tasks", type=Path, default=BENCH / "tasks", help="dossier des tâches")
    parser.add_argument("--task", action="append", default=[], help="garder cette tâche (id, répétable)")
    parser.add_argument("--arms", default=",".join(DEFAULT_ARMS), help="bras, séparés par des virgules (%s)" % ", ".join(ARMS))
    parser.add_argument("--reps", type=int, default=1, help="répétitions par tâche et par bras")
    parser.add_argument("--lang", choices=("fr", "en", "alternate", "both"), default="alternate")
    parser.add_argument("--seed", type=int, default=1, help="graine de l'ordre des tâches")
    parser.add_argument("--model", help="modèle imposé à tous les bras (recommandé)")
    parser.add_argument("--permission-mode", default="acceptEdits")
    parser.add_argument("--allow", action="append", default=[], help="règle --allowedTools supplémentaire, identique pour tous les bras")
    parser.add_argument("--max-turns", type=int)
    parser.add_argument("--timeout-min", type=float, default=45)
    parser.add_argument("--pause", type=float, default=0, help="secondes entre deux essais (cache chaud)")
    parser.add_argument("--grace", type=float, default=15, help="secondes laissées aux hooks en arrière-plan")
    parser.add_argument("--claude", default=real_claude())
    parser.add_argument("--user-settings", action="store_true",
                        help="charge aussi ~/.claude/settings.json (hooks utilisateur comme rtk) ; écarté par défaut")
    parser.add_argument("--plugin-dir", type=Path, default=PLUGIN)
    parser.add_argument("--home", type=Path, default=Path.home() / ".cache" / "dartlens-bench",
                        help="miroirs et résultats (jamais visibles depuis le dépôt d'un essai)")
    parser.add_argument("--trials-dir", help="dossier des dépôts jetables (défaut : dossier temporaire du système)")
    parser.add_argument("--campaign", default=datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--out", type=Path, help="dossier des résultats (défaut : <home>/results/<campaign>)")
    parser.add_argument("--project", action="append", default=[], help="NOM=CHEMIN, remplace le chemin d'un projet")
    parser.add_argument("--at", help="commit imposé à toutes les tâches (tests de branchement sur une copie)")
    parser.add_argument("--jev-url", help="URL Jev imposée (faux serveur : plomberie seulement)")
    parser.add_argument("--no-jev-ping", action="store_true", help="ne pas vérifier que Jev répond avant le premier essai")
    parser.add_argument("--extra-arg", action="append", default=[], help="argument passé tel quel à claude")
    parser.add_argument("--include-todo", action="store_true", help="inclure les tâches dont le setup est à écrire")
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan et les commandes, ne lance rien")
    parser.add_argument("--check-tasks", action="store_true", help="valide les tâches et les fichiers du plugin, puis s'arrête")
    parser.add_argument("--validate-setup", action="store_true",
                        help="met chaque tâche en situation, vérifie expect_before et la garde, sans claude")
    parser.add_argument("--validate-reference", action="store_true",
                        help="applique la solution de référence de chaque tâche et exige que tous ses critères passent")
    parser.add_argument("--force", action="store_true", help="reprendre malgré des conditions changées (campagne hétérogène)")
    parser.add_argument("--keep", action="store_true", help="ne supprime pas les dépôts jetables")
    parser.add_argument("--allow-installed-plugin", action="store_true")
    parser.add_argument("--allow-unisolated", action="store_true", help="lancer même si un bras n'est pas isolable")
    return parser.parse_args()


def main():
    args = parse()
    projects, tasks, problems = load_tasks(args.tasks)
    for name, found in problems.items():
        print("%s :\n  - %s" % (name, "\n  - ".join(found)))
    if args.check_tasks:
        for task in tasks:
            print("%-40s %-10s %-26s %-5s critères %d%s" % (task["id"], task["project"], task["type"],
                                                          task["setup"]["status"], len(task["checks"]),
                                                          "" if task["setup"].get("reference") else ", sans référence"))
        print("%d tâches valides, %d fichiers en erreur" % (len(tasks), len(problems)))
        sys.exit(1 if problems else 0)
    if problems:
        sys.exit("tâches invalides : corrige-les ou lance --check-tasks")
    if "--settings" in args.extra_arg and gate_enabled(args):
        sys.exit("--settings est réservé au garde-fou du banc (même liste de commandes pour tous les bras)")
    overrides = dict(item.split("=", 1) for item in args.project)
    tasks = [t for t in tasks if (not args.task or t["id"] in args.task)
             and (args.include_todo or t["setup"]["status"] == "ready" or args.task)]
    if not tasks:
        sys.exit("aucune tâche retenue")
    sources = {}
    for name in sorted({t["project"] for t in tasks}):
        source = Path(os.path.expanduser(overrides.get(name) or projects[name]["path"])).resolve()
        # Checked before any fetch: a refused repository is neither copied nor sent anywhere.
        denied = policy.refusal(source)
        if denied:
            sys.exit("projet %s (%s) refusé : %s. Le banc ne le copie pas." % (name, source, denied))
        sources[name] = (source, source_remotes(source))
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    unknown = [a for a in arms if a not in ARMS]
    if unknown:
        sys.exit("bras inconnus : %s" % ", ".join(unknown))
    validating = args.validate_setup or args.validate_reference
    gaps = {} if validating else isolation_gaps(arms, args.plugin_dir)
    for arm, missing in gaps.items():
        print("attention : le plugin ne lit pas %s, le bras « %s » n'est pas isolé" % (", ".join(missing), arm))
    if gaps and not (args.dry_run or args.allow_unisolated):
        sys.exit("bras non isolables : ajoute ces variables aux composants ou passe --allow-unisolated")
    if args.jev_url and jev_backend(args) == "fake":
        print("faux serveur Jev : essais de plomberie, aucune conclusion de qualité ni d'économie")
    sh = Shell(args.dry_run)
    home = args.home.expanduser().resolve()
    results = (args.out or home / "results" / args.campaign).expanduser().resolve()

    def attach(trial):
        name = trial["task"]["project"]
        trial["project"] = projects[name]
        trial["source"], trial["remotes"] = sources[name]
        trial["commit"] = args.at or trial["task"]["commit"]
        return trial

    if validating:
        trials = [attach(t) for t in schedule(tasks, ["control"], 1, "fr", args.seed)]
        sys.exit(validate_trials(sh, trials, home, args, args.validate_reference))
    trials = [attach(t) for t in schedule(tasks, arms, args.reps, args.lang, args.seed)]
    campaign = None
    if not args.dry_run:
        if not shutil.which(args.claude):
            sys.exit("CLI claude introuvable : %s" % args.claude)
        campaign = open_campaign(args, results, arms, trials, gaps)
    print("%d essais : %d tâches × %d bras × %d répétitions, langue %s, résultats %s"
          % (len(trials), len(tasks), len(arms), args.reps, args.lang, results))
    for number, trial in enumerate(trials, 1):
        print("[%d/%d] %s" % (number, len(trials), trial["id"]))
        try:
            run_trial(sh, args, trial, home, results, campaign)
        except InfraStop as error:
            sys.exit("arrêt, %s. Relance la même commande plus tard : les essais faits sont gardés, les autres reprennent." % error)
        except RuntimeError as error:
            sys.exit("arrêt : %s" % error)
        if args.pause and number < len(trials) and not args.dry_run:
            time.sleep(args.pause)


if __name__ == "__main__":
    main()
