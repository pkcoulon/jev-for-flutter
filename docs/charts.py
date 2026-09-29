#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

THEMES = {
    "light": {
        "surface": "#fcfcfb", "primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
        "grid": "#e1e0d9", "baseline": "#c3c2b7", "series": ["#2a78d6", "#eb6834"],
    },
    "dark": {
        "surface": "#1a1a19", "primary": "#ffffff", "secondary": "#c3c2b7", "muted": "#898781",
        "grid": "#2c2c2a", "baseline": "#383835", "series": ["#3987e5", "#d95926"],
    },
}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
WIDTH = 760
PAD_X = 28


def fmt(value, unit=""):
    if unit == "k":
        return "%s k" % format(round(value / 1000), ",").replace(",", " ")
    if unit == "%":
        return (("%.0f\u202f%%" if value >= 10 or value == 0 else "%.1f\u202f%%") % value)
    return format(round(value), ",").replace(",", " ")


def text(x, y, content, t, role="secondary", size=12, anchor="start", weight=400):
    return ('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%d" text-anchor="%s">%s</text>'
            % (x, y, t[role], size, weight, anchor, escape(content)))


def frame(t, height, title, subtitle, body):
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family=\'%s\'>'
        % (WIDTH, height, WIDTH, height, FONT),
        '<rect width="100%%" height="100%%" rx="10" fill="%s"/>' % t["surface"],
        text(PAD_X, 34, title, t, "primary", 16, weight=600),
        text(PAD_X, 55, subtitle, t, "secondary", 12),
        *body,
        "</svg>",
    ])


def nice_max(value):
    for power in range(-1, 10):
        for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8):
            candidate = step * 10 ** power
            if candidate >= value:
                return candidate
    return value


