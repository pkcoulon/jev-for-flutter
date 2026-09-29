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
- Tâches : 4, toutes sur Pioudex, au commit `91036cc`.
- Variantes : 3, garde et mémoire actives dans les deux variantes avec plugin.
  - Sans dartlens.
  - `all` : consigne au démarrage, puis une note sur chaque lecture complète d'un fichier Dart de 300 lignes ou plus, au plus 3 par session.
  - `all_refuse` : consigne au démarrage, puis arrêt unique de cette lecture. C'est le réglage par défaut depuis.
- Déroulé : Sonnet 5, un essai par tâche et par variante, avec la vraie clé Jev.
- Réussite : critères automatiques **et** accord d'un agent relecteur, à qui l'on n'a pas dit quelle variante avait produit le travail.

| Tâche | Sans dartlens | Note | Arrêt |
|---|---|---|---|
| `loc-silence` (localiser) | échec, 0,96 $ | réussite, 0,80 $ | réussite, 0,67 $ |
| `diag-gain-xp` (diagnostiquer) | réussite, 0,77 $ | réussite, 1,06 $ | réussite, 1,17 $ |
| `convention-olive` (convention) | échec, 1,14 $ | échec, 0,33 $ | échec, 0,62 $ |
| `memoire-vibrations` (mémoire) | échec, 3,35 $ | échec, 3,97 $ | échec, 2,67 $ (coupé à 25 min) |
| **Total Claude** | **1 sur 4, 6,23 $** | **2 sur 4, 6,16 $** | **2 sur 4, 5,12 $** |
| Jev, tokens (tarif publié pour `jev-1.12`) | 0 | 32 197 (≈ 0,001 $) | 125 808 (≈ 0,005 $) |

### Ce que Claude a reçu

Mesuré par `bench/adoption.py` : code Dart effectivement reçu, par outil. Les caractères comprennent les numéros de ligne de Read.

| | Sans dartlens | Note | Arrêt |
|---|---|---|---|
| Read complet | 26 appels, 450 010 car. | 19, 318 533 | 8, 56 395 |
| Read avec plage | 12, 26 511 | 6, 25 247 | 9, 24 984 |
| `lens` (lignes montrées / totales) | — | — | 10 appels, 1 367 / 5 995, 72 564 car. |
| Shell (`sed -n`…) | — | — | 2, 3 235 |
| **Code Dart reçu** | **476 521 car.** | **343 780** | **157 178** |
| Fichiers Dart de 300 lignes ou plus reçus entiers | 14 | 10 | 1, par `lens` |
| Notes ou arrêts affichés | — | 9 notes | 8 arrêts |
| Lecture complète redemandée après un arrêt | — | — | 0 |

Le fichier reçu entier par `lens` fait 507 lignes. La question de Claude portait sur la structure de tout l'écran de réglages, et Jev a jugé utiles les 23 morceaux.

Parcours observés après les arrêts :
- **olive** : 2 arrêts, 2 questions à `lens`, puis la modification, sans relire la zone avec Read.
- **diagnostic** : arrêt, `lens`, recherches et lectures ciblées, puis la correction.
- **localisation** : arrêt, `lens`, recherches, puis la réponse. Aucune modification n'était demandée.
- **vibrations** : arrêt, `lens`, puis une longue exploration (recherches, fiches mémoire), puis l'écriture.

### Coût : ce qu'on peut dire

- Le total baisse de 18 % avec l'arrêt, échecs compris. Tâche par tâche, le rapport au témoin va de 0,54 à 1,52, avec une médiane de 0,74.
- Sur les 2 tâches réussies par les deux variantes du plugin (localisation et diagnostic), le coût est presque le même : 1,86 $ avec la note, 1,83 $ avec l'arrêt. Environ 97 % de l'écart total vient des tâches échouées.
- Le diagnostic, seule tâche réussie partout, coûte 0,77 $ sans plugin et 1,17 $ avec l'arrêt.
- **Conclusion** : l'arrêt divise par trois le code reçu, mais une économie sur un même travail terminé n'est pas démontrée.

### Ce que le calcul des lectures permet d'estimer

`bench/ceiling.py` conserve son nom, mais ne calcule pas un plafond d'économie du plugin. Il estime seulement le coût attribuable aux grandes lectures complètes de Dart, en supposant que le reste du parcours ne change pas. Il ne simule ni les recherches que `find` ou `which` pourraient éviter, ni le détour par `lens`, ni le coût de Jev.

