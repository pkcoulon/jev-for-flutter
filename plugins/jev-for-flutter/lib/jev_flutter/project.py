import json
import os
import re
import shutil
from pathlib import Path

ROOT_MARKERS = (".fvmrc", ".fvm", ".git")


def project_root(start=None):
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env and Path(env).is_dir():
        return Path(env).resolve()
    here = Path(start or os.getcwd()).resolve()
    for candidate in (here, *here.parents):
        if any((candidate / marker).exists() for marker in ROOT_MARKERS):
            return candidate
    return here


def _fvm_version(root):
    rc = root / ".fvmrc"
    if rc.is_file():
        try:
            return json.loads(rc.read_text()).get("flutter")
        except (ValueError, OSError):
            pass
    legacy = root / ".fvm" / "fvm_config.json"
    if legacy.is_file():
        try:
            return json.loads(legacy.read_text()).get("flutterSdkVersion")
        except (ValueError, OSError):
            pass
    return None


def flutter_sdk(root=None):
    root = Path(root) if root else project_root()
    link = root / ".fvm" / "flutter_sdk"
    if (link / "bin" / "flutter").exists():
        return link.resolve()
    version = _fvm_version(root)
    if version:
        for base in (os.environ.get("FVM_CACHE_PATH"), os.environ.get("FVM_HOME"), str(Path.home() / "fvm")):
            if not base:
                continue
            sdk = Path(base) / "versions" / version
            if (sdk / "bin" / "flutter").exists():
                return sdk
    flutter_root = os.environ.get("FLUTTER_ROOT")
    if flutter_root and (Path(flutter_root) / "bin" / "flutter").exists():
        return Path(flutter_root)
    on_path = shutil.which("flutter")
    if on_path:
        return Path(on_path).resolve().parent.parent
    return None


def flutter_executable(root=None):
    sdk = flutter_sdk(root)
    return str(sdk / "bin" / "flutter") if sdk else None


def dart_executable(root=None):
    sdk = flutter_sdk(root)
    if sdk:
        for candidate in (sdk / "bin" / "dart", sdk / "bin" / "cache" / "dart-sdk" / "bin" / "dart"):
            if candidate.exists():
                return str(candidate)
    return shutil.which("dart")


def is_flutter_package(package_dir):
    pubspec = Path(package_dir) / "pubspec.yaml"
    try:
        text = pubspec.read_text()
    except OSError:
        return False
    return re.search(r"^\s+sdk:\s*flutter\b", text, re.MULTILINE) is not None


def package_dir_of(path, root=None):
    root = Path(root) if root else project_root()
    current = Path(path).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "pubspec.yaml").is_file():
            return candidate
        if candidate == root:
            break
    return None


def rel(path, base):
    try:
        return os.path.relpath(path, base)
    except ValueError:
        return str(path)
