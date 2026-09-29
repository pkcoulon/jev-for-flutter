# dartlens

**dartlens aide Claude Code à trouver et lire le bon code dans un projet Dart ou Flutter, sans tout charger dans la conversation.**

Il s'appuie sur Jev, un petit modèle de [TypeSafe](https://typesafe.ai) qui examine le code à côté de la conversation. Claude reçoit seulement ce qui répond à sa question, sait ce qui a été laissé de côté, et peut toujours tout lire.

Le but : faire le même travail avec moins de tokens, sans que tu aies à le demander à Claude.

> **État actuel : prototype.** Trouver le bon code et choisir les bons passages marche bien sur nos premiers essais. Claude s'en sert désormais de lui-même pour les gros fichiers. Reste à montrer qu'il termine le même travail avec moins de tokens.

## Ce que ça change pour toi

Tu demandes à Claude : « Pourquoi la carte ne zoome pas sur le département choisi ? »

**Sans dartlens**, Claude cherche avec grep, puis ouvre en entier les fichiers qui semblent concernés, parfois plus de 1 000 lignes chacun. Tout cela reste dans la conversation et sera relu à chaque échange suivant.

**Avec dartlens** :
1. Claude veut ouvrir `carte_screen.dart` (1 501 lignes) en entier. dartlens l'arrête une fois et lui propose de poser plutôt sa question.
2. Claude demande : `lens "How does the map zoom onto the selected department?" carte_screen.dart`. Il reçoit les 3 passages concernés, environ 100 lignes, et la liste de ce qui a été laissé de côté.
3. Il corrige, en relisant au besoin la zone exacte. S'il avait eu besoin de tout le fichier, il lui suffisait de redemander.

Tu n'as rien tapé de plus. L'exemple est illustratif : la sortie de `lens` est réelle, pas la session. Dans nos essais sur de vraies tâches, l'arrêt suivi d'une question à `lens` s'est produit à chaque fois. Chercher du code par description (`lens find`, ci-dessous) marche quand Claude l'appelle, mais il ne l'a pas encore fait de lui-même.

## Trois façons de trouver le bon code

### Lire seulement les passages utiles : `lens`

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/lens-dark.svg">
  <img alt="lens montre 3 morceaux sur 40 d'un écran de 1 501 lignes ; les passages attendus sont présents dans 92 % des cas avec Jev, contre 74 % avec une recherche par mots-clés, pour 10 % du fichier en général." src="docs/img/lens-light.svg">
</picture>

```bash
lens "How does the map zoom onto the selected department?" lib/features/carte/carte_screen.dart
lens "Why does this test fail?" -- flutter test test/foo_test.dart
```

Ce que `lens` laisse de côté est toujours listé, avec la commande pour le lire. Pour un fichier court (150 lignes ou moins) ou une sortie courte (80 lignes ou moins), tout est affiché.

### Trouver le code d'un comportement : `lens find`

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/find-dark.svg">
  <img alt="lens find retrouve la carte Selles et digestion d'un débrief de balade à partir d'une description qui n'emploie aucun mot du code ; le bon fichier arrive en premier 20 fois sur 20." src="docs/img/find-light.svg">
</picture>

```bash
lens find "where the user records how their dog's digestion went" lib
```

Ça marche même quand la description n'emploie aucun mot du code. Quand rien n'est sûr, `lens find` le dit.

### Repérer les fichiers qui ont une propriété : `lens which`

```bash
lens which -q "Does this widget hard-code a user-facing string?" lib/ui
```

Jev pose la même question oui/non à chaque fichier et ne garde que ceux qui répondent oui. Pas encore mesuré à part.

## Pourquoi c'est utile

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/why-dark.svg">
  <img alt="Au fil d'une vraie session, ce que Claude relit à chaque échange grossit jusqu'à 653 000 tokens ; une seule recherche y ajoute 63 000 tokens, relus ensuite à chaque échange." src="docs/img/why-light.svg">
</picture>

À chaque échange, Claude Code renvoie toute la conversation au modèle. Un fichier lu en entier y reste, et il est relu à chaque échange suivant : 17 fois en général, d'après nos sessions.

Sur 49 de nos vraies sessions Flutter, ce que les outils avaient ajouté représentait environ un tiers de ce que Claude relisait. Ce sont des estimations du besoin, pas des économies mesurées.

## En plus, en arrière-plan

Deux aides tournent sans que tu t'en occupes. Elles utilisent aussi Jev.

### Les conventions du projet

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/guard-dark.svg">
  <img alt="Après une modification, la garde signale en arrière-plan une règle probablement enfreinte ; 26 écarts repérés sur 30, aucune fausse alerte sur 30 exemples conformes." src="docs/img/guard-light.svg">
</picture>

`/dartlens:rules` lit les docs du projet et en tire des questions oui/non, une par convention qu'aucun lint ne sait vérifier. Après chaque modification, Jev les vérifie en arrière-plan. Claude n'est prévenu que si une règle est probablement enfreinte. Rien n'est bloqué.

### La mémoire au bon moment

À chaque demande, Jev choisit parmi tes fiches mémoire et tes skills ce qui la concerne, et Claude reçoit un lien vers la fiche. Une clé de ticket (`ABC-123`) mène directement à sa fiche, même sans Jev.

C'est l'aide la moins aboutie. Sur 40 demandes de test, il a proposé 20 fiches, dont 15 utiles. Mais il en a manqué beaucoup : il en fallait 58. Il ajoute environ 0,4 seconde à chaque demande.

