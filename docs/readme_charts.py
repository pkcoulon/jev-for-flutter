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
LABELS = ("Without plugin", "Suggestion only", "Focused read")
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
        "scope": "4 Pioudex tasks, 1 run per variant, before version 0.2",
        "units": {"dart_characters": "Dart code received through Read, lens and shell, including line numbers; not tokens",
                  "claude_usd": "Claude API-equivalent usage cost; excludes Jev, not a subscription invoice"},
        "limitations": ["Failures included in volumes", "Imperfect initial review",
                        "Timings affected by permission waits", "No demonstrated quality equivalence"],
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
    figure.text(0.035, 0.91, "Less code received. Savings still unproven.", fontsize=21, weight="bold")
    figure.text(0.035, 0.845, "One Flutter project · September 29, 2026 · exploratory results", color=muted, fontsize=12)
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
    axes[0].set_title("Dart code received · all 4 tasks", loc="left", fontsize=13, weight="bold", pad=18)
    axes[0].set_xticks([0, 250000, 500000], ["0", "250 000", "500 000"])
    axes[0].set_xlabel("characters, including failures", labelpad=13, fontsize=11)
    for y, value in enumerate(totals):
        axes[0].text(value + 9000, y, f"{value:,}".replace(",", " "), va="center", fontsize=12, weight="bold")
    axes[1].set_yticklabels([])
    axes[1].set_title("Cost · the only task accepted in every arm", loc="left", fontsize=12, weight="bold", pad=18)
    axes[1].set_xticks([0, 0.5, 1.0])
    axes[1].xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:g}"))
    axes[1].set_xlabel("Claude API cost, excluding Jev · 1 run", labelpad=13, fontsize=11)
    for y, value in enumerate(costs):
        axes[1].text(value + 0.035, y, f"${value:.2f}", va="center", fontsize=12, weight="bold")
    reduction = round(100 * (1 - totals[-1] / totals[0]))
    figure.text(0.035, 0.095, f"{reduction}% less code received with focused reads.", fontsize=13, weight="bold",
                color=COLORS[-1] if dark else "#087f75")
    figure.text(0.035, 0.047, "Before v0.2 · 1 run per task and variant · equal quality and overall savings unproven.",
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
    figure.text(0.035, 0.915, data.get("chart_title", "Tokens, cost, time: measured differences."), fontsize=21, weight="bold")
    figure.text(0.035, 0.85, "With the plugin vs. the same task without it · 0% = unchanged",
                fontsize=12, color=muted)
    figure.text(0.035, 0.78, "━", color=decrease, fontsize=19, weight="bold")
    figure.text(0.067, 0.785, "Decrease", fontsize=12, color=muted)
    figure.text(0.17, 0.78, "━", color=increase, fontsize=19, weight="bold")
    figure.text(0.202, 0.785, "Increase", fontsize=12, color=muted)
    metrics = (("claude_total_tokens", "Claude tokens", "including cache"),
               ("total_usd", "Claude + Jev cost", "API-equivalent"),
               ("verified_seconds", "Total time", "including verification"))
    for ax, (field, title, unit) in zip(axes, metrics):
        ax.set_facecolor(background)
        for index, task in enumerate(tasks):
            value = 100 * (rows[(task, "all")][field] / rows[(task, "control")][field] - 1)
            color = decrease if value < 0 else increase
            ax.barh(index, value, height=0.31, color=color, alpha=0.88, zorder=3)
            label = f"{value:+.0f}%".replace("-", "−")
            ax.text(value + (-3 if value < 0 else 3), index, label, va="center",
                    ha="right" if value < 0 else "left", fontsize=13, weight="bold", color=color)
        ax.set_xlim(-100, 70)
        ax.set_ylim(len(tasks) - 0.5, -0.5)
        ax.set_yticks(range(len(tasks)))
        ax.set_yticklabels([])
        ax.set_title(title, loc="left", fontsize=13, weight="bold", pad=19)
        ax.set_xticks([-50, 0, 50], ["−50%", "0%", "+50%"])
        ax.set_xlabel(unit, fontsize=11, labelpad=12)
        ax.tick_params(axis="both", length=0, pad=12)
        ax.grid(axis="x", color=grid, linewidth=0.7, zorder=0)
        ax.axvline(0, color=muted, linewidth=1, zorder=2)
        for spine in ax.spines.values():
            spine.set_visible(False)
    axes[0].set_yticklabels(data.get("chart_labels", ["Gambade\nExplain a threshold", "Pioudex\nFix a calculation"]))
    figure.text(0.035, 0.15, data.get("chart_scope", "Two tasks · one run per variant · before parallel context · September 29, 2026"),
                fontsize=11, color=muted)
    figure.text(0.035, 0.09, data.get("chart_verdict", "No lens calls: these differences do not establish a selection benefit."), fontsize=12, weight="bold")
    figure.text(0.035, 0.04, data.get("chart_limit", "Savings at equal quality remain unproven. See the report for data and limitations."),
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


def read_chart(data, theme, preview, stem="read-results"):
    dark = theme == "dark"
    background, foreground, muted, neutral, accent = (
        ("#111418", "#e6e9ee", "#9ba3af", "#414953", "#8faed3") if dark
        else ("#ffffff", "#242c36", "#717b88", "#dfe4eb", "#708fb4"))
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": foreground,
                         "svg.fonttype": "path", "svg.hashsalt": "jev-flutter-public-2026-09-29"})
    fig = plt.figure(figsize=(11.2, 4.8), facecolor=background)
    fig.text(.05, .91, data.get("chart_title", "Three focused reads"), fontsize=19, weight="medium")
    fig.text(.05, .85, data.get("chart_scope", "Jev for Flutter 0.3.0 · three questions about known files"),
             fontsize=10, color=muted)
    for x, color, label in ((.35, neutral, "Without plugin"), (.51, accent, "With Jev")):
        fig.add_artist(plt.Line2D([x, x + .017], [.75, .75], color=color, linewidth=5, solid_capstyle="round"))
        fig.text(x + .025, .75, label, va="center", fontsize=10, color=muted)
    for y, field, label in zip((.62, .43, .24), ("claude_tokens", "total_usd", "seconds"),
                               ("Claude tokens", "Claude + Jev cost", "Total time")):
        change = data["summary"]["percent_change"][field]
        control, plugin = (data["summary"][arm][field] for arm in ("control", "plugin"))
        ax = fig.add_axes((.35, y - .065, .42, .13), facecolor=background)
        ax.barh([1, 0], [control, plugin], height=.26, color=[neutral, accent])
        ax.set_xlim(0, max(control, plugin) * 1.29)
        ax.set_ylim(-.55, 1.55)
        ax.set_axis_off()
        fmt = ((lambda v: f"{v / 1000:.1f} k") if field == "claude_tokens" else
               (lambda v: f"${v:.3f}") if field == "total_usd" else (lambda v: f"{v:.1f} s"))
        for level, value in ((1, control), (0, plugin)):
            ax.text(value + max(control, plugin) * .035, level, fmt(value),
                    va="center", fontsize=9, color=muted)
        fig.text(.05, y, label, va="center", fontsize=12)
        fig.text(.95, y, f"{change:+.0f}%".replace("-", "−"), ha="right", va="center",
                 fontsize=23, weight="medium", color=accent if change < 0 else foreground)
    accepted = data["summary"]
    count = len(data["trials"]) // 2
    fig.text(.05, .075, f"Accepted answers: {accepted['plugin']['accepted']}/{count} with Jev · "
             f"{accepted['control']['accepted']}/{count} without. One run per variant.", fontsize=10, color=muted)
    output = HERE / "img" / f"{stem}-{theme}.svg"
    fig.savefig(output, facecolor=background, metadata={"Date": None})
    output.write_text("\n".join(line.rstrip() for line in output.read_text().splitlines()) + "\n")
    if preview:
        preview.mkdir(parents=True, exist_ok=True)
        fig.savefig(preview / f"{stem}-{theme}.png", facecolor=background, dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adoption", type=Path)
    parser.add_argument("--scores", type=Path)
    parser.add_argument("--preview", type=Path)
    args = parser.parse_args()
    if bool(args.adoption) != bool(args.scores):
        parser.error("--adoption and --scores must be supplied together")
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
    public = HERE / "public-read-results.json"
    if public.exists():
        for theme in ("light", "dark"):
            read_chart(json.loads(public.read_text()), theme, args.preview, "public-read-results")


if __name__ == "__main__":
    main()
