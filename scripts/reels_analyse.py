"""Analyse les statistiques des Reels pour savoir ce qui marche et améliorer les suivants.

Croise les relevés de scripts/reels_stats.py (reels/stats/*.json) avec les caractéristiques
de chaque Reel, extraites automatiquement de reels/<dossier>/reel.json et de sa légende :
durée, nombre de diapos, longueur des textes, chiffre dans l'accroche, thème, images,
heure et jour de publication, légende, hashtags…

Produit :
  reels/analyse/rapport.md   rapport lisible (ce qui marche, ce qui ne marche pas, recommandations)
  reels/analyse/modele.json  règles exploitables par la machine (valeurs cibles + niveau de confiance)
  reels/analyse/tableau.html tableau de bord visuel autonome (ouvrir dans un navigateur)

Fonctionne avec ou sans la permission « instagram_business_manage_insights » :
sans elle, le score repose seulement sur les j'aime, commentaires et abonnés.

Variable d'environnement facultative :
  REELS_ROOT  racine du dépôt à analyser (pour les tests sur des données simulées)
"""
import datetime as dt
import html
import json
import math
import os
import pathlib
import re
import statistics
import sys
import unicodedata
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(os.environ.get("REELS_ROOT") or pathlib.Path(__file__).resolve().parent.parent)
PARIS = ZoneInfo("Europe/Paris")
OUTRO_LEN = 3.2      # écran de fin ajouté par make_reel.py (secondes)
MIN_SOLIDE = 8       # en dessous de 8 Reels, aucune conclusion solide
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

# ---------------------------------------------------------------- thèmes (par mots-clés)
# Un mot-clé est comparé au mot entier (pluriels en -s/-x/-e/-es acceptés) ;
# terminé par « * », il accepte tout mot qui commence ainsi.
THEMES = {
    "animaux": ["animal", "animaux", "oiseau", "poisson", "chien", "chat", "mangouste", "phacochere", "vache",
                "troupeau", "abeille", "insecte*", "baleine", "requin", "singe", "elephant", "loup", "serpent",
                "cheval", "chevaux", "ours", "espece", "faune", "fourmi", "pieuvre", "dauphin", "predateur", "bete",
                "crocodile", "crabe"],
    "histoire": ["siecle", "roi", "reine", "empereur", "guerre", "bataille", "antique", "antiquite", "moyen age",
                 "revolution*", "pharaon", "romain", "medieval", "medievaux", "dynastie", "empire", "archeolog*",
                 "ancien", "historique"],
    "science": ["scientifi*", "chercheur", "laboratoire", "decouvert*", "physique", "chimie", "biolog*", "adn",
                "cellule", "bacterie", "experience", "invent*", "espace", "etoile", "planete", "cerveau",
                "medecin", "graine", "radiocarbone", "lumiere", "fossile"],
    "nature": ["fleur", "plante", "arbre", "foret", "glacier", "glaciaire", "volcan", "lac", "riviere",
               "fleuve", "montagne", "desert", "ocean", "mer", "glace", "pergelisol", "roche", "cascade", "falaise"],
    "lieux": ["chateau", "ville", "village", "temple", "monument", "statue", "pyramide", "tour", "cathedrale",
              "musee", "ruine", "palais", "bouddha", "pont", "ile", "cite", "eglise"],
    "personnages": ["homme", "femme", "fiancee", "mariage", "chanteuse", "chanteur", "artiste", "ouvrier",
                    "moine", "enfant", "fille", "garcon", "bergere", "berger", "inventrice", "savant"],
    "mysteres": ["mystere*", "secret", "legende*", "mythe", "enigm*", "inexplique", "fantome", "malediction"],
    "traditions": ["chant", "musique", "tradition*", "rituel", "coutume", "fete", "langue", "danse"],
}


def correspond(mot: str, cle: str) -> bool:
    if cle.endswith("*"):
        return mot.startswith(cle[:-1])
    return mot in (cle, cle + "s", cle + "x", cle + "e", cle + "es")


def sans_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def themes_de(titre: str, textes: str, legende: str) -> list:
    """Thèmes classés par score : titre ×3, textes du Reel ×2, légende ×1."""
    scores = {}
    for poids, bloc in ((3, titre), (2, textes), (1, legende)):
        mots = re.findall(r"[a-z]+", sans_accents(bloc))
        joint = " " + " ".join(mots) + " "
        for theme, cles in THEMES.items():
            n = sum(1 for m in mots for c in cles if " " not in c and correspond(m, c))
            n += sum(joint.count(f" {c} ") for c in cles if " " in c)
            if n:
                scores[theme] = scores.get(theme, 0) + poids * n
    if re.search(r"\b1[0-9]{3}\b", textes + " " + legende):  # une date ancienne : un peu d'histoire
        scores["histoire"] = scores.get("histoire", 0) + 1
    return [t for t, _ in sorted(scores.items(), key=lambda kv: -kv[1])] or ["autre"]


