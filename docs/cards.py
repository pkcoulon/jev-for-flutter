#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from xml.sax.saxutils import escape

W, H = 1600, 900
SANS = 'system-ui, -apple-system, "Segoe UI", sans-serif'
MONO = '"SF Mono", Menlo, Consolas, monospace'
THEMES = {
    "light": {"page": "#f9f9f7", "panel": "#fcfcfb", "ring": "rgba(11,11,11,0.10)", "primary": "#0b0b0b",
              "secondary": "#52514e", "muted": "#898781", "grid": "#e1e0d9", "base": "#c3c2b7",
              "accent": "#2a78d6", "accent_wash": "#2a78d6", "other": "#898781", "term": "#f2f1ed"},
    "dark": {"page": "#0d0d0d", "panel": "#1a1a19", "ring": "rgba(255,255,255,0.10)", "primary": "#ffffff",
             "secondary": "#c3c2b7", "muted": "#898781", "grid": "#2c2c2a", "base": "#383835",
             "accent": "#3987e5", "accent_wash": "#3987e5", "other": "#898781", "term": "#111110"},
}


def t(x, y, s, c, size=18, weight=400, anchor="start", font=SANS, preserve=False):
    keep = ' xml:space="preserve" style="white-space:pre"' if preserve else ""
    return ('<text x="%.1f" y="%.1f" fill="%s" font-size="%d" font-weight="%d" text-anchor="%s" font-family=\'%s\'%s>%s</text>'
            % (x, y, c, size, weight, anchor, font, keep, escape(str(s))))


def panel(x, y, w, h, th, fill=None):
    return '<rect x="%d" y="%d" width="%d" height="%d" rx="14" fill="%s" stroke="%s" stroke-width="1"/>' % (
        x, y, w, h, fill or th["panel"], th["ring"])


def header(spec, th):
    out = [t(64, 96, "dartlens", th["primary"], 40, 700), t(250, 96, spec.get("section", ""), th["muted"], 22)]
    out.append('<text x="64" y="162" font-size="36" font-weight="700" font-family=\'%s\' fill="%s">%s<tspan dx="12" fill="%s">%s</tspan></text>'
               % (SANS, th["primary"], escape(spec["title"]), th["secondary"], escape(spec.get("title_tail", ""))))
    out.append(t(64, 204, spec.get("subtitle", ""), th["secondary"], 21))
    if spec.get("hero"):
        out.append(t(W - 64, 110, spec["hero"]["value"], th["primary"], 64, 700, "end"))
        out.append(t(W - 64, 142, spec["hero"]["label"], th["secondary"], 18, 400, "end"))
    return out


def footer(spec, th):
    out = [t(64, H - 52, "github.com/pkcoulon/jev-for-flutter", th["secondary"], 22, 600, font=MONO)]
    for k, line in enumerate(spec.get("footer", [])):
        out.append(t(W - 64, H - 70 + 26 * k, line, th["muted"], 16, 400, "end"))
    return out


def nice(value):
    for power in range(-1, 10):
        for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8):
            if step * 10 ** power >= value:
                return step * 10 ** power
    return value


def kfmt(v):
    return "%dk" % round(v / 1000) if v >= 1000 else str(round(v))


