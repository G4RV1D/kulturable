"""Recherche d'images libres sur Wikimedia Commons (licence, auteur, miniatures) pour préparer les posts."""
import json, pathlib, re, urllib.parse, urllib.request
UA = {"User-Agent": "KulturableBot/1.0 (github.com/G4RV1D/kulturable)"}
API = "https://commons.wikimedia.org/w/api.php"
def get(params):
    url = API + "?" + urllib.parse.urlencode(dict(params, format="json", origin="*"))
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60))
def strip(s): return re.sub(r"<[^>]+>", "", s or "").strip()[:200]
q = json.loads(pathlib.Path("recherche/queries.json").read_text(encoding="utf-8"))
out, thumbs = {}, pathlib.Path("recherche/thumbs"); thumbs.mkdir(exist_ok=True)
for key, queries in q.items():
    res = []
    for query in queries:
        p = {"action": "query", "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": 360}
        if query.startswith("File:"): p["titles"] = query
        else: p.update(generator="search", gsrsearch=query + " filetype:bitmap", gsrnamespace=6, gsrlimit=12)
        try: pages = get(p).get("query", {}).get("pages", {})
        except Exception as e: res.append({"q": query, "err": str(e)}); continue
        for pg in sorted(pages.values(), key=lambda x: x.get("index", 0)):
            ii = (pg.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {})
            lic = m.get("LicenseShortName", {}).get("value", "")
            res.append({"q": query, "title": pg["title"], "w": ii.get("width"), "h": ii.get("height"),
                        "lic": lic, "artist": strip(m.get("Artist", {}).get("value")),
                        "credit": strip(m.get("Credit", {}).get("value")), "date": strip(m.get("DateTimeOriginal", {}).get("value")),
                        "desc": strip(m.get("ImageDescription", {}).get("value")), "url": ii.get("url"), "thumb": ii.get("thumburl")})
    # miniatures des 8 premières images de taille suffisante
    keep = [r for r in res if r.get("thumb") and (r.get("w") or 0) >= 1000][:8]
    for i, r in enumerate(keep):
        try:
            data = urllib.request.urlopen(urllib.request.Request(r["thumb"], headers=UA), timeout=60).read()
            fn = thumbs / f"{key}-{i}.jpg"; fn.write_bytes(data); r["local"] = fn.name
        except Exception as e: r["thumb_err"] = str(e)
    out[key] = res
pathlib.Path("recherche/results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
