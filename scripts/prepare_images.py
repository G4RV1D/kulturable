"""Télécharge l'image source de chaque post et la met au format Instagram.

Format produit : JPEG de 1080 px de large, la photo en plein cadre (format d'origine,
ramené entre 4:5 et 1,91:1 si besoin), sans fond flou.
Les images déjà prêtes ne sont pas refaites.
"""
import io
import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from PIL import Image

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
    """Photo en plein cadre, comme une publication classique : pas de fond flou.

    On garde le format d'origine de la photo, dans les limites acceptées par Instagram
    (du portrait 4:5 au paysage 1,91:1) ; au-delà, on recadre au centre. Largeur 1080 px.
    """
    r = src.width / src.height
    if r < 0.8:  # trop haut : recadrage en 4:5
        h = round(src.width / 0.8)
        top = (src.height - h) // 2
        src = src.crop((0, top, src.width, top + h))
    elif r > 1.91:  # trop large : recadrage en 1,91:1
        w = round(src.height * 1.91)
        left = (src.width - w) // 2
        src = src.crop((left, 0, left + w, src.height))
    return src.resize((W, round(W * src.height / src.width)), Image.LANCZOS)


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
                    import time; time.sleep(2)
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
