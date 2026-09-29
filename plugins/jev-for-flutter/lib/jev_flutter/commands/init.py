import argparse
import json
import os
import tempfile
from pathlib import Path

from .. import config, policy, project


def main(argv):
    parser = argparse.ArgumentParser(prog="jev-flutter init", description="Activer Jev pour ce projet sans écraser ses réglages.")
    parser.add_argument("--enable-jev", action="store_true", required=True, help="autoriser l'envoi de code à TypeSafe")
    args = parser.parse_args(argv)
    root = project.project_root()
    refused = policy.refusal(root)
    if refused:
        parser.exit(1, "Activation refusée : %s\n" % refused)
    target = root / config.CONFIG_FILES[0]
    if root not in target.resolve().parents:
        parser.exit(1, "Configuration hors du projet : aucune écriture.\n")
    source = next((root / n for n in config.CONFIG_FILES if (root / n).is_file()), None)
    try:
        data = json.loads(source.read_text()) if source else {}
        if not isinstance(data, dict) or not isinstance(data.get("jev", {}), dict):
            raise ValueError("objet JSON attendu, y compris pour jev")
    except (OSError, ValueError) as error:
        parser.exit(1, "Configuration à corriger, fichier conservé : %s\n" % error)
    data.setdefault("jev", {})["enabled"] = args.enable_jev
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = handle.name
    os.replace(temporary, target)
    print("Jev activé dans %s ; les autres réglages sont conservés." % target.relative_to(root))
    print("La question et le code nécessaire pourront être envoyés à TypeSafe. Aucun appel effectué ici.")
    print("Vérifiez la clé et la configuration avec jev-flutter doctor.")
    return 0
