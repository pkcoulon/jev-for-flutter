# Protocole de comparaison dartlens

Ce banc tranche une question : **avec Jev, Claude Code fait-il mieux, ou aussi bien pour moins cher, sur des tâches entières de projets Flutter perso ?** Il suit les points 4 à 6 du « Périmètre conseillé » de la contre-expertise d'Astra (`~/agent-context/global/research/2026-09-28-jev/CHALLENGE-gpt-6-astra.md`).

**Règle d'or : aucune conclusion à partir du faux serveur Jev.** Il valide le branchement (appels, pannes, journaux). Ses réponses sont lexicales et ne disent rien de la qualité des décisions de Jev. `score.py` supprime tout verdict dès qu'un essai l'a utilisé.

## 1. Questions et hypothèses

| Promesse | Question | Hypothèse à réfuter | Ce qui la réfuterait |
|---|---|---|---|
| `lens` (et `find`, `which`) | L'agent trouve-t-il plus vite ce qu'il cherche, sans rater d'information ? | Autant de réussites, moins de coût ou de temps par tâche réussie | Réussites en baisse, ou contournements systématiques (`Read` intégral après `lens`) |
| Garde des conventions | Un avis rapide après édition fait-il respecter les règles implicites ? | Plus de réussites sur les tâches de convention, sans alourdir les autres | Alertes ignorées, fausses alertes, coût ajouté sans gain |
| Mémoire et skill | Le routeur rappelle-t-il les bonnes fiches au bon moment ? | Plus de réussites sur les tâches mémoire, sans évincer une fiche utile | Fiche utile omise, contexte injecté inutilement |

Pour la mémoire, le témoin a la mémoire native de Claude Code (index `MEMORY.md` et fiches lisibles) : on compare Jev à ce que l'agent fait déjà, pas à rien. Le bras `all_nojev` (repli local, Jev coupé) sépare l'effet de Jev de celui de l'échafaudage du plugin.

## 2. Bras

| Bras | Plugin | Variables posées par `run.py` |
|---|---|---|
| `control` (témoin) | non | aucune |
| `lens` (A) | oui | `DARTLENS_GUARD_DISABLE=1`, `DARTLENS_ROUTER_DISABLE=1` |
| `guard` (B) | oui | `DARTLENS_LENS_DISABLE=1`, `DARTLENS_ROUTER_DISABLE=1` |
| `router` (C) | oui | `DARTLENS_LENS_DISABLE=1`, `DARTLENS_GUARD_DISABLE=1` |
| `all` (ensemble) | oui | aucune |
| `all_nojev` (optionnel) | oui | `DARTLENS_JEV_DISABLE=1` |

Tous les essais reçoivent :

- `DARTLENS_BENCH_RUN=<campagne>/<essai>/<session>`, que le client Jev inscrit dans chaque enregistrement ;
- `DARTLENS_STATE_DIR`, un dossier d'état neuf par essai : journaux (`usage.jsonl`, `guard.jsonl`, routeur), disjoncteurs, files de la garde et cache du catalogue y vivent, puis sont recopiés dans les résultats. Un disjoncteur ouvert par un essai ne coupe donc pas Jev dans le suivant, et aucun journal d'une autre campagne ne s'y mêle. Ce qui écrit encore dans `~/.cache/dartlens` (le journal propre de `bin/lens`) est rattaché par étiquette bornée dans le temps, par identifiant de session, ou à défaut par fenêtre (`window_attributed`).

**Contrat attendu des composants :** chaque composant coupé par sa variable ne fait rien, n'injecte rien et n'appelle pas Jev. `run.py` refuse de lancer un bras dont une variable n'apparaît nulle part dans le plugin (`--allow-unisolated` pour passer outre, en le notant). Limite connue : un composant coupé par variable reste décrit (skill, commande) dans le contexte ; son coût fixe se lit dans les classes de tokens.

