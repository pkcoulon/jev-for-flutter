import copy
import json
import math
from pathlib import Path

DEFAULTS = {
    "generated": [
        "**/*.g.dart",
        "**/*.freezed.dart",
        "**/*.gr.dart",
        "**/*.gen.dart",
        "**/*.mocks.dart",
        "**/*.pb.dart",
        "**/*.pbenum.dart",
        "**/*.pbjson.dart",
        "**/*.pbserver.dart",
        "**/generated/**",
        "**/.dart_tool/**",
        "**/build/**",
    ],
    "generated_dir_markers": [".openapi-generator"],
    "jev": {"enabled": False, "model": "jev-1.13.0", "hook_timeout_s": 1.5, "cli_timeout_s": 20},
    "lens": {"threshold": 0.5, "max_files": 20, "nudge": "hint", "nudge_min_lines": 300, "nudge_max": 3},
    "find": {"extensions": [".dart"], "include_tests": False, "top": 5, "min": 0.6},
    "guard": {"enabled": True, "rules_file": ".claude/dartlens/rules.json", "threshold": 0.85},
    "router": {
        "enabled": True,
        "memory": True,
        "skills": True,
        "memory_threshold": 0.8,
        "skill_confidence": 0.8,
        "max_notes": 3,
    },
    "ticket_regex": r"\b[A-Z][A-Z0-9]+-\d+\b",
}

CONFIG_FILES = (".claude/dartlens.json", ".dartlens.json")


def _expected(default, key, value):
    if isinstance(default, dict):
        return "objet"
    if isinstance(default, bool):
        return None if isinstance(value, bool) else "booléen"
    if isinstance(default, (int, float)):
        number = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        whole = isinstance(default, int) and not key.endswith("_s")
        if number and (isinstance(value, int) or not whole):
            return None
        return "entier" if whole else "nombre"
    if isinstance(default, str):
        return None if isinstance(value, str) else "chaîne"
    if isinstance(default, list):
        return None if isinstance(value, list) and all(isinstance(v, str) for v in value) else "liste de chaînes"
    return None


def _merge(base, override, prefix="", problems=None):
    for key, value in override.items():
        default = base.get(key)
        if isinstance(default, dict) and isinstance(value, dict):
            _merge(default, value, prefix + key + ".", problems)
            continue
        expected = _expected(default, key, value) if key in base else None
        if expected is None:
            base[key] = value
        elif problems is not None:
            problems.append("%s%s = %s (%s attendu, défaut %s appliqué)" % (
                prefix, key, json.dumps(value, ensure_ascii=False)[:40], expected,
                json.dumps(default, ensure_ascii=False)[:40]))
    return base


def load(root, problems=None):
    config = copy.deepcopy(DEFAULTS)
    for name in CONFIG_FILES:
        path = Path(root) / name
        if path.is_file():
            try:
                data = json.loads(path.read_text())
            except (ValueError, OSError) as error:
                data = None
                if problems is not None:
                    problems.append("illisible, valeurs par défaut : %s" % error)
            if isinstance(data, dict):
                _merge(config, data, "", problems)
            elif data is not None and problems is not None:
                problems.append("objet JSON attendu à la racine, valeurs par défaut")
            break
    return config