def line_block(box, block, th):
    x0, y0, w, h = box
    left, right, top, bottom = x0 + 90, x0 + w - 150, y0 + 60, y0 + h - 60
    series = block["series"]
    ymax = nice(max(max(s["values"]) for s in series) * 1.05)
    n = max(len(s["values"]) for s in series)
    out = [panel(x0, y0, w, h, th)]
    for k, s in enumerate(series if len(series) > 1 else []):
        out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="3" stroke-linecap="round"/>'
                   % (x0 + 32 + 250 * k, x0 + 56 + 250 * k, y0 + 34, y0 + 34, th["accent"] if s.get("emphasis") else th["other"]))
        out.append(t(x0 + 64 + 250 * k, y0 + 40, s["label"], th["secondary"], 17))
    for i in range(5):
        y = bottom - (bottom - top) * i / 4
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>' % (left, right, y, y, th["base"] if i == 0 else th["grid"]))
        out.append(t(left - 12, y + 6, kfmt(ymax * i / 4), th["muted"], 15, 400, "end", MONO))
    for i in range(0, n, max(1, n // 8)):
        out.append(t(left + (right - left) * i / max(1, n - 1), bottom + 28, i + 1, th["muted"], 15, 400, "middle", MONO))
    out.append(t((left + right) / 2, bottom + 52, block.get("x_label", ""), th["muted"], 15, 400, "middle"))
    for s in sorted(series, key=lambda s: s.get("emphasis", False)):
        vals = s["values"]
        pts = [(left + (right - left) * i / max(1, n - 1), bottom - (bottom - top) * v / ymax) for i, v in enumerate(vals)]
        color = th["accent"] if s.get("emphasis") else th["other"]
        path = " ".join("%.1f,%.1f" % p for p in pts)
        if s.get("emphasis"):
            out.append('<polygon points="%.1f,%d %s %.1f,%d" fill="%s" fill-opacity="0.1"/>' % (pts[0][0], bottom, path, pts[-1][0], bottom, th["accent_wash"]))
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>' % (path, color))
        ex, ey = pts[-1]
        out.append('<circle cx="%.1f" cy="%.1f" r="6" fill="%s" stroke="%s" stroke-width="3"/>' % (ex, ey, color, th["panel"]))
        out.append(t(ex + 16, ey + 2, kfmt(vals[-1]), th["primary"], 22, 700))
        out.append(t(ex + 16, ey + 24, s.get("end_label", ""), th["secondary"], 15))
    for note in block.get("notes", []):
        s = series[note.get("series", 0)]
        i = note["index"]
        px = left + (right - left) * i / max(1, n - 1)
        py = bottom - (bottom - top) * s["values"][i] / ymax
        out.append('<circle cx="%.1f" cy="%.1f" r="6" fill="%s" stroke="%s" stroke-width="3"/>' % (px, py, th["accent"], th["panel"]))
        for k, part in enumerate(note["label"].split("\n")):
            out.append(t(px + note.get("dx", -16), py + note.get("dy", -30) + 22 * k, part, th["secondary"], 17, 400, note.get("anchor", "end")))
    return out


def terminal_block(box, block, th):
    x0, y0, w, h = box
    out = [panel(x0, y0, w, h, th, th["term"])]
    for k, color in enumerate(("#e34948", "#eda100", "#1baf7a")):
        out.append('<circle cx="%d" cy="%d" r="7" fill="%s"/>' % (x0 + 30 + 22 * k, y0 + 28, color))
    out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s"/>' % (x0, x0 + w, y0 + 54, y0 + 54, th["ring"]))
    y = y0 + 96
    for line in block["lines"]:
        x = x0 + 28
        for seg in line if isinstance(line, list) else [[line, "primary"]]:
            text, role = seg[0], seg[1]
            color = th["accent"] if role == "accent" else th.get(role, th["primary"])
            out.append(t(x, y, text, color, 20, 600 if role == "accent" else 400, font=MONO, preserve=True))
            x += len(text) * 12.05
        y += 34
    return out


def bars_block(box, block, th):
    x0, y0, w, h = box
    out = [panel(x0, y0, w, h, th), t(x0 + 28, y0 + 48, block["title"].upper(), th["muted"], 17, 700)]
    vmax = block.get("max") or max(r["value"] for r in block["rows"])
    y = y0 + 90
    for row in block["rows"]:
        out.append(t(x0 + 170, y + 16, row["label"], th["primary"] if row.get("emphasis") else th["secondary"], 19, 600, "end"))
        track = w - 330
        out.append('<rect x="%d" y="%d" width="%d" height="22" rx="4" fill="%s"/>' % (x0 + 186, y, track, th["grid"]))
        out.append('<rect x="%d" y="%d" width="%.1f" height="22" rx="4" fill="%s"/>' % (
            x0 + 186, y, max(6, track * row["value"] / vmax), th["accent"] if row.get("emphasis") else th["other"]))
        out.append(t(x0 + w - 28, y + 18, row["text"], th["primary"], 21, 700 if row.get("emphasis") else 400, "end"))
        y += 42
    for k, line in enumerate(block.get("notes", [])):
        out.append(t(x0 + 28, y + 24 + 26 * k, line, th["secondary"], 17))
    return out


def tiles_block(box, block, th):
    x0, y0, w, h = box
    out = [panel(x0, y0, w, h, th)]
    step = w / max(1, len(block["tiles"]))
    for k, tile in enumerate(block["tiles"]):
        x = x0 + 28 + step * k
        out.append(t(x, y0 + 74, tile["value"], th["primary"], 50, 700))
        for j, part in enumerate(tile["label"].split("\n")):
            out.append(t(x, y0 + 108 + 24 * j, part, th["secondary"], 17, 600 if j else 400))
    return out


BLOCKS = {"line": line_block, "terminal": terminal_block, "bars": bars_block, "tiles": tiles_block}


def render(spec, th):
    body = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">' % (W, H, W, H),
            '<rect width="100%%" height="100%%" fill="%s"/>' % th["page"]]
    body += header(spec, th)
    for block in spec["blocks"]:
        body += BLOCKS[block["kind"]](block["box"], block, th)
    body += footer(spec, th)
    body.append("</svg>")
    return "\n".join(body)


def main(spec_path, out_dir):
    specs = json.loads(Path(spec_path).read_text())
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    for name, spec in specs.items():
        for mode, th in THEMES.items():
            (Path(out_dir) / ("%s-%s.svg" % (name, mode))).write_text(render(spec, th))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