**Jev réellement joignable :** avant chaque essai d'un bras qui doit appeler Jev, `run.py` évalue `policy.jev_allowed` dans l'environnement exact de l'essai (clé, politique, `jev.enabled`) et arrête la campagne en cas de refus ; au premier essai de ce type, une question constante (aucune donnée du projet) vérifie que Jev répond (`--no-jev-ping` pour les essais de plomberie). Après coup, `score.py` déclare « Jev indisponible » un bras sans aucun appel réussi ou avec plus de 10 % d'erreurs (`--max-jev-errors`), et supprime son verdict. Les indisponibilités sans requête (clé absente, disjoncteur ouvert) sont journalisées par le socle.

Le témoin ne doit pas charger dartlens par une autre voie : `run.py` s'arrête si un `dartlens@…` est activé dans les réglages utilisateur ou ceux du projet. Les fichiers propres au plugin (`.claude/dartlens.json`, `.claude/dartlens/rules.json`) ne sont écrits que dans les bras avec plugin, et masqués de git.

## 3. Conditions communes

- **Même modèle** pour tous les bras (`--model`), même mode de permission, **même liste `--allowedTools`** (`lens` et `dart-outline` y figurent, sans effet pour le témoin qui ne les a pas). Les outils de base restent grep, `Read`, et, si Pierrick les utilise d'ordinaire, le MCP Dart officiel ou un LSP : ils sont passés à tous les bras (`--extra-arg`), jamais reconstruits.
- **Mêmes permissions effectives** : `lens "Q" -- COMMANDE` exécute la commande sans passer par les permissions de Claude Code. Tous les bras reçoivent donc, par `--settings`, un hook `PreToolUse` du banc (`run.py --gate`) qui refuse une commande placée après `lens … --` (y compris dans `sh -c '…'`, pipelines et redirections comprises) si elle ne passe pas la même liste. `--settings` est réservé à ce hook. En mode `bypassPermissions`, aucune liste ni hook : tout est permis partout.
- **Mêmes conditions de départ, sans fuite** : chaque essai reçoit un dépôt autonome dans un dossier temporaire aléatoire (`$TMPDIR/dlb-…/<projet>`), hors du dossier du banc. Aucune référence partagée : en historique `keep`, seul le commit épinglé et ses ancêtres sont récupérés ; en `orphan`, l'arbre est extrait par `git archive` et commité seul. La branche s'appelle `main`, sans nom d'essai. Les remotes de la source sont recopiés pour que la politique du socle continue de s'appliquer. `task.json` n'est écrit dans les résultats qu'après la sortie de claude, et le correctif de mise en situation n'est jamais écrit sur disque. La préparation (`flutter pub get`) est faite avant l'essai et incluse dans le commit de base.
- **Dépôt refusé** : avant toute copie, `run.py` passe la source de chaque projet par `policy.refusal` (chemins et remotes de `~/.config/dartlens/policy.json`) et s'arrête si elle est refusée, en campagne comme en validation ou en `--dry-run`.
- **Ordre des bras alterné** : rotation par bloc (tâche, répétition) ; l'ordre des tâches change à chaque répétition (graine fixée). Le cache de prompt favorise l'essai qui suit un essai du même bras : `--pause 360` au-delà du TTL de 5 min si l'on veut l'écarter, sinon la rotation le répartit.
- **Langue** : `--lang alternate` donne une langue par bloc, la même pour tous les bras du bloc ; `--lang both` double les blocs.
- **Répétitions** : au moins 3 par tâche et par bras pour le pilote.
- **Configuration utilisateur écartée par défaut** : chaque essai reçoit `--setting-sources project,local`. Les hooks de `~/.claude/settings.json` ne s'appliquent donc pas : rtk, par exemple, réécrivait des commandes autorisées en commandes hors liste. `--user-settings` les rétablit pour tous les bras.
- **Vrai binaire `claude`** : par défaut, `run.py` saute les lanceurs de terminal placés en tête du PATH (cmux). Le 2026-09-29, un tel lanceur ajoutait ses propres hooks, et chaque demande de permission restait bloquée environ 115 s avant d'être refusée. `--claude CHEMIN` impose un binaire.
- Chaque essai est **une seule tentative** : un échec, un délai dépassé ou un refus de permission compte, avec son coût. **Exception : les pannes d'infrastructure** (quota d'abonnement, surcharge 529, limite de débit, authentification, CLI sans aucune réponse) sont classées `infra_failed`, archivées dans `infra-N/` et relancées à la reprise ; elles ne comptent ni comme échec ni dans les totaux, et leur coût est affiché à part. Un quota atteint ou une authentification refusée arrête la campagne au lieu de consommer les essais suivants.
- **Reprise à l'identique** : `campaign.json` fixe à la première exécution les conditions (modèle, mode de permission, liste d'outils, arguments passés à claude, délais, backend et URL Jev, empreinte du plugin, version de claude). Une reprise qui en change une est refusée (`--force` pour passer outre) ; chaque essai enregistre ses conditions réelles, et un plugin ou un claude modifié en cours de route arrête la campagne. `score.py` refuse tout verdict sur une campagne hétérogène.

