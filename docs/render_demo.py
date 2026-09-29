import html
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
DATA = json.loads((ROOT / "public-read-results.json").read_text())
TRIAL = next(t for t in DATA["trials"] if t["id"] == "appflowy-screen-plugin")
READ = TRIAL["narrowed"][0]
START, COUNT, TOTAL = READ["offset"], READ["limit"], READ["lines"]
FPS, DURATION = 12, 14


def text(x, y, value, size=20, fill="#526177", weight=400, **attrs):
    extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" '
            f'font-weight="{weight}" {extra}>{html.escape(str(value))}</text>')


def rect(x, y, width, height, fill, radius=0, **attrs):
    extra = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'rx="{radius}" fill="{fill}" {extra}/>')


def smooth(value):
    value = max(0, min(1, value))
    return value * value * (3 - 2 * value)


def frame(seconds):
    selected = seconds >= 6
    phase = 0 if seconds < 2.5 else 1 if not selected else 2
    focus = smooth((seconds - 2.5) / 1.8)
    output = smooth((seconds - 5.2) / 1.1)
    items = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="680" '
        'viewBox="0 0 1200 680" role="img" aria-labelledby="title description">',
        '<title id="title">Jev for Flutter: a focused Dart read</title>',
        f'<desc id="description">Animated explanation of a recorded AppFlowy read: '
        f'{TOTAL:,} lines become a {COUNT}-line excerpt, lines {START} to {START + COUNT - 1}. '
        'The requested method is preserved. Full files remain accessible. Timing is illustrative.</desc>',
        '<g font-family="Arial, Helvetica, sans-serif">',
        rect(1, 1, 1198, 678, "#f8fafc", 22, stroke="#dce4ed"),
        text(48, 51, "JEV FOR FLUTTER", 16, "#177fae", 700, letter_spacing="1.5"),
        text(1152, 51, "Recorded example · AppFlowy", 16, text_anchor="end"),
        text(48, 109, "Read the part that answers the question.", 37, "#172b42", 700),
        rect(48, 138, 1104, 58, "#ffffff", 12, stroke="#dce4ed"),
        text(68, 174, "YOU ASK", 13, "#63748a", 700, letter_spacing="1"),
        text(161, 174, "Explain _closestScreen in appflowy_popup_menu.dart.", 20, "#22374f"),
        rect(48, 226, 426, 304, "#ffffff", 16, stroke="#dce4ed"),
        text(72, 261, "DART SOURCE", 13, "#63748a", 700, letter_spacing="1"),
        text(72, 313, f"{TOTAL:,}", 45, "#172b42", 700),
        text(207, 311, "lines in the file", 18),
        rect(72, 337, 378, 126, "#f3f6fa", 9),
    ]
    for column in range(3):
        for row in range(13):
            width = 53 + ((row * 17 + column * 31) % 44)
            items.append(rect(88 + column * 120, 348 + row * 8, width, 3, "#cbd5e1", 1))
    highlight_y = 343 + 110 * START / TOTAL
    items += [
        rect(80, round(highlight_y, 2), 362, 11, "#21a8d6", 3, opacity=round(focus * 0.32, 3)),
        text(72, 502, "appflowy_popup_menu.dart", 17, "#526177", font_family="Menlo, monospace"),
        f'<path d="M490 378 H704" stroke="#d1deea" stroke-width="2"/>',
        f'<path d="M698 372 L704 378 L698 384" fill="none" stroke="#b0c3d4" stroke-width="2"/>',
        rect(548, 347, 104, 62, "#e9f6fc", 18, stroke="#c4e8f8"),
        text(600, 386, "Jev", 24, "#127dab", 700, text_anchor="middle"),
        text(600, 438, "Selects the passage", 16, text_anchor="middle"),
        rect(720, 226, 432, 304, "#ffffff", 16, stroke="#dce4ed"),
        text(744, 261, "CLAUDE READS", 13, "#63748a", 700, letter_spacing="1"),
    ]
    if output:
        items += [
            f'<g opacity="{round(output, 3)}">',
            text(744, 329, COUNT, 62, "#147b62", 700),
            text(843, 326, "selected lines", 20),
            text(744, 366, f"Lines {START}–{START + COUNT - 1}", 20, "#22374f"),
            rect(744, 392, 384, 61, "#edf8f3", 9),
            text(762, 418, "_closestScreen", 18, "#146d57", 700, font_family="Menlo, monospace"),
            text(762, 440, "Complete method kept · lines 798–807", 16, "#397562"),
            text(744, 502, "Original file and line numbers preserved", 16),
            '</g>',
        ]
    else:
        items += [
            text(744, 344, "A focused excerpt", 26, "#8a9bae", 600),
            text(744, 380, "Selected for your question", 19, "#8a9bae"),
        ]
    if phase == 1:
        items.append(f'<circle cx="{490 + (seconds * 68 % 214):.1f}" cy="378" r="4" fill="#21a8d6"/>')
    labels = ["Read requested", "Jev finds the method", "Focused read delivered"]
    for i, label in enumerate(labels):
        x = 48 + i * 370
        active = i == phase
        items += [
            rect(x, 557, 342, 3, "#23a6d4" if active else "#dce4ed", 1),
            text(x, 588, f"0{i + 1}", 14, "#177fae" if active else "#9aa8b9", 700),
            text(x + 35, 588, label, 17, "#172b42" if active else "#7b8b9d", 600 if active else 400),
        ]
    items += [
        text(48, 641, "Full-file reads stay available.", 16, "#526177"),
        text(1152, 641, "Animated replay · timing illustrative", 15, "#6b7c90", text_anchor="end"),
        '</g></svg>',
    ]
    return "\n".join(items)


def main():
    for name in ("rsvg-convert", "ffmpeg"):
        if not shutil.which(name):
            raise SystemExit(f"Install {name} to render the demo.")
    output = ROOT / "img"
    poster = output / "focused-read-demo.svg"
    poster.write_text(frame(10))
    with tempfile.TemporaryDirectory(prefix="jev-flutter-demo-") as directory:
        temp = Path(directory)
        for i in range(FPS * DURATION):
            svg = temp / "frame.svg"
            svg.write_text(frame(i / FPS))
            subprocess.run(["rsvg-convert", str(svg), "-o", str(temp / f"{i:04d}.png")], check=True)
        source = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS),
                  "-i", str(temp / "%04d.png")]
        clips = []
        for second, duration in ((0, 2.5), (3.5, 3.5), (7, 8)):
            image = temp / f"{int(second * FPS):04d}.png"
            clips.extend([f"file '{image}'", f"duration {duration}"])
        clips.append(f"file '{image}'")
        sequence = temp / "frames.txt"
        sequence.write_text("\n".join(clips) + "\n")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                        "-safe", "0", "-i", str(sequence), "-filter_complex",
                        "split[a][b];[a]palettegen=max_colors=128[p];"
                        "[b][p]paletteuse=dither=none:diff_mode=rectangle", "-fps_mode", "vfr",
                        "-loop", "0", str(output / "focused-read-demo.gif")], check=True)
        subprocess.run(source + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                                "-movflags", "+faststart", str(output / "focused-read-demo.mp4")], check=True)
    print(f"Rendered a three-step GIF and {DURATION}s video from {TRIAL['id']} in public-read-results.json")


if __name__ == "__main__":
    main()
