# Changelog

## 0.3.2 — 2026-09-29

- Recherche par groupes de huit plans, avec un score par fichier : moins d'allers-retours et de tokens Jev. Comparaison sur Flutter Form App, LocalSend et AppFlowy.
- Lectures de méthodes explicitement nommées plus courtes, avec conservation de leur déclaration entière et des dépendances locales repérées.
- Correction de la protection des limites de méthodes ; exclusion des fichiers générés `*.mapper.dart` ; vérification des marqueurs sans reparcourir le dépôt.
- Renommage du paquet en `plugins/jev-for-flutter`, du module en `jev_flutter` et des noms exposés. Compatibilité conservée pour les configurations, clés, règles, caches, exclusions et anciennes variables.
- `jev-flutter init --enable-jev` et `jev-flutter doctor` pour la première installation. Licence MIT et attribution incluses dans le paquet.
- README et graphiques clarifiés. Les mesures de recherche et de réponse Claude restent distinctes ; aucune promesse d'économie universelle.

## 0.3.1 — 2026-09-29

Préparation des lectures en parallèle lorsque la demande nomme un seul fichier Dart. Réutilisation dans la même session, sans seconde requête, avec invalidation et délai d'expiration.

## 0.3.0 — 2026-09-29

Lectures natives ciblées, intégration marketplace Jev for Flutter et recherche sémantique à la demande. Le contexte automatique expérimental reste désactivé par défaut.
