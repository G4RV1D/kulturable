"""Publie sur Instagram le prochain post validé dont l'heure est passée.

Règles :
- seuls les posts marqués "approved": true sont publiés ;
- un seul post par exécution, le plus ancien en attente ;
- après publication, le post est marqué publié dans queue.json.

Variables d'environnement :
  IG_ACCESS_TOKEN  clé d'accès Instagram (secret GitHub)
  IMAGE_BASE_URL   adresse publique du dossier images/
  DRY_RUN          "1" pour tout vérifier sans rien publier
  FORCE_ID         identifiant d'un post à publier tout de suite (test manuel)
"""
import datetime as dt
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "posts" / "queue.json"
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
MAX_CAPTION = 2200
MAX_HASHTAGS = 30


def call(method: str, path: str, params: dict) -> dict:
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    if method == "GET":
        url, data = f"{url}?{data.decode()}", None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Erreur API Instagram {e.code} : {e.read().decode()[:500]}")


def check_caption(text: str, post_id: str) -> None:
    if len(text) > MAX_CAPTION:
        raise ValueError(f"{post_id} : légende trop longue ({len(text)} > {MAX_CAPTION})")
    tags = sum(1 for w in text.split() if w.startswith("#"))
    if tags > MAX_HASHTAGS:
        raise ValueError(f"{post_id} : trop de hashtags ({tags})")


def check_image_online(url: str) -> None:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        ctype = r.headers.get("Content-Type", "")
        if "jpeg" not in ctype:
            raise ValueError(f"L'image {url} n'est pas servie en JPEG ({ctype})")


def main() -> int:
    dry = os.environ.get("DRY_RUN") == "1"
    force = os.environ.get("FORCE_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    base = os.environ["IMAGE_BASE_URL"].rstrip("/")
    posts = json.loads(QUEUE.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)

    if force:
        due = [p for p in posts if p["id"] == force and not p["published_at"]]
    else:
        due = [p for p in posts if p["approved"] and not p["published_at"]
               and dt.datetime.fromisoformat(p["publish_at"]) <= now]
        due.sort(key=lambda p: p["publish_at"])
    if not due:
        print("Rien à publier pour l'instant.")
        return 0

    post = due[0]
    if not post["approved"]:
        print(f"{post['id']} n'est pas validé : publication refusée.")
        return 1
    caption = (ROOT / post["caption_file"]).read_text(encoding="utf-8").strip()
    check_caption(caption, post["id"])
    image_url = f"{base}/{post['id']}.jpg"
    check_image_online(image_url)
    print(f"Prêt : {post['id']} ({len(caption)} caractères) avec {image_url}")

    if dry:
        print("Mode test : rien n'a été publié.")
        return 0
    if not token:
        print("IG_ACCESS_TOKEN manquant.")
        return 1

    me = call("GET", "me", {"fields": "user_id,username", "access_token": token})
    user_id = me.get("user_id") or me["id"]
    container = call("POST", f"{user_id}/media",
                     {"image_url": image_url, "caption": caption, "access_token": token})["id"]
    for _ in range(30):  # Instagram traite l'image avant publication
        status = call("GET", container, {"fields": "status_code", "access_token": token})
        if status.get("status_code") == "FINISHED":
            break
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram a refusé l'image : {status}")
        time.sleep(5)
    media = call("POST", f"{user_id}/media_publish",
                 {"creation_id": container, "access_token": token})

    post["published_at"] = now.isoformat(timespec="seconds")
    post["media_id"] = media["id"]
    QUEUE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Publié sur @{me.get('username')} : {post['id']} (media {media['id']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
