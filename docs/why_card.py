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
        "section": "pourquoi · mesuré sur nos sessions réelles",
        "title": "Claude relit tout, à chaque échange.",
        "title_tail": "Ce qu'un outil ajoute y reste.",
        "subtitle": "Ce que Claude Code renvoie au modèle à chaque échange, en tokens, sur une vraie session Flutter.",
        "hero": {"value": "×%d" % summary["median_rereads_of_tool_result"], "label": "relectures d'une sortie d'outil"},
        "blocks": [
            {"kind": "line", "box": [64, 240, 1000, 560], "x_label": "échange n°",
             "series": [{"label": "ce que Claude relit à chaque échange", "values": growth["values"], "emphasis": True, "end_label": "en fin de session"}],
             "notes": [{"index": n["index"], "label": n["label"].replace("appel", "échange"), "dx": -16, "dy": -52} for n in growth["notes"][1:]]},
            {"kind": "bars", "box": [1088, 240, 448, 330], "title": "ce qui est relu, par origine", "max": 40,
             "rows": [{"label": "sorties d'outils", "value": summary["tool_results_share_of_context_pct"], "text": pct(summary["tool_results_share_of_context_pct"]), "emphasis": True},
                      {"label": "fichiers lus", "value": reads, "text": pct(reads)},
                      {"label": "recherches", "value": rows.get("Bash · chercher / lister", 0), "text": pct(rows.get("Bash · chercher / lister", 0))},
                      {"label": "tests, analyse", "value": rows.get("Bash · tests / analyse", 0), "text": pct(rows.get("Bash · tests / analyse", 0))}]},
            {"kind": "tiles", "box": [1088, 594, 448, 206],
             "tiles": [{"value": "%dk" % round(summary["mean_context"] / 1000), "label": "tokens relus par\néchange, en moyenne"},
                       {"value": "%d %%" % round(over400[1]["values"][-1]), "label": "du coût vient des\néchanges > 400k"}]},
        ],
        "footer": ["%d sessions · %s échanges · 4 projets Flutter, dont 1 pro anonymisé" % (summary["sessions"], format(summary["calls"], ",").replace(",", " ")),
                   "des estimations du besoin, pas des économies mesurées · coût au tarif API du %s" % summary["pricing_date"]],
    }
    Path(out_path).write_text(json.dumps({"why": card}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