# ---------------------------------------------------------------- outils de lecture
def lire_json(path: pathlib.Path, defaut=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defaut


def date_iso(s):
    try:
        d = dt.datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def nb_mots(s: str) -> int:
    return len(re.findall(r"[\wÀ-ÿ'’-]+", s))


def mediane(v):
    v = [x for x in v if x is not None]
    return statistics.median(v) if v else None


def quantile(v, q):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    i = (len(v) - 1) * q
    lo, hi = math.floor(i), math.ceil(i)
    return v[lo] + (v[hi] - v[lo]) * (i - lo)


def arrondi(x, n=2):
    return None if x is None else round(x, n)


# ---------------------------------------------------------------- caractéristiques d'un Reel
def dossier_du_reel(entry: dict) -> pathlib.Path:
    for cle in ("video_file", "caption_file"):
        if entry.get(cle, "").startswith("reels/"):
            return ROOT / pathlib.Path(entry[cle]).parent
    return ROOT / "reels" / re.sub(r"^reel-", "", entry["id"])


def est_mention(t: dict) -> bool:
    return t.get("size", 60) < 50 or bool(re.search(r"sur (le|notre) profil|abonne", t.get("text", ""), re.I))


def caracteristiques(dossier: pathlib.Path, entry: dict) -> dict:
    cfg = lire_json(dossier / "reel.json", {}) or {}
    scenes = cfg.get("scenes", [])
    # texte de chaque diapo, sans la petite mention d'appel à l'action (« Histoire complète sur le profil »)
    textes = [" ".join(t.get("text", "") for t in s.get("text", []) if not est_mention(t)) for s in scenes]
    durees = [float(s.get("duration", 0)) for s in scenes]
    duree_diapos = sum(durees)
    duree_totale = duree_diapos + (OUTRO_LEN if cfg.get("outro", True) else 0)
    accroche = textes[0] if textes else ""
    mots = [nb_mots(t) for t in textes]
    debits = [m / d for m, d in zip(mots, durees) if d > 0]

    cap_path = ROOT / entry["caption_file"] if entry.get("caption_file") else dossier / "legende.txt"
    legende = cap_path.read_text(encoding="utf-8").strip() if cap_path.exists() else ""
    lignes = [l for l in legende.splitlines() if l.strip()]

    images = cfg.get("images", {})
    utilisees = [s.get("image") for s in scenes if s.get("image")]
    wikimedia = sum(1 for n in set(utilisees) if str(images.get(n, "")).startswith("File:"))
    uniques = len(set(utilisees))
    if not uniques:
        type_images = "aucune"
    elif uniques == 1:
        type_images = "une seule photo"
    elif wikimedia == uniques:
        type_images = "photos libres (Wikimedia)"
    elif wikimedia == 0:
        type_images = "photos personnelles"
    else:
        type_images = "mélange"

    quand = date_iso(entry.get("published_at") or entry.get("publish_at") or "")
    local = quand.astimezone(PARIS) if quand else None
    themes = themes_de(cfg.get("title", ""), " ".join(textes), legende)

    return {
        "titre": cfg.get("title", dossier.name),
        "dossier": str(dossier.relative_to(ROOT)) if dossier.is_relative_to(ROOT) else str(dossier),
        "duree_totale_s": round(duree_totale, 1),
        "duree_diapos_s": round(duree_diapos, 1),
        "nb_diapos": len(scenes),
        "duree_1re_diapo_s": durees[0] if durees else None,
        "duree_moy_diapo_s": arrondi(duree_diapos / len(scenes)) if scenes else None,
        "accroche": accroche,
        "mots_accroche": mots[0] if mots else 0,
        "mots_par_diapo": mots,
        "mots_max_diapo": max(mots) if mots else 0,
        "mots_total": sum(mots),
        "debit_max_mots_s": arrondi(max(debits)) if debits else None,
        "chiffre_accroche": bool(re.search(r"\d", accroche)),
        "chiffre_textes": bool(re.search(r"\d", " ".join(textes))),
        "question_accroche": "?" in accroche,
        "theme": themes[0],
        "themes": themes[:3],
        "type_images": type_images,
        "nb_images": uniques,
        "musique": cfg.get("music"),
        "heure_paris": local.hour if local else None,
        "jour": JOURS[local.weekday()] if local else None,
        "legende_caracteres": len(legende),
        "legende_mots": nb_mots(legende),
        "premiere_ligne_caracteres": len(lignes[0]) if lignes else 0,
        "nb_hashtags": len(re.findall(r"(?<!\w)#\w", legende)),
        "question_legende": any(l.strip().endswith("?") for l in lignes),
    }


# ---------------------------------------------------------------- relevés
def relever_abonnes() -> list:
    """Série (date, abonnés) tirée de tous les relevés (posts et Reels)."""
    points = {}
    for dossier in (ROOT / "posts" / "stats", ROOT / "reels" / "stats"):
        for f in sorted(dossier.glob("*.json")) if dossier.exists() else []:
            if f.name == "latest.json":
                continue
            d = lire_json(f, {}) or {}
            quand, n = date_iso(d.get("date", "")), (d.get("compte") or {}).get("followers_count")
            if quand and isinstance(n, (int, float)):
                points[quand] = n
    return sorted(points.items())


def charger_releves() -> dict:
    """{id du Reel : [relevé normalisé, …]} trié par âge."""
    series = {}
    dossier = ROOT / "reels" / "stats"
    for f in sorted(dossier.glob("*.json")) if dossier.exists() else []:
        if f.name == "latest.json":
            continue
        d = lire_json(f, {}) or {}
        abonnes = (d.get("compte") or {}).get("followers_count")
        for r in d.get("reels", []):
            series.setdefault(r["id"], []).append(normaliser(r, abonnes, d.get("date")))
    for v in series.values():
        v.sort(key=lambda x: x["age_h"])
    return series


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def normaliser(r: dict, abonnes, date) -> dict:
    s, b = r.get("stats") or {}, r.get("base") or {}
    avg = _num(s.get("ig_reels_avg_watch_time"))
    tot = _num(s.get("ig_reels_video_view_total_time"))
    skip = _num(s.get("reels_skip_rate"))
    likes = _num(s.get("likes")) if _num(s.get("likes")) is not None else _num(b.get("like_count"))
    comments = _num(s.get("comments")) if _num(s.get("comments")) is not None else _num(b.get("comments_count"))
    inter = _num(s.get("total_interactions"))
    if inter is None and _num(s.get("views")) is not None:
        inter = sum(_num(s.get(k)) or 0 for k in ("shares", "saved")) + (likes or 0) + (comments or 0)
    return {
        "date": date, "age_h": float(r.get("age_heures") or 0), "abonnes": abonnes,
        "views": _num(s.get("views")), "reach": _num(s.get("reach")),
        "likes": likes, "comments": comments,
        "shares": _num(s.get("shares")), "saved": _num(s.get("saved")), "reposts": _num(s.get("reposts")),
        "interactions": inter,
        # l'API donne les temps en millisecondes ; une petite valeur est supposée déjà en secondes
        "avg_watch_s": None if avg is None else (avg / 1000 if avg > 100 else avg),
        "total_watch_s": None if tot is None else tot / 1000,
        "skip_rate": None if skip is None else (skip * 100 if skip <= 1 else skip),
    }


def releve_de_reference(serie: list) -> tuple:
    """Relevé le plus proche de J+7 sans le dépasser de beaucoup (comparaison équitable)."""
    avant = [x for x in serie if x["age_h"] <= 8 * 24]
    ref = avant[-1] if avant else serie[0]
    return ref, ref["age_h"] < 6 * 24  # provisoire si le Reel a moins de 6 jours


def abonnes_gagnes(publie: dt.datetime, abonnes: list, publications: list):
    """Estimation : (abonnés ~J+1 − abonnés juste avant) ÷ nombre de publications dans l'intervalle."""
    avant = [(d, n) for d, n in abonnes if d <= publie and publie - d <= dt.timedelta(hours=36)]
    apres = [(d, n) for d, n in abonnes if publie + dt.timedelta(hours=18) <= d <= publie + dt.timedelta(hours=60)]
    if not avant or not apres:
        return None
    (d0, n0), (d1, n1) = avant[-1], apres[0]
    nb = max(1, sum(1 for p in publications if d0 < p <= d1))
    return round((n1 - n0) / nb, 2)


# ---------------------------------------------------------------- score
COMPOSANTES_COMPLET = [  # (clé, poids, plus grand = mieux, libellé)
    ("retention", 25, True, "Rétention (temps moyen ÷ durée)"),
    ("partages_1000", 20, True, "Partages pour 1 000 vues"),
    ("vues_par_abonne", 15, True, "Vues par abonné"),
    ("skip_rate", 10, False, "Taux d'abandon avant 3 s"),
    ("enregistrements_1000", 10, True, "Enregistrements pour 1 000 vues"),
    ("taux_interaction", 10, True, "Taux d'interaction"),
    ("abonnes_gagnes", 10, True, "Abonnés gagnés (estimés)"),
]
COMPOSANTES_REDUIT = [
    ("engagement_abonnes", 70, True, "J'aime + commentaires pour 100 abonnés"),
    ("abonnes_gagnes", 30, True, "Abonnés gagnés (estimés)"),
]


def rangs(valeurs: list) -> list:
    """Rangs moyens (1 = plus petit), ex aequo moyennés ; None conservé."""
    idx = sorted((v, i) for i, v in enumerate(valeurs) if v is not None)
    out = [None] * len(valeurs)
    k = 0
    while k < len(idx):
        j = k
        while j + 1 < len(idx) and idx[j + 1][0] == idx[k][0]:
            j += 1
        for m in range(k, j + 1):
            out[idx[m][1]] = (k + j) / 2 + 1
        k = j + 1
    return out


def percentiles(valeurs: list, plus_grand_mieux: bool) -> list:
    r = rangs(valeurs)
    n = sum(1 for v in valeurs if v is not None)
    out = []
    for x in r:
        if x is None:
            out.append(None)
        else:
            p = 50.0 if n == 1 else (x - 1) / (n - 1) * 100
            out.append(p if plus_grand_mieux else 100 - p)
    return out


def spearman(x: list, y: list):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    if len(pairs) < 3:
        return None
    rx, ry = rangs([float(a) for a, _ in pairs]), rangs([b for _, b in pairs])
    mx, my = statistics.mean(rx), statistics.mean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return None if sx == 0 or sy == 0 else sxy / (sx * sy)


def confiance(rho, n: int) -> str:
    """Niveau de confiance d'un lien caractéristique ↔ score (prudent)."""
    if rho is None or n < MIN_SOLIDE:
        return "insuffisante"
    t = abs(rho) * math.sqrt((n - 2) / max(1e-9, 1 - rho * rho))
    if t >= 3 and n >= 15:
        return "élevée"
    if t >= 2:
        return "moyenne"
    if abs(rho) >= 0.3:
        return "faible"
    return "aucune"


# ---------------------------------------------------------------- hypothèses de départ
def modele_de_depart() -> dict:
    """Bonnes pratiques Reels courantes : hypothèses à confirmer par nos propres données."""
    h = "hypothèse de départ, à confirmer"
    return {
        "duree_totale_s": {"cible": 15, "plage": [10, 18], "source": h, "caracteristique": "duree_totale_s",
                           "pourquoi": "Les Reels courts (moins de 15-20 s) sont plus souvent vus en entier, "
                                       "ce qui pèse lourd pour l'algorithme. Écran de fin de 3,2 s compris."},
        "duree_1re_diapo_max_s": {"max": 2.5, "source": h, "caracteristique": "duree_1re_diapo_s",
                                  "pourquoi": "Beaucoup de gens décident en moins de 3 s : la 1re diapo doit "
                                              "accrocher vite et laisser place à la suite."},
        "mots_accroche_max": {"max": 8, "source": h, "caracteristique": "mots_accroche",
                              "pourquoi": "Une accroche courte se lit d'un coup d'œil pendant le défilement."},
        "mots_par_diapo_max": {"max": 12, "source": h, "caracteristique": "mots_max_diapo",
                               "pourquoi": "Au-delà, le texte n'a pas le temps d'être lu."},
        "debit_max_mots_s": {"max": 4.5, "source": h, "caracteristique": "debit_max_mots_s",
                             "pourquoi": "Lecture confortable d'un texte court et percutant : environ 4 mots "
                                         "par seconde au plus (appel à l'action exclu)."},
        "nb_diapos": {"cible": 5, "plage": [4, 7], "source": h, "caracteristique": "nb_diapos",
                      "pourquoi": "Assez de diapos pour un rythme vif, pas trop pour rester court."},
        "chiffre_dans_accroche": {"prefere": True, "source": h, "caracteristique": "chiffre_accroche",
                                  "pourquoi": "Un nombre concret (date, poids, distance) rend l'accroche plus "
                                              "crédible et intrigante."},
        "nb_hashtags": {"plage": [3, 5], "source": h, "caracteristique": "nb_hashtags",
                        "pourquoi": "Instagram conseille 3 à 5 hashtags précis."},
        "premiere_ligne_max_caracteres": {"max": 110, "source": "règle du compte (MEMO.md)",
                                          "caracteristique": "premiere_ligne_caracteres",
                                          "pourquoi": "La 1re ligne doit tenir avant « … plus »."},
        "heure_conseillee_paris": {"valeur": 12, "plage": [11, 20], "source": h, "caracteristique": "heure_paris",
                                   "pourquoi": "Midi et la soirée sont des pics d'utilisation ; les Reels "
                                               "sont programmés à midi, les posts à 18 h."},
        "jours_conseilles": {"valeur": JOURS, "source": h, "caracteristique": "jour",
                             "pourquoi": "Aucun jour n'est privilégié tant que les données ne le montrent pas."},
        "themes_a_privilegier": {"valeur": [], "source": h, "caracteristique": "theme",
                                 "pourquoi": "Varier les thèmes au début pour découvrir ceux qui plaisent."},
        "themes_a_eviter": {"valeur": [], "source": h, "caracteristique": "theme", "pourquoi": ""},
    }


NUMERIQUES = [  # (clé, libellé)
    ("duree_totale_s", "Durée totale (s)"),
    ("nb_diapos", "Nombre de diapos"),
    ("duree_1re_diapo_s", "Durée de la 1re diapo (s)"),
    ("mots_accroche", "Mots dans l'accroche"),
    ("mots_max_diapo", "Mots max sur une diapo"),
    ("mots_total", "Mots à l'écran (total)"),
    ("debit_max_mots_s", "Débit max (mots/s)"),
    ("nb_images", "Photos différentes"),
    ("heure_paris", "Heure de publication"),
    ("legende_caracteres", "Longueur de la légende"),
    ("nb_hashtags", "Hashtags"),
]
BOOLEENS = [("chiffre_accroche", "Chiffre dans l'accroche"), ("question_accroche", "Question dans l'accroche"),
            ("question_legende", "Question dans la légende")]
CATEGORIES = [("theme", "Thème"), ("jour", "Jour"), ("type_images", "Type d'images")]


# ---------------------------------------------------------------- analyse principale
def analyser() -> dict:
    queue = lire_json(ROOT / "posts" / "queue.json", []) or []
    entrees = [p for p in queue if p.get("type") == "reel"]
    publications = sorted(d for d in (date_iso(p.get("published_at") or "") for p in queue) if d)
    series = charger_releves()
    abonnes = relever_abonnes()
    now = dt.datetime.now(dt.timezone.utc)

    publies, a_venir = [], []
    for e in entrees:
        dossier = dossier_du_reel(e)
        car = caracteristiques(dossier, e)
        item = {"id": e["id"], "car": car, "publie": e.get("published_at"), "prevu": e.get("publish_at"),
                "valide": e.get("approved", False)}
        if e.get("published_at") and series.get(e["id"]):
            item["serie"] = series[e["id"]]
            publies.append(item)
        elif not e.get("published_at"):
            a_venir.append(item)
        else:
            item["serie"] = []
            publies.append(item)  # publié mais pas encore relevé
    # Reels présents dans les dossiers mais pas encore dans la file
    connus = {dossier_du_reel(e).name for e in entrees}
    for cfg in sorted((ROOT / "reels").glob("*/reel.json")):
        if cfg.parent.name not in connus:
            a_venir.append({"id": cfg.parent.name, "car": caracteristiques(cfg.parent, {"id": cfg.parent.name}),
                            "publie": None, "prevu": None, "valide": False, "hors_file": True})

    complet = any(x["views"] is not None for it in publies for x in it.get("serie", []))
    composantes = COMPOSANTES_COMPLET if complet else COMPOSANTES_REDUIT

    # indicateurs normalisés sur le relevé de référence (~J+7)
    for it in publies:
        ind = {"provisoire": True, "age_ref_h": None}
        if it.get("serie"):
            ref, prov = releve_de_reference(it["serie"])
            dernier = it["serie"][-1]
            duree = it["car"]["duree_totale_s"] or None
            vues, portee = ref["views"], ref["reach"]
            base_inter = portee or vues
            ab = ref["abonnes"]
            ind = {
                "provisoire": prov, "age_ref_h": ref["age_h"], "age_h": dernier["age_h"],
                "vues": vues, "portee": portee, "likes": ref["likes"], "commentaires": ref["comments"],
                "partages": ref["shares"], "enregistrements": ref["saved"],
                "temps_moyen_s": arrondi(ref["avg_watch_s"]),
                "retention": arrondi(ref["avg_watch_s"] / duree, 3) if ref["avg_watch_s"] and duree else None,
                "skip_rate": arrondi(ref["skip_rate"], 1),
                "taux_interaction": arrondi(ref["interactions"] / base_inter * 100, 2)
                if ref["interactions"] is not None and base_inter else None,
                "partages_1000": arrondi(ref["shares"] / vues * 1000, 1) if ref["shares"] is not None and vues else None,
                "enregistrements_1000": arrondi(ref["saved"] / vues * 1000, 1) if ref["saved"] is not None and vues else None,
                "vues_par_abonne": arrondi(vues / ab, 2) if vues is not None and ab else None,
                "engagement_abonnes": arrondi(((ref["likes"] or 0) + (ref["comments"] or 0)) / ab * 100, 2) if ab else None,
                "abonnes_gagnes": abonnes_gagnes(date_iso(it["publie"]), abonnes, publications),
            }
        it["ind"] = ind

    # score composite : moyenne pondérée des rangs (percentiles 0-100) parmi nos Reels
    detail = {it["id"]: {} for it in publies}
    for cle, poids, mieux, _ in composantes:
        pc = percentiles([it["ind"].get(cle) for it in publies], mieux)
        for it, p in zip(publies, pc):
            if p is not None:
                detail[it["id"]][cle] = (round(p, 1), poids)
    for it in publies:
        d = detail[it["id"]]
        tot = sum(w for _, w in d.values())
        it["score"] = round(sum(p * w for p, w in d.values()) / tot, 1) if tot else None
        it["score_detail"] = {k: p for k, (p, _) in d.items()}
    classes = sorted([it for it in publies if it["score"] is not None], key=lambda it: -it["score"])
    for i, it in enumerate(classes, 1):
        it["rang"] = i
    n = len(classes)

    # meilleurs vs moins bons
    k = max(1, n // 3) if n >= 9 else max(1, n // 2)
    hauts, bas = classes[:k], classes[-k:] if n >= 2 else []
    scores = [it["score"] for it in classes]
    comparaison = []
    for cle, lib in NUMERIQUES:
        vals = [it["car"].get(cle) for it in classes]
        rho = spearman(vals, scores)
        comparaison.append({
            "cle": cle, "libelle": lib,
            "meilleurs": arrondi(mediane([it["car"].get(cle) for it in hauts])),
            "moins_bons": arrondi(mediane([it["car"].get(cle) for it in bas])) if bas else None,
            "min": arrondi(min((v for v in vals if v is not None), default=None) if vals else None),
            "max": arrondi(max((v for v in vals if v is not None), default=None) if vals else None),
            "rho": arrondi(rho), "confiance": confiance(rho, n),
        })
    booleens = []
    for cle, lib in BOOLEENS:
        oui = [it["score"] for it in classes if it["car"].get(cle)]
        non = [it["score"] for it in classes if not it["car"].get(cle)]
        booleens.append({"cle": cle, "libelle": lib, "score_oui": arrondi(mediane(oui), 1), "n_oui": len(oui),
                         "score_non": arrondi(mediane(non), 1), "n_non": len(non)})
    categories = {}
    for cle, lib in CATEGORIES:
        groupes = {}
        for it in classes:
            groupes.setdefault(it["car"].get(cle) or "?", []).append(it["score"])
        categories[cle] = {"libelle": lib, "groupes": sorted(
            ({"valeur": g, "n": len(v), "score_median": arrondi(mediane(v), 1)} for g, v in groupes.items()),
            key=lambda g: -(g["score_median"] or 0))}

    modele = construire_modele(classes, hauts, comparaison, categories, n, complet)
    for it in a_venir:
        it["ecarts"] = verifier(it["car"], modele["regles"])
    return {"genere": now.isoformat(timespec="seconds"), "mode": "complet" if complet else "réduit",
            "n": n, "publies": publies, "classes": classes, "a_venir": a_venir, "composantes": composantes,
            "comparaison": comparaison, "booleens": booleens, "categories": categories, "modele": modele,
            "abonnes": [(d.isoformat(), v) for d, v in abonnes]}


def construire_modele(classes, hauts, comparaison, categories, n, complet) -> dict:
    regles = modele_de_depart()
    par_cle = {c["cle"]: c for c in comparaison}
    for nom, r in regles.items():
        car = r["caracteristique"]
        r["n_reels"] = n
        c = par_cle.get(car)
        vals_hauts = [it["car"].get(car) for it in hauts]
        if c:
            r["observe"] = {"mediane_meilleurs": c["meilleurs"], "mediane_moins_bons": c["moins_bons"],
                            "correlation_score": c["rho"]}
        r["confiance"] = c["confiance"] if c else ("insuffisante" if n < MIN_SOLIDE else "non mesurée")
        if n < MIN_SOLIDE:
            r["confiance"] = "insuffisante"
            continue
        if c and c["confiance"] in ("faible", "moyenne", "élevée"):  # on apprend de nos données
            if "max" in r:
                if (c["rho"] or 0) < 0:  # moins = mieux : le maximum se cale sur les meilleurs Reels
                    r["max"] = arrondi(quantile(vals_hauts, 0.75), 1)
                else:  # plus = mieux (ou neutre) : on ne resserre pas la limite
                    r["max"] = max(r["max"], arrondi(quantile(vals_hauts, 0.75), 1))
            if "cible" in r:
                cible = arrondi(mediane(vals_hauts), 1)
                ecart = 1.5 if car.startswith("duree") else 1
                r["cible"] = cible
                r["plage"] = [arrondi(min(quantile(vals_hauts, 0.1), cible - ecart), 1),
                              arrondi(max(quantile(vals_hauts, 0.9), cible + ecart), 1)]
            if "valeur" in r and car == "heure_paris":
                r["valeur"] = round(mediane(vals_hauts))
            r["source"] = "appris de nos Reels"
    # booléen : chiffre dans l'accroche
    if n >= MIN_SOLIDE:
        avec = [it["score"] for it in classes if it["car"]["chiffre_accroche"]]
        sans = [it["score"] for it in classes if not it["car"]["chiffre_accroche"]]
        if len(avec) >= 3 and len(sans) >= 3:
            ecart = mediane(avec) - mediane(sans)
            r = regles["chiffre_dans_accroche"]
            r.update(prefere=ecart >= 0, source="appris de nos Reels", observe={"ecart_score": round(ecart, 1)},
                     confiance="moyenne" if abs(ecart) >= 20 else "faible")
        # thèmes et jours : au moins 2 Reels par groupe
        th = [g for g in categories["theme"]["groupes"] if g["n"] >= 2]
        if len(th) >= 2:
            med = mediane([it["score"] for it in classes])
            regles["themes_a_privilegier"].update(
                valeur=[g["valeur"] for g in th if g["score_median"] >= med + 10],
                source="appris de nos Reels", confiance="faible", observe={"groupes": th})
            regles["themes_a_eviter"].update(
                valeur=[g["valeur"] for g in th if g["score_median"] <= med - 15],
                source="appris de nos Reels", confiance="faible", observe={"groupes": th})
        jo = [g for g in categories["jour"]["groupes"] if g["n"] >= 2]
        if len(jo) >= 3:
            regles["jours_conseilles"].update(valeur=[g["valeur"] for g in jo[:3]], source="appris de nos Reels",
                                              confiance="faible", observe={"groupes": jo})
    return {
        "version": 1, "n_reels": n, "mode": "complet" if complet else "réduit",
        "avertissement": ("Moins de 8 Reels mesurés : les règles sont des hypothèses de départ, à confirmer."
                          if n < MIN_SOLIDE else "Règles apprises sur nos Reels ; à revoir à chaque nouveau relevé."),
        "regles": regles,
    }


CONSEILS = {  # règle -> conseil court, pour les recommandations
    "duree_totale_s": "Ajuster la durée totale",
    "duree_1re_diapo_max_s": "Raccourcir la 1re diapo",
    "mots_accroche_max": "Raccourcir l'accroche",
    "mots_par_diapo_max": "Alléger la diapo la plus chargée",
    "debit_max_mots_s": "Laisser plus de temps pour lire (ou moins de mots)",
    "nb_diapos": "Ajuster le nombre de diapos",
    "nb_hashtags": "Ajuster le nombre de hashtags",
    "premiere_ligne_max_caracteres": "Raccourcir la 1re ligne de la légende",
    "chiffre_dans_accroche": "Mettre un chiffre concret dans l'accroche",
    "themes_a_eviter": "Éviter les thèmes qui marchent le moins",
}


def verifier(car: dict, regles: dict) -> list:
    """Écarts d'un Reel (en préparation) par rapport au modèle : [{"regle", "texte"}, …]."""
    e = []

    def hors(nom, val, lib, unite=""):
        r = regles[nom]
        if val is None:
            return
        if "max" in r and r["max"] is not None and val > r["max"]:
            e.append({"regle": nom, "texte": f"{lib} : {fmt(val)}{unite} (max conseillé {fmt(r['max'])}{unite})"})
        if "plage" in r and r["plage"] and None not in r["plage"] and not (r["plage"][0] <= val <= r["plage"][1]):
            e.append({"regle": nom, "texte": f"{lib} : {fmt(val)}{unite} "
                                              f"(conseillé {fmt(r['plage'][0])} à {fmt(r['plage'][1])}{unite})"})

    hors("duree_totale_s", car["duree_totale_s"], "Durée totale", " s")
    hors("duree_1re_diapo_max_s", car["duree_1re_diapo_s"], "1re diapo", " s")
    hors("mots_accroche_max", car["mots_accroche"], "Accroche", " mots")
    hors("mots_par_diapo_max", car["mots_max_diapo"], "Diapo la plus chargée", " mots")
    hors("debit_max_mots_s", car["debit_max_mots_s"], "Débit de lecture", " mots/s")
    hors("nb_diapos", car["nb_diapos"], "Nombre de diapos")
    hors("nb_hashtags", car["nb_hashtags"], "Hashtags")
    hors("premiere_ligne_max_caracteres", car["premiere_ligne_caracteres"], "1re ligne de la légende", " car.")
    r = regles["chiffre_dans_accroche"]
    # tant que c'est une hypothèse, le chiffre est une variable à tester (A/B), pas un défaut
    if r["prefere"] and r["source"].startswith("appris") and not car["chiffre_accroche"]:
        e.append({"regle": "chiffre_dans_accroche", "texte": "Pas de chiffre dans l'accroche"})
    if car["theme"] in regles["themes_a_eviter"]["valeur"]:
        e.append({"regle": "themes_a_eviter", "texte": f"Thème « {car['theme']} » moins performant jusqu'ici"})
    return e


# ---------------------------------------------------------------- rapport Markdown
def fmt(x, suffixe=""):
    if x is None:
        return "–"
    if isinstance(x, float):
        x = f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{x}{suffixe}"


def recommandations(a: dict) -> list:
    recs = []
    if a["mode"] == "réduit":
        recs.append("**Activer les statistiques détaillées** (permission instagram_business_manage_insights) : "
                    "sans vues, temps de visionnage ni partages, l'analyse ne voit que les j'aime, ce qui est "
                    "très pauvre avec peu d'abonnés. Voir la fin de ce rapport.")
    if a["n"] < MIN_SOLIDE:
        recs.append(f"**Publier au moins {MIN_SOLIDE} Reels** avant de tirer des conclusions, en ne changeant "
                    "qu'une chose à la fois d'un Reel à l'autre (par exemple : accroche avec un chiffre / sans "
                    "chiffre, ou thème animaux / histoire) pour savoir ce qui fait la différence.")
    c = {x["cle"]: x for x in a["comparaison"]}
    for x in a["comparaison"]:
        if x["confiance"] in ("moyenne", "élevée") and x["rho"] is not None and x["meilleurs"] is not None:
            sens = "plus" if x["rho"] > 0 else "moins"
            recs.append(f"**{x['libelle']}** : les meilleurs Reels en ont {sens} (médiane {fmt(x['meilleurs'])} "
                        f"contre {fmt(x['moins_bons'])}). Viser environ {fmt(x['meilleurs'])} "
                        f"(confiance {x['confiance']}).")
    meds = [it["ind"].get("retention") for it in a["classes"]]
    ret = mediane(meds)
    if ret is not None and ret < 0.6:
        recs.append(f"**Rétention faible** (les gens regardent en moyenne {fmt(round(ret * 100), ' %')} du Reel) : "
                    "raccourcir, couper les diapos les moins fortes, et mettre la révélation plus tôt.")
    skip = mediane([it["ind"].get("skip_rate") for it in a["classes"]])
    if skip is not None and skip > 50:
        recs.append(f"**Beaucoup d'abandons dans les 3 premières secondes** ({fmt(skip, ' %')}) : "
                    "accroche plus courte et plus choc dès la 1re image, texte visible immédiatement.")
    ecarts = {}
    for it in a["a_venir"]:
        for e in it["ecarts"]:
            ecarts.setdefault(e["regle"], []).append(it["id"])
    for nom, ids in sorted(ecarts.items(), key=lambda kv: -len(kv[1]))[:2]:
        recs.append(f"**{CONSEILS.get(nom, nom)}** : concerne {len(ids)} Reel(s) en préparation "
                    f"({', '.join(ids[:4])}{'…' if len(ids) > 4 else ''}), détail plus bas.")
    base = [
        "**Accroche en moins de 8 mots, avec un chiffre concret**, lisible dès la 1re seconde.",
        "**Garder le Reel court** (10 à 15 s écran de fin compris) : un Reel vu en entier est davantage "
        "montré par Instagram.",
        "**Finir sur une question ou une révélation** qui donne envie de commenter ou d'envoyer le Reel à "
        "quelqu'un : les partages sont le signal le plus fort.",
    ]
    for b in base:
        if len(recs) >= 5:
            break
        if len(recs) < 3 or a["n"] < MIN_SOLIDE:
            recs.append(b + " *(bonne pratique générale, à confirmer)*")
    return recs[:5]


def rapport_md(a: dict) -> str:
    L = []
    L.append("# Analyse des Reels Kulturable\n")
    L.append(f"*Généré le {a['genere'][:16].replace('T', ' à ')} UTC par `scripts/reels_analyse.py`. "
             "Tableau de bord visuel : `reels/analyse/tableau.html`.*\n")
    L.append("## En bref\n")
    if a["n"] == 0:
        L.append("- **Aucun Reel publié et mesuré pour l'instant.** Le modèle contient des *hypothèses de départ* "
                 "tirées des bonnes pratiques Reels, à confirmer.")
    else:
        best = a["classes"][0]
        L.append(f"- **{a['n']} Reel(s) mesuré(s).** Meilleur pour l'instant : **{best['car']['titre']}** "
                 f"(score {fmt(best['score'])}/100).")
    if a["mode"] == "réduit":
        L.append("- **Mode réduit** : la permission des statistiques détaillées manque ; seuls les j'aime, "
                 "commentaires et abonnés sont connus.")
    else:
        L.append("- **Mode complet** : vues, portée, temps de visionnage, partages et enregistrements disponibles.")
    if a["n"] < MIN_SOLIDE:
        L.append(f"- **Prudence** : avec moins de {MIN_SOLIDE} Reels, les différences peuvent être dues au hasard. "
                 "Les tendances ci-dessous sont des pistes, pas des preuves.")
    L.append("")

    L.append("## Recommandations pour les prochains Reels\n")
    for i, r in enumerate(recommandations(a), 1):
        L.append(f"{i}. {r}")
    L.append("")

    if a["classes"]:
        L.append("## Classement\n")
        if a["mode"] == "complet":
            L.append("| Rang | Reel | Score | Vues | Rétention | Abandon <3 s | Partages /1000 vues | Enreg. /1000 vues | Abonnés gagnés | Âge |")
            L.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
            for it in a["classes"]:
                i = it["ind"]
                L.append(f"| {it['rang']} | {it['car']['titre']} | **{fmt(it['score'])}** | {fmt(i.get('vues'))} | "
                         f"{fmt(None if i.get('retention') is None else round(i['retention'] * 100), ' %')} | "
                         f"{fmt(i.get('skip_rate'), ' %')} | {fmt(i.get('partages_1000'))} | "
                         f"{fmt(i.get('enregistrements_1000'))} | {fmt(i.get('abonnes_gagnes'))} | "
                         f"J+{fmt(round(i['age_ref_h'] / 24))}{' (provisoire)' if i['provisoire'] else ''} |")
        else:
            L.append("| Rang | Reel | Score | J'aime | Commentaires | Pour 100 abonnés | Abonnés gagnés | Âge |")
            L.append("|---:|---|---:|---:|---:|---:|---:|---:|")
            for it in a["classes"]:
                i = it["ind"]
                L.append(f"| {it['rang']} | {it['car']['titre']} | **{fmt(it['score'])}** | {fmt(i.get('likes'))} | "
                         f"{fmt(i.get('commentaires'))} | {fmt(i.get('engagement_abonnes'))} | "
                         f"{fmt(i.get('abonnes_gagnes'))} | J+{fmt(round(i['age_ref_h'] / 24))}"
                         f"{' (provisoire)' if i['provisoire'] else ''} |")
        L.append("")

        L.append("## Ce qui marche, ce qui ne marche pas\n")
        if a["n"] < 2:
            L.append("Il faut au moins 2 Reels mesurés pour comparer.\n")
        else:
            if a["n"] < MIN_SOLIDE:
                L.append(f"*Tendances provisoires sur {a['n']} Reels : rien de solide avant {MIN_SOLIDE}.*\n")
            L.append("Comparaison des caractéristiques : médiane des **meilleurs** Reels contre celle des "
                     "**moins bons** ; « lien » = corrélation de rang avec le score (de −1 à +1).\n")
            L.append("| Caractéristique | Meilleurs | Moins bons | Lien avec le score | Confiance |")
            L.append("|---|---:|---:|---:|---|")
            for c in sorted(a["comparaison"], key=lambda c: -abs(c["rho"] or 0)):
                L.append(f"| {c['libelle']} | {fmt(c['meilleurs'])} | {fmt(c['moins_bons'])} | {fmt(c['rho'])} | "
                         f"{c['confiance']} |")
            L.append("")
            for b in a["booleens"]:
                if b["n_oui"] and b["n_non"]:
                    L.append(f"- {b['libelle']} : score médian {fmt(b['score_oui'])} avec ({b["n_oui"]} Reel(s)) "
                             f"contre {fmt(b['score_non'])} sans ({b['n_non']}).")
            for cle, cat in a["categories"].items():
                g = ", ".join(f"{x['valeur']} {fmt(x['score_median'])} ({x['n']})" for x in cat["groupes"])
                L.append(f"- {cat['libelle']} (score médian, nombre de Reels) : {g}.")
            L.append("")

    if a["a_venir"]:
        L.append("## Reels en préparation : contrôle par rapport au modèle\n")
        for it in a["a_venir"]:
            c = it["car"]
            etat = "validé" if it.get("valide") else ("hors file" if it.get("hors_file") else "non validé")
            quand = f", prévu le {it['prevu'][:10]}" if it.get("prevu") else ""
            L.append(f"- **{c['titre']}** ({it['id']}, {etat}{quand}) : {fmt(c['duree_totale_s'])} s, {c['nb_diapos']} "
                     f"diapos, accroche de {c['mots_accroche']} mots, thème {c['theme']}. "
                     + ("Conforme." if not it["ecarts"] else "À revoir : " + " ; ".join(e["texte"] for e in it["ecarts"]) + "."))
        L.append("")

    L.append("## Le modèle (règles pour les prochains Reels)\n")
    L.append(f"*{a['modele']['avertissement']}* Fichier machine : `reels/analyse/modele.json`.\n")
    L.append("| Règle | Valeur | Source | Confiance |")
    L.append("|---|---|---|---|")
    for nom, r in a["modele"]["regles"].items():
        v = []
        for k in ("cible", "max", "plage", "valeur", "prefere"):
            if k in r:
                val = r[k]
                if isinstance(val, list):
                    val = " à ".join(map(str, val)) if k == "plage" else (", ".join(val) if val else "(aucun)")
                elif isinstance(val, bool):
                    val = "oui" if val else "non"
                v.append(f"{k} {val}")
        L.append(f"| {nom.replace('_', ' ')} | {' ; '.join(v)} | {r['source']} | {r['confiance']} |")
    L.append("")

    L.append("## Comment le score est calculé\n")
    L.append("Chaque Reel est comparé aux **autres Reels du compte**, sur son relevé le plus proche de **J+7** "
             "(pour comparer des Reels du même âge ; « provisoire » s'il a moins de 6 jours). Pour chaque "
             "indicateur, on calcule son rang en pourcentage (0 = le moins bon de nos Reels, 100 = le meilleur), "
             "puis on fait la moyenne pondérée :\n")
    for cle, poids, mieux, lib in a["composantes"]:
        L.append(f"- {lib} : poids {poids}{'' if mieux else ' (plus c’est bas, mieux c’est)'}")
    L.append("\nUn indicateur absent pour un Reel est ignoré et les autres poids sont réajustés. "
             "Le score est donc **relatif** : 100 = meilleur de nos Reels sur tous les critères, pas un succès "
             "absolu.\n")
    L.append("**Indicateurs** : rétention = temps moyen de visionnage ÷ durée du Reel (au-delà de 100 %, des gens "
             "le revoient) ; taux d'interaction = (j'aime + commentaires + partages + enregistrements) ÷ portée ; "
             "partages et enregistrements ramenés à 1 000 vues ; abonnés gagnés = variation du nombre d'abonnés "
             "entre le relevé précédant la publication et celui du lendemain, divisée par le nombre de "
             "publications dans l'intervalle (estimation grossière).\n")

    if a["mode"] == "réduit":
        L.append("## Activer les statistiques détaillées\n")
        L.append("1. Sur developers.facebook.com, ouvrir l'application Kulturable, rubrique **Instagram > "
                 "Configuration de l'API avec connexion Instagram**.")
        L.append("2. Dans les autorisations, ajouter **instagram_business_manage_insights** (en plus de "
                 "instagram_business_basic et instagram_business_content_publish).")
        L.append("3. **Générer une nouvelle clé d'accès** pour le compte @kulturable (bouton « Générer un jeton ») "
                 "et accepter la nouvelle autorisation quand Instagram la demande.")
        L.append("4. Remplacer le secret GitHub **IG_ACCESS_TOKEN** par cette nouvelle clé (Settings > Secrets and "
                 "variables > Actions).")
        L.append("5. Lancer le workflow « Statistiques des Reels » à la main : le rapport passe en mode complet.\n")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- tableau de bord HTML
def donnees_tableau(a: dict) -> dict:
    def reel(it):
        return {"id": it["id"], "titre": it["car"]["titre"], "score": it.get("score"), "rang": it.get("rang"),
                "detail": it.get("score_detail", {}), "ind": it.get("ind", {}), "car": it["car"],
                "serie": it.get("serie", []), "publie": it.get("publie")}
    return {"genere": a["genere"], "mode": a["mode"], "n": a["n"], "min_solide": MIN_SOLIDE,
            "reels": [reel(it) for it in a["classes"]],
            "composantes": [{"cle": c, "poids": p, "mieux": m, "libelle": l} for c, p, m, l in a["composantes"]],
            "comparaison": a["comparaison"], "a_venir": [{"id": it["id"], "titre": it["car"]["titre"],
                                                         "car": it["car"], "ecarts": it["ecarts"],
                                                         "prevu": it.get("prevu")} for it in a["a_venir"]],
            "regles": a["modele"]["regles"], "avertissement": a["modele"]["avertissement"],
            "abonnes": a["abonnes"], "recommandations": recommandations(a)}


def tableau_html(a: dict) -> str:
    gabarit = (pathlib.Path(__file__).resolve().parent / "reels_tableau.html").read_text(encoding="utf-8")
    data = json.dumps(donnees_tableau(a), ensure_ascii=False).replace("</", "<\\/")
    return gabarit.replace("/*__DONNEES__*/null", data).replace("__GENERE__", html.escape(a["genere"][:16]))


def main() -> int:
    a = analyser()
    out = ROOT / "reels" / "analyse"
    out.mkdir(parents=True, exist_ok=True)
    (out / "rapport.md").write_text(rapport_md(a), encoding="utf-8")
    modele = dict(a["modele"], genere=a["genere"],
                  classement=[{"id": it["id"], "titre": it["car"]["titre"], "score": it["score"],
                               "provisoire": it["ind"]["provisoire"]} for it in a["classes"]])
    (out / "modele.json").write_text(json.dumps(modele, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "tableau.html").write_text(tableau_html(a), encoding="utf-8")
    print(f"Analyse : {a['n']} Reel(s) mesuré(s), mode {a['mode']}, {len(a['a_venir'])} en préparation.")
    print(f"Écrit : {out / 'rapport.md'}, {out / 'modele.json'}, {out / 'tableau.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