def line_chart(spec, t):
    values = spec["values"]
    top, left, right, bottom = 80, 64, WIDTH - PAD_X - 70, 300
    ymax = nice_max(max(values) * 1.05)
    xs = [left + (right - left) * i / max(1, len(values) - 1) for i in range(len(values))]
    ys = [bottom - (bottom - top) * v / ymax for v in values]
    body = []
    for i in range(5):
        value = ymax * i / 4
        y = bottom - (bottom - top) * i / 4
        body.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                    % (left, right, y, y, t["baseline"] if i == 0 else t["grid"]))
        body.append(text(left - 8, y + 4, fmt(value, spec.get("unit", "")), t, "muted", 11, "end"))
    for i in range(0, len(values), max(1, len(values) // 6)):
        body.append(text(xs[i], bottom + 18, str(i + 1), t, "muted", 11, "middle"))
    body.append(text((left + right) / 2, bottom + 36, spec["x_label"], t, "muted", 11, "middle"))
    points = " ".join("%.1f,%.1f" % p for p in zip(xs, ys))
    color = t["series"][0]
    body.append('<polygon points="%.1f,%d %s %.1f,%d" fill="%s" fill-opacity="0.1"/>' % (xs[0], bottom, points, xs[-1], bottom, color))
    body.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>' % (points, color))
    body.append('<circle cx="%.1f" cy="%.1f" r="4.5" fill="%s" stroke="%s" stroke-width="2"/>' % (xs[-1], ys[-1], color, t["surface"]))
    body.append(text(xs[-1] + 10, ys[-1] + 4, fmt(values[-1], spec.get("unit", "")), t, "primary", 12, weight=600))
    for note in spec.get("notes", []):
        i = note["index"]
        body.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="%s" stroke-width="2"/>' % (xs[i], ys[i], color, t["surface"]))
        dx, dy, anchor = note.get("dx", 10), note.get("dy", 16), note.get("anchor", "start")
        for k, part in enumerate(note["label"].split("\n")):
            body.append(text(xs[i] + dx, ys[i] + dy + 15 * k, part, t, "secondary", 11, anchor))
    return frame(t, bottom + 52, spec["title"], spec["subtitle"], body)


def bar_path(x0, y, x1, h, radius=4):
    radius = min(radius, max(0.0, x1 - x0), h / 2)
    return ("M%.1f,%.1f H%.1f Q%.1f,%.1f %.1f,%.1f V%.1f Q%.1f,%.1f %.1f,%.1f H%.1f Z"
            % (x0, y, x1 - radius, x1, y, x1, y + radius, y + h - radius, x1, y + h, x1 - radius, y + h, x0))


def hbar_chart(spec, t):
    rows = spec["rows"]
    top, label_w, row_h, bar_h = 78, 300, 30, 18
    left, right = PAD_X + label_w, WIDTH - PAD_X - 60
    vmax = nice_max(max(r["value"] for r in rows))
    body = []
    bottom = top + row_h * len(rows)
    for i in range(5):
        x = left + (right - left) * i / 4
        body.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1"/>'
                    % (x, x, top - 6, bottom, t["baseline"] if i == 0 else t["grid"]))
        body.append(text(x, bottom + 16, fmt(vmax * i / 4, spec.get("unit", "")), t, "muted", 11, "middle"))
    for index, row in enumerate(rows):
        y = top + index * row_h + (row_h - bar_h) / 2
        x1 = left + (right - left) * row["value"] / vmax
        body.append(text(left - 10, y + bar_h / 2 + 4, row["label"], t, "secondary", 12, "end"))
        body.append('<path d="%s" fill="%s"/>' % (bar_path(left, y, max(x1, left + 2), bar_h), t["series"][0]))
        body.append(text(x1 + 8, y + bar_h / 2 + 4, fmt(row["value"], spec.get("unit", "")), t, "primary", 12))
    return frame(t, bottom + 34, spec["title"], spec["subtitle"], body)


def grouped_chart(spec, t):
    groups, series = spec["groups"], spec["series"]
    top, label_w, bar_h, gap, group_gap = 96, spec.get("label_width", 190), 16, 2, 16
    left, right = PAD_X + label_w, WIDTH - PAD_X - 60
    vmax = nice_max(max(v for s in series for v in s["values"]))
    group_h = len(series) * bar_h + (len(series) - 1) * gap
    bottom = top + len(groups) * (group_h + group_gap) - group_gap
    body = []
    for k, s in enumerate(series):
        x = PAD_X + k * spec.get("legend_step", 300)
        body.append('<rect x="%d" y="66" width="10" height="10" rx="2" fill="%s"/>' % (x, t["series"][k]))
        body.append(text(x + 16, 75, s["label"], t, "secondary", 12))
    for i in range(5):
        x = left + (right - left) * i / 4
        body.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s" stroke-width="1"/>'
                    % (x, x, top - 6, bottom + 4, t["baseline"] if i == 0 else t["grid"]))
        body.append(text(x, bottom + 20, fmt(vmax * i / 4, spec.get("unit", "")), t, "muted", 11, "middle"))
    for g, label in enumerate(groups):
        y0 = top + g * (group_h + group_gap)
        body.append(text(left - 10, y0 + group_h / 2 + 4, label, t, "secondary", 12, "end"))
        for k, s in enumerate(series):
            y = y0 + k * (bar_h + gap)
            x1 = left + (right - left) * s["values"][g] / vmax
            body.append('<path d="%s" fill="%s"/>' % (bar_path(left, y, max(x1, left + 2), bar_h), t["series"][k]))
            if g in spec.get("label_groups", range(len(groups))):
                body.append(text(x1 + 6, y + bar_h / 2 + 4, fmt(s["values"][g], spec.get("unit", "")), t, "primary", 11))
    return frame(t, bottom + 38, spec["title"], spec["subtitle"], body)


RENDER = {"line": line_chart, "hbar": hbar_chart, "grouped": grouped_chart}


def main(data_path, out_dir):
    charts = json.loads(Path(data_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, spec in charts.items():
        for mode, theme in THEMES.items():
            (out / ("%s-%s.svg" % (name, mode))).write_text(RENDER[spec["kind"]](spec, theme))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
