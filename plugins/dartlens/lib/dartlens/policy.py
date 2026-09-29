import json
import os
import re
from pathlib import Path

from . import jev, paths

USER_POLICY = Path.home() / ".config" / "dartlens" / "policy.json"
SECRET_FILES = [
    "**/.env", "**/.env.*", "**/*.pem", "**/*.key", "**/*.p12", "**/*.jks", "**/*.keystore",
    "**/key.properties", "**/google-services.json", "**/GoogleService-Info.plist", "**/*secret*", "**/*credential*",
]
SECRET_RE = re.compile(
    r"glpat-[A-Za-z0-9_.-]{10,}|figd_[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|xox[abp]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|sk_(?:live|test)_[A-Za-z0-9]{16,}|sb_secret_[A-Za-z0-9_-]{16,}|(?i:bearer)\s+[A-Za-z0-9._~+/-]{20,}"
    r"|(?i:(?:api[_-]?key|secret|token|password|(?<![a-z0-9])pat|service[_-]?role)['\"]?\s*[:=]\s*['\"][^'\"\s]{12,}['\"])"
    r"|(?<![A-Za-z0-9_])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"
)


def user_policy():
    rules = {"deny_remotes": [], "deny_paths": [], "error": None}
    try:
        data = json.loads(USER_POLICY.read_text())
    except FileNotFoundError:
        return rules
    except (OSError, ValueError) as error:
        rules["error"] = "%s: %s" % (type(error).__name__, error)
        return rules
    if not isinstance(data, dict):
        rules["error"] = "objet JSON attendu"
        return rules
    for key in ("deny_remotes", "deny_paths"):
        value = data.get(key, [])
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            rules[key] = value
        else:
            rules["error"] = "%s : liste de chaînes attendue" % key
    return rules


def _git_config(root):
    git = Path(root) / ".git"
    if git.is_file():
        match = re.search(r"gitdir:\s*(.+)", git.read_text())
        if not match:
            return None
        gitdir = (Path(root) / match.group(1).strip()).resolve()
        common = gitdir / "commondir"
        if common.is_file():
            gitdir = (gitdir / common.read_text().strip()).resolve()
        return gitdir / "config"
    return git / "config"


def git_remotes(root):
    try:
        config = _git_config(root)
        text = config.read_text() if config else ""
    except (OSError, ValueError):
        return []
    return re.findall(r"^\s*url\s*=\s*(\S+)", text, re.MULTILINE)


def path_refused(path):
    resolved = Path(os.path.realpath(os.path.expanduser(str(path))).casefold())
    rules = user_policy()
    if rules["error"]:
        return True
    for denied in rules["deny_paths"]:
        denied = Path(os.path.realpath(os.path.expanduser(denied)).casefold())
        if resolved == denied or denied in resolved.parents:
            return True
    return False


def refusal(root):
    error = user_policy()["error"]
    if error:
        return "politique ~/.config/dartlens/policy.json illisible (%s), rien n'est envoyé" % error
    if path_refused(root):
        return "projet exclu par ~/.config/dartlens/policy.json"
    denied = user_policy()["deny_remotes"]
    resolved = Path(root).resolve()
    # A package with its own .fvmrc inside an excluded repo is its own root: every enclosing repo counts.
    for directory in (resolved, *resolved.parents):
        if (directory / ".git").exists() and any(
                pattern and pattern in url for url in git_remotes(directory) for pattern in denied):
            return "dépôt exclu par ~/.config/dartlens/policy.json"
    return None


def jev_allowed(root, config, component=None):
    if os.environ.get("DARTLENS_JEV_DISABLE"):
        return False, "Jev désactivé (DARTLENS_JEV_DISABLE)"
    switch = "DARTLENS_%s_DISABLE" % component.upper() if component else None
    if switch and os.environ.get(switch):
        return False, "%s désactivé (%s)" % (component, switch)
    denied = refusal(root)
    if denied:
        return False, denied
    if not config["jev"].get("enabled"):
        return False, "Jev non activé pour ce projet (.claude/dartlens.json : jev.enabled)"
    if not jev.api_key():
        return False, "clé TypeSafe absente (TYPESAFE_API_KEY ou ~/.config/dartlens/typesafe.key)"
    return True, ""


def sendable(path, root, extra_roots=()):
    resolved = Path(os.path.realpath(path))
    allowed = [Path(os.path.realpath(r)) for r in (root, *extra_roots)]
    base = next((r for r in allowed if resolved == r or r in resolved.parents), None)
    if base is None or path_refused(resolved):
        return False
    return not paths.matches(os.path.relpath(resolved, base).casefold(), [p.casefold() for p in SECRET_FILES])


def redact(text):
    return SECRET_RE.sub("[REDACTED]", text)
