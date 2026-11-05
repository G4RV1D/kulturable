"""Relève les statistiques de chaque Reel publié (entrées "type": "reel" de posts/queue.json).

Pour chaque Reel : les métriques d'insights Reels de l'API Instagram (une requête par métrique,
pour qu'une métrique refusée ne bloque pas les autres), plus like_count / comments_count,
et le nombre d'abonnés du compte au moment du relevé (pour estimer les abonnés gagnés).

Lancé chaque jour : chaque Reel est donc relevé à J+1, J+2, … J+7, J+30…, ce qui donne
une courbe d'évolution. Résultat : reels/stats/AAAA-MM-JJTHHMM.json et reels/stats/latest.json.

Les métriques détaillées (vues, portée, temps de visionnage…) demandent la permission
« instagram_business_manage_insights ». Sans elle, l'API répond 403 : seuls les j'aime,
les commentaires et les abonnés sont relevés, et l'analyse s'en contente.

Métriques retenues (source : developers.facebook.com/docs/instagram-platform/reference/
instagram-media/insights, consultée le 5/11/2026), valables pour media_product_type REELS :
  views, reach, likes, comments, shares, saved, total_interactions, reposts,
  ig_reels_avg_watch_time, ig_reels_video_view_total_time, reels_skip_rate
Écartées :
  plays, clips_replays_count, ig_reels_aggregated_all_plays_count : dépréciées (v22.0, 21/04/2025) ;
  impressions, video_views : dépréciées ;
  crossposted_views, facebook_views : erreur si le Reel n'est pas partagé sur Facebook (notre cas) ;
  total_views, total_likes, total_comments : réservées à la connexion Facebook (Facebook Login).

Variables d'environnement :
  IG_ACCESS_TOKEN  clé d'accès Instagram (secret GitHub)
  DAYS             âge maximal (en jours) des Reels relevés, 90 par défaut
"""
import datetime as dt
import json
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from publish import QUEUE, ROOT, call  # noqa: E402

REEL_METRICS = [
    "views",                           # lectures sur Instagram
    "reach",                           # comptes uniques touchés (estimé)
    "likes",
    "comments",
    "shares",                          # partages (le meilleur signal pour l'algorithme)
    "saved",                           # enregistrements
    "total_interactions",              # likes + enregistrements + commentaires + partages
    "reposts",
    "ig_reels_avg_watch_time",         # temps moyen de visionnage (millisecondes)
    "ig_reels_video_view_total_time",  # temps total de visionnage, relectures comprises (millisecondes)
    "reels_skip_rate",                 # % de vues abandonnées dans les 3 premières secondes
]


def insight(media_id: str, metric: str, token: str):
    """Valeur d'une métrique (None si l'API ne renvoie rien)."""
    data = call("GET", f"{media_id}/insights", {"metric": metric, "access_token": token}).get("data") or []
    if not data:
        return None  # l'API renvoie une liste vide quand la donnée n'est pas (encore) disponible
    d = data[0]
    if d.get("values"):
        return d["values"][0].get("value")
    return (d.get("total_value") or {}).get("value")


def reel_insights(media_id: str, token: str) -> dict:
    out, errors = {}, []
    for m in REEL_METRICS:  # une par une : une métrique refusée ne bloque pas les autres
        try:
            out[m] = insight(media_id, m, token)
        except Exception as e:
            out[m] = None
            errors.append(f"{m}: {str(e)[:160]}")
    if errors:
        out["_erreurs"] = errors
    return out


def permission_missing(errors: list) -> bool:
    """Vrai si les erreurs sont celles d'une permission absente (403, code 10)."""
    return bool(errors) and all("403" in e or '"code":10' in e for e in errors)


def main() -> int:
    token = os.environ["IG_ACCESS_TOKEN"]
    days = int(os.environ.get("DAYS", "90"))
    now = dt.datetime.now(dt.timezone.utc)
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    reels = [p for p in queue if p.get("type") == "reel" and p.get("published_at") and p.get("media_id")]
    reels = [p for p in reels if now - dt.datetime.fromisoformat(p["published_at"]) <= dt.timedelta(days=days)]
    if not reels:
        print("Aucun Reel publié à relever pour l'instant.")
        return 0

    me = call("GET", "me", {"fields": "user_id,username,followers_count,follows_count,media_count",
                            "access_token": token})
    report = {"date": now.isoformat(timespec="seconds"), "compte": me,
              "metriques_demandees": REEL_METRICS, "reels": []}
    refus = 0
    for p in reels:
        published = dt.datetime.fromisoformat(p["published_at"])
        entry = {"id": p["id"], "media_id": p["media_id"], "publie": p["published_at"],
                 "age_heures": round((now - published).total_seconds() / 3600, 1)}
        try:
            entry["base"] = call("GET", p["media_id"], {
                "fields": "like_count,comments_count,permalink,media_product_type,timestamp",
                "access_token": token})
        except Exception as e:
            entry["base"] = {"erreur": str(e)[:200]}
        entry["stats"] = reel_insights(p["media_id"], token)
        if permission_missing(entry["stats"].get("_erreurs", [])) and len(entry["stats"]["_erreurs"]) == len(REEL_METRICS):
            refus += 1
        report["reels"].append(entry)
    report["insights_autorises"] = refus < len(report["reels"])
    if not report["insights_autorises"]:
        print("Métriques détaillées refusées (permission instagram_business_manage_insights absente) : "
              "seuls j'aime, commentaires et abonnés sont relevés.")

    out = ROOT / "reels" / "stats"
    out.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    (out / f"{now:%Y-%m-%dT%H%M}.json").write_text(text, encoding="utf-8")
    (out / "latest.json").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
