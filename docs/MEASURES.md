# Mesures de dartlens

Le détail derrière les chiffres du README. Toutes les mesures avec Jev utilisent le modèle `jev-1.13.0` et la clé officielle, sur le code de 3 projets Flutter perso. Les sessions du projet pro n'apparaissent qu'en totaux anonymes.

Trois niveaux, qui ne disent pas la même chose :

| Niveau | Question | Ce qu'on peut en conclure |
|---|---|---|
| Branchement | Le plugin démarre-t-il ? Respecte-t-il les exclusions ? Gère-t-il les pannes ? | Le mécanisme marche. Rien sur la qualité de Jev ni sur une économie. |
| Composants | Jev retrouve-t-il les bons passages, les écarts, les bonnes fiches ? | Les outils peuvent être utiles quand Claude s'en sert. |
| Tâches complètes | Claude s'en sert-il ? Termine-t-il aussi bien ? À quel coût ? | Seul ce niveau peut valider la promesse. Premiers résultats plus bas, sur peu d'essais. |

## Le besoin, sur nos sessions réelles

49 sessions, 15 835 échanges, 4 projets Flutter, dont 1 pro anonymisé. Les usages sont comptés une seule fois par message. Le coût est valorisé au tarif API de chaque modèle au 2026-09-28 : c'est une estimation, pas une facture.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/context-growth-dark.svg">
  <img alt="Taille de ce que Claude relit à chaque échange au fil de sessions réelles." src="img/context-growth-light.svg">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/tool-residency-dark.svg">
  <img alt="Part de ce qui est relu qui vient des sorties d'outils, par type d'outil." src="img/tool-residency-light.svg">
</picture>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/cost-by-context-dark.svg">
  <img alt="Part des échanges et du coût selon la taille de ce qui est relu." src="img/cost-by-context-light.svg">
</picture>

- En moyenne, Claude relit 250 000 tokens à chaque échange.
- Les sorties d'outils font 31,9 % de ce qui est relu. Une sortie d'outil est relue 17 fois en médiane.
- Les échanges au-delà de 400 000 tokens sont 20 % des échanges, mais 47 % du coût.

Ce que `lens` pourrait viser : les fichiers de 150 lignes ou plus lus en entier, et les sorties de 80 lignes ou plus.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/lens-target-dark.svg">
  <img alt="Part de ce qui est relu que lens pourrait viser : 13,9 % sur le projet pro, 10,3 % sur les projets perso." src="img/lens-target-light.svg">
</picture>

Ce sont des estimations du besoin, pas des économies. Elles supposent environ 2,3 caractères par token, et qu'une sortie reste dans la conversation jusqu'à la compaction suivante. Le cache, et les lectures nécessaires après un filtrage, changent le coût réel.

## Composants, avec Jev

| Aide | Résultat | Portée |
|---|---|---|
| `lens` | Passages attendus tous présents dans 66 cas sur 72 (91,7 %), contre 73,6 % par mots-clés (BM25). En médiane, 10,1 % des lignes du fichier montrées ; 12,9 % des caractères d'une lecture complète, indications et omissions comprises. Jamais moins bon que les mots-clés. Aucun passage montré pour les 8 questions pièges. Environ 0,45 s. | 36 questions sur 12 fichiers, en français et en anglais : les deux versions d'une question ne sont pas deux cas indépendants. Des passages présents ne garantissent pas que Claude réponde juste. Ce n'est pas une économie sur une tâche. |
| `lens find` | Le bon fichier en premier pour les 20 descriptions (intervalle de confiance à 95 % : 83–100 %) ; 19 sur 20 en ne gardant que les résultats jugés sûrs. Par mots-clés : 35 %, et 5 % sur les descriptions sans aucun mot du code ; grep : 18 %. Environ 1,6 s. | Descriptions écrites en lisant le code. Sur 6 descriptions vagues : 3 réussites. Sur 8 pièges proches, 2 fausses réponses. Un grep naïf ne représente pas toute la façon de chercher d'un agent. |
| Garde | 26 écarts repérés sur 30, 4 manqués ; aucune alerte sur 30 exemples conformes. Mêmes réponses sur 3 passages. Environ 0,3 s de Jev, en arrière-plan. | Règles et exemples écrits par le même agent, surtout synthétiques. Chaque exemple teste sa règle ; une vraie modification en déclenche plusieurs. |
| Mémoire | 20 fiches proposées sur 40 demandes, dont 15 utiles ; il en fallait 58. Au moins une bonne fiche pour 14 des 34 demandes qui en avaient besoin. Dans le top 3 : 60 %, contre 47 % par mots-clés. Skills : 4 bons choix sur 6, aucune fausse suggestion. Environ 0,4 s par demande. | Le seuil n'explique pas tout : le catalogue et la description des fiches comptent aussi. |

