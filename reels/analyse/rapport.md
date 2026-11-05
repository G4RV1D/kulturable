# Analyse des Reels Kulturable

*Généré le 2026-11-05 à 12:55 UTC par `scripts/reels_analyse.py`. Tableau de bord visuel : `reels/analyse/tableau.html`.*

## En bref

- **Aucun Reel publié et mesuré pour l'instant.** Le modèle contient des *hypothèses de départ* tirées des bonnes pratiques Reels, à confirmer.
- **Mode réduit** : la permission des statistiques détaillées manque ; seuls les j'aime, commentaires et abonnés sont connus.
- **Prudence** : avec moins de 8 Reels, les différences peuvent être dues au hasard. Les tendances ci-dessous sont des pistes, pas des preuves.

## Recommandations pour les prochains Reels

1. **Activer les statistiques détaillées** (permission instagram_business_manage_insights) : sans vues, temps de visionnage ni partages, l'analyse ne voit que les j'aime, ce qui est très pauvre avec peu d'abonnés. Voir la fin de ce rapport.
2. **Publier au moins 8 Reels** avant de tirer des conclusions, en ne changeant qu'une chose à la fois d'un Reel à l'autre (par exemple : accroche avec un chiffre / sans chiffre, ou thème animaux / histoire) pour savoir ce qui fait la différence.
3. **Laisser plus de temps pour lire (ou moins de mots)** : concerne 3 Reel(s) en préparation (reel-02-oiseau-guide, 08-lac-drogue, 12-velo-ali), détail plus bas.
4. **Raccourcir l'accroche** : concerne 3 Reel(s) en préparation (08-lac-drogue, 10-crabe-oursin, 12-velo-ali), détail plus bas.
5. **Accroche en moins de 8 mots, avec un chiffre concret**, lisible dès la 1re seconde. *(bonne pratique générale, à confirmer)*

## Reels en préparation : contrôle par rapport au modèle

- **Le château de corail** (reel-01-coral-castle, validé, prévu le 2026-11-06) : 18 s, 6 diapos, accroche de 8 mots, thème lieux. À revoir : Diapo la plus chargée : 13 mots (max conseillé 12 mots).
- **L'oiseau qui guide les hommes** (reel-02-oiseau-guide, validé, prévu le 2026-11-07) : 15,6 s, 5 diapos, accroche de 8 mots, thème animaux. À revoir : Débit de lecture : 4,62 mots/s (max conseillé 4,5 mots/s).
- **Timon et Pumbaa en vrai** (reel-04-mangoustes, validé, prévu le 2026-11-08) : 15,4 s, 5 diapos, accroche de 6 mots, thème animaux. Conforme.
- **La fleur de l'ère glaciaire** (reel-05-fleur-glaciaire, validé, prévu le 2026-11-09) : 15,6 s, 5 diapos, accroche de 6 mots, thème nature. Conforme.
- **Le poisson aux phares** (reel-06-poisson-phares, validé, prévu le 2026-11-10) : 15,6 s, 5 diapos, accroche de 8 mots, thème animaux. Conforme.
- **Le Bouddha caché dans la montagne** (reel-07-bouddha-leshan, validé, prévu le 2026-11-11) : 15,6 s, 5 diapos, accroche de 8 mots, thème nature. Conforme.
- **Le chant qui appelle les troupeaux** (reel-03-kulning, non validé, prévu le 2026-11-12) : 15,6 s, 5 diapos, accroche de 7 mots, thème animaux. Conforme.
- **Le lac de la drogue** (08-lac-drogue, hors file) : 15,6 s, 5 diapos, accroche de 10 mots, thème nature. À revoir : Accroche : 10 mots (max conseillé 8 mots) ; Débit de lecture : 4,58 mots/s (max conseillé 4,5 mots/s).
- **Le dentiste des crocodiles** (09-dentiste-crocodiles, hors file) : 15,6 s, 5 diapos, accroche de 7 mots, thème animaux. Conforme.
- **Le crabe au casque d'oursin** (10-crabe-oursin, hors file) : 15,6 s, 5 diapos, accroche de 9 mots, thème animaux. À revoir : Accroche : 9 mots (max conseillé 8 mots).
- **Le peuple qui dit non au monde** (11-north-sentinel, hors file) : 15,6 s, 5 diapos, accroche de 8 mots, thème lieux. Conforme.
- **Le vélo qui a créé une légende** (12-velo-ali, hors file) : 15,4 s, 5 diapos, accroche de 11 mots, thème mysteres. À revoir : Accroche : 11 mots (max conseillé 8 mots) ; Débit de lecture : 4,58 mots/s (max conseillé 4,5 mots/s).
- **La plante qui héberge des chauves-souris** (13-chauves-souris-nepenthes, hors file) : 15,6 s, 5 diapos, accroche de 6 mots, thème nature. Conforme.
- **Le jour où papa est parti sur la Lune** (14-papa-sur-la-lune, hors file) : 15,6 s, 5 diapos, accroche de 8 mots, thème personnages. Conforme.

