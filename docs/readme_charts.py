import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

HERE = Path(__file__).resolve().parent
ARMS = ("control", "all", "all_refuse")
LABELS = ("Sans dartlens", "Simple suggestion", "Lecture ciblée")
COLORS = ("#8390a5", "#8493d7", "#14b8a6")
FIELDS = ("read_full_chars", "read_range_chars", "lens_chars", "shell_chars")


def extract(adoption_path, score_path):
    adoption = json.loads(adoption_path.read_text())
    scores = json.loads(score_path.read_text())
    indexed = {row["trial"]: row for row in scores["trials"]}
    trials = []
    for row in adoption["trials"]:
        score = indexed[row["trial"]]
        trials.append({"id": row["trial"], "task": score["task"], "variant": row["arm"],
                       "dart_characters": sum(row.get(key, 0) for key in FIELDS),
                       "claude_usd": score["usage"]["usd"], "accepted_by_original_review": score["accepted"],
                       "jev_input_tokens": score["jev_input_tokens"], "jev_output_tokens": None,
                       "claude_tokens": {key: score["usage"][key]
                                         for key in ("input", "write_5m", "write_1h", "read", "output")}})
    return {
        "campaign": "adoption-2026-09-29", "date": "2026-09-29",
        "scope": "4 tâches Pioudex, 1 essai par variante, avant la version 0.2",
        "units": {"dart_characters": "Code Dart reçu via Read, lens et shell, numéros de ligne compris ; pas des tokens",
                  "claude_usd": "Valorisation API des usages Claude ; hors Jev, pas une facture d'abonnement"},
        "limitations": ["Échecs compris dans les volumes", "Relecture initiale imparfaite",
                        "Durées contaminées par des attentes de permission", "Aucune équivalence de qualité démontrée"],
        "inputs": {"adoption_sha256": hashlib.sha256(adoption_path.read_bytes()).hexdigest(),
                   "score_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest(),
                   "pricing": scores["pricing"]},
        "trials": trials,
    }


def chart(data, theme, preview):
    dark = theme == "dark"
    background, foreground, muted, grid = (("#0d1422", "#edf2fa", "#a3b0c4", "#263348") if dark
                                         else ("#f8fafc", "#142033", "#58677e", "#dce3ed"))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "text.color": foreground,
                         "axes.labelcolor": muted, "xtick.color": muted, "ytick.color": foreground,
                         "svg.fonttype": "none", "svg.hashsalt": "dartlens-readme-2026-09-29"})
    by_arm = {arm: [row for row in data["trials"] if row["variant"] == arm] for arm in ARMS}
    assert all(len(rows) == 4 for rows in by_arm.values())
    totals = [sum(row["dart_characters"] for row in by_arm[arm]) for arm in ARMS]
    common = set.intersection(*(set(row["task"] for row in rows if row["accepted_by_original_review"])
                                for rows in by_arm.values()))
    assert common == {"pioudex-diag-gain-xp"}
    costs = [sum(row["claude_usd"] for row in by_arm[arm] if row["task"] in common) for arm in ARMS]
    figure, axes = plt.subplots(1, 2, figsize=(12.6, 5.4), gridspec_kw={"width_ratios": [1.5, 1]})
    figure.set_facecolor(background)
    figure.subplots_adjust(left=0.175, right=0.955, top=0.70, bottom=0.245, wspace=0.33)
    figure.text(0.035, 0.91, "Moins de code reçu. L’économie reste à prouver.", fontsize=21, weight="bold")
    figure.text(0.035, 0.845, "Essais sur un projet Flutter · 29 septembre 2026 · résultats exploratoires", color=muted, fontsize=12)
    for ax, values, maximum in zip(axes, (totals, costs), (550000, 1.4)):
        ax.set_facecolor(background)
        ax.barh(range(3), values, color=COLORS, height=0.48, zorder=3)
        ax.set_ylim(2.55, -0.55)
        ax.set_xlim(0, maximum)
        ax.set_yticks(range(3))
        ax.tick_params(axis="both", length=0, pad=10)
        ax.grid(axis="x", color=grid, linewidth=0.7, zorder=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
    axes[0].set_yticklabels(LABELS)
    axes[0].set_title("Code Dart reçu · les 4 tâches", loc="left", fontsize=13, weight="bold", pad=18)
    axes[0].set_xticks([0, 250000, 500000], ["0", "250 000", "500 000"])
    axes[0].set_xlabel("caractères, échecs compris", labelpad=13, fontsize=11)
    for y, value in enumerate(totals):
        axes[0].text(value + 9000, y, f"{value:,}".replace(",", " "), va="center", fontsize=12, weight="bold")
    axes[1].set_yticklabels([])
    axes[1].set_title("Coût · la seule tâche acceptée partout", loc="left", fontsize=12, weight="bold", pad=18)
    axes[1].set_xticks([0, 0.5, 1.0])
    axes[1].xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}".replace(".", ",") + " $"))
    axes[1].set_xlabel("Claude au tarif API, hors Jev · 1 essai", labelpad=13, fontsize=11)
    for y, value in enumerate(costs):
        axes[1].text(value + 0.035, y, f"{value:.2f} $".replace(".", ","), va="center", fontsize=12, weight="bold")
    reduction = round(100 * (1 - totals[-1] / totals[0]))
    figure.text(0.035, 0.095, f"−{reduction} % de code reçu avec la lecture ciblée.", fontsize=13, weight="bold",
                color=COLORS[-1] if dark else "#087f75")
    figure.text(0.035, 0.047, "Avant v0.2 · 1 essai par tâche et par variante · qualité équivalente et gain global non démontrés.",
                fontsize=11, color=muted)
    output = HERE / "img" / f"readme-results-{theme}.svg"
    output.parent.mkdir(exist_ok=True)
    figure.savefig(output, facecolor=background, metadata={"Date": None})
    output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        figure.savefig(preview / f"readme-results-{theme}.png", facecolor=background, dpi=140)
    plt.close(figure)


