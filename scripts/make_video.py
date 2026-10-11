"""Monte une vidéo TikTok verticale (1080 x 1920) à partir d'un dossier tiktok/<id>/.

Contenu du dossier :
  script.txt   le texte lu, un paragraphe par plan (séparés par une ligne vide)
  video.json   les images de chaque plan (sources, recadrage, sens du zoom)
  voix.*       (facultatif) l'enregistrement de la voix : m4a, mp3, wav, ogg, aac, opus

Sans voix, le script produit apercu.mp4, muet, au rythme d'une lecture normale.
Avec la voix, il produit video.mp4 : chaque plan dure à proportion de son texte.

Usage : python scripts/make_video.py tiktok/01-disque-rosetta [--force]
"""
import hashlib
import io
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "fonts" / "Poppins-Bold.ttf"
W, H, FPS = 1080, 1920, 30
ZOOM = 1.12          # amplitude du lent mouvement de caméra
WORDS_PER_SEC = 2.6  # rythme de lecture pour l'aperçu sans voix
UA = "KulturablePublisher/1.0 (+https://github.com)"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


# ---------- entrées ----------

def paragraphs(folder: pathlib.Path) -> list:
    text = (folder / "script.txt").read_text(encoding="utf-8").strip()
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def find_voice(folder: pathlib.Path):
    for ext in ("m4a", "mp3", "wav", "ogg", "aac", "opus", "webm"):
        for f in folder.glob(f"voix*.{ext}"):
            return f
    return None


def audio_duration(path: pathlib.Path) -> float:
    out = subprocess.run([FFMPEG, "-i", str(path)], capture_output=True, text=True).stderr
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def load_image(urls: list, cache: pathlib.Path) -> Image.Image:
    if cache.exists():
        return Image.open(cache).convert("RGB")
    last = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                img = Image.open(io.BytesIO(r.read())).convert("RGB")
            img.save(cache, "JPEG", quality=92)
            return img
        except Exception as e:
            last = e
            print(f"   échec {url} : {e}")
    raise RuntimeError(f"Aucune source utilisable pour {cache.name} ({last})")


# ---------- image ----------

