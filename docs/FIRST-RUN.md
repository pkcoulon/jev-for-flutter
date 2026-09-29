# Première utilisation

Jev for Flutter est un plugin **Claude Code**, pas une dépendance `pubspec.yaml`, ni une extension Android Studio ou VS Code. Son code est sous [licence MIT](../LICENSE). Le compte Claude Code et les appels TypeSafe ont leur propre tarification.

## Parcours conseillé

1. Installez Python 3.9+ et Claude Code sur macOS ou Linux. Pour Windows, utilisez Claude Code et Python **dans WSL** ; Windows natif n'est pas pris en charge par ce plugin. Le Flutter SDK n'est pas nécessaire pour commencer. L'installation réelle de cette version a été vérifiée sous macOS ; WSL n'a pas été essayé dans cette campagne.
2. Ajoutez la marketplace et installez le plugin avec les commandes du [README](../README.md#installation). Ce dépôt fournit sa propre marketplace ; il n'est pas dans le catalogue officiel Anthropic. Tant qu'il est privé, un compte GitHub autorisé est nécessaire.
3. Configurez votre clé TypeSafe avant de lancer Claude, ou placez-la dans le [fichier personnel prévu](USAGE.md#clé-et-activation). Ne la collez pas dans une conversation ni dans le dépôt.
4. Lancez une nouvelle session Claude Code à la racine du projet. Exécutez `! jev-flutter init --enable-jev`, puis `! jev-flutter doctor`. L'activation crée ou fusionne `.claude/jev-for-flutter.json` ; elle ne remplace pas les autres réglages.
5. Travaillez normalement. Pour une méthode connue, nommez-la et indiquez son fichier. Pour un comportement sans nom connu, demandez une recherche par description. Les fichiers et fonctionnalités de votre projet déterminent la question utile.

`doctor` ne contacte aucun service et ne valide pas la clé auprès de TypeSafe. Il indique seulement sa présence et les conditions locales d'activation. `jev-flutter status` détaille les limites, les exclusions et l'usage journalisé.

## Situations fréquentes

| Situation | Comportement et action |
|---|---|
| Pas de clé ou pas d'activation | Les lectures restent ordinaires. Utilisez `find --local` pour la recherche locale ou terminez l'installation. |
| Clé refusée, crédit épuisé, réseau indisponible | Une lecture automatique reste complète ; la recherche signale son repli ou les jugements manquants. Corrigez la clé ou le service. Les pauses après erreurs apparaissent dans `status`. |
| Petit fichier | En dessous de 400 lignes, aucune sélection de lecture. Il n'y a pas d'économie systématique sur un petit projet. |
| Fichier de plus de 64 Ko | Lecture native inchangée. Demandez une plage précise si vous connaissez la zone. |
| Audit ou refonte globale | Le plugin doit laisser le fichier entier. Les lectures ciblées servent aux questions localisées. |
| Extrait insuffisant | Relire le fichier entièrement, ou lire explicitement une autre plage. L'original sur disque est intact. |
| Projet très volumineux | Réduisez le dossier de recherche ou augmentez explicitement `--max-files`. Pour une recherche complète lente, ajustez le délai décrit dans le [guide](USAGE.md#au-quotidien). |
| Application en plusieurs packages | Lancez Claude à la racine voulue. `doctor` affiche la racine retenue ; passez un périmètre de recherche explicite. Le plugin n'impose aucun dossier `services`, `bloc` ou `repository`. |
| Code généré | Les formats connus sont exclus. La liste `generated` et les marqueurs de dossiers sont configurables ; vérifiez leur contenu si votre projet utilise un générateur particulier. |
| Pas de SDK Dart, ou plan approximatif | Le plugin fonctionne avec une reconnaissance approximative. Ce n'est pas une analyse résolue des types. Aucun SDK n'est installé par `init` ou `doctor`. |
| Commande introuvable dans le terminal | Les commandes sont ajoutées au terminal de la session Claude par le hook de démarrage. Ouvrez une nouvelle session après installation ; vérifiez que les hooks sont activés. |
| Configuration JSON invalide | `init` refuse de l'écraser et `doctor` signale le problème. Corrigez le JSON avant de recommencer. |
| Projet confidentiel ou politique d'équipe | L'activation est propre au projet. Une exclusion utilisateur reste prioritaire, y compris après migration ; elle empêche les envois. |
| Plusieurs copies du plugin | Chargez soit la marketplace, soit `--plugin-dir`. Retirez l'ancienne installation avant la nouvelle pour éviter des hooks exécutés deux fois. |
| Préparation inutilisée | Une demande nommant un fichier peut déclencher une requête anticipée même si Claude ne le lit pas. Désactivez `read.prefetch` si ce fonctionnement ne convient pas. |
| Mise à jour depuis l'ancien nom | Les configurations, clés, règles, exclusions et variables d'environnement historiques restent reconnues. Le cache existant reste utilisable. Voir la [migration](USAGE.md#migration-depuis-dartlens-02). |

Les évaluations en anglais et en français de cette campagne passent leur grille ; les autres langues n'ont pas été mesurées.

## Désactiver ou désinstaller

Désactivez Jev pour un projet en passant `jev.enabled` à `false` dans sa configuration. Le réglage `lens.nudge` à `off` coupe seulement la sélection native de lecture.

Pour retirer le plugin utilisateur :

```bash
claude plugin uninstall jev-for-flutter@jev-for-flutter
claude plugin marketplace remove jev-for-flutter
```

Ajoutez `--scope local` à la première commande si l'installation utilisait cette portée. Relancez Claude. Les fichiers du projet, vos règles, votre clé personnelle et vos caches ne sont pas effacés par ces commandes du plugin.

[Installation Claude Code et WSL](https://code.claude.com/docs/en/setup) · [Référence officielle des plugins](https://code.claude.com/docs/en/plugins-reference) · [Tarifs TypeSafe](https://docs.typesafe.ai/models)