## 4. Tâches

Une tâche est un fichier `tasks/<id>.json` : projet, commit épinglé, type, `prompt_fr`, `prompt_en`, `setup` (patch, historique `keep` ou `orphan`, mémoire semée, `expect_before`, `reference` et `reference_answer`), critères exécutables, grille de revue, fichiers attendus. `tasks/_projects.json` donne les chemins, la préparation et les fichiers du plugin par projet ; son `rules.json` suit le schéma v1 de la garde (question en anglais dont le OUI signale la violation, `true`/`false`, `message`, `applies_to`, exemples).

- `run.py --check-tasks` valide les tâches et, en mode strict, le `rules.json` de chaque projet : un fichier que la garde rejetterait rendrait le bras B muet.
- `run.py --validate-setup` met chaque tâche en situation sans claude, vérifie `expect_before`, puis fait passer une édition type par le vrai hook de garde de chaque projet et exige un verdict dans `guard.jsonl` (Jev requis : `--jev-url` du faux serveur pour la plomberie).
- `run.py --validate-reference` applique `setup` puis la solution de référence (`setup.reference`, diff git) et exige que tous les critères passent, exécutables comme notés par `score.py` (`setup.reference_answer` pour les critères sur la réponse). Une tâche sans référence est signalée comme non vérifiée.
- Les fichiers cachés d'un critère (tests posés après l'essai) n'existent que le temps de ce critère : `analyze` et `format` ne jugent que l'arbre laissé par l'agent.

| Tâche | Type | Promesse visée | Setup |
|---|---|---|---|
| `pioudex-loc-xp-niveau` | localisation (homonymes « palier ») | lens | prêt |
| `pioudex-loc-silence` | localisation par description | lens | prêt |
| `pioudex-diag-gain-xp` | diagnostic d'un test rouge | lens | prêt, à valider |
| `pioudex-i18n-compteur-prises` | libellé paramétré | lens, garde | prêt |
| `pioudex-convention-olive` | convention implicite (tokens) | garde | prêt |
| `pioudex-memoire-vibrations` | plusieurs fiches mémoire | routeur | prêt (fiches synthétiques) |
| `gambade-loc-chaleur` | localisation avec calcul | lens | prêt |
| `gambade-diag-serie-dst` | diagnostic sur symptôme | lens | prêt, à valider |
| `gambade-i18n-entete-debriefs` | libellé paramétré bilingue | lens, garde | prêt, à valider |
| `gambade-multi-jour-utc` | correction répartie (11 fichiers) | lens | prêt |
| `gambade-convention-jours-sans-balade` | convention implicite (UTC, tests) | garde | prêt, référence vérifiée |
| `panorameuh-memoire-note-version` | fiches mémoire réelles | routeur | **à écrire par Pierrick** |

