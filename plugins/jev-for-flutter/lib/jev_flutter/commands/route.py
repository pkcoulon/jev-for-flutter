import argparse
import os
import sys
import time
from pathlib import Path

from jev_flutter import catalog, config, jev, memory, policy, project


def fake_warning():
    url = jev.base_url()
    if url != jev.DEFAULT_URL:
        return "attention : Jev servi par %s, pas par l'API officielle ; ces scores ne mesurent aucune qualité." % url
    return None


def _home(path):
    return memory.display(path) if path else "-"


def main(argv):
    argv = list(argv)
    if argv[:1] == ["route"] and len(argv) > 1:
        argv = argv[1:]
    parser = argparse.ArgumentParser(prog="jev-flutter route", description="Simule le routeur mémoire/skill sur un prompt, sans rien injecter ni mémoriser.")
    parser.add_argument("prompt", nargs="+", help="texte du prompt, ou - pour le lire sur stdin")
    parser.add_argument("--project", help="racine du projet (défaut : dossier courant)")
    parser.add_argument("--memory", help="dossier mémoire (défaut : celui du projet dans ~/.claude/projects)")
    parser.add_argument("--local", action="store_true", help="sans Jev : voie rapide et BM25 seulement")
    args = parser.parse_args(argv)

    started = time.monotonic()
    prompt = sys.stdin.read() if args.prompt == ["-"] else " ".join(args.prompt)
    if args.project:
        root = Path(args.project).expanduser().resolve()
        denied = policy.refusal(root)
    else:
        # Same roots as the hook: the current directory's project, and the session's one when Claude runs this.
        cwd = os.getcwd()
        root = None if policy.path_refused(cwd) else catalog.root_of(cwd)
        denied = (policy.refusal(root) if root else "dossier courant exclu par ~/.config/jev-for-flutter/policy.json") or policy.refusal(project.project_root())
    if denied:
        print("jev-flutter route : refusé, %s ; le hook ne fait rien dans ce projet." % denied, file=sys.stderr)
        return 2
    settings = config.load(root)
    router = settings["router"]
    memory_dir = Path(args.memory).expanduser() if args.memory else catalog.default_memory(root)
    cat = catalog.build(root, memory_dir)
    branch = catalog.git_branch(root)
    tickets = catalog.ticket_notes(prompt, branch, cat, settings)
    note_bm25 = catalog.note_index(cat).scores(prompt) if cat["notes"] else []
    skill_bm25 = catalog.skill_index(cat).scores(prompt) if cat["skills"] else []

    print("jev-flutter route : simulation, rien n'est injecté ni mémorisé")
    print("projet  : %s · branche : %s" % (_home(root), branch or "-"))
    refused = ", %d refusée(s) par la politique (non lues, non envoyées)" % cat["notes_refused"] if cat["notes_refused"] else ""
    if cat["memory_refused"]:
        print("mémoire : %s refusée par ~/.config/jev-for-flutter/policy.json, catalogue vide" % _home(memory_dir))
    else:
        print("mémoire : %s · %d fiche(s)%s" % (_home(cat["memory_dir"]), len(cat["notes"]), refused))
    print("skills  : %d invocable(s) par le modèle%s" % (
        len(cat["skills"]), ", %d refusé(s) par la politique" % cat["skills_refused"] if cat["skills_refused"] else ""))
    idle = ("routeur désactivé pour ce projet (router.enabled)" if not router.get("enabled")
            else "prompt ignoré (commande « / » ou moins de 8 caractères)" if not catalog.eligible(prompt)
            else "catalogue vide" if not cat["notes"] and not cat["skills"] else None)
    if idle:
        print("Jev     : non appelé, le hook s'arrête avant")
        print("\nsortie du hook : (rien), %s" % idle)
        return 0

    note_p, skill, errors = {}, None, []
    allowed, reason = (False, "option --local") if args.local else policy.jev_allowed(root, settings, "router")
    if allowed:
        jobs = catalog.requests(prompt, branch, cat, settings)
        if jobs:
            # The hook's conditions, not the CLI's: its timeout and no retry, or the output below would not be the hook's.
            client = catalog.hook_client(settings, "route", started)
            began = time.monotonic()
            results = catalog.judge(client, jobs)
            elapsed = int((time.monotonic() - began) * 1000)
            note_p, skill, errors = catalog.interpret(jobs, results)
            questions = sum(len(q) for _, q in jobs)
            print("Jev     : %s, %d requête(s), %d question(s), %d ms (délai du hook %.1f s, sans nouvel essai)%s" % (
                jev.model_name(settings), len(jobs), questions, elapsed, client.timeout, ", erreurs : %s" % errors if errors else ""))
            if errors and not note_p and any(key != "skill" for _, q in jobs for key in q):
                print("          réponse incomplète : le hook ne retiendrait aucune fiche par Jev (tickets inchangés)")
            warning = fake_warning()
            if warning:
                print(warning)
        else:
            print("Jev     : aucune question à poser (catalogue vide ou routeur désactivé)")
    else:
        print("Jev     : non appelé (%s)" % reason)
    if tickets:
        print("tickets : %s" % ", ".join("%s → %s" % (key, cat["notes"][i]["file"]) for i, key in tickets))

    if cat["notes"]:
        threshold = float(router.get("memory_threshold", 0.8))
        order = sorted(range(len(cat["notes"])), key=lambda i: (-note_p.get(i, -1), -note_bm25[i]))
        rank = {i: r + 1 for r, i in enumerate(sorted(range(len(cat["notes"])), key=lambda i: -note_bm25[i]))}
        width = min(48, max(len(n["file"]) for n in cat["notes"]))
        print("\n%-*s  %7s  %6s  %4s" % (width, "fiche", "Jev p", "BM25", "rang"))
        for i in order:
            p = note_p.get(i)
            mark = " *" if p is not None and p >= threshold else ("  " if p is not None else "")
            print("%-*s  %7s  %6.2f  %4d" % (width, catalog.clean(cat["notes"][i]["file"], width),
                                             ("%.2f" % p + mark) if p is not None else "-", note_bm25[i], rank[i]))
        print("(* : p ≥ %.2f ; le hook en garde %d au plus, hors tickets et fiches déjà suggérées)" % (threshold, int(router.get("max_notes", 3))))

    if cat["skills"]:
        probabilities = skill["probabilities"] if skill else {}
        order = sorted(range(len(cat["skills"])), key=lambda i: (-probabilities.get("s%d" % i, -1), -skill_bm25[i]))
        rank = {i: r + 1 for r, i in enumerate(sorted(range(len(cat["skills"])), key=lambda i: -skill_bm25[i]))}
        width = min(48, max(len(s["name"]) for s in cat["skills"]))
        print("\n%-*s  %7s  %6s  %4s" % (width, "skill", "Jev p", "BM25", "rang"))
        for i in order:
            p = probabilities.get("s%d" % i)
            print("%-*s  %7s  %6.2f  %4d" % (width, catalog.clean(cat["skills"][i]["name"], width),
                                             "%.2f" % p if p is not None else "-", skill_bm25[i], rank[i]))
        if skill:
            if "none" in probabilities:
                print("%-*s  %7.2f" % (width, "(aucun)", probabilities["none"]))
            name = "aucun" if skill["choice"] == "none" else cat["skills"][int(skill["choice"][1:])]["name"]
            gates = []
            if skill["p"] < catalog.SKILL_MIN_P:
                gates.append("p < %.2f" % catalog.SKILL_MIN_P)
            if skill["confidence"] < float(router.get("skill_confidence", 0.8)):
                gates.append("confiance < %.2f" % float(router.get("skill_confidence", 0.8)))
            verdict = "écarté (%s)" % ", ".join(gates) if gates and skill["choice"] != "none" else ("retenu" if skill["choice"] != "none" else "rien")
            print("choix Jev : %s, p=%.2f, confiance %.2f → %s" % (name, skill["p"], skill["confidence"], verdict))

    chosen, pick = catalog.select(settings, cat, note_p, skill, tickets, {})
    text, shown, shown_pick = catalog.render(cat, chosen, pick)
    dropped = len(chosen) - len(shown) + (1 if pick and not shown_pick else 0)
    if note_p and catalog.abstains(settings, note_p):
        print("abstention : trop de fiches au-dessus du seuil, aucune retenue par Jev")
    print("\nsortie du hook (session neuve, %d caractères%s) :" % (len(text), ", %d suggestion(s) retirée(s) faute de place" % dropped if dropped else ""))
    print(text or "(rien)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
