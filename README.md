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

## Configuration (une seule fois)

1. **Compte Instagram professionnel** : Paramètres > Type de compte et outils > Passer à un compte professionnel > Créateur.
2. **Application Meta** : sur developers.facebook.com, créer une application avec le cas d'usage Instagram, puis, dans « Configuration de l'API avec connexion Instagram », ajouter le compte @kulturable et générer une clé d'accès.
3. **Secrets GitHub** (Settings > Secrets and variables > Actions > New repository secret) :
   - `IG_ACCESS_TOKEN` : la clé d'accès Instagram ;
   - `GH_PAT` : un jeton GitHub « fine-grained » limité à ce dépôt, avec la permission *Secrets : Read and write*. Il sert uniquement à enregistrer la clé Instagram renouvelée.

## Test

Onglet **Actions** > **Publier sur Instagram** > **Run workflow**, en laissant « Mode test » coché : le script vérifie tout sans rien publier.
