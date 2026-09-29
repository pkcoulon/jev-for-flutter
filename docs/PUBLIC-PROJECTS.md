# Benchmarks sur trois projets Flutter publics

Le regroupement des requêtes accélère la recherche, surtout sur les gros projets. Les lectures ciblées réduisent le coût Claude observé, mais ne rendent pas encore ses réponses plus rapides. **La campagne mesure la recherche et la compréhension du code, pas un développement complet.**

## Projets et sources

| Projet | Périmètre examiné | Fichiers Dart examinés | Révision figée |
|---|---|---:|---|
| Flutter Form App | Exemple officiel, `form_app/lib` | 6 | [8a4cf1d](https://github.com/flutter/samples/tree/8a4cf1db16d52741f0e59e1bfe818723430c35bc/form_app) |
| LocalSend | Application et deux packages Dart | 250 | [c5bbe36](https://github.com/localsend/localsend/tree/c5bbe3630bb50e0de8253502b41523c4a58825bb) |
| AppFlowy | `appflowy_flutter/lib` et packages | 1 691 | [5cf3a36](https://github.com/AppFlowy-IO/AppFlowy/tree/5cf3a365dec0d59f64bad1ee4bb1050471a39b93/frontend/appflowy_flutter) |

Code généré, tests et fichiers exclus par la politique écartés. AppFlowy contient trois autres fichiers Dart dans l'inventaire initial, exclus par cette politique. Les backends Rust et les plateformes natives ne sont pas couverts. Aucun build, aucune modification des applications.

## Recherche : mêmes fichiers examinés, moins d'allers-retours

Comparaison du même moteur avec **un fichier par requête** et **huit fichiers au plus par requête**. Chaque fichier conserve un jugement distinct ; le code des meilleurs candidats est ensuite vérifié. Aucun fichier n'est présélectionné par mots-clés.

| Projet | Temps moyen individuel → groupé | Écart | Coût Jev moyen par recherche | Écart |
|---|---:|---:|---:|---:|
| Form App | 1,69 → 1,40 s | **−17 %** | 0,000533 → 0,000475 $ | −11 % |
| LocalSend | 14,76 → 3,89 s | **−74 %** | 0,007977 → 0,005587 $ | −30 % |
| AppFlowy | 89,78 → 15,88 s | **−82 %** | 0,047691 → 0,030974 $ | −35 % |

**12 recherches sur 12 satisfont la grille dans chaque variante.** Par projet : deux recherches ciblées, dont une en français, une recherche de fonctionnalité absente et un parcours réparti sur deux fichiers. Les deux variantes retrouvent les deux fichiers nécessaires aux trois parcours. Aucune réponse de LLM n'est évaluée dans cette partie.

Un cas positif passe si tous les chemins attendus figurent parmi les cinq premiers résultats avec un score d'au moins 0,60. Les chemins supplémentaires ne sont pas pénalisés. Un cas négatif passe si aucun chemin ne dépasse ce seuil. Cela vérifie une sélection de cas ; cela ne prouve pas un rappel parfait sur un autre projet.

Quatre questions différentes par projet, **une exécution par question et variante**. Ordre alterné, même modèle `jev-1.13.0`, huit requêtes simultanées au plus, plan syntaxique approximatif identique. Le plafond a été explicitement porté à 3 000 fichiers et le délai réseau à 180 secondes pour permettre la comparaison individuelle sur AppFlowy. Le réglage courant reste 150 fichiers et 20 secondes ; le dépassement exige un choix explicite du périmètre.

[Données, questions, chemins attendus et sorties classées](public-search-results.json).

## Lecture par Claude : coût, tokens et qualité

Trois questions fixées avant les appels, une par projet. Outil `Read` uniquement dans les deux variantes, même source copiée dans un projet isolé, mêmes prompts, Sonnet 5 et effort moyen. Le plugin est activé avec ses réglages par défaut. Les réponses doivent couvrir quatre critères chacune ; une omission suffit à refuser une réponse.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/public-read-results-dark.svg">
  <img alt="Sur trois questions ciblées : tokens Claude −23 %, coût Claude et Jev −53 %, durée +7 %. Réponses acceptées : 3/3 avec, 2/3 sans." src="img/public-read-results-light.svg" width="960">
</picture>

| Question | Réponses acceptées sans / avec | Coût sans → avec, Jev inclus | Durée sans → avec |
|---|---|---:|---:|
| Form App : requête de connexion et statuts HTTP | Oui / Oui | 0,03795 → 0,03856 $ | 4,44 → 4,99 s |
| LocalSend : représentation des grandes et petites sessions | Non / Oui | 0,08249 → 0,04461 $ | 7,11 → 7,70 s |
| AppFlowy : écran le plus proche, égalité, entrée vide | Oui / Oui | 0,14346 → 0,03978 $ | 5,64 → 5,64 s |

La réponse LocalSend sans plugin ne décrit pas explicitement les petites sessions dans le cas mixte. Elle reste dans tous les totaux. Revue par Astra, **ni indépendante ni à l'aveugle** ; réponses et critères publiés pour permettre une autre lecture.

Le fichier Form App fait 111 lignes : aucune sélection de lecture ni économie attendue. Les deux autres fichiers font 851 et 1 667 lignes ; la méthode explicitement nommée et les dépendances locales repérées tiennent dans 64 lignes. Les passages attendus sont conservés. Sur LocalSend, Claude fait une lecture supplémentaire d'une ligne avant la lecture ciblée : elle est comptée.

Les tokens Claude incluent entrées, écritures et lectures de cache, et sorties : **107 419 → 82 505**. Jev traite séparément 45 262 tokens d'entrée et 2 923 de sortie pour cette partie. **Le total de tokens des deux modèles ne diminue pas** : une partie du travail est confiée au modèle moins cher. Le coût comprend aussi les trois appels du routeur ; il a considéré 18 descriptions de skills personnels, sans en suggérer. La mémoire et les règles des projets de test étaient vides.

Les coûts Claude sont ceux rapportés par les sessions, rapprochés des messages dédupliqués avec leurs catégories de cache. Ils sont exprimés au tarif API, pas comme une mesure du quota d'un abonnement. La durée vient de `duration_ms` rapportée par Claude. Une seule session par variante ne permet pas d'attribuer tout écart au plugin ni d'estimer sa variabilité.

[Données et réponses complètes](public-read-results.json). Les essais ont utilisé le moteur candidat figé avant le renommage interne et l'ajout des commandes locales `init` et `doctor`. La distribution renommée a repassé les contrôles hors ligne ; ces mesures ne constituent pas une deuxième campagne payante sur cet habillage final.

## Vérifications et reproductibilité

- Deux demandes de revue globale conservent le fichier entier ; deux relectures identiques retrouvent aussi le fichier complet, avec le vrai Jev.
- 200 méthodes reconnues, tirées de LocalSend et AppFlowy avec une graine fixe, restent entières dans les plages proposées ou la lecture complète. Ce contrôle utilise le parseur approximatif ; il ne vérifie pas la résolution des types ni la pertinence du modèle.
- Les contrôles locaux couvrent les dépendances proches et éloignées, grandes méthodes, plafonds, génération, indisponibilité, plages explicites, refus de projet, concurrence, invalidation et compatibilité.
- L'installation marketplace et les manifestes sont vérifiés dans une configuration Claude isolée. Les parcours d'activation et de diagnostic ne font aucun appel réseau.

Exemple de reproduction de la comparaison de recherche, depuis un checkout figé autorisé :

```json
{"jev":{"enabled":true,"cli_timeout_s":180},"find":{"batch_files":1}}
```

```bash
jev-flutter find "QUESTION_DU_JEU" CHEMINS_DU_JEU --max-files 3000 --top 5 --min 0.6
```

Remplacer ensuite `batch_files` par `8`, sans changer la question ou les sources. Les questions, périmètres, révisions et critères sont dans les JSON liés. Cette reproduction appelle TypeSafe et consomme du crédit. Les traces API, transcripts et sources figées sont conservés dans l'archive privée de la campagne `flutter-public-2026-09-29` ; ils ne sont pas tous publiés dans le dépôt.

Une dernière session sur le paquet renommé, dans un chemin contenant espaces et accents, passe les quatre critères AppFlowy. `init`, `doctor`, préparation et lecture de 64 lignes fonctionnent ; source inchangée. Elle est conservée séparément des trois paires comparées : 0,038383 $ Claude et 0,001149 $ Jev.

**Dépense totale, intégration finale comprise : 0,379057 $ TypeSafe pour 8 999 requêtes ; 0,423417 $ Claude comptabilisés de façon conservatrice.** Le plafond TypeSafe de 10 $ n'est pas une somme à consommer. Le précédent budget Claude reste respecté. Tarif Jev : [0,042 $ par million de tokens d'entrée, sortie gratuite](https://docs.typesafe.ai/models).

## Pourquoi ces garde-fous Flutter

Une fonctionnalité Flutter peut traverser vue, logique d'état, repository et service. Trouver son écran ne suffit donc pas à comprendre son parcours : les essais répartis sur plusieurs fichiers visent précisément cette limite. C'est une application du [guide officiel d'architecture Flutter](https://docs.flutter.dev/app-architecture/guide), sans imposer MVVM aux projets utilisant BLoC ou Riverpod.

Le plan syntaxique ne remplace pas une analyse résolue des types. L'API officielle [`parseString`](https://pub.dev/documentation/analyzer/latest/dart_analysis_utilities/parseString.html) distingue elle-même l'analyse syntaxique ; lancer un serveur d'analyse complet à chaque lecture ajouterait un travail évitable. La [documentation Dart sur les performances de l'analyseur](https://dart.dev/tools/analyzer-performance) justifie de limiter le périmètre et les calculs répétés. Le plugin garde donc la résolution précise comme aide facultative, et laisse les lectures complètes accessibles.
