"""Affiche l'auteur et la licence (d'après Wikimedia Commons) des images des posts non publiés.

Sert à vérifier que la ligne « Photo : … » de chaque légende crédite la bonne personne
avec la bonne licence. Usage : python scripts/check_credits.py [id ...]
"""
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "posts" / "queue.json"
UA = "KulturablePublisher/1.0 (+https://github.com)"
API = "https://commons.wikimedia.org/w/api.php"


def clean(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").strip()


def info(title: str) -> dict:
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo",
                                "iiprop": "extmetadata|size", "format": "json"})
    req = urllib.request.Request(f"{API}?{q}", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        page = next(iter(json.load(r)["query"]["pages"].values()))
    ii = page.get("imageinfo", [{}])[0]
    meta = ii.get("extmetadata", {})
    return {"auteur": clean(meta.get("Artist", {}).get("value")),
            "licence": clean(meta.get("LicenseShortName", {}).get("value")),
            "taille": f"{ii.get('width')} x {ii.get('height')}"}


def main() -> int:
    wanted = set(sys.argv[1:])
    for post in json.loads(QUEUE.read_text(encoding="utf-8")):
        if post.get("published_at") or (wanted and post["id"] not in wanted):
            continue
        for img in post.get("images", []):
            page = img.get("credit_page", "")
            if "commons.wikimedia.org/wiki/File:" not in page:
                continue
            title = "File:" + urllib.parse.unquote(page.split("/wiki/File:", 1)[1])
            try:
                print(post["id"], "|", title, "|", info(title))
            except Exception as e:
                print(post["id"], "|", title, "| erreur :", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
