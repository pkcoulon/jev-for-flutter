import argparse
import json
import re
import sys
import threading
import time
from collections import Counter
from pathlib import Path

from dartlens import catalog, config, jev, memory, policy, transcript
from dartlens.commands.route import fake_warning

WINDOW = 30
KS = (1, 3, 5)
JEV_THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9)
BM25_THRESHOLDS = (1.0, 2.0, 4.0, 6.0)
READ_COMMAND = re.compile(r"(?:^|[;&|(]|\s)(?:cat|sed|head|tail|less|bat|nl)\s[^;&|]*?memory/([\w.@-]+\.md)")
SHELL_ECHO = ("<bash-input>", "<bash-stdout>", "<bash-stderr>")
COMMAND_ECHO = ("<command-message>", "<command-name>")


def _prompt_text(entry):
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def _echo(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return None
    text = _prompt_text(entry).lstrip()
    return "command" if text.startswith(COMMAND_ECHO) else "shell" if text.startswith(SHELL_ECHO) else None


def _tool_traffic(entry):
    content = (entry.get("message") or {}).get("content")
    return entry.get("type") == "assistant" or (
        isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content))


def _cwd_refused(cwd, verdicts):
    if cwd not in verdicts:
        # path_refused first: nothing under a refused path is looked at, not even its .git.
        verdicts[cwd] = policy.path_refused(cwd) or bool(policy.refusal(catalog.root_of(cwd)))
    return verdicts[cwd]


class _Measured(jev.Client):
    # Records, per request, the attempts and the last one's duration: the hook makes one attempt within its own timeout.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.local, self.runs = threading.local(), {}

    def _post(self, body):
        self.local.attempts += 1
        began = time.monotonic()
        try:
            return super()._post(body)
        finally:
            self.local.seconds = time.monotonic() - began

    def ask(self, state, questions):
        self.local.attempts, self.local.seconds = 0, 0.0
        try:
            return super().ask(state, questions)
        finally:
            self.runs[id(state)] = (self.local.attempts, self.local.seconds)


def _read_notes(name, tool_input):
    if name == "Read":
        path = tool_input.get("file_path")
        if isinstance(path, str) and "/memory/" in path and path.endswith(".md"):
            yield Path(path).name
    elif name == "Bash" and isinstance(tool_input.get("command"), str):
        for match in READ_COMMAND.finditer(tool_input["command"]):
            yield match.group(1)


def collect(directory, cat):
    notes, skills = {n["file"] for n in cat["notes"]}, {s["name"] for s in cat["skills"]}
    samples, outside, verdicts = [], Counter(), {}
    for path in sorted(directory.glob("*.jsonl")):
        if not path.is_file():
            continue
        # Checked per file, links resolved: a transcript linked from a refused area is neither read nor sent.
        if policy.path_refused(path):
            outside["refused"] += 1
            continue
        current, cwd = None, None
        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                routed = catalog.ROUTED_MARK in line
                if not routed and '"user"' not in line and '"tool_use"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("isSidechain"):
                    continue
                cwd = entry.get("cwd") if isinstance(entry.get("cwd"), str) else cwd
                # Reading dartlens' own source or output in a tool call is not a suggestion made to this prompt.
                routed = routed and not _tool_traffic(entry)
                echo = _echo(entry)
                if echo:
                    # A slash command closes the previous prompt's window, as a prompt the hook skips; bash mode (!) does not.
                    if echo == "command":
                        current = None
                    continue
                if transcript.is_human_prompt(entry):
                    text = _prompt_text(entry)
                    current = None
                    # A prompt typed in a refused project, its branch included, is neither sampled nor sent.
                    if cwd and _cwd_refused(cwd, verdicts):
                        outside["refused_cwd"] += 1
                        continue
                    if catalog.eligible(text):
                        current = {"prompt": text, "branch": entry.get("gitBranch") or "", "ts": entry.get("timestamp") or "",
                                   "notes": set(), "skills": set(), "calls": 0, "routed": routed}
                        samples.append(current)
                    continue
                if current is None:
                    continue
                # A read that follows a router suggestion is not an independent label.
                if routed:
                    current["routed"] = True
                for name, tool_input in transcript.tool_uses([entry]):
                    if current["calls"] >= WINDOW:
                        break
                    current["calls"] += 1
                    for file in _read_notes(name, tool_input):
                        if file.lower() == "memory.md":
                            continue
                        if file in notes:
                            current["notes"].add(file)
                        else:
                            outside["notes"] += 1
                    if name == "Skill":
                        skill = tool_input.get("skill")
                        if skill in skills:
                            current["skills"].add(skill)
                        else:
                            outside["skills"] += 1
    samples.sort(key=lambda s: s["ts"])
    return samples, outside


