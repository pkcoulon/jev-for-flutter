import argparse
import json
import sys
from pathlib import Path

from .. import config, jev, policy, project


def main(argv):
    parser = argparse.ArgumentParser(prog="jev-flutter doctor", description="Vérifier l'installation sans appel réseau.")
    parser.add_argument("--project", help="dossier du projet à vérifier")
    args = parser.parse_args(argv)
    start = Path(args.project).expanduser().resolve() if args.project else project.project_root()
    if not start.is_dir():
        parser.error("dossier introuvable : %s" % start)
    root = next((p for p in (start, *start.parents) if any((p / m).exists() for m in project.ROOT_MARKERS)), start)
    version = json.loads((Path(__file__).resolve().parents[3] / ".claude-plugin/plugin.json").read_text())["version"]
    print("Jev for Flutter %s · diagnostic local, aucun appel facturé" % version)
    print("Projet : %s" % root)
    if sys.version_info < (3, 9) or sys.platform not in ("darwin", "linux"):
        print("À corriger : Python 3.9+ sous macOS, Linux ou WSL est nécessaire.")
        return 1
    denied = policy.refusal(root)
    if denied:
        print("Envoi bloqué par votre politique : %s" % denied)
        return 1
    problems = []
    cfg = config.load(root, problems)
    if problems:
        print("À corriger : " + "; ".join(problems))
        return 1
    allowed, reason = policy.jev_allowed(root, cfg)
    if not cfg["jev"]["enabled"]:
        print('À faire : ajouter "jev": {"enabled": true} dans .claude/jev-for-flutter.json pour autoriser TypeSafe.')
    if not jev.api_key():
        print("À faire : définir TYPESAFE_API_KEY ou enregistrer la clé dans ~/.config/jev-for-flutter/typesafe.key.")
    else:
        print("Clé trouvée ; sa validité auprès de TypeSafe n'est pas testée ici.")
    if allowed:
        print("Prêt pour Jev. Relancez Claude Code après l'installation ou un changement de clé.")
        print("Les lectures ciblées concernent les fichiers Dart de 400 lignes ou plus, jusqu'à 64 Ko.")
    else:
        print("Jev inactif : %s. Les commandes --local restent disponibles." % reason)
    print("Flutter et Dart ne sont pas nécessaires pour démarrer ; le plan de code peut être approximatif.")
    print("Détails : jev-flutter status · Aide : jev-flutter --help")
    return 0 if allowed else 1
