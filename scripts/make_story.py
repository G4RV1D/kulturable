"""Fabrique l'image de story (1080 x 1920) d'un post : la photo, l'accroche et un renvoi vers le post.

Usage : python scripts/make_story.py <id du post> [chemin de l'image source]
Sortie : stories/<id>.jpg
"""
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT = ROOT / "fonts" / "Poppins-Bold.ttf"
W, H = 1080, 1920
ACCENT = (255, 196, 72)


def photo_region(post_img: Image.Image) -> Image.Image:
    """Récupère la photo nette au centre de l'image du post (sans le fond flouté)."""
    import numpy as np
    a = np.asarray(post_img.convert("L"), dtype=np.float32)
    # détail fin : écart entre pixels voisins (quasi nul dans le fond flouté)
    gy = np.abs(np.diff(a, axis=0))[:, :-1]
    gx = np.abs(np.diff(a, axis=1))[:-1, :]
    g = gx + gy
    rows, cols = g.mean(axis=1), g.mean(axis=0)
    def bounds(v):
        thr = max(np.percentile(v, 95) * 0.25, 1.5)
        idx = np.flatnonzero(v > thr)
        return (int(idx[0]), int(idx[-1]) + 1) if len(idx) else (0, len(v))
    y0, y1 = bounds(rows)
    x0, x1 = bounds(cols)
    w, h = post_img.size
    if (x1 - x0) < w * 0.4 or (y1 - y0) < h * 0.3:
        return post_img
    return post_img.crop((x0 + 2, y0 + 2, x1 - 2, y1 - 2))


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split():
        test = (cur + " " + word).strip()
        if draw.textlength(test, font=font) <= width:
            cur = test
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def make(post_id: str, src: pathlib.Path | None = None) -> pathlib.Path:
    queue = json.loads((ROOT / "posts" / "queue.json").read_text(encoding="utf-8"))
    post = next(p for p in queue if p["id"] == post_id)
    hook = (ROOT / post["caption_file"]).read_text(encoding="utf-8").split("\n")[0].strip()
    title, _, sentence = hook.partition(" : ")
    sentence = sentence[:1].upper() + sentence[1:]

    img = Image.open(src or ROOT / "images" / f"{post_id}.jpg").convert("RGB")
    photo = photo_region(img) if src is None else img

    # fond : la photo agrandie et floutée, assombrie
    bg = photo.copy()
    s = max(W / bg.width, H / bg.height)
    bg = bg.resize((int(bg.width * s) + 1, int(bg.height * s) + 1))
    bg = bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H))
    bg = bg.filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (8, 8, 12)), 0.55)

    d0 = ImageDraw.Draw(bg)
    f_brand = ImageFont.truetype(str(FONT), 34)
    f_title = ImageFont.truetype(str(FONT), 52)
    f_text = ImageFont.truetype(str(FONT), 58)
    f_cta = ImageFont.truetype(str(FONT), 38)
    t_lines = wrap(d0, title, f_title, W - 140)
    s_lines = wrap(d0, sentence, f_text, W - 140)
    text_h = len(t_lines) * 66 + 24 + len(s_lines) * 76

    # photo nette en haut, pleine largeur, coins arrondis ; sa hauteur s'adapte au texte
    pw = W - 80
    cy = H - 300  # bouton hors de la zone couverte par la barre de réponse
    ph = max(600, min(960, (cy - 46 - 50) - 200 - 70 - text_h))
    ps = max(pw / photo.width, ph / photo.height)
    p = photo.resize((int(photo.width * ps) + 1, int(photo.height * ps) + 1))
    p = p.crop(((p.width - pw) // 2, (p.height - ph) // 2, (p.width - pw) // 2 + pw, (p.height - ph) // 2 + ph))
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw, ph), 36, fill=255)
    py = 200
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle((40, py + 14, 40 + pw, py + 14 + ph), 36, fill=160)
    bg = Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), bg, shadow.filter(ImageFilter.GaussianBlur(24)))
    bg.paste(p, (40, py), mask)

    d = ImageDraw.Draw(bg)

    d.text((W // 2, 140), "@kulturable", font=f_brand, fill=(255, 255, 255), anchor="mm")

    y = py + ph + 70
    for line in t_lines:
        d.text((W // 2, y), line, font=f_title, fill=ACCENT, anchor="mm")
        y += 66
    y += 24
    for line in s_lines:
        d.text((W // 2, y), line, font=f_text, fill=(255, 255, 255), anchor="mm",
               stroke_width=2, stroke_fill=(0, 0, 0))
        y += 76

    # renvoi vers le post
    cta = "Toute l'histoire dans le dernier post"
    tw = d.textlength(cta, font=f_cta)
    d.rounded_rectangle((W // 2 - tw / 2 - 40, cy - 46, W // 2 + tw / 2 + 40, cy + 46), 46, fill=(255, 255, 255))
    d.text((W // 2, cy), cta, font=f_cta, fill=(20, 20, 24), anchor="mm")

    out = ROOT / "stories" / f"{post_id}.jpg"
    out.parent.mkdir(exist_ok=True)
    bg.save(out, "JPEG", quality=92)
    return out


if __name__ == "__main__":
    print(make(sys.argv[1], pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None))
