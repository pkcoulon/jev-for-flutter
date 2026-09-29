# Ce que fait Jev, et ce que nous reprenons

Audit du 29 septembre 2026 de **tous les fichiers source Go, tests, scripts de mesure et manifestes** de [BorisLeMeec/jev, commit e81c1d0](https://github.com/BorisLeMeec/jev/tree/e81c1d006b8b23a616486610f311039088521d0c). Lecture statique ; aucun build ni nouvel essai de son plugin. Les images de présentation ne servent pas de preuve.

## Pourquoi ses résultats sont meilleurs

Son moteur remplace une partie du travail de lecture et de recherche. Notre essai de contexte en arrière-plan ajoutait parfois une deuxième exploration : sur le dernier correctif, Claude utilisait 16 appels contre 13 sans plugin. Il faut éviter ces appels ou leur contenu, pas simplement faire travailler Jev davantage.

| Mesure annoncée par Boris | Ce qui est comparé | Portée |
|---|---|---|
| −30 % de tokens d'entrée | 7 paires de recherches ; consigne « Jev d'abord » contre recherche sans Jev | Localisation, sans modification ni tests ; une exécution par variante |
| −38 % de tokens d'entrée | 3 paires d'audits de 12–18 fichiers | Une omission avec Jev ; qualité non identique |
| −41 % de tokens d'entrée | 3 paires de lectures de fichiers Hugo entiers contre plages ciblées | Cas favorable à une réduction de lecture, pas un développement complet |
| 118× « leverage » | Volume examiné hors conversation / volume renvoyé | Pas une économie mesurée sur Claude |

Sources : [recherche](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/tokenecon/TOKENS.md), [audit](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/tokenecon/TOKENS_ASK.md), [lecture](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/hook/RESULTS_HOOK.md), [calcul du ratio](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/usage/report.go).

Ces résultats constituent un signal intéressant. Ils ne démontrent pas une économie universelle de 30–41 %, ni une baisse équivalente en dollars. Le script additionne entrées nouvelles, écritures et lectures de cache sans pondérer leurs tarifs ; la sortie Claude et la facture Jev ne font pas partie de ce pourcentage. Les tailles de résultats d'outils sont estimées en caractères divisés par quatre. [Code du compteur](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/agentstats.py).

Le temps est plus nuancé : pour `find`, le rapport médian avec/sans est **1,03**, soit +3 %. La moyenne favorable vient surtout d'un cas d'absence de fonctionnalité. Le README dit lui-même que le gain porte sur les tokens, pas généralement sur le temps. [Mesure du temps](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/TIMING.md).

## Architecture comparée

| Composant | Boris | Jev for Flutter 0.3 |
|---|---|---|
| Recherche | Chaque fichier est jugé séparément ; 8 requêtes simultanées ; vérification des leaders sur le contenu ; localisation finale | Même principe disponible dans `jev-flutter find`. Plus de filtre lexical avant Jev : au-delà du plafond, demander un dossier ou `--max-files` |
| Grande lecture | Un choix de plage sur le fichier entier ; modification de `Read.offset/limit` | Nouvelle lecture native ciblée, sans refus ni appel volontaire à lens ; question de périmètre en plus, source masquée et politique par projet |
| Incertitude | Lecture inchangée si erreur, faible confiance ou fichier >80 Ko | Lecture inchangée si erreur, demande large, faible confiance, fichier >64 Ko ou modifié pendant le jugement |
| Plusieurs fichiers | Requêtes parallèles, une par fichier | Recherche parallèle conservée ; le contexte automatique est désormais une option |
| Conventions | Classification des modifications ; activation volontaire et règles explicites | Garde existante conservée, sans alerte quand aucune règle ne s'applique |
| Mémoire | Aucun composant équivalent dans ce dépôt | Routeur existant conservé ; ne constitue pas une preuve d'économie |

Sources : [find.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/find.go), [hook.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/hook.go), [locate.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/locate.go), [lint.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/lint.go). L'adaptation conserve l'attribution MIT dans [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).

## Limites repérées dans le code public

- Les transcripts, les associations tâche/session et les jeux de questions privés ne sont pas publiés. Les sommes des tableaux sont recalculables, leur qualité finale ne peut pas être revue de manière indépendante depuis ce dépôt seul. Des cas de localisation sur Hugo/Prometheus sont publics ; leurs dépôts ne sont pas épinglés par le script de lecture.
- Le score des réponses `find` vérifie le rappel des chemins attendus, mais ne pénalise pas les chemins supplémentaires sur les cas positifs. Ce n'est pas une revue de toute l'explication. [report.py](https://github.com/BorisLeMeec/jev/blob/e81c1d0/bench/tokenecon/report.py).
- Le compteur ne déduplique pas les messages portant le même identifiant de réponse API. C'est un risque si le format de transcript répète l'usage sur plusieurs fragments ; sans les traces d'origine, on ne peut pas affirmer que ses chiffres sont effectivement doublés.
- `verifyTop` coupe à 90 000 octets mais marque quand même le fichier « verified ». Le criblage peut aussi perdre des fichiers sur erreur et afficher le nombre initial comme « scanned ». Notre lecture automatique ne découpe pas un fichier trop grand en jugements indépendants.
- Le `scan` de coût conserve un calcul par lots de 25 fichiers alors que `find` envoie une requête par fichier. Il sous-estime le nombre d'appels et omet les passes suivantes. [scan.go](https://github.com/BorisLeMeec/jev/blob/e81c1d0/internal/run/scan.go).
- Le hook place sa note au niveau supérieur de la réponse JSON. Le schéma Claude Code actuel attend `hookSpecificOutput.additionalContext` pour `PreToolUse` : notre adaptation utilise ce champ et en vérifie la livraison réelle. [Schéma officiel](https://code.claude.com/docs/en/hooks#pretooluse-decision-control).
- Le hook installé vise `bin/jev`, absent des fichiers suivis ; aucun hook d'installation ne le construit. Une installation fraîche depuis les seules commandes marketplace suppose donc une étape de build/copie non couverte par ces commandes. Notre distribution utilise Python, sans binaire à compiler.

Ces limites cadrent la comparaison ; elles n'annulent pas le mécanisme intéressant de délégation des lectures.

## Pourquoi la facture TypeSafe reste petite

La capture de Pierrick affiche **19 089 427 tokens, 2 538 requêtes et 0,7699 $** pour sept jours, tous trafics confondus. Elle établit une activité Jev importante, pas un manque d'utilisation. Elle ne mesure ni les appels Claude évités, ni les résultats de notre seul dernier lot.

Jev 1.13 facture **0,042 $ par million de tokens d'entrée**, sortie gratuite. Lire un million de tokens côté Jev coûte donc environ quatre centimes. Le bon indicateur produit reste le coût **Claude + Jev d'une réponse correcte**, avec les catégories de cache et le temps observé. [Tarif TypeSafe](https://docs.typesafe.ai/models).
