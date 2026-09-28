---
name: dartlens
description: Lire seulement les passages utiles d'un gros fichier (plus de 150 lignes ou 15 000 caractères) ou d'une longue sortie de commande (tests, build, logs) pour une question précise, trouver du code dont on ignore le nom (« où est géré X ? ») ou balayer une propriété oui/non fichier par fichier. Outils lens, lens find, lens which (juge Jev hors conversation, omissions visibles, lecture intégrale toujours possible) et dart-outline (plan AST d'un fichier Dart avec plages de lignes).
---

# dartlens : lens, find, which, dart-outline

## Quand l'utiliser

- `dart-outline FICHIER.dart...` : plan (déclarations, membres, tests) avec plages `début-fin`. Avant de lire un gros fichier Dart, pour choisir la plage. `--json` pour un script.
- `lens "QUESTION" FICHIER...` : question précise sur un gros fichier ; ne montre que les blocs retenus, numérotés comme `cat -n` et `sed -n`.
- `lens "QUESTION" -- COMMANDE ARGS...` : dépouiller une longue sortie. Pas de shell : pour un pipeline, `lens "Q" -- sh -c 'cmd | autre'`. `--timeout S` si besoin. Le code de sortie de la commande est conservé (128+n si un signal l'a tuée).
- `lens find "DESCRIPTION" [DOSSIER...]` : localiser du code par ce qu'il fait, sans connaître son nom. `--tests` inclut les tests, `--top N`.
- `lens which [-q] "QUESTION OUI/NON" CHEMIN|DOSSIER...` : sonder une propriété fichier par fichier (`-q` : seulement les oui). Au-delà de 200 fichiers (`lens.which_max_files`), rien n'est envoyé : restreins le dossier ou passe `--max N` après avoir lu le coût estimé.

## Quand NE PAS l'utiliser

- Fichier que tu vas éditer : lis la plage exacte (Read avec offset/limit, via `dart-outline`), pas un extrait filtré.
- Symbole ou texte connu : `grep`/`rg`, plus sûr et exhaustif.
- Petit fichier (150 lignes et 15 000 caractères au plus) ou courte sortie (80 lignes et 15 000 caractères au plus) : lis directement ; lens affiche tout de toute façon.

## Bien poser la question

- En anglais, précise, une seule intention : `lens "Where is the retry delay computed after a 429?" lib/data/api_client.dart`.
- `find` : décris le comportement (`"schedules the evening reminder notification"`), pas un nom supposé.
- `which` : propriété existentielle (« Does this file call setState? »). Un fichier long est jugé par sections et le plus fort l'emporte : ne l'utilise pas pour « tous les widgets sont-ils const ? ».

## Lire la sortie

- En-tête `== chemin (N lignes) · k/M blocs · x/N lignes · Jev <version>` : ce qui est montré et par qui.
- `@@ a-b label p=0.93` : bloc retenu ; `(contexte)` : en-tête de classe ou de groupe ajouté pour situer ; `p=? (non jugé)` : Jev n'a pas répondu pour ce bloc, affiché par défaut.
- `@@ N:a-b` : morceau d'une ligne géante (ligne N, caractères a à b), annoncé par `-- lignes géantes découpées`. Lecture : `sed -n 'Np' fichier | cut -c a-b`.
- `-- omis` : plages non montrées avec leurs labels, `N (car. a-b)` pour une ligne géante montrée en partie. Lis-les avant de conclure qu'une chose n'existe pas : `sed -n 'A,Bp' fichier`, ou `lens --all ...` pour tout afficher.
- Sélection de 60 % des lignes ou plus (fichier de 80 000 caractères au plus) : fichier intégral. Aucun bloc retenu : carte des blocs avec leur p. L'affichage est plafonné à 80 000 caractères : `-- N blocs retenus non affichés` les renvoie dans « omis ».
- `!! fichier modifié` : le fichier a changé pendant l'appel ; relis-le.
- Commande : 5 premières lignes, 30 dernières et lignes d'erreur (±2, 60 au plus, les répétitions jugées comme le reste) toujours gardées ; chemin de la sortie brute complète en fin de sortie, gardée 24 h. `-- sortie tronquée` : un processus détaché (démon adb, gradle…) garde la sortie ouverte ; lens rend la main 2 s après la fin de la commande ou le `--timeout`.
- `find` : `0.94  chemin:ligne  Symbole` vérifié sur le contenu ; `chemin:~ligne … (emplacement estimé)` : fichier confirmé mais bloc non désigné par Jev ; `~0.71` non vérifié (plan seul). « aucune correspondance sûre » n'est PAS une preuve d'absence : passe à grep ou reformule.
- `find` et `which` : `-- dossier de plateforme ignoré` (android, ios, web… au niveau d'un paquet) : passe-le en argument s'il le faut.
- `which` : « non » veut dire « non vu dans les passages envoyés », pas « absent ». `?  illisible|vide|erreur Jev` et `-- k fichiers non jugés` : ces fichiers n'ont pas été sondés.

## Doute, mode local, erreurs

- `(mode local : raison)` : pas de Jev (projet non activé, clé absente, erreur, délai global `jev.cli_timeout_s` dépassé, `--local`, commande qui lit hors du projet). Le classement est lexical (BM25), pas un jugement : reviens aux outils ordinaires (grep, Read) dès que le résultat ne suffit pas.
- `lens which` exige Jev : sans lui, code 3 et message ; utilise grep.
- Un bloc omis n'est pas « non pertinent » en général, seulement pour CETTE question. Pour une autre question, relance lens ou lis la plage.

## Données

Seuls les fichiers du projet courant autorisés partent vers Jev (projet activé par `jev.enabled` dans `.claude/dartlens.json`, politique `~/.config/dartlens/policy.json`), secrets de formats connus rédigés (clés `sk-`, `ghp_`, `AKIA`, `AIza`, `glpat-`, `password = "…"` entre guillemets). Un JWT ou un mot de passe sans guillemets n'est PAS rédigé. Fichiers hors projet, secrets (`.env`, clés) ou exclus : traités en local, rien n'est envoyé. Code généré exclu de `find` et `which`.

La sortie d'une commande peut contenir des données hors projet. lens reste en local si le dossier courant ou un chemin cité par la commande (argv, script `sh -c`, redirection `<`, glob) est hors du projet ou refusé. En revanche, il ne voit pas ce qu'un programme lit de lui-même (`python3 -c`, script, fichier de config, réseau) : `--local` dans le doute.
