# Mémo Kulturable — où on en est (3 novembre 2026)

À coller au début d'une nouvelle conversation avec Claude, pour reprendre là où on s'est arrêtés.

## Le compte

- Instagram **@kulturable**, slogan « La culture se cultive ». Des anecdotes vraies, incroyables, surréalistes, historiques ou légendaires. Varier les sujets, pas trop d'astronomie.
- Environ 14 abonnés début novembre, 1 à 3 j'aime par post. On veut développer l'audience, puis lancer les Reels et TikTok.

## Les règles de publication (à respecter pour tout nouveau post)

- **Sources** vérifiables (institutions, musées, revues, presse reconnue). **Jamais Wikipédia.**
- **Images** : uniquement libres de droits, sans autorisation à demander : domaine public ou Creative Commons, avec le photographe crédité. Jamais d'agence de presse. Si aucune photo libre n'existe, une illustration originale signalée comme telle.
- **Une seule image** par post, le portrait de la personne quand c'est possible, **en couleur** (pas de noir et blanc).
- Photo en **plein cadre**, format d'origine entre 4:5 et 1,91:1, **sans fond flou**.
- **Texte** : un récit écrit comme par un humain, presque sans émojis.
- **Structure de la légende** :
  1. 1re ligne = accroche de 100 à 110 caractères, visible avant « … plus » : `TITRE EN MAJUSCULES : phrase qui donne envie de cliquer`.
  2. L'histoire.
  3. Une question au lecteur.
  4. 4 à 6 hashtags, dont #Kulturable et #HistoireVraie.
  5. Tout en bas : « Source(s) : … » puis « Photo : … ».

## Le système automatique (déjà en place, fonctionne)

- Dépôt GitHub **G4RV1D/kulturable**. La clé Instagram est uniquement dans le secret GitHub `IG_ACCESS_TOKEN` : ne jamais la copier dans une conversation.
- **Un post par jour à 18h (heure de Paris)**, suivi automatiquement de sa **story** (1080 × 1920, avec le bouton « Toute l'histoire dans le dernier post »).
- **Rythme** : les 7 posts de la semaine suivante sont préparés environ une semaine à l'avance et envoyés pour validation (notification + e-mail).
- **Validation tacite** : sans réponse 48 h avant le premier post du lot (le lundi 18h), le lot est validé. Un « stop » ou une demande de modification suspend le post concerné.
- **Filet de sécurité** : une alerte GitHub (e-mail) part s'il reste moins de 3 posts validés.
- **Anti-doublon** : après le triple post du 3/11 (Göbekli Tepe), une vérification sur Instagram empêche de republier un post ou une story déjà en ligne. Testé et fonctionnel.
- Limites connues :
  - L'API Instagram **ne peut pas modifier une légende** déjà publiée.
  - Les **statistiques de vues et de portée** ne sont pas accessibles : il faudrait régénérer la clé avec la permission `instagram_business_manage_insights`.
  - Les rappels programmés de Claude ont parfois disparu, d'où l'alerte GitHub en secours.

## Posts programmés

- Publiés : jusqu'à Göbekli Tepe (3/11).
- Validés et programmés **jusqu'au 17 novembre** :
  - 4/11 catacombes · 5/11 Glass Beach · 6/11 Hashima · 7/11 Sedlec · 8/11 moaï · 9/11 lac Hillier · 10/11 arbre propriétaire de lui-même
  - 11/11 Chaussée des Géants · 12/11 forêt tordue · 13/11 Pompéi · 14/11 Dallol · 15/11 Neuschwanstein · 16/11 tour de Pise · 17/11 Kukulcán
- **À faire** : préparer la semaine du **18 au 24 novembre** vers le 11/11. Validation tacite le 16/11 à 18h.
- **À vérifier** : que le post des catacombes (4/11) et sa story ne sortent qu'une seule fois.
- En réserve, non validés : plusieurs anciens projets de posts (Phineas Gage, Hedy Lamarr…).

## Les 63 anciens posts (2022 → octobre 2026)

- Tous réécrits au nouveau format, avec les erreurs corrigées et des sources sans Wikipédia. Ils sont dans le dépôt, dans `posts/anciens/`.
- Il faut les coller à la main dans Instagram avec « Modifier ». Une page avec un bouton « Copier » et une case « Collé » a été créée pour ça : « Kulturable, textes à recoller », dans les artifacts.
- Ces textes servent de **base commune pour créer les Reels**.

## Reels (projet en cours, rien de publié)

- Consigne : **ne pas publier de Reel pour l'instant**. On prépare des brouillons et des aperçus.
- Format choisi :
  - Une vidéo verticale de 20 à 30 s, avec plusieurs photos en mouvement (zoom ou glissement) et de courtes phrases à l'écran, placées assez haut pour ne pas être cachées par les boutons des Reels.
  - Une version condensée de l'anecdote qui donne envie d'aller lire le post complet.
  - De la musique, même si beaucoup de gens regardent sans le son.
- **Reel n°1 terminé (brouillon)** : *Le château de corail* (Edward Leedskalnin), 7 scènes, 24 s, avec ses photos libres créditées et sa légende complète. Il est dans `reels/01-coral-castle/`, et un aperçu dans une fausse page Instagram a été montré.
- **Musique de la chaîne** :
  - La mélodie choisie est la proposition 1, « boîte à musique, mystère » : ré-la-fa-mi-ré-do#-ré.
  - Elle a été peaufinée avec des cordes, un violoncelle, un coup sourd au début et de la réverbération. C'est une composition originale, sans droits.
  - Version courte : `music/signature-kulturable.m4a` (≈ 10 s). Version longue pour le fond des Reels : `music/theme-mystere.m4a` (≈ 47 s).
  - **En attente** : ton avis sur la version peaufinée et sur le Reel Coral Castle.
- **Prochaines étapes** :
  1. Valider la musique et le Reel n°1.
  2. Faire les Reels suivants à partir des anciens posts réécrits.
  3. Plus tard, mettre en place la publication automatique des Reels.

## TikTok (projet, rien créé)

- Consigne : **ne rien mettre en ligne, ne créer aucun compte**.
- 12 scripts prêts dans `tiktok/` : disque de Rosetta, Shackleton, Phineas Gage, Houdini, Strasbourg 1518, Hedy Lamarr, Wojtek, Desmond Doss, ampoule de Livermore, pierres mouvantes, manuscrit de Voynich et Jack le babouin.
- **En attente** : tes enregistrements de voix (m4a ou mp3). Le montage se fait ensuite automatiquement, avec des sous-titres au mot près et la musique.
- Pour le disque de Rosetta, les photos protégées ont été remplacées par une illustration originale.

## Préférences

- Me répondre **en français**.
- Je suis novice en Reels et TikTok : expliquer simplement et conseiller.
- E-mail pour les rappels de lot : celui du compte (déjà configuré).
