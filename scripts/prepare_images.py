"""Télécharge l'image source de chaque post et la met au format Instagram.

Format produit : JPEG 1080 x 1350 (portrait 4:5). L'image d'origine est
affichée en entier, sans recadrage, sur un fond flou tiré d'elle-même.
Les images déjà prêtes ne sont pas refaites.
"""
import io
import json
import pathlib
import sys
import urllib.request

from PIL import Image, ImageFilter, ImageEnhance

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "posts" / "queue.json"
OUT_DIR = ROOT / "images"
W, H = 1080, 1350
UA = "KulturablePublisher/1.0 (+https://github.com)"


def download(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    img = Image.open(io.BytesIO(data))
    img.load()
    return img.convert("RGB")


def compose(src: Image.Image) -> Image.Image:
    # Fond : l'image agrandie pour couvrir, floutée et assombrie.
    scale = max(W / src.width, H / src.height)
    bg = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left, top = (bg.width - W) // 2, (bg.height - H) // 2
    bg = bg.crop((left, top, left + W, top + H)).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.45)
    # Premier plan : l'image entière, ajustée au cadre.
    scale = min(W / src.width, H / src.height)
    fg = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return bg


def main() -> int:
    posts = json.loads(QUEUE.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(exist_ok=True)
    failed = []
    for post in posts:
        out = OUT_DIR / f"{post['id']}.jpg"
        if out.exists():
            continue
        for url in post["image_sources"]:
            try:
                img = compose(download(url))
                img.save(out, "JPEG", quality=92, optimize=True, progressive=True)
                print(f"OK   {post['id']} <- {url}")
                break
            except Exception as e:  # on essaie la source suivante
                print(f"..   {post['id']} : échec avec {url} ({e})")
        else:
            failed.append(post["id"])
    if failed:
        print("Images introuvables pour : " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