def exploratory_chart(data, theme, preview):
    dark = theme == "dark"
    background, foreground, muted, grid = (("#0d1422", "#edf2fa", "#a3b0c4", "#263348") if dark
                                         else ("#f8fafc", "#142033", "#58677e", "#dce3ed"))
    decrease = "#2dd4bf" if dark else "#087f75"
    increase = "#fbbf80" if dark else "#ad5928"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "text.color": foreground,
                         "axes.labelcolor": muted, "xtick.color": muted, "ytick.color": foreground,
                         "svg.fonttype": "none", "svg.hashsalt": "dartlens-exploratory-2026-09-29"})
    tasks = data.get("chart_tasks", ("gambade-loc-chaleur", "pioudex-diag-gain-xp"))
    rows = {(row["task"], row["variant"]): row for row in data["trials"]}
    assert len(rows) == len(data["trials"]) == 2 * len(tasks)
    figure, axes = plt.subplots(1, 3, figsize=(12.6, 5.6))
    figure.set_facecolor(background)
    figure.subplots_adjust(left=0.19, right=0.965, top=0.65, bottom=0.30, wspace=0.30)
    figure.text(0.035, 0.915, data.get("chart_title", "Tokens, coût, temps : les écarts mesurés."), fontsize=21, weight="bold")
    figure.text(0.035, 0.85, "Avec dartlens, par rapport à la même tâche sans plugin · 0 % = identique",
                fontsize=12, color=muted)
    figure.text(0.035, 0.78, "━", color=decrease, fontsize=19, weight="bold")
    figure.text(0.067, 0.785, "Baisse", fontsize=12, color=muted)
    figure.text(0.17, 0.78, "━", color=increase, fontsize=19, weight="bold")
    figure.text(0.202, 0.785, "Hausse", fontsize=12, color=muted)
    metrics = (("claude_total_tokens", "Tokens Claude", "cache compris"),
               ("total_usd", "Coût Claude + Jev", "au tarif API"),
               ("verified_seconds", "Temps total", "vérifications comprises"))
    for ax, (field, title, unit) in zip(axes, metrics):
        ax.set_facecolor(background)
        for index, task in enumerate(tasks):
            value = 100 * (rows[(task, "all")][field] / rows[(task, "control")][field] - 1)
            color = decrease if value < 0 else increase
            ax.barh(index, value, height=0.31, color=color, alpha=0.88, zorder=3)
            label = f"{value:+.0f} %".replace("-", "−")
            ax.text(value + (-3 if value < 0 else 3), index, label, va="center",
                    ha="right" if value < 0 else "left", fontsize=13, weight="bold", color=color)
        ax.set_xlim(-100, 70)
        ax.set_ylim(len(tasks) - 0.5, -0.5)
        ax.set_yticks(range(len(tasks)))
        ax.set_yticklabels([])
        ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=19)
        ax.set_xticks([-50, 0, 50], ["−50 %", "0 %", "+50 %"])
        ax.set_xlabel(unit, fontsize=11, labelpad=12)
        ax.tick_params(axis="both", length=0, pad=12)
        ax.grid(axis="x", color=grid, linewidth=0.7, zorder=0)
        ax.axvline(0, color=muted, linewidth=1, zorder=2)
        for spine in ax.spines.values():
            spine.set_visible(False)
    axes[0].set_yticklabels(data.get("chart_labels", ["Gambade\nExpliquer un seuil", "Pioudex\nCorriger un calcul"]))
    figure.text(0.035, 0.15, data.get("chart_scope", "Deux tâches · une session par variante · avant la refonte en parallèle · 29 septembre 2026"),
                fontsize=11, color=muted)
    figure.text(0.035, 0.09, data.get("chart_verdict", "Aucun appel à lens : ces écarts ne prouvent pas le bénéfice de la sélection."), fontsize=12, weight="bold")
    figure.text(0.035, 0.04, data.get("chart_limit", "L’économie à qualité égale reste à démontrer. Données brutes et réserves dans le rapport."),
                fontsize=11, color=muted)
    name = data.get("chart_name", "exploratory-results")
    output = HERE / "img" / f"{name}-{theme}.svg"
    output.parent.mkdir(exist_ok=True)
    figure.savefig(output, facecolor=background, metadata={"Date": None})
    output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        figure.savefig(preview / f"{name}-{theme}.png", facecolor=background, dpi=140)
    plt.close(figure)


