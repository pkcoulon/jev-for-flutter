import json
import os


def reverse_lines(path, chunk_size=1 << 16):
    with open(path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        remainder = b""
        while position > 0:
            step = min(chunk_size, position)
            position -= step
            handle.seek(position)
            block = handle.read(step) + remainder
            lines = block.split(b"\n")
            remainder = lines.pop(0)
            for line in reversed(lines):
                if line.strip():
                    yield line.decode("utf-8", "replace")
        if remainder.strip():
            yield remainder.decode("utf-8", "replace")


def reverse_entries(path):
    for line in reverse_lines(path):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def is_human_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isCompactSummary"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content.strip()
    elif isinstance(content, list):
        if any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
            return False
        text = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
    else:
        return False
    if not text:
        return False
    return not text.startswith(("<command-name>", "<local-command", "<task-notification>", "[Request interrupted"))


def current_turn(path):
    turn = []
    for entry in reverse_entries(path):
        if is_human_prompt(entry):
            break
        turn.append(entry)
    turn.reverse()
    return turn


def tool_uses(entries):
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        for block in (entry.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                yield block.get("name"), block.get("input") or {}


def last_usage(path):
    for entry in reverse_entries(path):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message") or {}
        usage = message.get("usage")
        if not usage or message.get("model") == "<synthetic>":
            continue
        context = sum(int(usage.get(k) or 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
        return entry.get("timestamp"), context
    return None, 0