Le calcul utilise les tarifs par modèle et les classes de tokens observées dans les traces, avec les écritures de cache de cinq minutes et d'une heure distinguées. Chaque résultat Read reste dans le contexte de l'agent qui l'a reçu, jusqu'à une compaction ou à la fin de cet agent. Les usages répétés sont dédoublonnés ; les journaux persistés complètent notamment les tokens de sortie absents du flux terminal.

Deux incertitudes restent explicites : la conversion des caractères en tokens (2,3 ou 3,5 caractères par token) et la classe de facturation de chaque passage. Les traces donnent les totaux par appel, sans dire quelle classe correspond à chaque extrait. Le script affiche donc les deux allocations extrêmes compatibles avec ces totaux, sous l'hypothèse de conservation du texte. Ce ne sont pas des intervalles de confiance.

Sur les sept témoins, le coût des appels enregistrés est de 9,68 $. Selon la conversion et l'attribution supposées, les lectures sélectionnées représentent entre 0,57 $ et 2,23 $. **Cette fourchette n'est ni une économie observée ni une promesse de gain.** Elle ne permet pas de conclure sur l'intérêt global de dartlens ou du plugin de Boris.

Les anciennes conclusions « quelques pour cent au mieux » et « des centaines d'essais nécessaires » sont retirées : le calcul ne les établissait pas. Aucun effectif d'essais n'est déclaré décisif sans protocole et analyse adaptés.

Reproduction hors ligne, sans appel Claude ou Jev :

```bash
python3 -B bench/ceiling.py '~/.cache/dartlens-bench/results/*/*.control.*' --json /tmp/dartlens-read-estimate.json
```

### Où examiner le parcours de recherche

L'analyse de la branche `claude/savings-scope` est conservée dans `bench/search_cost.py`. Elle situe les appels avant la première modification ou, pour une tâche sans modification, avant la réponse finale. Cette phase représente 58 % du coût des sept témoins, et 48 % en retirant leur premier appel principal.

Ce total comprend aussi la compréhension, des tests et le chargement de consignes. **Il n'indique pas une part économisable par `find` ou `which`.** Les coûts attribués aux contenus d'outils restent des estimations qui supposent leur conservation jusqu'à la fin de leur contexte.

Le script repère également les fichiers lus qui ne sont ensuite ni modifiés ni cités dans les éléments examinés. Ce repérage par nom ne prouve pas qu'une lecture était inutile : elle peut avoir servi à vérifier une hypothèse ou à écarter une piste.

Dans les douze essais avec plugin, aucune commande ni entrée de journal n'atteste un appel à `find` ou `which`. Leurs gains éventuels restent inconnus. Les commandes et journaux sont comptés séparément, car ils peuvent décrire une même exécution.

```bash
python3 -B bench/search_cost.py --json /tmp/dartlens-search-analysis.json
```

### Ajout ultérieur : l'outil `find_code`

Après cette campagne, le plugin expose aussi la recherche par comportement comme outil `find_code`, au moyen d'un [serveur MCP fourni par le plugin](https://code.claude.com/docs/en/plugins-reference#mcpservers). Il appelle la même commande `lens find`. L'hypothèse est qu'un outil directement disponible soit plus facile à choisir que la commande de terminal mentionnée dans une consigne. Ce n'est pas une cause démontrée de l'absence d'appels dans les essais précédents.

Vérification locale du 29 septembre : déclaration du plugin validée par Claude Code, échanges MCP, recherche sur les trois fichiers attendus de la tâche Pioudex, aller-retour avec le faux serveur Jev existant, repli local sans activation, refus des chemins extérieurs, arrêt du processus de recherche après annulation ou déconnexion. Le faux serveur vérifie le raccordement ; il ne mesure pas la pertinence de Jev.

Le banc reconnaît ces appels MCP et les distingue des commandes et journaux. Le texte du classement n'est pas compté comme du code Dart reçu. Le recalcul des mesures d'adoption sur les 19 archives donne les mêmes résultats qu'avant ce changement.

#### Première observation réelle de `find_code`

