import os
import re
from functools import lru_cache
from pathlib import Path

SKIP_WALK = {".git", ".dart_tool", "build", "node_modules", "Pods", ".gradle", ".idea", ".fvm", "ios", "android", "macos", "windows", "linux", "web"}


@lru_cache(maxsize=256)
def glob_regex(pattern):
    out = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif char == "*":
            out.append("[^/]*")
            i += 1
        elif char == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(char))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(rel_path, patterns):
    rel_path = rel_path.replace(os.sep, "/")
    while rel_path.startswith("./"):
        rel_path = rel_path[2:]
    return any(glob_regex(p).match(rel_path) for p in patterns)


def marker_dirs(root, markers, max_depth=5):
    if not markers:
        return []
    found = []
    root = Path(root)
    base_depth = len(root.parts)
    for current, dirs, files in os.walk(root):
        depth = len(Path(current).parts) - base_depth
        names = set(dirs) | set(files)
        if any(marker in names for marker in markers):
            found.append(os.path.relpath(current, root).replace(os.sep, "/"))
            dirs[:] = []
            continue
        if depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d not in SKIP_WALK and not d.startswith(".")]
    return sorted(d for d in found if d != ".")


def generated_patterns(config, root):
    patterns = list(config.get("generated", []))
    for directory in marker_dirs(root, tuple(config.get("generated_dir_markers", []))):
        patterns.append(f"{directory}/**")
    return patterns


def is_generated(path, config, root):
    root = Path(root).resolve()
    try:
        rel_path = Path(path).resolve().relative_to(root)
    except ValueError:
        return False
    if matches(rel_path.as_posix(), config.get("generated", [])):
        return True
    markers = [m for m in config.get("generated_dir_markers", []) if Path(m).name == m]
    for parent in (rel_path.parent, *rel_path.parent.parents):
        if 0 < len(parent.parts) <= 5 and any(os.path.lexists(root / parent / m) for m in markers):
            return True
    return False