## Sur des tâches complètes

Nous avons fait faire 4 vraies tâches à Claude (Sonnet 5) sur un projet Flutter perso, de trois façons : sans dartlens, avec une simple suggestion, et avec l'arrêt de la première lecture complète (le réglage actuel). Un seul essai à chaque fois : ce sont des premiers signaux.

| | Sans dartlens | Suggestion | Arrêt (défaut) |
|---|---|---|---|
| Code Dart reçu par Claude | 477 000 caractères | 344 000 | 157 000 |
| Gros fichiers reçus en entier | 14 | 10 | 1 |
| Tâches réussies | 1 sur 4 | 2 sur 4 | 2 sur 4 |
| Coût, au tarif de l'API | 6,23 $ | 6,16 $ | 5,12 $ |

**Ce qui marche** : avec l'arrêt, Claude pose ses questions à `lens` au lieu d'ouvrir les gros fichiers en entier. Il a reçu trois fois moins de code. Une seule fois, `lens` lui a donné un fichier entier (507 lignes) : sa question portait sur la structure de tout l'écran. Une simple suggestion, elle, ne change rien.

**Ce qui n'est pas encore démontré** :
- **Moins de tokens pour le même travail.** Les deux réglages de dartlens réussissent les mêmes 2 tâches, pour presque le même coût (1,86 $ et 1,83 $). La baisse du total vient surtout des tâches ratées.
- **La qualité.** Deux tâches échouent dans les trois cas :
  - Pour la première, Claude a changé une couleur sans vérifier ce qu'elle touchait autour : la lisibilité du texte, le motif en filigrane. C'est un manque de Claude, pas de dartlens.
  - Pour la seconde, plus longue, les trois versions cassent 2 tests qui passaient avant.
- **Les durées.** Pendant ces essais, un réglage de notre machine bloquait près de 2 minutes chaque demande de permission de Claude. Le banc en est isolé depuis ; ces durées ne valent rien.

Prochaine étape : refaire quelques tâches que Claude sait réussir, avec le banc isolé, pour voir s'il termine le même travail avec moins de tokens. Le détail : [docs/MEASURES.md](docs/MEASURES.md).

## Installer

```bash
claude plugin marketplace add pkcoulon/dartlens
claude plugin install dartlens@dartlens

# clé TypeSafe (console.typesafe.ai), jamais dans un dépôt
mkdir -p ~/.config/dartlens && pbpaste > ~/.config/dartlens/typesafe.key && chmod 600 ~/.config/dartlens/typesafe.key
```

Puis, dans chaque projet où tu veux Jev :

```bash
mkdir -p .claude && echo '{"jev": {"enabled": true}}' > .claude/dartlens.json
```

Ensuite, dans Claude Code :
- `/dartlens:rules` écrit les règles des conventions ;
- `! dartlens status` montre si la clé est là, si Jev est activé, et ce qu'il a consommé.

Sans clé ou sans activation, `lens` choisit les passages par mots-clés, sur ta machine, et le dit. Rien n'arrête les lectures, et les conventions et la mémoire se taisent.

Pour que dartlens laisse passer les lectures complètes et se contente d'une suggestion : `"lens": {"nudge": "hint"}` dans `.claude/dartlens.json`. Pour ne rien suggérer du tout : `"nudge": "off"`.

## Tes données

- **Rien ne part** chez TypeSafe tant que Jev n'est pas activé dans le projet. Une fois activé, Jev reçoit ce dont il a besoin pour chaque demande : des passages de code, les règles des conventions, les descriptions de tes fiches mémoire.
- **Certains projets sont interdits d'office**, même activés par erreur : ceux que tu listes dans `~/.config/dartlens/policy.json` (`deny_paths`, `deny_remotes`). Typiquement, un dépôt client.
- **Certains formats connus de secrets sont masqués** avant l'envoi. Les fichiers sensibles (`.env`, clés, `google-services.json`…) ne partent jamais.
- **Le modèle est figé** sur `jev-1.13.0`, pour que son comportement ne change pas sans prévenir. TypeSafe héberge aux États-Unis.
- **Coût** : TypeSafe annonce 0,042 $ le million de tokens pour `jev-1.12`. Ce tarif n'est pas confirmé pour `jev-1.13.0`.

## Mesurer toi-même

- `cc-usage` : ce que Claude Code a consommé sur un projet, sans double comptage, valorisé au tarif de chaque modèle. C'est une estimation, pas une facture.
- `docs/need_data.py` et `docs/lens_opportunity.py` : les courbes du besoin, sur tes propres sessions. Seuls des totaux en sortent.
- `bench/` : le banc qui compare Claude avec et sans dartlens sur des copies jetables de projets (`bench/PROTOCOL.md`).

Le détail de nos mesures : [docs/MEASURES.md](docs/MEASURES.md).

## Limites

- **Peu de projets.** Les mesures portent sur 3 projets Flutter perso d'un seul auteur. Les passages attendus et les descriptions de test ont été écrits en lisant le code. Sur des descriptions vagues, `lens find` ne trouve que 3 fois sur 6.
- **Conventions : un plafond.** Leurs règles et leurs exemples ont été écrits par le même agent. Le nombre de fausses alertes en usage réel reste à mesurer.
- **Langue.** Jev est pensé d'abord pour l'anglais. Sur nos mesures, `lens` fait aussi bien en français.
- **Claude Code seulement.** dartlens est un plugin Claude Code. Il ne confie jamais une décision de permission à Jev.
