"""Monte un Reel court sans voix : des photos qui défilent (léger zoom), un texte à l'écran par plan,
une musique, et un écran de fin. Format 1080 x 1920, 30 images/s.

Usage : python scripts/make_reel.py reels/<dossier>   (lit reel.json, écrit reel.mp4)
"""
import json
import pathlib
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = str(ROOT / "fonts" / "Poppins-Bold.ttf")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1080, 1920, 30
ACCENT = (255, 196, 72)


def cover(img, w, h):
    s = max(w / img.width, h / img.height)
    return img.resize((round(img.width * s) + 1, round(img.height * s) + 1), Image.LANCZOS)


def wrap(d, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        t = (cur + " " + word).strip()
        if d.textlength(t, font=font) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def text_layer(lines_spec):
    """Calque transparent avec le texte (liste de (texte, taille, couleur)), centré vers le milieu de l'écran."""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    blocks = []
    for txt, size, color in lines_spec:
        f = ImageFont.truetype(FONT, size)
        for ln in wrap(d, txt, f, W - 200):
            blocks.append((ln, f, color, int(size * 1.22)))
        blocks.append(("", None, None, int(size * 0.35)))
    blocks.pop()
    total = sum(b[3] for b in blocks)
    y = int(H * 0.60) - total // 2  # au-dessus de la zone couverte par la légende du Reel
    # bandeau sombre derrière le texte
    pad = 40
    d.rounded_rectangle((60, y - pad, W - 60, y + total + pad - 10), 36, fill=(0, 0, 0, 120))
    for ln, f, color, h in blocks:
        if f:
            d.text((W // 2, y + h // 2), ln, font=f, fill=color, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
        y += h
    return layer


def render_scene(scene, folder, out, idx):
    dur = scene["duration"]
    n = round(dur * FPS)
    if scene.get("image"):
        src = Image.open(folder / "_images" / scene["image"]).convert("RGB")
        if scene.get("crop"):
            l, t, r, b = scene["crop"]
            src = src.crop((round(l * src.width), round(t * src.height), round(r * src.width), round(b * src.height)))
        big = cover(src, int(W * 1.12), int(H * 1.12))
    else:
        big = None
    text = text_layer([(t["text"], t.get("size", 72), tuple(t.get("color", (255, 255, 255)))) for t in scene["text"]])
    zoom_in = scene.get("zoom", "in") == "in"
    pan = scene.get("pan", 0.5)  # 0 = gauche, 1 = droite (pour les photos larges)
    tmp = out.with_name(out.stem + ".part.mp4")
    proc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                             "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)], stdin=subprocess.PIPE)
    for i in range(n):
        p = i / max(1, n - 1)
        if big is not None:
            z = 1.0 + 0.08 * (p if zoom_in else 1 - p)
            cw, ch = int(W * 1.12 / z), int(H * 1.12 / z)  # fenêtre au format 9:16, jamais déformée
            cw, ch = min(cw, big.width), min(ch, big.height)
            x0 = int((big.width - cw) * (pan if scene.get("pan_to") is None else pan + (scene["pan_to"] - pan) * p))
            y0 = (big.height - ch) // 2
            frame = big.crop((x0, y0, x0 + cw, y0 + ch)).resize((W, H), Image.BILINEAR)
        else:
            frame = Image.new("RGB", (W, H), (12, 12, 16))
        # le texte apparaît en 0,25 s (sauf au premier plan : visible dès la première image)
        a = 1.0 if (idx == 0 and scene.get("instant", True)) else min(1.0, i / (0.25 * FPS))
        lay = text if a >= 1 else Image.eval(text, lambda v: v)  # même calque
        if a < 1:
            r, g, b, al = text.split()
            al = al.point(lambda v: int(v * a))
            lay = Image.merge("RGBA", (r, g, b, al))
        frame = Image.alpha_composite(frame.convert("RGBA"), lay).convert("RGB")
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg a échoué pour le plan {idx}")
    tmp.rename(out)


def build(folder: pathlib.Path) -> pathlib.Path:
    cfg = json.loads((folder / "reel.json").read_text(encoding="utf-8"))
    work = folder / "_plans"
    work.mkdir(exist_ok=True)
    parts = []
    for i, sc in enumerate(cfg["scenes"]):
        out = work / f"plan{i:02d}.mp4"
        render_scene(sc, folder, out, i)
        parts.append(out)
    lst = work / "liste.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    silent = work / "muet.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)], check=True)
    total = sum(s["duration"] for s in cfg["scenes"])
    music = ROOT / cfg.get("music", "music/rythme-01.m4a")
    start = cfg.get("music_start", 0)
    final = folder / "reel.mp4"
    tmp = folder / "reel.part.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(silent), "-ss", str(start), "-i", str(music),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-af", f"afade=t=in:d=0.3,afade=t=out:st={total - 1.5}:d=1.5", "-t", str(total), str(tmp)], check=True)
    tmp.rename(final)
    return final


if __name__ == "__main__":
    print(build(pathlib.Path(sys.argv[1])))
