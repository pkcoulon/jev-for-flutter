# dartlens

**Claude lit ce qui répond à sa question. Jev tranche le reste, hors de la conversation.**

Plugin Claude Code pour Flutter/Dart, propulsé par [Jev](https://typesafe.ai) (TypeSafe). Jev est un petit modèle qui ne rédige rien : il répond par des probabilités, en 0,3 s environ, pour 0,042 $ le million de tokens. dartlens s'en sert comme d'un juge rapide. Il décide ce que Claude doit lire, vérifie tes conventions après chaque édition et rappelle la bonne mémoire au bon moment.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/why-dark.svg">
  <img alt="Le contexte envoyé à chaque appel grossit au fil d'une session réelle ; une seule recherche y ajoute 63 k tokens, relus à chaque appel suivant." src="docs/img/why-light.svg">
</picture>

## Pourquoi

À chaque appel, Claude Code renvoie tout le contexte au modèle. Ce qu'une commande y verse, un fichier lu en entier ou un grep de 300 lignes, y reste et se relit à chaque appel suivant : **17 fois en médiane**.

Mesures sur 49 sessions réelles (4 projets Flutter) :
- les sorties d'outils occupent **32 %** du contexte relu ;
- les appels au-delà de 400 k tokens font **47 %** du coût.

La plupart de ces sorties servent à répondre à une question précise. Il suffit donc de montrer la réponse.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/lens-target-dark.svg">
  <img alt="Part du contexte relu que lens peut viser : 13,9 % sur le projet le plus utilisé, 10,3 % sur les projets perso." src="docs/img/lens-target-light.svg">
</picture>

## Ce que ça fait

### 1. `lens` : lire ce qui répond, pas tout le fichier

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/lens-dark.svg">
  <img alt="lens montre 3 blocs sur 40 d'un écran de 1 501 lignes ; tout le nécessaire est montré dans 92 % des cas avec Jev contre 74 % en BM25, pour 10 % du fichier contre 27 %." src="docs/img/lens-light.svg">
</picture>

```bash
lens "How does the map zoom onto the selected department?" lib/features/carte/carte_screen.dart
lens "Why does this test fail?" -- flutter test test/foo_test.dart
lens which -q "Does this widget hard-code a user-facing string?" lib/ui
```

C'est Claude qui pose la question. Ce que `lens` omet est toujours listé, avec la commande pour le lire. Pour un fichier de 150 lignes ou moins, ou une sortie de 80 lignes ou moins, tout est affiché.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/find-dark.svg">
  <img alt="lens find retrouve la carte Selles et digestion d'un débrief de balade à partir d'une description qui n'emploie aucun mot du code ; bon fichier en tête 20 fois sur 20 contre 35 % en BM25 et 18 % avec grep." src="docs/img/find-light.svg">
</picture>

```bash
lens find "where the user records how their dog's digestion went" lib
```

Quand rien n'est sûr, `lens find` le dit et liste les candidats faibles. Il ne présente jamais une absence de résultat comme une preuve.

### 2. Garde des conventions

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/guard-dark.svg">
  <img alt="Après une édition, la garde signale en arrière-plan une règle probablement enfreinte ; précision 100 % et rappel 87 % au seuil par défaut, 0 ms ajoutée à l'édition." src="docs/img/guard-light.svg">
</picture>

Dans Claude Code, `/dartlens:rules` lit les docs du projet et écrit `.claude/dartlens/rules.json` : des questions oui/non, une par convention qu'aucun lint ne sait vérifier. Après chaque édition, Jev les juge toutes en une requête, en arrière-plan. Claude n'est réveillé que si une violation est probable.

### 3. Mémoire et skill au bon moment

À chaque prompt, Jev choisit parmi tes fiches mémoire et tes skills ce qui concerne la demande, et Claude reçoit un pointeur. Une clé de ticket (`ABC-123`) mène directement à sa fiche, même sans Jev.

C'est la promesse la moins aboutie. Mesures sur 40 prompts : les fiches injectées sont justes à **75 %**, mais seules **26 %** des fiches utiles arrivent, parce que le seuil est prudent. Le classement bat BM25 (60 % contre 47 % dans le top 3). Le routeur ajoute environ 0,4 s par prompt.

## Sur des tâches complètes

*Pilote en cours : 6 tâches sur 3 projets perso, avec et sans dartlens, même modèle. Résultats à venir ici.*

## Installer

```bash
claude plugin marketplace add pkcoulon/dartlens
claude plugin install dartlens@dartlens

# clé officielle (console.typesafe.ai), jamais dans un dépôt
mkdir -p ~/.config/dartlens && pbpaste > ~/.config/dartlens/typesafe.key && chmod 600 ~/.config/dartlens/typesafe.key
```

Puis, dans chaque projet où tu veux Jev :

```bash
mkdir -p .claude && echo '{"jev": {"enabled": true}}' > .claude/dartlens.json
```

Ensuite, dans Claude Code :
- `/dartlens:rules` génère les règles de la garde ;
- `! dartlens status` affiche la clé, l'activation, le disjoncteur, l'usage et le coût Jev.

Sans clé ou sans activation, `lens` passe en mode local (BM25) et le dit. La garde et le routeur se taisent.

## Tes données

- **Rien ne part** sans `jev.enabled` dans le projet.
- **Refus absolu** de chemins ou de dépôts listés dans `~/.config/dartlens/policy.json` (`deny_paths`, `deny_remotes`), même activés par erreur. C'est vérifié sur les chemins résolus, liens symboliques et fiches mémoire compris. Typiquement : un dépôt client.
- **Secrets rédigés** avant l'envoi ; les fichiers sensibles (`.env`, clés, `google-services.json`…) ne partent jamais.
- **Modèle épinglé** `jev-1.13.0`, pour que les seuils calibrés ne bougent pas en silence. TypeSafe héberge aux États-Unis.

## Mesurer toi-même

- `cc-usage` : consommation Claude Code d'un projet, dédoublonnée et valorisée par modèle. C'est une estimation, pas une facture.
- `docs/need_data.py` et `docs/lens_opportunity.py` : les courbes du besoin, sur tes propres sessions. Seuls des agrégats en sortent.
- `bench/` : protocole et banc avec et sans dartlens, sur des dépôts jetables (`bench/PROTOCOL.md`).

## Limites

- **Échantillon restreint.** Les mesures portent sur 3 projets Flutter perso d'un seul auteur, avec des étiquettes écrites par des agents qui lisaient le code sans lens ni Jev. Les requêtes de `find` ont été écrites en lisant le code : sur des requêtes vagues, Jev tombe à 3 sur 6.
- **Garde : une borne haute.** Ses règles et ses cas ont été écrits par le même agent. Le taux de fausses alertes par édition réelle reste à mesurer en usage.
- **Langue.** Jev est « anglais d'abord ». Sur nos mesures, `lens` fait aussi bien en français.
- **Pas de décision de permission.** dartlens ne confie jamais une permission à Jev.
