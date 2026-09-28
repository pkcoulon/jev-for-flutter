#!/usr/bin/env python3
import os
import re
import shlex
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
try:
    from dartlens import config, hookio, paths, project, transcript
except Exception:
    sys.exit(0)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
HEREDOC = re.compile(r"(<<-?[ \t]*(['\"]?)([A-Za-z_]\w*)\2)([^\n]*)\n.*?\n[ \t]*\3[ \t]*(?=\n|$)", re.S)
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
PIPES = {"|", "|&"}
SED_INPLACE = re.compile(r"^(-[nErsuz]*i|--in-place)")
PERL_INPLACE = re.compile(r"^-[plnaws0-9]*i")
VERIFY_SINGLE = {"fanalyze", "ftest", "flutter-lint"}
VERIFY_PAIRS = {("dart", "analyze"), ("flutter", "analyze"), ("flutter", "test"), ("dart", "test"), ("very_good", "test"), ("dcm", "analyze")}
MAX_FILES = 8


def tokenize(command):
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
        lexer.whitespace = " \t\r"
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return re.findall(r"&&|\|\||>>|&>|\n|[|;&<>()]|[^\s|;&<>()]+", command)


def is_separator(token):
    return bool(token) and set(token) <= set("();&|\n") and token not in PIPES


def segments(tokens):
    current = []
    for index, token in enumerate(tokens):
        if is_separator(token):
            if current:
                yield current
            current = []
        else:
            current.append((index, token))
    if current:
        yield current


def dart_targets(pairs):
    return [(i, t.strip("\"'")) for i, t in pairs if t.strip("\"'").endswith(".dart")]


def bash_events(command):
    tokens = tokenize(HEREDOC.sub(r"\1\4", command))
    events = []
    for index, token in enumerate(tokens[:-1]):
        target = tokens[index + 1].strip("\"'")
        if token in REDIRECTS and target.endswith(".dart"):
            events.append((index + 1, "edit", target))
    for segment in segments(tokens):
        for position, (index, token) in enumerate(segment):
            name = os.path.basename(token)
            after = []
            for pair in segment[position + 1:]:
                if pair[1] in PIPES:
                    break
                after.append(pair)
            if name in VERIFY_SINGLE or (after and (name, after[0][1]) in VERIFY_PAIRS):
                events.append((index, "verify", None))
            elif name == "tee":
                events.extend((i, "edit", t) for i, t in dart_targets(after))
            elif name in ("sed", "gsed", "perl"):
                flag = SED_INPLACE if name != "perl" else PERL_INPLACE
                if any(flag.match(t) for _, t in after):
                    targets = dart_targets(after) or dart_targets(segment[:position])
                    events.extend((i, "edit", t) for i, t in targets)
    return [(kind, path) for _, kind, path in sorted(events, key=lambda event: event[0])]


def turn_events(entries):
    for name, tool_input in transcript.tool_uses(entries):
        if not isinstance(name, str):
            continue
        if name in EDIT_TOOLS:
            path = tool_input.get("file_path") or tool_input.get("notebook_path")
            if isinstance(path, str) and path.endswith(".dart"):
                yield "edit", path
        elif name == "Bash" and isinstance(tool_input.get("command"), str):
            for event in bash_events(tool_input["command"]):
                yield event
        elif name.startswith("mcp__") and ("analyze" in name.lower() or "run_tests" in name.lower()):
            yield "verify", None


def under(path, base):
    return path == base or path.startswith(base.rstrip(os.sep) + os.sep)


def main(payload):
    if payload.get("stop_hook_active"):
        return None
    path = payload.get("transcript_path")
    if not isinstance(path, str) or not os.path.isfile(path):
        return None
    cwd = payload.get("cwd") or os.getcwd()
    root = project.project_root(cwd)
    settings = config.load(root)
    if settings.get("stop_gate") == "off":
        return None
    pending = []
    for kind, target in turn_events(transcript.current_turn(path)):
        if kind == "verify":
            pending = []
        else:
            pending.append(target)
    if not pending:
        return None
    root_real = os.path.realpath(str(root))
    temp_dirs = [os.path.realpath(d) for d in (tempfile.gettempdir(), "/tmp", "/var/folders", payload.get("scratchpad_dir")) if d]
    patterns = paths.generated_patterns(settings, root)
    files = []
    for target in pending:
        absolute = os.path.realpath(os.path.join(cwd, os.path.expanduser(target)))
        if under(absolute, root_real):
            shown = project.rel(absolute, root_real)
            if paths.matches(shown, patterns):
                continue
        elif any(under(absolute, d) for d in temp_dirs) or paths.matches(absolute, settings.get("generated", [])):
            continue
        else:
            shown = absolute.replace(os.path.expanduser("~"), "~", 1)
        if shown not in files:
            files.append(shown)
    if not files:
        return None
    listed = " ".join(shlex.quote(f) if " " in f else f for f in files[:MAX_FILES])
    if len(files) > MAX_FILES:
        listed += " (+%d autres)" % (len(files) - MAX_FILES)
    return hookio.block(
        "Dart modifié sans analyse ni test ensuite (%d fichier%s).\n"
        "Lance fanalyze %s (et ftest sur les tests du module si le comportement a changé), puis corrige.\n"
        "Si c'est inutile, dis pourquoi en une phrase et termine." % (len(files), "s" if len(files) > 1 else "", listed)
    )


if __name__ == "__main__":
    hookio.run(main)
