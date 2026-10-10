"""Prolonge la clé d'accès Instagram (valable 60 jours) et met à jour le secret GitHub.

Lancé automatiquement chaque semaine. Si Instagram renvoie une nouvelle clé,
elle remplace l'ancienne dans le secret IG_ACCESS_TOKEN grâce à la commande gh
(il faut le secret GH_PAT, voir README).
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

token = os.environ["IG_ACCESS_TOKEN"]
url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
    {"grant_type": "ig_refresh_token", "access_token": token})
with urllib.request.urlopen(url, timeout=60) as r:
    data = json.loads(r.read())

new = data["access_token"]
days = int(data.get("expires_in", 0)) // 86400
print(f"Clé prolongée : encore {days} jours de validité.")

if new != token:
    if not os.environ.get("GH_TOKEN"):
        print("Nouvelle clé reçue mais GH_PAT absent : impossible de mettre à jour le secret.")
        sys.exit(1)
    subprocess.run(["gh", "secret", "set", "IG_ACCESS_TOKEN", "--body", new], check=True)
    print("Secret IG_ACCESS_TOKEN mis à jour.")
