import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_URL = "https://api.typesafe.ai"
KEY_ENV = ("TYPESAFE_API_KEY", "TYPE_SAFE_AI_KEY", "TYPESAFE_AI_API_KEY")
KEY_FILE = Path.home() / ".config" / "dartlens" / "typesafe.key"
STATE_DIR = Path(os.environ.get("DARTLENS_STATE_DIR") or Path.home() / ".cache" / "dartlens")
# Jev accepts 32k tokens for state + longest question; stay well under with a conservative estimate.
STATE_TOKEN_BUDGET = 24000
CHARS_PER_TOKEN = 3.0
MAX_OPTIONS = 255
MIN_INTERVAL = 0.05
BREAKER_FAILURES = 3
BREAKER_COOLDOWN = 300


class JevError(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status

    @property
    def kind(self):
        if self.status:
            return "HTTP %d" % self.status
        return "réseau: délai dépassé" if "timed out" in str(self) else "réseau"


class JevUnavailable(JevError):
    pass


def api_key():
    for name in KEY_ENV:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    try:
        return KEY_FILE.read_text().strip() or None
    except OSError:
        return None


def base_url():
    return os.environ.get("DARTLENS_JEV_URL", DEFAULT_URL).rstrip("/")


def model_name(config):
    return os.environ.get("DARTLENS_JEV_MODEL") or config["jev"]["model"]


def estimate_tokens(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return int(len(text) / CHARS_PER_TOKEN) + 1


def noul(instructions, true=None, false=None):
    question = {"type": "noul", "instructions": instructions}
    if true or false:
        question["criteria"] = {"true": true or "Yes", "false": false or "No"}
    return question


def choice(instructions, options):
    if not 2 <= len(options) <= MAX_OPTIONS:
        raise ValueError("choice needs 2 to %d options" % MAX_OPTIONS)
    return {"type": "choice", "instructions": instructions, "criteria": options}


def score(instructions, levels):
    if not 2 <= len(levels) <= 10:
        raise ValueError("score needs 2 to 10 levels")
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


def _log(name, record):
    if os.environ.get("DARTLENS_BENCH_RUN"):
        record["run"] = os.environ["DARTLENS_BENCH_RUN"]
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_DIR / name, "a") as handle:
            handle.write(json.dumps(record) + "\n")
    except OSError:
        pass


class Breaker:
    def __init__(self, path):
        self.path = Path(path)

    def _read(self):
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {"failures": 0, "last": 0}

    def is_open(self):
        data = self._read()
        return data["failures"] >= BREAKER_FAILURES and time.time() - data["last"] < BREAKER_COOLDOWN

    def record(self, ok):
        data = {"failures": 0, "last": 0} if ok else self._read()
        if not ok:
            data = {"failures": data["failures"] + 1, "last": time.time()}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data))
        except OSError:
            pass


class Client:
    def __init__(self, config, tool, timeout=None, retries=None, use_breaker=False):
        self.key = api_key()
        self.model = model_name(config)
        self.tool = tool
        interactive = not use_breaker
        self.timeout = timeout or (config["jev"]["cli_timeout_s"] if interactive else config["jev"]["hook_timeout_s"])
        self.retries = (2 if interactive else 0) if retries is None else retries
        self.breaker = Breaker(STATE_DIR / "breaker.json") if use_breaker else None
        self._lock = threading.Lock()
        self._next = 0.0

    def _reserve(self):
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + MIN_INTERVAL
        if wait:
            time.sleep(wait)

    def _post(self, body):
        request = urllib.request.Request(
            base_url() + "/v1/systemone",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")[:300]
            raise JevError("HTTP %d: %s" % (error.code, detail), error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            raise JevError("réseau: %s" % error, 0) from None

    def ask(self, state, questions):
        reason = "clé TypeSafe absente" if not self.key else (
            "Jev en pause après plusieurs échecs" if self.breaker and self.breaker.is_open() else None)
        if reason:
            _log("usage.jsonl", {"ts": time.time(), "tool": self.tool, "error": "indisponible", "reason": reason,
                                 "attempts": 0})
            raise JevUnavailable(reason)
        body = {"model": self.model, "state": state, "questions": questions}
        attempt = 0
        began = time.monotonic()
        while True:
            self._reserve()
            started = time.monotonic()
            try:
                result = self._post(body)
                answers = result.get("answers") if isinstance(result, dict) else None
                if not isinstance(answers, dict):
                    raise JevError("réponse invalide", 0)
                now = time.monotonic()
                _log("usage.jsonl", {
                    "ts": time.time(), "tool": self.tool, "questions": len(questions),
                    "input_tokens": (result.get("usage") or {}).get("input_tokens"),
                    "ms": int((now - started) * 1000), "model": result.get("model"),
                    "total_ms": int((now - began) * 1000), "attempts": attempt + 1,
                })
                if self.breaker:
                    self.breaker.record(True)
                return answers
            except JevError as error:
                retryable = error.status in (0, 429, 500, 502, 503, 504, 529)
                if attempt >= self.retries or not retryable:
                    now = time.monotonic()
                    _log("usage.jsonl", {
                        "ts": time.time(), "tool": self.tool, "error": error.kind, "status": error.status,
                        "ms": int((now - started) * 1000), "total_ms": int((now - began) * 1000),
                        "attempts": attempt + 1,
                    })
                    if self.breaker:
                        self.breaker.record(False)
                    raise
                attempt += 1
                time.sleep((0.5 * 2 ** attempt) * (1 + random.random() / 2))

    def ask_many(self, jobs, workers=8):
        def run(job):
            try:
                return self.ask(*job)
            except JevError as error:
                return error
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            return list(pool.map(run, jobs))


def probability(answer):
    if not isinstance(answer, dict):
        return None
    if answer.get("type") == "noul" or "noul" in answer:
        return answer.get("noul")
    return answer.get("confidence")
