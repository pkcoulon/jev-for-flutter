import json
import os
import re
import signal
import sys
from pathlib import Path


class Deadline(Exception):
    pass


def _expire(signum, frame):
    raise Deadline()


def run(main, deadline=4.0):
    # Fail open: any error, bad input or overrun exits 0 with nothing on stdout.
    try:
        if deadline and hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, _expire)
            signal.setitimer(signal.ITIMER_REAL, deadline)
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "null")
        output = main(payload) if isinstance(payload, dict) else None
        text = json.dumps(output) if output else ""
        if hasattr(signal, "SIGALRM"):
            signal.setitimer(signal.ITIMER_REAL, 0)
        if text:
            sys.stdout.write(text)
            sys.stdout.flush()
    except BaseException as error:
        try:
            sys.stderr.write("dartlens: %s: %r\n" % (os.path.basename(sys.argv[0]), error))
            sys.stderr.flush()
        except BaseException:
            pass
    os._exit(0)


def context(event, text):
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def block(reason):
    return {"decision": "block", "reason": reason}


def permission(decision, reason):
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision, "permissionDecisionReason": reason}}


def state_file(kind, session_id, suffix=""):
    directory = Path(os.environ.get("DARTLENS_STATE_DIR") or Path.home() / ".cache" / "dartlens") / kind
    directory.mkdir(parents=True, exist_ok=True)
    return directory / (re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "default") + suffix)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path, data):
    path = Path(path)
    tmp = path.with_name("%s.%d.tmp" % (path.name, os.getpid()))
    tmp.write_text(json.dumps(data))
    os.replace(str(tmp), str(path))
