"""Relève les statistiques Instagram : abonnés, et pour chaque post et story récents, vues, portée et interactions.

Résultat : posts/stats/AAAA-MM-JJTHHMM.json et posts/stats/latest.json.
Les statistiques détaillées demandent la permission « instagram_business_manage_insights » ;
sans elle, seuls les j'aime, commentaires et abonnés sont relevés.
"""
import datetime as dt
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from publish import QUEUE, ROOT, call  # noqa: E402

POST_METRICS = ["views", "reach", "likes", "comments", "shares", "saved", "total_interactions"]
STORY_METRICS = ["views", "reach", "replies", "shares", "total_interactions", "navigation"]


def insights(media_id: str, metrics: list, token: str) -> dict:
    out = {}
    for m in metrics:  # une par une : une métrique refusée ne bloque pas les autres
        try:
            data = call("GET", f"{media_id}/insights", {"metric": m, "access_token": token})["data"]
            out[m] = data[0]["values"][0]["value"] if data and data[0].get("values") else data[0].get("total_value", {}).get("value")
        except Exception as e:
            out[m] = None
            out.setdefault("_erreurs", []).append(f"{m}: {str(e)[:160]}")
    return out


def main() -> int:
    token = os.environ["IG_ACCESS_TOKEN"]
    days = int(os.environ.get("DAYS", "10"))
    now = dt.datetime.now(dt.timezone.utc)
    me = call("GET", "me", {"fields": "user_id,username,followers_count,follows_count,media_count", "access_token": token})
    report = {"date": now.isoformat(timespec="seconds"), "compte": me, "posts": []}
    posts = json.loads(QUEUE.read_text(encoding="utf-8"))
    for p in posts:
        if not p.get("published_at"):
            continue
        if now - dt.datetime.fromisoformat(p["published_at"]) > dt.timedelta(days=days):
            continue
        entry = {"id": p["id"], "publie": p["published_at"]}
        try:
            entry["base"] = call("GET", p["media_id"], {"fields": "like_count,comments_count,permalink", "access_token": token})
        except Exception as e:
            entry["base"] = {"erreur": str(e)[:200]}
        entry["stats"] = insights(p["media_id"], POST_METRICS, token)
        if p.get("story_media_id"):
            entry["story"] = insights(p["story_media_id"], STORY_METRICS, token)
            entry["story_publiee"] = p.get("story_published_at")
        report["posts"].append(entry)
    out = ROOT / "posts" / "stats"
    out.mkdir(exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    (out / f"{now:%Y-%m-%dT%H%M}.json").write_text(text, encoding="utf-8")
    (out / "latest.json").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
