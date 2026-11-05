"""Télécharge les photos telles qu'elles ont été publiées sur Instagram (une par post, toutes celles des carrousels).

Résultat : posts/originaux/<id Instagram>.jpg (et <id>-2.jpg, -3.jpg… pour les carrousels),
plus posts/originaux/index.json (id -> date, première ligne de la légende, fichiers).
Ces photos servent de base aux Reels : chaque Reel reprend au minimum la photo du post d'origine.
"""
import json
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
OUT = ROOT / "posts" / "originaux"
token = os.environ["IG_ACCESS_TOKEN"]


def get(path, **params):
    params["access_token"] = token
    with urllib.request.urlopen(f"{API}/{path}?" + urllib.parse.urlencode(params), timeout=60) as r:
        return json.loads(r.read())


def save(url, name):
    out = OUT / name
    if out.exists():
        return name
    with urllib.request.urlopen(url, timeout=120) as r:
        out.write_bytes(r.read())
    return name


OUT.mkdir(parents=True, exist_ok=True)
index = {}
url = None
data = get("me/media", fields="id,caption,media_type,media_url,thumbnail_url,timestamp", limit=50)
while True:
    for m in data.get("data", []):
        files = []
        try:
            if m["media_type"] == "CAROUSEL_ALBUM":
                kids = get(f"{m['id']}/children", fields="id,media_type,media_url,thumbnail_url")["data"]
                for i, k in enumerate(kids):
                    u = k.get("media_url") if k["media_type"] == "IMAGE" else k.get("thumbnail_url")
                    if u:
                        files.append(save(u, f"{m['id']}{'' if i == 0 else f'-{i + 1}'}.jpg"))
            else:
                u = m.get("media_url") if m["media_type"] == "IMAGE" else m.get("thumbnail_url")
                if u:
                    files.append(save(u, f"{m['id']}.jpg"))
        except Exception as e:
            print(f"{m['id']} : {e}")
        index[m["id"]] = {"date": m["timestamp"], "type": m["media_type"], "fichiers": files,
                          "legende": (m.get("caption") or "").strip().split("\n")[0][:160]}
    nxt = data.get("paging", {}).get("next")
    if not nxt:
        break
    with urllib.request.urlopen(nxt, timeout=60) as r:
        data = json.loads(r.read())
(OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"{len(index)} publications, {sum(len(v['fichiers']) for v in index.values())} photos")