## Le modèle (règles pour les prochains Reels)

*Moins de 8 Reels mesurés : les règles sont des hypothèses de départ, à confirmer.* Fichier machine : `reels/analyse/modele.json`.

| Règle | Valeur | Source | Confiance |
|---|---|---|---|
| duree totale s | cible 15 ; plage 10 à 18 | hypothèse de départ, à confirmer | insuffisante |
| duree 1re diapo max s | max 2.5 | hypothèse de départ, à confirmer | insuffisante |
| mots accroche max | max 8 | hypothèse de départ, à confirmer | insuffisante |
| mots par diapo max | max 12 | hypothèse de départ, à confirmer | insuffisante |
| debit max mots s | max 4.5 | hypothèse de départ, à confirmer | insuffisante |
| nb diapos | cible 5 ; plage 4 à 7 | hypothèse de départ, à confirmer | insuffisante |
| chiffre dans accroche | prefere oui | hypothèse de départ, à confirmer | insuffisante |
| nb hashtags | plage 3 à 5 | hypothèse de départ, à confirmer | insuffisante |
| premiere ligne max caracteres | max 110 | règle du compte (MEMO.md) | insuffisante |
| heure conseillee paris | plage 11 à 20 ; valeur 12 | hypothèse de départ, à confirmer | insuffisante |
| jours conseilles | valeur lundi, mardi, mercredi, jeudi, vendredi, samedi, dimanche | hypothèse de départ, à confirmer | insuffisante |
| themes a privilegier | valeur (aucun) | hypothèse de départ, à confirmer | insuffisante |
| themes a eviter | valeur (aucun) | hypothèse de départ, à confirmer | insuffisante |

## Comment le score est calculé

Chaque Reel est comparé aux **autres Reels du compte**, sur son relevé le plus proche de **J+7** (pour comparer des Reels du même âge ; « provisoire » s'il a moins de 6 jours). Pour chaque indicateur, on calcule son rang en pourcentage (0 = le moins bon de nos Reels, 100 = le meilleur), puis on fait la moyenne pondérée :

- J'aime + commentaires pour 100 abonnés : poids 70
- Abonnés gagnés (estimés) : poids 30

Un indicateur absent pour un Reel est ignoré et les autres poids sont réajustés. Le score est donc **relatif** : 100 = meilleur de nos Reels sur tous les critères, pas un succès absolu.

**Indicateurs** : rétention = temps moyen de visionnage ÷ durée du Reel (au-delà de 100 %, des gens le revoient) ; taux d'interaction = (j'aime + commentaires + partages + enregistrements) ÷ portée ; partages et enregistrements ramenés à 1 000 vues ; abonnés gagnés = variation du nombre d'abonnés entre le relevé précédant la publication et celui du lendemain, divisée par le nombre de publications dans l'intervalle (estimation grossière).

## Activer les statistiques détaillées

1. Sur developers.facebook.com, ouvrir l'application Kulturable, rubrique **Instagram > Configuration de l'API avec connexion Instagram**.
2. Dans les autorisations, ajouter **instagram_business_manage_insights** (en plus de instagram_business_basic et instagram_business_content_publish).
3. **Générer une nouvelle clé d'accès** pour le compte @kulturable (bouton « Générer un jeton ») et accepter la nouvelle autorisation quand Instagram la demande.
4. Remplacer le secret GitHub **IG_ACCESS_TOKEN** par cette nouvelle clé (Settings > Secrets and variables > Actions).
5. Lancer le workflow « Statistiques des Reels » à la main : le rapport passe en mode complet.

