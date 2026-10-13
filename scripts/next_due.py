"""Affiche le nombre de secondes à attendre avant le prochain post validé non publié.

Si ce post est prévu dans moins de LOOKAHEAD_MIN minutes (ou déjà en retard), on affiche
le délai (0 s'il est en retard) ; sinon -1. Le workflow attend ce délai puis publie : ainsi le
post part à l'heure prévue même quand GitHub déclenche les tâches planifiées en retard.
"""
import datetime as dt
import json
import os

LOOKAHEAD = int(os.environ.get("LOOKAHEAD_MIN", "340")) * 60
now = dt.datetime.now(dt.timezone.utc)
posts = json.load(open("posts/queue.json", encoding="utf-8"))
waits = [(dt.datetime.fromisoformat(p["publish_at"]) - now).total_seconds()
         for p in posts if p.get("approved") and not p.get("published_at")]
nxt = min(waits) if waits else None
print(-1 if nxt is None or nxt > LOOKAHEAD else max(0, int(nxt) + 5))
