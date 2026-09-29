import argparse
import asyncio
import json
import os
import signal
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "lib"))
from dartlens import config, policy

PROTOCOLS = ("2025-11-25", "2025-06-18", "2024-11-05")
TOOL = {
    "name": "find_code",
    "description": (
        "Find Dart/Flutter code by what it does when the file or symbol name is unknown. "
        "Use before broad file exploration for questions such as where a behavior is implemented. "
        "Describe one behavior, preferably in English; use Grep for a known symbol or literal. "
        "Returns ranked files, symbols and line numbers, with uncertainty and exclusions shown. "
        "Results are starting points, not a complete flow or proof of absence. "
        "Read the code and follow calls and data conversions to cover each part of the user's question before answering. "
        "Uses Jev (TypeSafe) only in enabled projects, otherwise reports local keyword matching."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 1000,
                      "description": "The behavior to locate, without guessing file or symbol names."},
            "path": {"type": "string", "default": ".",
                     "description": "File or directory relative to the current project; narrow it if known."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 10,
                      "description": "Number of results; the project setting (5 by default) applies otherwise."},
            "include_tests": {"type": "boolean", "default": False},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": True},
}


def offered(root):
    return config.load(root)["find"].get("mcp") is True and not os.environ.get("DARTLENS_LENS_DISABLE")


def result(text, error=False):
    return {"content": [{"type": "text", "text": text}], "isError": error}


async def stop(process):
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        await asyncio.wait_for(process.wait(), 2)
    except asyncio.TimeoutError:
        os.killpg(process.pid, signal.SIGKILL)
        await process.wait()
    except ProcessLookupError:
        await process.wait()


async def find_code(root, arguments):
    if not isinstance(arguments, dict) or set(arguments) - set(TOOL["inputSchema"]["properties"]):
        return result("Expected query, optional path, limit and include_tests.", True)
    query, path = arguments.get("query"), arguments.get("path", ".")
    limit, tests = arguments.get("limit"), arguments.get("include_tests", False)
    if not isinstance(query, str) or not query.strip() or len(query) > 1000 or "\0" in query:
        return result("query must contain 1 to 1000 characters.", True)
    if not isinstance(path, str) or not path.strip() or "\0" in path:
        return result("path must be a file or directory inside the current project.", True)
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 10) or type(tests) is not bool:
        return result("limit must be an integer from 1 to 10; include_tests must be a boolean.", True)
    denied = policy.refusal(root)
    if denied or not offered(root):
        return result("dartlens search is disabled for this project. Use the ordinary search tools.", True)
    target = (root / path).resolve()
    if not policy.sendable(target, root) or policy.refusal(target if target.is_dir() else target.parent):
        return result("Search is restricted to permitted paths inside the current project.", True)
    if not target.exists():
        return result("Search path does not exist. Check its name with Glob.", True)
    cfg = config.load(root)
    if any(part.startswith(".") for part in target.relative_to(root).parts) \
            or target.is_file() and target.suffix != ".dart":
        return result("Search is restricted to Dart code inside the current project.", True)
    command = [sys.executable, "-B", str(PLUGIN / "bin" / "lens"), "find", "--project-only"]
    if limit:
        command += ["--top", str(limit)]
    if tests:
        command.append("--tests")
    command += ["--", query, str(target)]
    process = await asyncio.create_subprocess_exec(
        *command, cwd=root, env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root), DARTLENS_OUTLINE_NO_BUILD="1"),
        stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), min(120, max(1, cfg["jev"]["cli_timeout_s"]) + 15))
    except asyncio.TimeoutError:
        await stop(process)
        return result("dartlens search timed out. Continue with Grep, Glob and Read.", True)
    except asyncio.CancelledError:
        await stop(process)
        raise
    text = stdout.decode("utf-8", "replace").strip()
    if process.returncode and not text:
        text = "dartlens search failed. Continue with Grep, Glob and Read."
        if stderr:
            text += "\n" + stderr.decode("utf-8", "replace")[-1000:]
    if len(text) > 16000:
        text = text[:16000] + "\n-- output truncated; narrow the search path."
    return result(text or "No search result returned. Continue with Grep or Glob.", process.returncode != 0)


def send(key, value, error=False):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": key, "error" if error else "result": value}) + "\n")
    sys.stdout.flush()


async def serve(root):
    loop = asyncio.get_running_loop()
    current = asyncio.current_task()
    for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        loop.add_signal_handler(signum, current.cancel)
    reader = asyncio.StreamReader(limit=1 << 20)
    transport, _ = await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    active, ready, initialized, oversized = {}, False, False, False
    slots = asyncio.Semaphore(2)
    version = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())["version"]

    async def call(key, arguments):
        try:
            async with slots:
                value = await find_code(root, arguments)
            send(key, value)
        except Exception as error:
            print("dartlens MCP search failed: %s" % type(error).__name__, file=sys.stderr)
            send(key, result("dartlens search is unavailable. Continue with the ordinary search tools.", True))
        finally:
            active.pop(key, None)

    try:
        while True:
            try:
                raw = await reader.readline()
            except ValueError as error:
                if not oversized:
                    send(None, {"code": -32700, "message": "Message too large"}, True)
                oversized = "not found" in str(error)
                continue
            if not raw:
                break
            if oversized:
                oversized = False
                continue
            try:
                message = json.loads(raw)
            except (ValueError, UnicodeError):
                send(None, {"code": -32700, "message": "Invalid JSON"}, True)
                continue
            if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" \
                    or not isinstance(message.get("method"), str):
                send(None, {"code": -32600, "message": "Invalid request"}, True)
                continue
            method, params, key = message["method"], message.get("params", {}), message.get("id")
            if "id" not in message:
                if method == "notifications/initialized" and initialized:
                    ready = True
                elif method == "notifications/cancelled" and isinstance(params, dict):
                    cancelled = params.get("requestId")
                    if isinstance(cancelled, (str, int)) and cancelled in active:
                        active[cancelled].cancel()
                continue
            if type(key) not in (str, int) or key in active:
                send(None, {"code": -32600, "message": "Invalid request id"}, True)
            elif not isinstance(params, dict):
                send(key, {"code": -32602, "message": "Invalid params"}, True)
            elif method == "initialize" and not initialized:
                protocol = params.get("protocolVersion")
                send(key, {"protocolVersion": protocol if protocol in PROTOCOLS else PROTOCOLS[0],
                           "capabilities": {"tools": {"listChanged": False}},
                           "serverInfo": {"name": "dartlens", "version": version}})
                initialized = True
            elif method == "ping":
                send(key, {})
            elif not ready:
                send(key, {"code": -32600, "message": "Initialize the connection first"}, True)
            elif method == "tools/list":
                send(key, {"tools": [TOOL] if not policy.refusal(root) and offered(root) else []})
            elif method == "tools/call":
                if params.get("name") != TOOL["name"]:
                    send(key, {"code": -32602, "message": "Unknown tool"}, True)
                else:
                    active[key] = asyncio.create_task(call(key, params.get("arguments", {})))
            else:
                send(key, {"code": -32601, "message": "Method not found"}, True)
    finally:
        pending = list(active.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        transport.close()


def main():
    parser = argparse.ArgumentParser(description="dartlens code search over MCP stdio")
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args()
    root = args.project.resolve()
    if not root.is_dir():
        parser.error("project directory does not exist")
    try:
        asyncio.run(serve(root))
    except (asyncio.CancelledError, BrokenPipeError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
