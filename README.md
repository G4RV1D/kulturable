# Kulturable – publication automatique

Ce dépôt publie automatiquement les posts validés sur le compte Instagram @kulturable, via l'API officielle de Meta.

## Fonctionnement

- `posts/queue.json` : la file d'attente (date et heure de publication, image source, statut).
- `posts/captions/` : le texte de chaque post.
- `images/` : les images au format Instagram (1080 × 1350), générées automatiquement.
- **Préparer les images** : se lance à chaque ajout de post, télécharge l'image depuis l'institution qui la conserve et la met au format.
- **Publier sur Instagram** : vérifie chaque heure s'il y a un post **validé** (`"approved": true`) dont l'heure est passée, et le publie.
- **Renouveler la clé Instagram** : prolonge chaque lundi la clé d'accès, qui expire sinon au bout de 60 jours.

Un post non validé n'est jamais publié.

## Règles éditoriales

- Sources : uniquement des institutions (musées, bibliothèques, archives), des encyclopédies ou une presse reconnue. Pas de Wikipedia.
- Images : conservées par une institution, avec des droits vérifiés.
- Une seule image par post, comme le reste de la page. Quand le sujet est une personne, cette image est son portrait si un portrait de source fiable existe.
- Style : un récit écrit comme par un humain, presque sans emojis, avec une question au lecteur puis les sources.

## Configuration (une seule fois)

1. **Compte Instagram professionnel** : Paramètres > Type de compte et outils > Passer à un compte professionnel > Créateur.
2. **Application Meta** : sur developers.facebook.com, créer une application avec le cas d'usage Instagram, puis, dans « Configuration de l'API avec connexion Instagram », ajouter le compte @kulturable et générer une clé d'accès.
3. **Secrets GitHub** (Settings > Secrets and variables > Actions > New repository secret) :
   - `IG_ACCESS_TOKEN` : la clé d'accès Instagram ;
   - `GH_PAT` : un jeton GitHub « fine-grained » limité à ce dépôt, avec la permission *Secrets : Read and write*. Il sert uniquement à enregistrer la clé Instagram renouvelée.

## Test

Onglet **Actions** > **Publier sur Instagram** > **Run workflow**, en laissant « Mode test » coché : le script vérifie tout sans rien publier.

## Vidéos TikTok

Chaque vidéo a son dossier dans `tiktok/` : `script.txt` (texte à lire, un paragraphe par plan), `video.json` (images, recadrages, zooms), `legende.txt` (légende TikTok).
- Sans voix, **Monter les vidéos TikTok** produit `apercu.mp4` (léger, muet) pour vérifier les images.
- Dès qu'un enregistrement `voix.m4a` est ajouté au dossier, il produit `video.mp4` en 1080 × 1920 : images et sous-titres calés sur les pauses de la voix, musique calme pendant l'accroche puis rythmée (compositions originales, `music/`), qui baisse quand la voix parle.
- Si un changement d'image tombe mal, on peut fixer les instants à la main avec `"cuts"` dans `video.json`.
- Publication : à programmer soi-même dans TikTok Studio (l'API TikTok ne permet pas la publication publique automatique pour un usage personnel).