« À valider » : le patch s'applique au commit épinglé (vérifié), mais l'échec qu'il doit provoquer n'a pas été exécuté ; `run.py --validate-setup` le confirme sans lancer claude. Seule `gambade-convention-jours-sans-balade` a une solution de référence ; les autres restent à doter avant le pilote. La tâche panorameuh demande un commit postérieur à une livraison, des fiches réelles et des règles de garde choisies par Pierrick, et ses critères ; elle est exclue tant que son statut est `todo`.

Couverture des exigences d'Astra : code généré utile (fichiers l10n générés de Pioudex), homonymes, libellés paramétrés, conventions implicites, demandes à plusieurs fiches, deux projets aux conventions différentes (ARB contre classes Dart), prompts FR et EN.

## 5. Mesure

**Critère principal : tâche correcte et absence de régression.**
1. Critères exécutables, tous requis : commandes (`flutter test`, `analyze`, `format`, tests cachés posés après l'essai), `grep` sur le résultat, diff (fichiers touchés ou intacts, lignes ajoutées), réponse finale pour les localisations.
2. Revue aveugle au bras : `score.py --export-review DOSSIER --key CLÉ` produit un paquet par essai sous un code stable (HMAC d'un sel gardé dans la clé) : demande, grille, réponse, commandes git, signalements, diff. Dans **tous** les paquets, les phrases et lignes qui mentionnent l'outillage (dartlens, lens, Jev, garde, routeur, identifiants de règles, probabilités) sont retirées et une mention constante le dit ; la part de paquets retouchés par bras est affichée à l'opérateur, avec une alerte si elle diffère trop. La clé doit être hors du dossier du relecteur. Un nouvel export dans le même dossier n'ajoute que les nouveaux essais et ne touche ni aux revues ni aux paquets existants. Le relecteur remplit `accepted` **et** `regression` dans `reviews.json`.

Un essai réussi passe les critères exécutables, est accepté et sans régression. Une revue où manque l'un des deux champs est incomplète. Tant qu'une revue manque, `score.py` affiche les résultats exécutables comme provisoires et ne rend aucun verdict.

**Critères secondaires :**
- temps jusqu'au résultat accepté (durée de l'essai réussi) ;
- valorisation API par tâche réussie : usages dédoublonnés par message et résultats d'outils par identifiant (`scan` et `valuation` de `bin/cc-usage`), cinq classes de tokens, tarif standard par modèle et version de grille (`PRICING_VERSION`), pondération uniforme de l'étude en regard ; **coût total du bras sur la tâche, échecs compris, divisé par ses réussites**. C'est une valorisation, pas une facture ni un quota d'abonnement ;
- appels API, résultats d'outils, appels `lens`, commandes git ;
- **signalements** : commandes qui visent l'état d'origine (`--all`, `refs/`, reflog…), le dossier du banc, d'autres essais ou les transcripts de `~/.claude/projects` ; listés par `score.py` et joints aux paquets de revue ;
- appels Jev, erreurs, indisponibilités et latence (p50, p95), contexte injecté par les hooks (nombre et caractères, hook du banc exclu) ;
- refus de permission. En `claude -p`, aucune intervention humaine n'est possible : une tâche qui en exigerait une échoue.

**Présentation :** totaux et distributions par tâche, jamais une moyenne de ratios. Le rapport des coûts est donné deux fois : rapport des totaux, et distribution des rapports par tâche (médiane, quartiles, extrêmes). Aucun verdict avec le faux serveur, une campagne hétérogène, une revue incomplète, ou pour un bras où Jev était indisponible.

## 6. Montée en charge

1. **Branchement** : 2 ou 3 tâches, 1 répétition, faux serveur (`--jev-url http://127.0.0.1:<port>`, `TYPESAFE_API_KEY=test`). On vérifie que chaque bras charge ce qu'il doit, que les journaux s'attribuent par `run`, que les critères tournent. Aucun chiffre n'est interprété.
2. **Pilote** : 20 à 30 tâches (compléter ce jeu de départ, chacune avec sa référence), 3 répétitions, clé officielle, modèle Jev épinglé. Le pilote estime la variance par tâche et écarte les composants sans effet. Il ne prouve pas une qualité identique.
3. **Décision** : fixer ensuite la marge de non-infériorité (`--margin`, en points de taux de réussite ; 10 par défaut, à revoir) et dimensionner la suite d'après la variance du pilote. L'incertitude se calcule en regroupant les répétitions par tâche (bootstrap sur les tâches) : des répétitions d'une même tâche ne sont pas des tâches indépendantes.

## 7. Déroulé

```bash
cd ~/projects/dartlens/bench
./run.py --check-tasks                                   # valide les JSON et le rules.json de chaque projet
./run.py --validate-setup --jev-url http://127.0.0.1:<port>   # mise en situation, expect_before, garde de bout en bout, sans claude
./run.py --validate-reference                            # solutions de référence : tous les critères doivent passer
./run.py --dry-run --model <modèle> --reps 3             # plan et commandes, rien n'est lancé
./run.py --model <modèle> --reps 3 --campaign pilote-1   # campagne ; relancer la même commande reprend là où elle s'est arrêtée
./score.py ~/.cache/dartlens-bench/results/pilote-1 --export-review /tmp/revue-pilote-1 --key ~/.cache/dartlens-bench/keys/pilote-1.json
./score.py ~/.cache/dartlens-bench/results/pilote-1 --reviews /tmp/revue-pilote-1/reviews.json --key ~/.cache/dartlens-bench/keys/pilote-1.json --json pilote-1.json
```

Artefacts par essai (`~/.cache/dartlens-bench/results/<campagne>/<essai>/`) : `meta.json` (bras, variables, étiquette, conditions, commit de base, durée, code, vérification Jev), `transcript.jsonl` (stream-json), `session/` (transcript persistant et sous-agents), `stderr.log`, `diff.patch`, `changes.json`, `checks.json`, `dartlens_logs.jsonl`, `state/` (disjoncteurs de l'essai), `task.json`, et `infra-N/` pour chaque tentative en panne d'infrastructure. `campaign.json` garde les conditions fixées à la première exécution et chaque reprise ; `_preflight/` le journal de la vérification de Jev.

## 8. Biais et limites connus

- Tarifs : grille de `bin/cc-usage` (version affichée), à revérifier avant la campagne ; `score.py --prices` la remplace. Le `total_cost_usd` déclaré par Claude Code est gardé dans le détail JSON, pas dans les totaux.
- Écritures hors du banc : `run.py` crée miroirs et résultats sous `~/.cache/dartlens-bench`, les dépôts jetables dans le dossier temporaire du système (supprimés après l'essai sauf `--keep`), et Claude Code enregistre chaque session (avec la mémoire semée) dans `~/.claude/projects/<chemin du dépôt>`. Ces dossiers de session ne sont pas supprimés ; ils ne se mélangent pas aux projets réels, dont le chemin diffère.
- Fuites encore possibles, détectées mais pas empêchées : l'agent peut lire `~/.cache/dartlens-bench` (résultats et diffs des essais précédents) ou les transcripts d'autres essais sous `~/.claude/projects` avec `cat`, `ls`, `find` ou `Read`, qui acceptent des chemins absolus. Ces accès figurent dans les signalements et dans les paquets de revue.
- Le hook du banc imite la correspondance par préfixe de Claude Code et ses variables d'environnement tolérées ; il refuse les substitutions de commande et les redirections vers un fichier. Les commandes que Claude Code approuve seul comme lecture (`echo`, `sort`…) restent refusées après `lens --` : désavantage mineur pour les bras avec plugin.
- Les injections de hooks sont repérées dans le transcript persistant selon son format actuel ; un changement de format de Claude Code peut les faire sortir du compte.
- Masquage de la revue : il retire des phrases, pas des mots ; un relecteur attentif peut encore deviner un bras à la manière de travailler. La part de paquets retouchés par bras est affichée pour en juger.
- Les fiches de la tâche Pioudex sont synthétiques ; la tâche Panorameuh est prévue pour des fiches réelles.
- Les critères `grep` et `diff` approchent la convention ; la revue tranche les cas limites.
