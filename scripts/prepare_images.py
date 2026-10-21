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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

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


def image_files(post: dict) -> list:
    """Liste (nom de fichier, sources) : une image simple ou plusieurs (carrousel)."""
    imgs = post["images"] if "images" in post else [{"sources": post["image_sources"]}]
    return [(f"{post['id']}.jpg" if i == 0 else f"{post['id']}-{i + 1}.jpg", img["sources"], img.get("crop"))
            for i, img in enumerate(imgs)]


def main() -> int:
    posts = json.loads(QUEUE.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(exist_ok=True)
    failed = []
    for post in posts:
        for name, sources, crop in image_files(post):
            out = OUT_DIR / name
            if out.exists():
                continue
            for url in sources:
                try:
                    src = download(url)
                    if crop:  # recadrage en fractions (gauche, haut, droite, bas)
                        l, h, r, b = crop
                        src = src.crop((round(l * src.width), round(h * src.height),
                                        round(r * src.width), round(b * src.height)))
                    img = compose(src)
                    img.save(out, "JPEG", quality=92, optimize=True, progressive=True)
                    print(f"OK   {name} <- {url}")
                    break
                except Exception as e:  # on essaie la source suivante
                    print(f"..   {name} : échec avec {url} ({e})")
            else:
                failed.append(name)
    # image de story (1080 x 1920) pour chaque post pas encore publié
    from make_story import make as make_story
    for post in posts:
        story = ROOT / "stories" / f"{post['id']}.jpg"
        if post.get("published_at") or story.exists() or not (OUT_DIR / f"{post['id']}.jpg").exists():
            continue
        try:
            make_story(post["id"])
            print(f"OK   story {post['id']}")
        except Exception as e:
            print(f"..   story {post['id']} : {e}")
    if failed:
        print("Images introuvables pour : " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
