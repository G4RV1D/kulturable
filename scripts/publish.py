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
  STORY_ONLY       identifiant d'un post déjà publié dont on publie seulement la story

Après chaque post, sa story (stories/<id>.jpg) est publiée si elle existe.
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

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


def wait_ready(container: str, token: str) -> None:
    for _ in range(30):  # Instagram traite le média avant publication
        status = call("GET", container, {"fields": "status_code", "access_token": token})
        if status.get("status_code") == "FINISHED":
            return
        if status.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram a refusé le média : {status}")
        time.sleep(5)
    raise RuntimeError("Instagram n'a pas fini de traiter le média à temps.")


def publish_story(post: dict, user_id: str, token: str) -> None:
    """Publie la story du post ; un échec n'annule pas le post."""
    if post.get("story_media_id") or not (ROOT / "stories" / f"{post['id']}.jpg").exists():
        return
    base = os.environ["IMAGE_BASE_URL"].rstrip("/").rsplit("/images", 1)[0]
    url = f"{base}/stories/{post['id']}.jpg"
    try:
        check_image_online(url)
        container = call("POST", f"{user_id}/media",
                         {"image_url": url, "media_type": "STORIES", "access_token": token})["id"]
        wait_ready(container, token)
        media = call("POST", f"{user_id}/media_publish", {"creation_id": container, "access_token": token})
        post["story_media_id"] = media["id"]
        post["story_published_at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        print(f"Story publiée : {post['id']} (media {media['id']})")
    except Exception as e:
        print(f"Story non publiée pour {post['id']} : {e}")


def main() -> int:
    dry = os.environ.get("DRY_RUN") == "1"
    force = os.environ.get("FORCE_ID", "").strip()
    token = os.environ.get("IG_ACCESS_TOKEN", "")
    base = os.environ["IMAGE_BASE_URL"].rstrip("/")
    posts = json.loads(QUEUE.read_text(encoding="utf-8"))
    now = dt.datetime.now(dt.timezone.utc)

    story_only = os.environ.get("STORY_ONLY", "").strip()
    if story_only:
        post = next(p for p in posts if p["id"] == story_only)
        me = call("GET", "me", {"fields": "user_id,username", "access_token": token})
        if dry:
            print(f"Mode test : story de {story_only} prête, rien publié.")
            return 0
        publish_story(post, me.get("user_id") or me["id"], token)
        QUEUE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0 if post.get("story_media_id") else 1

    if force:
        due = [p for p in posts if p["id"] == force and not p["published_at"]]
    else:
        due = [p for p in posts if p["approved"] and not p["published_at"]
               and dt.datetime.fromisoformat(p["publish_at"]) <= now]
        due.sort(key=lambda p: p["publish_at"])
    if not due and dry:
        due = [p for p in posts if p["approved"] and not p["published_at"]][:1]
        if due:
            print(f"Mode test : vérification du prochain post ({due[0]['id']}).")
    if not due:
        print("Rien à publier pour l'instant.")
        return 0

    post = due[0]
    if not post["approved"]:
        print(f"{post['id']} n'est pas validé : publication refusée.")
        return 1
    caption = (ROOT / post["caption_file"]).read_text(encoding="utf-8").strip()
    check_caption(caption, post["id"])
    from prepare_images import image_files
    image_urls = [f"{base}/{name}" for name, _, _ in image_files(post)]
    for url in image_urls:
        check_image_online(url)
    print(f"Prêt : {post['id']} ({len(caption)} caractères), {len(image_urls)} image(s)")

    if not token:
        print("IG_ACCESS_TOKEN manquant.")
        return 1
    me = call("GET", "me", {"fields": "user_id,username", "access_token": token})
    user_id = me.get("user_id") or me["id"]
    print(f"Clé Instagram valide pour le compte @{me.get('username')}.")
    if dry:
        print("Mode test : rien n'a été publié.")
        return 0
    if len(image_urls) == 1:
        container = call("POST", f"{user_id}/media",
                         {"image_url": image_urls[0], "caption": caption, "access_token": token})["id"]
    else:  # carrousel : un conteneur par image, puis le conteneur du carrousel
        children = []
        for url in image_urls:
            child = call("POST", f"{user_id}/media",
                         {"image_url": url, "is_carousel_item": "true", "access_token": token})["id"]
            wait_ready(child, token)
            children.append(child)
        container = call("POST", f"{user_id}/media",
                         {"media_type": "CAROUSEL", "children": ",".join(children),
                          "caption": caption, "access_token": token})["id"]
    wait_ready(container, token)
    media = call("POST", f"{user_id}/media_publish",
                 {"creation_id": container, "access_token": token})

    post["published_at"] = now.isoformat(timespec="seconds")
    post["media_id"] = media["id"]
    QUEUE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Publié sur @{me.get('username')} : {post['id']} (media {media['id']})")
    publish_story(post, user_id, token)
    QUEUE.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