**Corrections d'étiquettes.** Des vérificateurs ont relevé des passages attendus mal étiquetés dans le jeu `lens`. Une fois corrigés, Jev passe à 98,6 % et les mots-clés à 79,2 %. Les chiffres ci-dessus restent ceux d'origine.

## Tâches complètes

**Pilote du 2026-09-29.**
- Déroulé : Sonnet 5, un essai par tâche et par variante, avec la vraie clé Jev. Arrêté avant la fin pour préserver le quota.
- Tâches : 3 tâches ont leurs deux essais, avec et sans dartlens.
- Réussite : 2 sur 3 dans les deux cas, d'après les seuls critères automatiques. La relecture des modifications manque encore.
- Coût : 3,11 $ avec dartlens, contre 3,45 $ sans, au tarif API. Sur si peu d'essais, ce n'est pas une preuve.
- Usage : aucun appel à `lens`, `dart-outline` ni au skill. La garde a tourné sans fausse alerte.

**Campagne d'adoption du 2026-09-29** (`adoption-2026-09-29`).
- Tâches : 4, toutes sur Pioudex.
- Variantes : 3, chacune avec la garde et la mémoire actives.
  - Sans dartlens.
  - `all` : consigne au démarrage, puis une note sur chaque lecture complète d'un fichier Dart de 300 lignes ou plus, au plus 3 par session.
  - `all_refuse` : consigne au démarrage, puis un refus unique de cette lecture.
- Déroulé : Sonnet 5, un essai par tâche et par variante, avec la vraie clé Jev.
- Réussite : il faut que les critères automatiques passent **et** qu'un agent relecteur, à qui l'on n'a pas dit quelle variante avait produit le travail, l'accepte. Relecture : 12 paquets, aucun retouché par le masquage.

| Tâche | Sans dartlens | Note | Refus |
|---|---|---|---|
| `loc-silence` (localiser) | échec, 0,96 $ | réussite, 0,80 $ | réussite, 0,67 $ |
| `diag-gain-xp` (diagnostiquer) | réussite, 0,77 $ | réussite, 1,06 $ | réussite, 1,17 $ |
| `convention-olive` (convention) | échec, 1,14 $ | échec, 0,33 $ | échec, 0,62 $ |
| `memoire-vibrations` (mémoire) | échec, 3,35 $ | échec, 3,97 $ | échec, 2,67 $ (délai de 25 min dépassé) |
| **Total** | **1 sur 4, 6,23 $** | **2 sur 4, 6,16 $** | **2 sur 4, 5,12 $** |

Aucune régression relevée par le relecteur.

Le parcours d'adoption (`bench/adoption.py`) :

| | Sans dartlens | Note | Refus |
|---|---|---|---|
| Lectures complètes de fichiers Dart ≥ 300 lignes | 14 (≈ 163 k tokens) | 10 (≈ 115 k) | 0 |
| Notes ou refus affichés | — | 9 notes | 8 refus |
| Appels à `lens` | 0 | 0 | 10 |
| Lecture complète relancée après un refus | — | — | 0 |
| Lecture complète après un appel à `lens` | — | — | 0 |
| Lectures ciblées (`offset`/`limit`) | 18 | 11 | 11 |
| Modifications refusées faute de lecture | 0 | 0 | 0 |

Ce qu'on peut en dire :
- **La note ne suffit pas** : Claude la reçoit, puis lit le fichier en entier quand même.
- **Le refus unique change le parcours** : `lens` en mode Jev, sans erreur, en 0,33 à 0,51 s ; puis une lecture ciblée ; puis la modification. Une lecture partielle suffit à Claude Code avant une modification.
- **Le coût total baisse de 18 % avec le refus.** Tâche par tâche, le rapport au témoin va de 0,54 à 1,52 (médiane 0,74). La tâche de diagnostic a coûté plus cher.
- **Réussite** : 1 sur 4 sans dartlens, 2 sur 4 dans les deux autres variantes. La différence tient à une seule tâche (`loc-silence`), sur un seul essai. `score.py` affiche une « non-infériorité établie », mais sur 4 tâches cela ne veut pas dire grand-chose.
- Le dépassement de délai sur « vibrations » avec refus vient de longs tours de réflexion du modèle, pas de `lens` : 3 appels, tous sous la demi-seconde.

À faire pour conclure :
- plusieurs essais par tâche ;
- des tâches sur d'autres projets ;
- mesurer les fausses alertes de la garde en usage réel.

## Rejouer

- Besoin : `python3 docs/need_data.py …` puis `python3 docs/charts.py …`, et `docs/lens_opportunity.py`.
- Banc : `bench/PROTOCOL.md`, puis `bench/run.py` et `bench/score.py`.
