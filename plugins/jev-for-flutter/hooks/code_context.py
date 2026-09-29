import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from jev_flutter import bm25, catalog, config, context, hookio, jev, policy, project


def update(path, token, values):
    with open(str(path) + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = hookio.read_json(path, {})
        if state.get("token") != token or state.get("status") == "cancelled":
            return False
        state.update(values)
        context.save(path, state)
        return True


def work(path, token):
    state = hookio.read_json(path, {})
    if state.get("token") != token or state.get("status") != "pending":
        return
    root = Path(state["root"])
    cfg = config.load(root)

    def expire(*_):
        try:
            with open(str(path) + ".lock", "a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                current = hookio.read_json(path, {})
                if current.get("token") == token and current.get("status") == "pending":
                    current.update(status="timed_out", query="", result=None)
                    context.save(path, current)
            jev._log("context.jsonl", {"event": "timed_out", "session": state.get("session"), "ts": time.time()})
        finally:
            os._exit(0)

    signal.signal(signal.SIGALRM, expire)
    signal.setitimer(signal.ITIMER_REAL, context.bounds(cfg)["timeout_s"])

    def cancelled():
        current = hookio.read_json(path, {})
        return current.get("token") != token or current.get("status") == "cancelled"

    try:
        if not cfg["context"]["enabled"] or not policy.jev_allowed(root, cfg, "context")[0]:
            return
        packet = context.build(root, state["query"], cancelled=cancelled, max_bytes=8000)
        if packet["shown"] and context.fresh(root, packet):
            update(path, token, {"status": "ready", "result": packet})
        else:
            update(path, token, {"status": "empty"})
        record = {k: packet[k] for k in ("files_indexed", "ms", "backend", "requests", "cache", "errors")}
        record.update(ts=time.time(), event="prepared", session=state.get("session"))
        jev._log("context.jsonl", record)
    except Exception as error:
        update(path, token, {"status": "failed", "error": type(error).__name__})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def main(payload):
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    cwd = payload.get("cwd") or os.getcwd()
    root = Path(catalog.root_of(cwd)).resolve()
    if policy.refusal(root) or policy.refusal(project.project_root()):
        return None
    path = hookio.state_file("context", context.digest(str(root) + "\0" + session), ".json")
    event = payload.get("hook_event_name", "")
    cfg = config.load(root)
    if event in ("Stop", "SessionEnd"):
        if payload.get("agent_id"):
            return None
        current = hookio.read_json(path, {})
        update(path, current.get("token"), {"status": "cancelled", "result": None, "query": ""})
        return None
    if event == "UserPromptSubmit":
        prompt = payload.get("prompt")
        previous = hookio.read_json(path, {})
        update(path, previous.get("token"), {"status": "cancelled", "result": None, "query": ""})
        if not isinstance(prompt, str) or not 20 <= len(prompt) <= 2000 or not catalog.eligible(prompt) \
                or len(bm25.tokens(prompt)) < 3 or not cfg["context"]["enabled"] \
                or not policy.jev_allowed(root, cfg, "context")[0]:
            return None
        token = os.urandom(16).hex()
        context.save(path, {"token": token, "root": str(root), "query": policy.redact(prompt),
                            "session": session, "created": time.time(), "status": "pending"})
        subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), "work", str(path), token],
                         cwd=root, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root), JEV_FLUTTER_OUTLINE_NO_BUILD="1"),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return None
    if event not in ("PostToolUse", "SubagentStart") or not cfg["context"]["enabled"] or not policy.jev_allowed(root, cfg, "context")[0]:
        return None
    with open(str(path) + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = hookio.read_json(path, {})
        if state.get("status") != "ready" or time.time() - state.get("created", 0) > 90:
            return None
        packet = state.get("result") or {}
        fresh = context.fresh(root, packet)
        state.update(status="delivered" if fresh else "stale", result=None, query="")
        context.save(path, state)
        jev._log("context.jsonl", {"event": state["status"], "chars": len(packet.get("text", "")), "ts": time.time(),
                                   "session": session, "agent": payload.get("agent_id")})
        if fresh:
            return hookio.context(event, packet["text"])
    return None


if __name__ == "__main__":
    os.umask(0o077)
    if len(sys.argv) == 4 and sys.argv[1] == "work":
        work(Path(sys.argv[2]), sys.argv[3])
    else:
        hookio.run(main, deadline=2)