def _counts(counter):
    return ", ".join("%s ×%d" % item for item in counter.most_common())


def _ratio(a, b):
    return "%.2f" % (a / b) if b else "  - "


def _ranked(scores, files, positive_only=False):
    pairs = sorted(((s, i) for i, s in scores.items() if not positive_only or s > 0), key=lambda x: -x[0])
    return [files[i] for _, i in pairs]


def main(argv):
    argv = list(argv)
    while argv[:1] and argv[0] in ("eval", "router"):
        argv = argv[1:]
    parser = argparse.ArgumentParser(prog="dartlens eval router", description="Compare Jev et BM25 sur les fiches mémoire et skills réellement utilisés dans les transcripts du projet.")
    parser.add_argument("--project", required=True, help="racine du projet")
    parser.add_argument("--limit", type=int, default=50, help="prompts étiquetés gardés, autant de prompts sans étiquette (défaut 50)")
    parser.add_argument("--transcripts", help="dossier des transcripts (défaut : ~/.claude/projects/<projet>)")
    parser.add_argument("--memory", help="dossier mémoire (défaut : <transcripts>/memory)")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit doit valoir au moins 1")

    root = Path(args.project).expanduser().resolve()
    denied = policy.refusal(root)
    if denied:
        print("dartlens eval router : refusé, %s." % denied, file=sys.stderr)
        return 2
    settings = config.load(root)
    router = settings["router"]
    allowed, reason = policy.jev_allowed(root, settings, "router")
    if not allowed:
        print("dartlens eval router : refusé, %s." % reason, file=sys.stderr)
        return 2
    directory = Path(args.transcripts).expanduser() if args.transcripts else catalog.transcripts_dir(root)
    if not directory or not directory.is_dir():
        print("dartlens eval router : aucun transcript pour ce projet (utilise --transcripts).", file=sys.stderr)
        return 2
    if policy.path_refused(directory):
        print("dartlens eval router : refusé, transcripts exclus par ~/.config/dartlens/policy.json.", file=sys.stderr)
        return 2
    cat = catalog.build(root, Path(args.memory).expanduser() if args.memory else directory / "memory")
    if not cat["notes"] and not cat["skills"]:
        print("dartlens eval router : catalogue vide (mémoire absente ou refusée, aucun skill).", file=sys.stderr)
        return 1

    started = time.monotonic()
    samples, outside = collect(directory, cat)
    routed = sum(1 for s in samples if s["routed"])
    samples = [s for s in samples if not s["routed"]]
    labelled = [s for s in samples if s["notes"] or s["skills"]]
    others = [s for s in samples if not (s["notes"] or s["skills"])]
    chosen = labelled[-args.limit:] + others[-args.limit:]
    print("dartlens eval router · projet %s · transcripts %s" % (memory.display(root), memory.display(directory)))
    warning = fake_warning()
    if warning:
        print(warning.replace("ces scores", "ces chiffres"))
    print("catalogue : %d fiches (%s), %d skills" % (
        len(cat["notes"]), "mémoire refusée" if cat["memory_refused"] else memory.display(cat["memory_dir"]) if cat["memory_dir"] else "pas de mémoire", len(cat["skills"])))
    print("prompts éligibles : %d · avec fiche lue : %d · avec skill invoqué : %d · lectures hors catalogue : %d fiche(s), %d skill(s)" % (
        len(samples), sum(1 for s in samples if s["notes"]), sum(1 for s in samples if s["skills"]), outside["notes"], outside["skills"]))
    if routed or outside["refused"] or outside["refused_cwd"]:
        print("exclus : %d prompt(s) influencé(s) par le routeur (étiquettes non indépendantes), %d transcript(s) refusé(s) par la politique, "
              "%d prompt(s) tapé(s) dans un projet refusé (non envoyés)" % (routed, outside["refused"], outside["refused_cwd"]))
    if not labelled:
        print("aucun prompt étiqueté : rien à mesurer.")
        return 1

    jobs, owners = [], []
    for index, sample in enumerate(chosen):
        for job in catalog.requests(sample["prompt"], sample["branch"], cat, settings):
            jobs.append(job)
            owners.append(index)
    began = time.monotonic()
    client = _Measured(settings, "eval-router")
    results = catalog.judge(client, jobs, workers=args.workers) if jobs else []
    jev_seconds = time.monotonic() - began
    budget = min(float(settings["jev"]["hook_timeout_s"]), catalog.JEV_BUDGET_S)
    grouped = [([], []) for _ in chosen]
    for owner, job, result in zip(owners, jobs, results):
        grouped[owner][0].append(job)
        grouped[owner][1].append(result)
    note_bm25, skill_bm25 = catalog.note_index(cat), catalog.skill_index(cat)
    files = [n["file"] for n in cat["notes"]]
    names = [s["name"] for s in cat["skills"]]
    failures, kept, late = Counter(), [], 0
    for sample, (sample_jobs, sample_results) in zip(chosen, grouped):
        sample["note_p"], sample["skill"], errors = catalog.interpret(sample_jobs, sample_results)
        if errors:
            failures.update(("HTTP %d" % e) if isinstance(e, int) else e for e in errors)
            continue
        sample["bm25"] = dict(enumerate(note_bm25.scores(sample["prompt"]))) if files else {}
        sample["skill_bm25"] = skill_bm25.scores(sample["prompt"]) if names else []
        sample["tokens"] = sum(jev.estimate_tokens(state) + jev.estimate_tokens(questions) for state, questions in sample_jobs)
        tickets = catalog.ticket_notes(sample["prompt"], sample["branch"], cat, settings)
        # A request the hook would not have got back in one attempt within its timeout leaves it with the tickets only.
        in_time = all(client.runs.get(id(state), (0, 0.0))[0] == 1 and client.runs[id(state)][1] <= budget for state, _ in sample_jobs)
        late += not in_time
        picked, pick = catalog.select(settings, cat, sample["note_p"] if in_time else {}, sample["skill"] if in_time else None, tickets, {})
        text, shown, shown_pick = catalog.render(cat, picked, pick)
        sample["hook_notes"] = {files[i] for i, _ in shown}
        sample["hook_skill"] = names[shown_pick[0]] if shown_pick else None
        sample["injected"] = len(text)
        kept.append(sample)
    positives = [s for s in kept if s["notes"]]
    reads = sum(len(s["notes"]) for s in positives)
    print("échantillon : %d prompts étiquetés + %d sans étiquette · %d requête(s) Jev en %.1f s · %d prompt(s) en erreur, exclus%s" % (
        sum(1 for s in chosen if s["notes"] or s["skills"]), sum(1 for s in chosen if not (s["notes"] or s["skills"])), len(jobs), jev_seconds,
        len(chosen) - len(kept), " (%s)" % _counts(failures) if failures else ""))
    if not kept:
        print("rien mesuré : aucune réponse exploitable de Jev%s." % (" (%s)" % _counts(failures) if failures else ""))
        return 1

    if positives:
        print("\nrappel des fiches lues (%d lectures, %d prompts)" % (reads, len(positives)))
        print("          " + "".join("   @%d " % k for k in KS))
        for label, key, strict in (("Jev", "note_p", False), ("BM25", "bm25", True)):
            cells = []
            for k in KS:
                hits = sum(len(s["notes"] & set(_ranked(s[key], files, strict)[:k])) for s in positives)
                cells.append(" %5s" % _ratio(hits, reads))
            print("%-9s%s" % (label, "".join(cells)))
        print("\n%-22s %7s %10s %14s" % ("seuil", "rappel", "précision", "fiches/prompt"))
        for label, key, thresholds in (("Jev p ≥ %.2f", "note_p", JEV_THRESHOLDS), ("BM25 ≥ %.1f", "bm25", BM25_THRESHOLDS)):
            for t in thresholds:
                selected = [{files[i] for i, v in s[key].items() if v >= t} for s in kept]
                hits = sum(len(s["notes"] & chosen_files) for s, chosen_files in zip(kept, selected))
                count = sum(len(x) for x in selected)
                print("%-22s %7s %10s %14.2f" % (label % t, _ratio(hits, reads), _ratio(hits, count), count / len(kept)))
        hook_hits = sum(len(s["notes"] & s["hook_notes"]) for s in kept)
        hook_count = sum(len(s["hook_notes"]) for s in kept)
        print("\nhook tel que configuré (p ≥ %.2f, %d fiches au plus, tickets inclus) : rappel %s, précision %s" % (
            float(router.get("memory_threshold", 0.8)), int(router.get("max_notes", 3)), _ratio(hook_hits, reads), _ratio(hook_hits, hook_count)))
    if late:
        print("hook : %d/%d prompt(s) sans réponse de Jev en un essai sous %.1f s ; comptés avec les seuls tickets" % (late, len(kept), budget))

    with_skill = [s for s in kept if s["skills"]]
    without = [s for s in kept if not s["skills"]]
    if names:
        def top_choice(s):
            probabilities = s["skill"]["probabilities"] if s["skill"] else {}
            best = max(probabilities, key=probabilities.get) if probabilities else "none"
            return None if best == "none" else names[int(best[1:])]

        def bm25_top(s, minimum=0.0):
            if not s["skill_bm25"]:
                return None
            best = max(range(len(names)), key=lambda i: s["skill_bm25"][i])
            return names[best] if s["skill_bm25"][best] > minimum else None

        print("\nskills : %d prompt(s) avec skill invoqué, %d sans" % (len(with_skill), len(without)))
        if with_skill:
            print("  bon skill : Jev retenu %d/%d, Jev top-1 %d/%d, BM25 top-1 %d/%d" % (
                sum(1 for s in with_skill if s["hook_skill"] in s["skills"]), len(with_skill),
                sum(1 for s in with_skill if top_choice(s) in s["skills"]), len(with_skill),
                sum(1 for s in with_skill if bm25_top(s) in s["skills"]), len(with_skill)))
        if without:
            print("  suggestion sans invocation : Jev retenu %d/%d, BM25 score > 2 %d/%d" % (
                sum(1 for s in without if s["hook_skill"]), len(without), sum(1 for s in without if bm25_top(s, 2.0)), len(without)))

    injected = [s["injected"] for s in kept]
    print("\ncoûts (après le rappel) : injection non vide sur %d/%d prompts, %d caractères en moyenne quand non vide (max %d) ; "
          "entrée Jev estimée %d tokens par prompt (3 caractères/token)" % (
              sum(1 for v in injected if v), len(kept), sum(injected) / max(1, sum(1 for v in injected if v)), max(injected or [0]),
              sum(s["tokens"] for s in kept) / max(1, len(kept))))
    print("limites : étiquettes implicites (fiche lue ou skill invoqué dans les %d appels suivants). Une fiche utile déjà en contexte n'est pas comptée, "
          "la précision est donc sous-estimée ; le rappel ne porte que sur les fiches effectivement lues. Durée totale %.1f s." % (
              WINDOW, time.monotonic() - started))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
