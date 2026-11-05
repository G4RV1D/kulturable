"""Monte un Reel court sans voix : des photos qui défilent (léger zoom), un texte à l'écran par plan,
et un écran de fin. Format 1080 x 1920, 30 images/s.

Sans "music" dans reel.json (ou "music": null), le Reel est muet (piste son silencieuse).
"images" dans reel.json : nom du fichier -> titre Wikimedia Commons ("File:...") ou URL ;
les images manquantes sont téléchargées dans _images/.

Usage : python scripts/make_reel.py reels/<dossier>   (lit reel.json, écrit reel.mp4 et apercu.mp4)
"""
import io
import json
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

import imageio_ffmpeg
import numpy as np
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


def text_layer(lines_spec, y_frac=0.70):
    """Calque transparent : léger dégradé sombre en bas de l'écran et texte posé dessus, sans encadré.

    Le haut de la photo reste intact. Le texte reste dans la zone visible des Reels :
    au-dessus de la légende (bas de l'écran) et à l'écart des boutons (bord droit).
    """
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # dégradé : transparent jusqu'à 48 % de la hauteur, puis assombrissement progressif
    grad = Image.new("L", (1, H), 0)
    for yy in range(H):
        t = (yy / H - 0.42) / 0.40
        grad.putpixel((0, yy), int(215 * max(0.0, min(1.0, t)) ** 1.3))
    layer.paste(Image.new("RGBA", (W, H), (0, 0, 0, 255)), (0, 0), grad.resize((W, H)))
    d = ImageDraw.Draw(layer)
    width = W - 300  # marges : 150 px de chaque côté (boutons à droite)
    blocks = []
    for txt, size, color in lines_spec:
        f = ImageFont.truetype(FONT, size)
        for ln in wrap(d, txt, f, width):
            blocks.append((ln, f, color, int(size * 1.18)))
        blocks.append(("", None, None, int(size * 0.30)))
    blocks.pop()
    total = sum(b[3] for b in blocks)
    y0 = int(H * y_frac) - total // 2
    # ombre douce du texte
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow)
    y = y0
    for ln, f, color, h in blocks:
        if f:
            ds.text((W // 2 + 3, y + h // 2 + 4), ln, font=f, fill=(0, 0, 0, 200), anchor="mm")
        y += h
    layer = Image.alpha_composite(layer, shadow.filter(ImageFilter.GaussianBlur(6)))
    d = ImageDraw.Draw(layer)
    y = y0
    for ln, f, color, h in blocks:
        if f:
            d.text((W // 2, y + h // 2), ln, font=f, fill=color, anchor="mm")
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
    text = text_layer([(t["text"], t.get("size", 72), tuple(t.get("color", (255, 255, 255)))) for t in scene["text"]],
                      scene.get("text_y", 0.70))
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


UA = "KulturablePublisher/1.0 (+https://github.com)"


def fetch_images(cfg, folder):
    cache = folder / "_images"
    cache.mkdir(exist_ok=True)
    for name, src in cfg.get("images", {}).items():
        out = cache / name
        if out.exists():
            continue
        if (ROOT / src).is_file():  # image fournie dans le dépôt
            shutil.copy(ROOT / src, out)
            print(f"image {name} <- {src}")
            continue
        url = src
        if src.startswith("File:"):
            url = ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                   + urllib.parse.quote(src[5:].replace(" ", "_")) + "?width=2400")
        time.sleep(1)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            Image.open(io.BytesIO(r.read())).convert("RGB").save(out, "JPEG", quality=94)
        print(f"image {name} <- {src}")


OUTRO_LEN = 3.2
NAVY = (40, 43, 53)  # gris ardoise du fond du logo officiel
LOGO = ROOT / "assets" / "logo-kulturable.png"


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def emblem(size, grow):
    """Emblème de la chaîne : une pousse qui sort d'un livre ouvert (« la culture se cultive »)."""
    S = size * 4  # dessin en grand puis réduit : traits lisses
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gold = ACCENT + (255,)
    w = S // 22
    d.ellipse((w, w, S - w, S - w), outline=gold, width=w)
    # livre ouvert
    cx, by = S // 2, int(S * 0.70)
    d.line([(int(S * 0.24), by - S // 20), (cx, by), (int(S * 0.76), by - S // 20)], fill=gold, width=w, joint="curve")
    d.line([(int(S * 0.24), by - S // 20 - S // 12), (cx, by - S // 12), (int(S * 0.76), by - S // 20 - S // 12)],
           fill=gold, width=w // 2, joint="curve")
    # tige et feuilles qui poussent
    top = by - int(S * 0.36 * grow)
    if grow > 0.02:
        d.line([(cx, by - S // 12), (cx, top)], fill=gold, width=w)
    if grow > 0.5:
        k = (grow - 0.5) * 2
        lw, lh = int(S * 0.17 * k), int(S * 0.08 * k)
        y = top + S // 14
        leaf = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        dl = ImageDraw.Draw(leaf)
        dl.ellipse((cx - lw * 2, y - lh, cx, y + lh), fill=gold)
        im.alpha_composite(leaf.rotate(-25, center=(cx, y)))
        leaf = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        dl = ImageDraw.Draw(leaf)
        dl.ellipse((cx, y - lh, cx + lw * 2, y + lh), fill=gold)
        im.alpha_composite(leaf.rotate(25, center=(cx, y)))
    return im.resize((size, size), Image.LANCZOS)


_LOGO_CACHE = {}


def logo_image(size):
    """Logo officiel, bords fondus dans le fond pour qu'on ne voie pas le carré."""
    if size not in _LOGO_CACHE:
        im = Image.open(LOGO).convert("RGB").crop((150, 140, 874, 864)).resize((size, size), Image.LANCZOS)
        yy, xx = np.mgrid[0:size, 0:size]
        r = np.hypot(xx - size / 2, yy - size / 2) / (size / 2)
        mask = np.clip((1.0 - r) / 0.18, 0, 1) * 255
        im = im.convert("RGBA")
        im.putalpha(Image.fromarray(mask.astype(np.uint8)))
        _LOGO_CACHE[size] = im
    return _LOGO_CACHE[size].copy()


def outro_frame(t, stars):
    frame = Image.new("RGBA", (W, H), NAVY + (255,))
    d = ImageDraw.Draw(frame)
    for (x, y, r, ph) in stars:  # poussière d'étoiles qui scintille doucement
        a = int(90 + 80 * np.sin(ph + t * 3))
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 230, 170, a))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    k0 = ease(t / 0.7)
    size = int(560 * (0.86 + 0.14 * k0))
    em = logo_image(size)
    em.putalpha(em.getchannel("A").point(lambda v: int(v * k0)))
    layer.alpha_composite(em, (W // 2 - size // 2, int(H * 0.29) - size // 2))
    dl = ImageDraw.Draw(layer)

    def txt(y, text, size, color, start, dur=0.45, rise=30):
        k = ease((t - start) / dur)
        if k <= 0:
            return
        f = ImageFont.truetype(FONT, size)
        dl.text((W // 2, y + int(rise * (1 - k))), text, font=f, fill=color + (int(255 * k),), anchor="mm")

    txt(int(H * 0.465), "KULTURABLE", 104, ACCENT, 0.35)
    txt(int(H * 0.515), "La culture se cultive", 50, (255, 255, 255), 0.7)
    txt(int(H * 0.575), "Des histoires vraies,", 48, (220, 220, 230), 1.05)
    txt(int(H * 0.603), "insolites et fascinantes.", 48, (220, 220, 230), 1.15)
    txt(int(H * 0.638), "Une nouvelle chaque jour.", 48, (220, 220, 230), 1.25)
    # appel à s'abonner : renvoie vers le vrai bouton « Suivre » d'Instagram, en bas à gauche du Reel
    k = ease((t - 1.6) / 0.35)
    if k > 0:
        cx, cy = W // 2, int(H * 0.705)
        bw, bh = 640, 104
        dl.rounded_rectangle((cx - bw // 2, cy - bh // 2, cx + bw // 2, cy + bh // 2), bh // 2,
                             fill=ACCENT + (int(255 * k),))
        f = ImageFont.truetype(FONT, 46)
        dl.text((cx, cy + 2), "ABONNEZ-VOUS !", font=f, fill=NAVY + (int(255 * k),), anchor="mm")
        f2 = ImageFont.truetype(FONT, 40)
        dl.text((cx, cy + 92), "Touchez « Suivre » juste ici", font=f2, fill=(255, 255, 255, int(235 * k)), anchor="mm")
        # flèche qui rebondit vers le nom du compte (zone du bouton « Suivre »)
        bounce = 14 * np.sin(max(0.0, t - 1.6) * 8)
        x0, y0 = 330 + bounce * 0.6, int(H * 0.775) + bounce
        x1, y1 = 190 + bounce * 0.6, int(H * 0.835) + bounce
        col = ACCENT + (int(255 * k),)
        dl.line([(x0, y0), (x1, y1)], fill=col, width=12)
        ang = np.arctan2(y1 - y0, x1 - x0)
        for da in (2.6, -2.6):
            dl.line([(x1, y1), (x1 + 46 * np.cos(ang + da), y1 + 46 * np.sin(ang + da))], fill=col, width=12)
    frame.alpha_composite(layer)
    return frame.convert("RGB")


def render_outro(out):
    rng = np.random.default_rng(7)
    stars = [(int(rng.uniform(0, W)), int(rng.uniform(0, H)), int(rng.uniform(1, 4)), rng.uniform(0, 6.28))
             for _ in range(140)]
    n = round(OUTRO_LEN * FPS)
    tmp = out.with_name(out.stem + ".part.mp4")
    proc = subprocess.Popen([FFMPEG, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                             "-pix_fmt", "yuv420p", "-r", str(FPS), str(tmp)], stdin=subprocess.PIPE)
    for i in range(n):
        proc.stdin.write(outro_frame(i / FPS, stars).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg a échoué pour l'écran de fin")
    tmp.replace(out)


def build(folder: pathlib.Path) -> pathlib.Path:
    cfg = json.loads((folder / "reel.json").read_text(encoding="utf-8"))
    fetch_images(cfg, folder)
    work = folder / "_plans"
    work.mkdir(exist_ok=True)
    parts = []
    for i, sc in enumerate(cfg["scenes"]):
        out = work / f"plan{i:02d}.mp4"
        render_scene(sc, folder, out, i)
        parts.append(out)
    story = sum(s["duration"] for s in cfg["scenes"])
    if cfg.get("outro", True):  # écran de fin : logo, ce que propose la chaîne, abonnement
        out = work / "fin.mp4"
        render_outro(out)
        parts.append(out)
    lst = work / "liste.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    silent = work / "muet.mp4"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)], check=True)
    total = story + (OUTRO_LEN if cfg.get("outro", True) else 0)
    final = folder / "reel.mp4"
    tmp = folder / "reel.part.mp4"
    if cfg.get("music") == "signature":  # son de la chaîne, chute calée sur la dernière diapositive
        from reel_sound import make as make_sound
        hit = story - cfg["scenes"][-1]["duration"]
        wav = work / "son.wav"
        make_sound(total, hit, str(wav))
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(silent), "-i", str(wav),
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-t", str(total), "-movflags", "+faststart", str(tmp)], check=True)
    elif cfg.get("music"):
        music = ROOT / cfg["music"]
        start = cfg.get("music_start", 0)
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(silent), "-ss", str(start), "-i", str(music),
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-af", f"afade=t=in:d=0.3,afade=t=out:st={total - 1.5}:d=1.5", "-t", str(total), str(tmp)],
                       check=True)
    else:  # Reel muet : piste son silencieuse (format accepté partout)
        subprocess.run([FFMPEG, "-v", "error", "-y", "-i", str(silent), "-f", "lavfi",
                        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "64k",
                        "-t", str(total), "-movflags", "+faststart", str(tmp)], check=True)
    tmp.replace(final)
    shutil.copy(final, folder / "apercu.mp4")
    return final


if __name__ == "__main__":
    folders = [pathlib.Path(a) for a in sys.argv[1:]] or sorted(p.parent for p in (ROOT / "reels").glob("*/reel.json"))
    failed = []
    for f in folders:
        try:
            print(build(f))
        except Exception as e:  # un Reel en échec ne bloque pas les autres
            print(f"ÉCHEC {f.name} : {e}")
            failed.append(f.name)
    sys.exit(1 if failed else 0)
