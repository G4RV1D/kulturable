"""Exporte toutes les publications du compte (texte, date, lien, type) dans posts/instagram-export.json.

Utilise la clé IG_ACCESS_TOKEN (lecture de ses propres publications uniquement).
"""
import json
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
token = os.environ["IG_ACCESS_TOKEN"]

url = f"{API}/me/media?" + urllib.parse.urlencode({
    "fields": "id,caption,media_type,timestamp,permalink",
    "limit": 50,
    "access_token": token,
})
posts = []
while url:
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read())
    posts += data.get("data", [])
    url = data.get("paging", {}).get("next")

posts.sort(key=lambda p: p["timestamp"])
out = ROOT / "posts" / "instagram-export.json"
out.write_text(json.dumps(posts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{len(posts)} publications exportées dans {out.relative_to(ROOT)}")
