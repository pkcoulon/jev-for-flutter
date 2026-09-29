#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def pct(v):
    return ("%.1f %%" % v)


def main(out_path):
    need = json.loads(Path("need_data.json").read_text())
    summary = json.loads(Path("need_summary.json").read_text())
    growth = need["context-growth"]
    rows = {r["label"]: r["value"] for r in summary["rows"]}
    reads = rows.get("Bash · file reads", 0) + rows.get("Read · files", 0)
    over400 = need["cost-by-context"]["series"]
    card = {
        "section": "Context use · measured in real sessions",
        "title": "Context is supplied on every exchange.",
        "title_tail": "Tool results remain in later context.",
        "subtitle": "Context tokens supplied per exchange in a real Flutter session.",
        "hero": {"value": "×%d" % summary["median_rereads_of_tool_result"], "label": "median reuses of a tool result"},
        "blocks": [
            {"kind": "line", "box": [64, 240, 1000, 560], "x_label": "Exchange",
             "series": [{"label": "Context tokens per exchange", "values": growth["values"], "emphasis": True, "end_label": "At session end"}],
             "notes": [{"index": n["index"], "label": n["label"].replace("call", "exchange"), "dx": -16, "dy": -52} for n in growth["notes"][1:]]},
            {"kind": "bars", "box": [1088, 240, 448, 330], "title": "Repeated context by source", "max": 40,
             "rows": [{"label": "Tool outputs", "value": summary["tool_results_share_of_context_pct"], "text": pct(summary["tool_results_share_of_context_pct"]), "emphasis": True},
                      {"label": "File reads", "value": reads, "text": pct(reads)},
                      {"label": "Searches", "value": rows.get("Bash · search / list", 0), "text": pct(rows.get("Bash · search / list", 0))},
                      {"label": "Tests, analysis", "value": rows.get("Bash · tests / analysis", 0), "text": pct(rows.get("Bash · tests / analysis", 0))}]},
            {"kind": "tiles", "box": [1088, 594, 448, 206],
             "tiles": [{"value": "%dk" % round(summary["mean_context"] / 1000), "label": "Mean context tokens\nper exchange"},
                       {"value": "%d %%" % round(over400[1]["values"][-1]), "label": "of cost comes from\nexchanges above 400k"}]},
        ],
        "footer": ["%d sessions · %s exchanges · 4 Flutter projects, including 1 anonymized work project" % (summary["sessions"], format(summary["calls"], ",")),
                   "Opportunity estimates, not measured savings · API prices as of %s" % summary["pricing_date"]],
    }
    Path(out_path).write_text(json.dumps({"why": card}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
