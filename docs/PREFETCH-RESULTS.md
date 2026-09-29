# Préparer la lecture pendant que Claude raisonne

La version 0.3.1 commence l'analyse Jev en arrière-plan lorsque la demande nomme un seul fichier Dart admissible. Claude peut alors réutiliser la sélection au moment de lire. Les questions envoyées à Jev, les seuils et les tailles de fenêtre sont inchangés.

## Vérification réelle du 29 septembre 2026

Les trois fichiers du [lot de lectures 0.3.0](READ-RESULTS.md) ont été essayés une fois dans chaque mode, avec de vrais appels Jev : analyse au moment de lire, puis analyse déjà préparée. L'ordre est inversé pour le deuxième fichier.

| Fichier | Analyse au moment de lire | Sélection déjà préparée | Même passage fourni |
|---|---:|---:|---|
| Notifications | 545 ms | 92 ms | oui |
| Caches de synchronisation | 522 ms | 118 ms | oui |
| Identification audio | 551 ms | 130 ms | oui |
| **Moyenne** | **539 ms** | **114 ms** | **3/3** |

Le tableau mesure l'exécution du hook de lecture, démarrage Python compris. **L'attente à cet endroit baisse de 79 % sur ces trois cas.** Les préparations ont elles-mêmes pris 455 à 533 ms, hors de cette durée : le travail est avancé, pas supprimé. Si Claude lit trop tôt, il attend ce qui reste de la même requête ; aucun doublon ne part. Sans chemin explicite, ce mécanisme ne s'applique pas.

Une session Claude Sonnet 5 supplémentaire a vérifié le fonctionnement complet sur la question audio : sélection prête environ trois secondes avant le Read, réutilisation confirmée, une seule lecture, méthode attendue présente. Le moteur a pris 33 ms dans le hook de lecture. La réponse couvre les quatre critères existants, après vérification du code par Astra, sans relecteur indépendant. Cette session a duré 9,053 s selon Claude et coûté 0,047921 $ pour Claude.

Ce lot ne compare pas deux réponses complètes avec et sans préparation. **Il ne démontre donc ni une réponse globalement 79 % plus rapide, ni une nouvelle économie de tokens ou de coût.** Les pourcentages du README restent ceux du lot 0.3.0, identifié comme tel. Une préparation non utilisée peut ajouter une requête Jev.

## Vérifications et budget

- Les requêtes de sélection des trois cas sont identiques à celles archivées pour 0.3.0 ; seules les réponses probabilistes peuvent varier. Les trois fenêtres obtenues sont identiques dans les deux modes.
- 27 contrôles supplémentaires avec serveur HTTP simulé : lectures concurrentes, déduplication, expiration, source/question/modèle changés, activation retirée, budget partagé, erreur, liens externes, résultat trop large et récupération du fichier entier.
- Les 69 contrôles existants des lectures et du contexte facultatif passent aussi. Aucun build ni simulateur.
- La validation réelle ajoute huit appels Jev et une session Claude : **0,05110 $**, dont 0,00317 $ pour Jev. Budget cumulé : **3,48515 $ sur 5 $**.

Le plan, le plugin figé et les traces sont conservés dans le cache privé `~/.cache/dartlens-bench/read-prefetch-2026-09-29/`. [Données, réponses et critères](prefetch-results.json). Le moteur publié est identique à la copie testée.

[Architecture](ARCHITECTURE.md) · [Installation et réglages](USAGE.md) · [Retour au README](../README.md)