def read_chart(data, theme, preview):
    dark = theme == "dark"
    background, foreground, muted, grid = (("#0b1220", "#edf4fb", "#a1b0c5", "#26354a") if dark
                                         else ("#f6f9fc", "#142238", "#51627b", "#dce5ef"))
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": foreground,
                         "svg.fonttype": "none", "svg.hashsalt": "jev-flutter-read-2026-09-29"})
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.5))
    fig.set_facecolor(background)
    fig.subplots_adjust(left=.055, right=.955, top=.62, bottom=.32, wspace=.35)
    fig.text(.045, .88, "Moins de contexte. Des lectures moins chères.", fontsize=21, weight="bold")
    fig.text(.045, .79, "Jev for Flutter · 3 questions sur des fichiers connus · 1 session par variante", fontsize=12, color=muted)
    for ax, field, label in zip(axes, ("claude_tokens", "total_usd", "seconds"),
                               ("Tokens Claude · cache inclus", "Coût Claude + Jev", "Durée rapportée par Claude")):
        change = data["summary"]["percent_change"][field]
        color = "#19bba8" if change < 0 else "#ed9459"
        ax.set_facecolor(background)
        ax.barh([1, 0], [100, 100 + change], height=.40, color=[grid, color])
        ax.set_xlim(0, 145)
        ax.set_ylim(-.6, 1.6)
        ax.set_axis_off()
        ax.text(0, 1.9, f"{change:+.0f} %".replace("-", "−"), fontsize=31, weight="bold", color=color)
        ax.text(0, -.9, label, fontsize=11, color=foreground)
        ax.text(103, 1, "sans", fontsize=10, va="center", color=muted)
        ax.text(103 + change, 0, "avec", fontsize=10, va="center", color=muted)
    fig.text(.045, .15, "Passages attendus conservés : 3/3. Réponses entièrement acceptées : 2/3 avec, 1/3 sans.", fontsize=11, color=foreground)
    fig.text(.045, .065, "Tous les essais inclus. Pas une preuve sur un développement complet ni d'accélération générale.", fontsize=11, color=muted)
    output = HERE / "img" / f"read-results-{theme}.svg"
    fig.savefig(output, facecolor=background, metadata={"Date": None})
    output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview / f"read-results-{theme}.png", facecolor=background, dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adoption", type=Path)
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    if bool(args.adoption) != bool(args.scores):
        parser.error("--adoption et --scores sont nécessaires ensemble")
    path = HERE / "readme-results.json"
    if args.adoption:
        data = extract(args.adoption, args.scores)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    else:
        data = json.loads(path.read_text())
    for theme in ("light", "dark"):
        chart(data, theme, args.preview)
    current = json.loads((HERE / "exploratory-results.json").read_text())
    for theme in ("light", "dark"):
        exploratory_chart(current, theme, args.preview)
    compact = json.loads((HERE / "context-final-results.json").read_text())
    for theme in ("light", "dark"):
        exploratory_chart(compact, theme, args.preview)
    reads = json.loads((HERE / "read-results.json").read_text())
    for theme in ("light", "dark"):
        read_chart(reads, theme, args.preview)


if __name__ == "__main__":
    main()
