#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def pct(v):
    return ("%.1f %%" % v).replace(".", ",")


def main(out_path):
    need = json.loads(Path("need_data.json").read_text())
    summary = json.loads(Path("need_summary.json").read_text())
    growth = need["context-growth"]
    rows = {r["label"]: r["value"] for r in summary["rows"]}
    reads = rows.get("Bash · lire des fichiers", 0) + rows.get("Read (fichiers)", 0)
    over400 = need["cost-by-context"]["series"]
    card = {
        "section": "pourquoi · mesuré sur des sessions réelles",
        "title": "Chaque appel relit tout le contexte.",
        "title_tail": "Ce qu'un outil y verse y reste.",
        "subtitle": "Tokens envoyés à chaque appel API, une session réelle sur un projet Flutter.",
        "hero": {"value": "×%d" % summary["median_rereads_of_tool_result"], "label": "relectures médianes d'une sortie d'outil"},
        "blocks": [
            {"kind": "line", "box": [64, 240, 1000, 560], "x_label": "appel API n°",
             "series": [{"label": "contexte envoyé à chaque appel", "values": growth["values"], "emphasis": True, "end_label": "en fin de session"}],
             "notes": [{"index": n["index"], "label": n["label"], "dx": -16, "dy": -52} for n in growth["notes"][1:]]},
            {"kind": "bars", "box": [1088, 240, 448, 330], "title": "part du contexte relu", "max": 40,
             "rows": [{"label": "sorties d'outils", "value": summary["tool_results_share_of_context_pct"], "text": pct(summary["tool_results_share_of_context_pct"]), "emphasis": True},
                      {"label": "lire un fichier", "value": reads, "text": pct(reads)},
                      {"label": "chercher", "value": rows.get("Bash · chercher / lister", 0), "text": pct(rows.get("Bash · chercher / lister", 0))},
                      {"label": "tests, analyse", "value": rows.get("Bash · tests / analyse", 0), "text": pct(rows.get("Bash · tests / analyse", 0))}]},
            {"kind": "tiles", "box": [1088, 594, 448, 206],
             "tiles": [{"value": "%dk" % round(summary["mean_context"] / 1000), "label": "contexte moyen\npar appel"},
                       {"value": "%d %%" % round(over400[1]["values"][-1]), "label": "du coût dans les\nappels > 400k"}]},
        ],
        "footer": ["%d sessions · %s appels · 4 projets Flutter, dont 1 pro anonymisé" % (summary["sessions"], format(summary["calls"], ",").replace(",", " ")),
                   "coût valorisé aux tarifs API du %s : une estimation, pas une facture" % summary["pricing_date"]],
    }
    Path(out_path).write_text(json.dumps({"why": card}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
