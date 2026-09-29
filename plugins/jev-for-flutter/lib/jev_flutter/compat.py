import os
from pathlib import Path

LEGACY_NAME = "dartlens"

for name, value in list(os.environ.items()):
    if name.startswith(LEGACY_NAME.upper() + "_"):
        os.environ.setdefault("JEV_FLUTTER_" + name[len(LEGACY_NAME) + 1:], value)


def cache_dir():
    current = Path.home() / ".cache" / "jev-for-flutter"
    previous = current.with_name(LEGACY_NAME)
    return previous if previous.is_dir() and not current.exists() else current
