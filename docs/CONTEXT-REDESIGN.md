# Un contexte préparé pendant le travail de Claude

> Historique : la version 0.3 utilise désormais la lecture native ciblée et garde le contexte automatique en option. Voir [les dernières mesures](READ-RESULTS.md) et [l’architecture actuelle](ARCHITECTURE.md).

29 septembre 2026 — implémentation locale par Codex, non publiée. Les mesures de la v0.2 ne sont pas des mesures de cette refonte.

## Le problème corrigé

Les essais précédents montraient deux défauts : Claude pouvait ignorer l'outil de recherche, et les résultats pouvaient l'arrêter trop tôt sur les écrans sans vérifier le service. Réduire le nombre de caractères ou le coût d'une réponse incomplète ne répond pas à la promesse.

La nouvelle architecture prépare le contexte automatiquement, en parallèle de Claude, et ajoute des références locales aux résultats de recherche. Elle ne demande plus au modèle de découvrir `find_code` ni de subir un refus pour commencer. Les déclarations trop longues restent à lire avec un chemin et des lignes, au lieu de disparaître derrière un classement.

## Réalisé

- Moteur commun à `lens context`, au hook automatique et au MCP facultatif.
- Index local des déclarations et références, mis à jour par empreinte ; aucun build ni embedding.
- Classement Jev par fichier, jusqu'à quatre requêtes simultanées par demande, huit au total, sans reprise.
- Contexte remis une seule fois au parent ou au sous-agent, sans attendre dans le hook de collecte.
- Annulation des requêtes encore en attente, délai du worker, repli local et rejet des sources obsolètes.
- Lecture libre par défaut ; l'ancien refus reste une option explicite. Conventions et mémoire conservées, routeur rendu asynchrone.

## Vérification hors ligne

Le script temporaire et ses données sont conservés dans `~/.cache/dartlens-bench/context-redesign-2026-09-29/`. Cette vérification locale utilise un faux serveur, sans clé réelle ni build ; elle ne mesure pas la pertinence du modèle Jev. Les [sessions réelles suivantes](CONTEXT-RESULTS.md) sont comptées séparément, dans l'enveloppe de 5 $ autorisée.

**41 contrôles réussis** sur les limites, la concurrence, le cache, les modifications des sources, les exclusions, les liens symboliques, les secrets PEM, le repli, les hooks, l'annulation, le remplacement d'une demande, la remise au sous-agent et le MCP. Les requêtes de deux demandes successives peuvent se chevaucher le temps que les appels déjà partis terminent ; le plafond de quatre s'applique à chacune.

Sur la copie Pioudex épinglée par la tâche historique, la recherche **locale**, sans Jev, fait apparaître dans sa carte :

| Partie du parcours | Source visible dans la carte |
|---|---|
| Interprétation de la réponse | `ConfidenceTier`, `Identification.fromJson` |
| Écoute et décision d'affichage | `ListenSession._verdict` |
| Photo et décision d'affichage | `PhotoSession` |
| Traitement embarqué | `EmbeddedBirdIdentifier` |
| Repli serveur | `RepliBirdIdentifier` |

Le contexte tient désormais dans **8 000 octets UTF-8**. Le corps long du traitement embarqué est indiqué par sa plage, sans être recopié intégralement. Retrouver ce symbole corrige un défaut de visibilité ; cela ne démontre pas encore que Claude le lira et raisonnera correctement. Les scores archivés de huit requêtes Jev Pioudex ont aussi été rejoués hors ligne pour vérifier ce format compact.

## Ce qui reste à mesurer

Le gain visé vient des recherches évitées et du travail effectué en parallèle. Ajouter un contexte inutile pourrait au contraire augmenter les tokens. Les premiers essais réels confirment la remise du contexte au parent et au sous-agent, mais leurs réponses sont incomplètes. Le [bilan réel](CONTEXT-RESULTS.md) distingue ce défaut de qualité du problème de transport corrigé ensuite.

Chaque comparaison garde le même prompt et contrôle les branches complètes avant de comparer les tokens, le coût Claude + Jev et le temps jusqu'aux vérifications terminées. Les anciens cas Pioudex fournissent un contrôle de régression ; ils ne constituent pas une validation générale sur des projets inconnus.

[Architecture et limites](ARCHITECTURE.md) · [Utilisation](USAGE.md) · [Données antérieures](EXPERIMENT-5USD.md)