Le 29 septembre, après autorisation d'un budget de 1 $, Claude a exécuté une fois la tâche `pioudex-loc-silence`, avec Sonnet 5, la demande française inchangée et le plugin complet. Archive : `find-code-obs-2026-09-29/pioudex-loc-silence.all.fr.r1`.

- `find_code` figurait parmi les 106 outils disponibles, dont 75 MCP. Dans les traces de la conversation principale et du sous-agent `Explore`, il apparaît dans la liste des outils différés : son nom est visible, sa description doit être chargée par `ToolSearch`.
- Aucun appel à `ToolSearch`, `find_code` ou `lens`. Claude a délégué la recherche à `Explore`, qui a utilisé les outils habituels. Le refus de grandes lectures a joué trois fois ; la session comporte onze lectures partielles de Dart, dont huit dans le sous-agent. Ce parcours ne reproduit donc pas l'adoption de `lens` observée dans la campagne précédente.
- Réponse acceptée par le relecteur sur les quatre critères existants, sans fichier modifié. Une attribution de commentaire inexacte est signalée hors grille.
- Coût Claude au tarif API : 0,598 $. Durée enregistrée par le banc : 157 s. C'est un seul essai, sans nouveau témoin apparié ; ce résultat ne démontre ni une économie du plugin ni un bénéfice de `find_code`, qui n'a pas été appelé. Les autres composants du plugin restaient actifs.

#### Correction de la visibilité

