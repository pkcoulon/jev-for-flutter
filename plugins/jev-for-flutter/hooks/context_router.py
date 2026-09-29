#!/usr/bin/env python3
import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
try:
    from jev_flutter import catalog, config, hookio, jev, memory, policy, project
except Exception:
    sys.exit(0)

EVENT = "UserPromptSubmit"
# Its own breaker: router outages do not pause the guard, and a prompt counts once however many requests it needed.
BREAKER = "breaker-router.json"


def main(payload):
    started = time.monotonic()
    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not catalog.eligible(prompt):
        return None
    cwd, transcript_path = payload.get("cwd") or os.getcwd(), payload.get("transcript_path")
    # A refused project is left alone: neither its config, its skills nor its memory are read.
    # Both the directory Claude is in and the one the session started from count.
    if policy.path_refused(cwd) or (transcript_path and policy.path_refused(transcript_path)):
        return None
    root = catalog.root_of(cwd)
    if any(policy.refusal(r) for r in {root, project.project_root()}):
        return None
    settings = config.load(root)
    if not settings["router"].get("enabled"):
        return None
    cat = catalog.build(root, memory.directory(transcript_path))
    if not cat["notes"] and not cat["skills"]:
        return None
    state_path = hookio.state_file("router", payload.get("session_id"), ".json")
    seen = hookio.read_json(state_path, {})
    seen = seen if isinstance(seen, dict) else {}
    branch = catalog.git_branch(root)
    tickets = catalog.ticket_notes(prompt, branch, cat, settings)
    allowed, _ = policy.jev_allowed(root, settings, "router")
    note_p, skill, errors, jev_ms, sent, asked_notes, mode = {}, None, [], 0, 0, 0, "local"
    if allowed:
        seen_notes = set(seen.get("notes") or [])
        skip = {i for i, note in enumerate(cat["notes"]) if note["file"] in seen_notes}
        jobs = catalog.requests(prompt, branch, cat, settings, skip_notes=skip)
        asked_notes = sum(1 for _, questions in jobs for key in questions if key != "skill")
        breaker = jev.Breaker(jev.STATE_DIR / BREAKER)
        if jobs and breaker.is_open():
            errors, mode = ["breaker"], "paused"
        elif jobs:
            client = catalog.hook_client(settings, "router", started)
            began = time.monotonic()
            try:
                results = catalog.judge(client, jobs)
            except hookio.Deadline:
                # Too slow is a failure like any other: logged, counted by the breaker, tickets still shown.
                results = [hookio.Deadline()] * len(jobs)
            jev_ms = int((time.monotonic() - began) * 1000)
            note_p, skill, errors = catalog.interpret(jobs, results)
            breaker.record(any(not isinstance(result, Exception) for result in results))
            sent, mode = len(jobs), "jev"
    chosen, pick = catalog.select(settings, cat, note_p, skill, tickets, seen)
    text, shown, shown_pick = catalog.render(cat, chosen, pick)
    top = sorted(note_p.items(), key=lambda item: -item[1])[:5]
    catalog.log({
        "session": payload.get("session_id"),
        "mode": mode,
        "candidates": [len(cat["notes"]), len(cat["skills"])],
        "requests": sent,
        "errors": errors,
        "partial": bool(errors),
        "asked": asked_notes,
        "abstained": "error" if asked_notes and not note_p else "flat" if catalog.abstains(settings, note_p) else None,
        "top": [[cat["notes"][i]["file"], round(p, 3)] for i, p in top],
        "skill": [cat["skills"][int(skill["choice"][1:])]["name"] if skill["choice"] != "none" else "none",
                  round(skill["p"], 3), round(skill["confidence"], 3)] if skill else None,
        "kept": [cat["notes"][i]["file"] for i, _ in shown] + (["skill:" + cat["skills"][shown_pick[0]]["name"]] if shown_pick else []),
        "dropped": len(chosen) - len(shown) + (1 if pick and not shown_pick else 0),
        "tickets": len(tickets),
        "jev_ms": jev_ms,
        "ms": int((time.monotonic() - started) * 1000),
    })
    if not text:
        return None
    # Once the state says "suggested", the output must reach stdout: no deadline between the two.
    if hasattr(signal, "SIGALRM"):
        signal.setitimer(signal.ITIMER_REAL, 0)
    catalog.remember(state_path, seen, cat, shown, shown_pick)
    return hookio.context(EVENT, text)


if __name__ == "__main__":
    hookio.run(main, deadline=4)