def base_canvas(src: Image.Image, crop) -> Image.Image:
    """Image entière sur fond flou, à la taille agrandie pour le mouvement de caméra."""
    if crop:
        l, t, r, b = crop
        src = src.crop((round(l * src.width), round(t * src.height),
                        round(r * src.width), round(b * src.height)))
    BW, BH = round(W * ZOOM), round(H * ZOOM)
    s = max(BW / src.width, BH / src.height)
    bg = src.resize((round(src.width * s), round(src.height * s)), Image.BILINEAR)
    x, y = (bg.width - BW) // 2, (bg.height - BH) // 2
    bg = bg.crop((x, y, x + BW, y + BH)).filter(ImageFilter.GaussianBlur(45))
    bg = ImageEnhance.Brightness(bg).enhance(0.4)
    s = min(BW / src.width, BH * 0.62 / src.height)  # laisse de la place aux sous-titres
    fg = src.resize((round(src.width * s), round(src.height * s)), Image.LANCZOS)
    bg.paste(fg, ((BW - fg.width) // 2, round(BH * 0.36 - fg.height / 2)))
    return bg


def camera(base: Image.Image, t: float, direction: str) -> Image.Image:
    """t de 0 à 1 : zoom avant ('in') ou arrière ('out'), centré."""
    k = t if direction == "in" else 1 - t
    k = k * k * (3 - 2 * k)  # mouvement doux
    z = 1 + (ZOOM - 1) * k   # 1 = plan large, ZOOM = plan serré
    cw, ch = base.width / z, base.height / z
    x, y = (base.width - cw) / 2, (base.height - ch) / 2
    return base.resize((W, H), Image.BILINEAR, box=(x, y, x + cw, y + ch))


# ---------- sous-titres ----------

def chunks(paragraph: str, max_words: int = 5) -> list:
    """Découpe en petits blocs de mots, en coupant de préférence après la ponctuation."""
    words, out, cur = paragraph.split(), [], []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or (len(cur) >= 2 and re.search(r"[.,:;?!…]$", w)):
            out.append(" ".join(cur))
            cur = []
    if cur:
        out.append(" ".join(cur))
    return out


def draw_caption(frame: Image.Image, text: str, font: ImageFont.FreeTypeFont) -> None:
    d = ImageDraw.Draw(frame)
    lines, line = [], ""
    for w in text.split():
        trial = (line + " " + w).strip()
        if d.textlength(trial, font=font) > 900 and line:
            lines.append(line)
            line = w
        else:
            line = trial
    lines.append(line)
    y = 1290 - len(lines) * 45
    for ln in lines:
        x = (W - d.textlength(ln, font=font)) / 2
        d.text((x, y), ln, font=font, fill="white", stroke_width=7, stroke_fill="black")
        y += 92


def draw_signature(frame: Image.Image, font: ImageFont.FreeTypeFont) -> None:
    d = ImageDraw.Draw(frame)
    txt = "@kulturable"
    d.text(((W - d.textlength(txt, font=font)) / 2, 150), txt, font=font,
           fill=(255, 255, 255, 200), stroke_width=3, stroke_fill="black")


# ---------- montage ----------

def build(folder: pathlib.Path, force: bool = False) -> pathlib.Path:
    spec = json.loads((folder / "video.json").read_text(encoding="utf-8"))
    paras = paragraphs(folder)
    segs = spec["segments"]
    if len(segs) != len(paras):
        raise ValueError(f"{len(paras)} paragraphes mais {len(segs)} plans dans video.json")
    voice = find_voice(folder)
    out = folder / ("video.mp4" if voice else "apercu.mp4")

    # Ne refait la vidéo que si une entrée a changé.
    h = hashlib.sha256()
    for f in sorted([folder / "script.txt", folder / "video.json", pathlib.Path(__file__)] + ([voice] if voice else [])):
        h.update(f.read_bytes())
    stamp = folder / f".{out.stem}.hash"
    if out.exists() and stamp.exists() and stamp.read_text() == h.hexdigest() and not force:
        print(f"{out} est déjà à jour.")
        return out

    weights = [len(p.split()) + 1.5 for p in paras]  # +1.5 : la pause entre deux paragraphes
    total = audio_duration(voice) + 0.6 if voice else sum(weights) / WORDS_PER_SEC
    durations = [total * w / sum(weights) for w in weights]
    print(f"{folder.name} : {len(paras)} plans, {total:.1f} s, voix : {voice.name if voice else 'aucune (aperçu)'}")

    cache = folder / "_images"
    cache.mkdir(exist_ok=True)
    sources = {k: load_image(v, cache / f"{k}.jpg") for k, v in spec["images"].items()}
    cap_font = ImageFont.truetype(str(FONT), 68)
    sig_font = ImageFont.truetype(str(FONT), 40)

    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if voice:
        cmd += ["-i", str(voice), "-c:a", "aac", "-b:a", "192k", "-af", "apad"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-t", f"{total:.2f}", str(out)]
    ff = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    for seg, para, dur in zip(segs, paras, durations):
        base = base_canvas(sources[seg["image"]], seg.get("crop"))
        caps = chunks(para)
        cap_w = [len(c.split()) for c in caps]
        n = max(1, round(dur * FPS))
        for i in range(n):
            t = i / n
            # sous-titre courant, à proportion du nombre de mots
            acc, idx = 0, len(caps) - 1
            for j, cw in enumerate(cap_w):
                acc += cw / sum(cap_w)
                if t < acc:
                    idx = j
                    break
            frame = camera(base, t, seg.get("zoom", "in"))
            draw_signature(frame, sig_font)
            draw_caption(frame, caps[idx], cap_font)
            ff.stdin.write(frame.tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg a échoué")
    stamp.write_text(h.hexdigest())
    print(f"OK : {out}")
    return out


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    folders = [pathlib.Path(a) for a in args] or sorted(p for p in (ROOT / "tiktok").iterdir() if p.is_dir())
    failed = 0
    for f in folders:
        try:
            build(f, force)
        except Exception as e:
            failed += 1
            print(f"ÉCHEC {f.name} : {e}")
    sys.exit(1 if failed else 0)