La [documentation Claude Code](https://code.claude.com/docs/en/mcp#exempt-a-server-from-deferral) prévoit `alwaysLoad: true` dans la configuration d'un serveur MCP, y compris stdio : sa description d'outil est chargée au démarrage sans recherche préalable. Ce réglage est ajouté au seul serveur dartlens, qui expose un outil. Le rappel de démarrage ne demande plus de charger cet outil avec `ToolSearch`.

Le nom différé était bien présent dans les deux agents : leur absence d'appel ne prouve ni une impossibilité d'intégration, ni que le chargement différé soit l'unique cause. Cette correction vise l'accès à la description ; elle ne force pas Claude à choisir `find_code` et ne contourne pas les restrictions d'outils des sous-agents.

La correction de visibilité a ensuite été observée dans les sessions ci-dessous, autorisées séparément. Elle ne suffit pas à établir la qualité ni l'économie.

#### Observations après `alwaysLoad` : réponses incomplètes

Campagnes `find-code-obs2-2026-09-29` et `find-code-obs3-2026-09-29`, sur la même tâche et la même demande. Les coûts ci-dessous concernent Claude au tarif API, sans Jev.

| Session | `find_code` | Coût Claude | Relecture |
|---|---|---|---|
| adoption, sans plugin | absent | 0,96 $ | refusée |
| adoption, note | absent | 0,80 $ | acceptée |
| adoption, refus | absent | 0,67 $ | acceptée |
| obs1, outil différé | non utilisé | 0,60 $ | acceptée |
| obs2, `alwaysLoad` | utilisé | 0,29 $ | refusée |
| obs3, répétition 1 | utilisé | 0,22 $ | refusée |
| obs3, répétition 2 | non utilisé | 0,54 $ | refusée |

Les deux sessions utilisant `find_code` reçoivent cinq résultats centrés sur le modèle et l'affichage, sans les services d'identification. Les réponses omettent `ConfidenceTier.parse`, exigé par la grille. Elles n'expliquent pas non plus que l'écoute peut construire directement le résultat via le moteur embarqué, sans passer par `Identification.fromJson`.

**Vérification des traces par Codex :** dans les deux sessions avec `find_code`, un Read intégral de `identification.dart` a bien fourni `ConfidenceTier.parse` à Claude. Son omission dans la réponse n'est donc pas une disparition de ce code causée par le filtrage. La recherche incomplète des services et l'oubli d'un élément pourtant lu sont deux problèmes distincts.

Le bilan est descriptif : les versions, l'exploration et la relecture diffèrent entre sessions. Les deux derniers relecteurs ont reçu une consigne attirant l'attention sur le moteur embarqué. L'oubli de `parse` reste un manquement au critère préexistant. Ces essais ne démontrent pas un gain à qualité égale ; on ne présente pas leur petit coût comme une réussite du produit.

#### Révision du moteur à partir de Jev

Comparaison du 29 septembre avec le [code de Boris au commit `e81c1d0`](https://github.com/BorisLeMeec/jev/blob/e81c1d006b8b23a616486610f311039088521d0c/internal/run/find.go). Son criblage juge un seul fichier par requête ; il documente une dégradation des classements quand plusieurs fichiers étaient réunis. La version de dartlens des essais ci-dessus groupait les 120 fichiers en deux requêtes. Elle vérifiait ensuite huit candidats en présélectionnant leurs morceaux par mots-clés, et plaçait tous les fichiers vérifiés avant les autres, indépendamment du score.

Changements locaux :
- Une requête de criblage par fichier ; même question de pertinence au criblage et à la vérification, seul le contenu présenté change.
- Vérification sur le contenu intégral des premiers candidats, après masquage. Si le contenu dépasse le budget de la requête, son score reste explicitement non vérifié ; aucun préfixe n'est présenté comme un fichier entier.
- Classement par score, puis localisation dans au plus trois résultats. Une localisation incertaine ou indisponible ne retire pas le fichier du classement.
- Candidats au-dessus du seuil masqués par la limite signalés. Le résultat rappelle de suivre les appels et les modèles pour couvrir chaque partie de la demande.

Le nombre de résultats par défaut reste cinq. Le changement ne repose ni sur une hausse arbitraire de cette limite, ni sur une traduction supposée réparer la qualité. Les écarts d'implémentation sont établis ; leur rôle causal dans les deux mauvaises réponses reste à mesurer.

Contrôles hors ligne : les deux formulations françaises archivées passent par le serveur MCP et le faux Jev existant sur les 120 fichiers du commit Pioudex épinglé. Pour chacune : 120 requêtes de criblage, huit vérifications contenant bien le fichier entier, trois localisations ; aucune requête hors budget. Des réponses contrôlées vérifient les erreurs, les contenus trop grands, le classement, les positions incertaines et la limite d'affichage. Le manifeste Claude Code et la syntaxe passent également. **Le faux modèle valide le raccordement, pas la pertinence de Jev.**

Cette méthode fait plus de requêtes Jev. La rapidité de toute la tâche doit être mesurée ; on ne promet pas que l'appel de recherche seul soit plus rapide. Les résultats composants précédents décrivent l'ancien moteur et ne valident pas cette révision.

#### Observations du moteur révisé : couverture améliorée, qualité non validée

Claude a ensuite exécuté les deux recherches avec le vrai Jev, puis trois sessions, dans des lots autorisés séparément. Les deux recherches proposent désormais `embedded_bird_identifier.dart`, cinquième résultat. L'aiguillage `repli_bird_identifier.dart` reste hors des huit candidats vérifiés. Les requêtes et réponses Jev sont archivées dans `jev-search-2026-09-29` : 262 appels, 285 260 tokens d'entrée et 6 144 de sortie. Ce résultat de recherche ne prouve pas que Claude examine le parcours complet.

| Session | `find_code` | Coût Claude, hors Jev | Durée du banc | Résultat |
|---|---|---:|---:|---|
| obs4 | utilisé | 0,2712 $ | 52,7 s | acceptée par la grille ; erreur factuelle hors grille |
| obs5, répétition 1 | utilisé deux fois | 0,2474 $ | 65,7 s | refusée |
| obs5, répétition 2 | non utilisé | 0,3355 $ | 103,7 s | aucune réponse, budget épuisé |

**L'acceptation d'obs4 ne valide pas la qualité demandée.** La réponse nomme les symboles exigés, mais situe une conversion commune avant la séparation écoute/photo. L'écoute essaie pourtant d'abord le moteur embarqué, qui construit directement `Identification`, tandis que la photo utilise le serveur. Le fichier du moteur figure dans les résultats, mais Claude ne l'ouvre pas. Le même raccourci est reproché à obs5 r1, qui omet aussi le nom `ConfidenceTier.parse`. Les verdicts historiques sont conservés ; leur différence de sévérité interdit de conclure à une qualité équivalente.

Obs5 r2 ne livre qu'un message d'attente avant `error_max_budget_usd`. Son rapport de sous-agent avait d'abord été pris à tort pour la réponse : le banc exclut désormais les textes de sous-agents du texte final de secours. Cette répétition reste un échec, même si le sous-agent avait trouvé les éléments demandés.

Les durées ci-dessus sont descriptives. Les anciennes durées d'adoption, contaminées par les attentes de permission, ne doivent pas servir à annoncer un gain de vitesse. Aucun bénéfice à qualité égale n'est établi par ces trois essais.

Le réglage `--max-budget-usd 0.30` n'a pas empêché obs5 r2 d'atteindre 0,3355 $. La [documentation du CLI](https://code.claude.com/docs/en/cli-reference) inclut les sous-agents de la session dans ce budget ; les appels Jev et les workflows de relecture lancés séparément n'y sont pas compris. Ce réglage ne doit pas être présenté comme une garantie de dépense totale maximale. Les coûts Jev restent des estimations tant que le tarif du modèle utilisé n'est pas confirmé.

La prochaine correction doit traiter l'arrêt de l'exploration alors que des branches du parcours restent à vérifier. Une nouvelle liste de fichiers ou une consigne supplémentaire ne suffisent pas à en démontrer la résolution. Exploiter d'abord les traces archivées ; tout nouvel appel réel reste soumis à un lot et un budget autorisés.

### Qualité : ce qu'on peut dire

- **Rejeu.** Les vérifications ont été rejouées sur un clone propre, avec les mêmes résultats sur les 12 essais. Au départ, tout passe (339 tests, analyse, formatage), sauf le bug semé exprès pour le diagnostic.
- **Tests cassés.** Dans les trois variantes, la tâche vibrations casse 2 tests qui passaient avant.
  - Sans plugin et avec la note : le nouveau panneau pousse la carte « À propos » hors de l'écran de test.
  - Avec l'arrêt : une clé de traduction sans utilisateur, et un fichier généré pas à jour.
  - Le relecteur ne voyait pas les tests : son « aucune régression » ne vaut pas pour eux.
- **Olive**, refusée dans les trois variantes. C'est un vrai manque de l'agent, le même partout, et le plugin n'y joue aucun rôle.
  - Les critères automatiques passaient déjà sans aucune modification.
  - Aucune variante ne vérifie ce que la nouvelle couleur touche. Le texte crème est à 4,55:1, juste au-dessus du seuil. Le motif en filigrane tombe vers 1,34:1, sous le minimum du design system.
  - La grille avait été écrite avant la campagne.
- **Vibrations**, jamais aboutie.
  - Le témoin s'arrête à 60 tours. La note « termine » en laissant ses tests tourner en arrière-plan : l'un d'eux bloque. L'arrêt est coupé à 25 minutes.
  - La tâche est serrée : `DECISIONS.md` fait 299 Ko et coûte 7 à 9 tours de détour.
  - Le routeur a bien classé les 5 fiches utiles en tête, sans que ça suffise.
- **Verdict.** Avec 4 tâches et un essai chacune, `score.py` n'affiche plus de verdict de qualité.

### L'environnement a faussé les durées

26 demandes de permission sont restées bloquées environ 115 s chacune avant d'être refusées.
- Le hook utilisateur `rtk` réécrivait des commandes autorisées en commandes hors liste.
- Un lanceur de terminal (cmux) passait devant le vrai binaire `claude`. Il est suspect, sans preuve directe.
- Sur vibrations, cela représente 691 s sans plugin, 461 s avec la note et 807 s avec l'arrêt.
- **Les durées de cette campagne ne sont pas exploitables.** Pour l'essai coupé à 25 minutes, on sait seulement que plus de la moitié du temps s'est passée à attendre, et que chaque appel à `lens` a pris moins d'une seconde. L'effet de l'arrêt sur la suite du travail n'est pas établi.
- Depuis, `run.py` écarte par défaut les réglages utilisateur et le lanceur (`bench/PROTOCOL.md`).

### Suite

1. Refaire, avec le banc isolé, quelques tâches que Claude sait réussir et assez différentes, dont une où il faut vraiment lire tout un fichier. Plusieurs essais par tâche.
2. Pour les prochaines versions des tâches, sans ré-noter celle-ci :
   - olive : préciser que « vérifier » veut dire « en rendre compte », et dire si la bande de barre d'état fait partie du travail ;
   - vibrations : revoir le budget de tours.

## Rejouer

- Besoin : `python3 docs/need_data.py …` puis `python3 docs/charts.py …`, et `docs/lens_opportunity.py`.
- Banc : `bench/PROTOCOL.md`, puis `bench/run.py` et `bench/score.py`.
