# Installer et utiliser Jev for Flutter

Ce document décrit la version 0.3.1. Le dépôt, le plugin et sa marketplace s'appellent `jev-for-flutter`.

## Installation

Le dépôt fournit sa propre marketplace, nommée `jev-for-flutter`. Il ne s'agit pas de la marketplace officielle Anthropic. Tant que le dépôt est privé, votre environnement Git doit être authentifié avec un compte autorisé.

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

Ces commandes installent le plugin pour votre utilisateur. Pour une installation limitée au projet courant, utilisez `claude plugin install jev-for-flutter@jev-for-flutter --scope local`. Voir les [instructions officielles Claude Code](https://code.claude.com/docs/en/discover-plugins).

Prérequis : Python 3.9 ou plus récent, macOS ou Linux. Windows natif n'est pas pris en charge. Pour analyser précisément la structure Dart, le plugin utilise le SDK du projet et `package:analyzer`. Sans analyseur disponible, il continue avec un plan approximatif, signalé dans les résultats.

## Clé et activation

Créez une clé depuis la console TypeSafe. Enregistrez-la dans un fichier personnel, jamais dans le dépôt :

```bash
mkdir -p ~/.config/jev-for-flutter
```

Avec votre éditeur, placez uniquement la clé dans `~/.config/jev-for-flutter/typesafe.key`, puis restreignez ses permissions :

```bash
chmod 600 ~/.config/jev-for-flutter/typesafe.key
```

Vous pouvez aussi fournir `TYPESAFE_API_KEY` dans l'environnement du processus Claude Code. Le fichier évite de saisir la clé dans une commande enregistrée par le terminal.

Dans chaque projet autorisé, créez `.claude/jev-for-flutter.json`, ou ajoutez la clé suivante à son contenu existant :

```json
{
  "jev": { "enabled": true }
}
```

Ne remplacez pas vos autres réglages. Priorité : `.claude/jev-for-flutter.json`, `.jev-for-flutter.json`, puis les deux anciens fichiers `.claude/dartlens.json` et `.dartlens.json`. Le premier présent est utilisé. La clé dans `~/.config/dartlens/typesafe.key` reste reconnue si aucune nouvelle clé n'est disponible. Ouvrez une **nouvelle session Claude Code**, puis lancez :

```text
! jev-flutter status
```

Le hook de démarrage ajoute les exécutables du plugin au `PATH` des commandes de cette session via [`CLAUDE_ENV_FILE`](https://code.claude.com/docs/en/hooks#persist-environment-variables). Il ne modifie pas votre profil de terminal. Depuis un terminal extérieur à Claude, les commandes ne sont donc pas automatiquement disponibles.

Pour essayer les changements d'un clone local avant publication : `claude --plugin-dir /chemin/vers/jev-for-flutter/plugins/dartlens`, depuis votre projet. Évitez de charger en même temps la copie installée et la copie locale.

## Au quotidien

Continuez à demander votre travail à Claude normalement. Une lecture complète d'un fichier Dart de 400 lignes ou plus peut être ciblée automatiquement sur la question. La note indique les lignes omises. Refaire le Read récupère le fichier entier ; un `offset` ou `limit` explicite est toujours respecté. Demande large, incertitude, fichier trop grand ou erreur : lecture inchangée.

Si votre demande contient exactement un chemin de fichier Dart, Jev peut préparer cette sélection pendant que Claude raisonne. Aucun parcours du dépôt n'est lancé pour deviner le fichier. La lecture réutilise le résultat seulement si la question, le fichier et le modèle correspondent, pendant 90 secondes au plus. Une préparation en cours et la lecture partagent la même requête Jev. Celle-ci compte dans le plafond de 24 par session, même si Claude ne lit finalement pas le fichier. Pour désactiver l'anticipation : `"read": {"prefetch": false}`.

Les commandes disponibles dans le terminal de Claude :

```bash
lens context "How is an empty response handled?" lib
lens context --local "response conversion" lib
lens "How is the selected area displayed?" lib/map_screen.dart
lens find "where a walk is saved after confirmation" lib/features
lens which -q "Does this widget contain a user-facing text literal?" lib/ui
lens --all "Read everything" lib/map_screen.dart
lens --local "selected area" lib/map_screen.dart
dart-outline lib/map_screen.dart
```

`lens` peut aussi exécuter une commande et filtrer sa sortie : `lens "Why does the test fail?" -- flutter test test/example_test.dart`. La commande est réellement exécutée ; son code de sortie est conservé. La sortie complète reste disponible dans un fichier local privé pendant environ 24 heures, avec nettoyage lors des usages suivants.

`lens find` donne des pistes, pas un parcours complet. Au-delà de 150 fichiers, rien n'est envoyé : précisez un dossier ou passez `--max-files N`. Tous les fichiers admissibles du périmètre sont alors soumis à Jev, sans présélection par mots-clés. Pour un symbole connu, la recherche textuelle reste appropriée.

Pour essayer la préparation de contexte en arrière-plan, désactivée par défaut après des résultats défavorables :

```json
{ "context": { "enabled": true } }
```

La préparation utilise au plus huit requêtes Jev par demande, quatre simultanément, sans reprise, avec une limite de 24 000 tokens d'entrée **estimés** au total. Le processus en arrière-plan s'arrête après huit secondes ; une panne ne bloque pas Claude. La remise automatique contient au plus 8 Ko de texte UTF-8. Les mêmes questions et sources réutilisent leurs scores pendant dix minutes. Les fichiers changés invalident un contexte déjà préparé.

Ces réglages peuvent être abaissés :

```json
{ "context": { "max_requests": 4, "max_input_tokens": 12000, "max_chars": 8000 } }
```

`"lens": {"nudge": "off"}` désactive la sélection automatique. `"nudge": "hint"` affiche seulement une suggestion. `"nudge": "narrow"` sélectionne directement la plage, réglage par défaut. `"nudge": "refuse_once"` conserve l'ancien refus unique pour les projets qui le souhaitent ; un réglage existant n'est pas effacé par la mise à jour. L'outil MCP `find_code`, désormais équivalent à `lens context`, s'active séparément avec `"find": {"mcp": true}` puis une nouvelle session. Il reste désactivé par défaut ; la préparation automatique ne dépend pas de sa visibilité.

## Conventions et mémoire

`/jev-for-flutter:rules` demande à Claude de préparer `.claude/dartlens/rules.json` depuis vos conventions. Relisez ces règles : la garde donne ensuite des avis probabilistes sur les modifications, elle ne remplace ni les lints ni les tests. Sans ce fichier, aucune règle n'est évaluée. Cette commande utilise la conversation Claude et peut faire des évaluations Jev ; ce n'est pas une étape gratuite de l'installation.

Le routeur exploite en arrière-plan les descriptions des fiches de la mémoire Claude associée au projet et des skills découverts. Il suggère des liens ; il ne charge pas automatiquement toutes les fiches. Un dossier partagé arbitraire n'est pas raccordé par le simple fait d'exister. Le routage exact d'un identifiant de ticket peut fonctionner localement sans Jev.

Pour couper ces aides séparément : `"guard": {"enabled": false}` et `"router": {"enabled": false}`.

## Confidentialité

L'activation de Jev autorise l'envoi à TypeSafe des éléments requis par chaque composant : extraits ou contenu de candidats, question, modifications et règles, descriptions de mémoire et de skills. Le masquage reconnaît certains formats, pas tout secret possible. N'activez le service que pour du code autorisé à quitter la machine.

Dans `~/.config/dartlens/policy.json`, vous pouvez exclure des chemins et des remotes Git, même si un projet active Jev :

```json
{
  "deny_paths": ["~/projects/confidential"],
  "deny_remotes": ["example.com/private-team/"]
}
```

Ces listes sont personnelles : aucun dépôt client particulier n'est codé dans le plugin. Une politique illisible refuse l'envoi. Les chemins sont résolus avant vérification ; un lien symbolique ne doit pas contourner l'exclusion. Les remotes sont comparés par sous-chaîne.

Sans activation, ou avec `DARTLENS_JEV_DISABLE=1` dans l'environnement de Claude, les recherches de `lens` restent locales et le précisent. Aucun contexte de code n'est préparé automatiquement. `DARTLENS_CONTEXT_DISABLE=1` désactive seulement les appels Jev et l'automatisation de `context`.

## Dépannage

- **Commande introuvable** : ouvrez une nouvelle session après installation ; vérifiez que le plugin et ses hooks sont activés. Le correctif d'initialisation du `PATH` est nécessaire pour les sessions sans configuration personnelle.
- **Plan approximatif** : le parseur Dart est indisponible. La CLI peut préparer le parseur en arrière-plan au premier usage ; `DARTLENS_OUTLINE_NO_BUILD=1` l'interdit. Le serveur MCP utilise toujours cette interdiction. Aucun code Flutter de l'application n'est compilé par cette préparation, mais le helper Dart et ses dépendances le sont.
- **Jev indisponible** : `lens` annonce un classement local. Cela change la pertinence possible ; ce n'est pas la preuve qu'aucun autre passage n'existe.
- **Contexte absent** : demande trop courte, commande slash, dépassement du délai, absence de correspondance, résultat devenu obsolète ou session déjà terminée. Consultez `context.jsonl` dans `~/.cache/dartlens` ; `lens context --local "question" lib` permet un diagnostic sans Jev.
- **Coût affiché** : les tokens Claude et Jev sont distincts. Les anciens journaux Jev n'enregistraient que l'entrée ; la facturation complète ne peut pas en être déduite. `dartlens status` reste un diagnostic, pas une facture.

## Migration depuis dartlens 0.2

Dans la portée où l'ancienne version est installée (`user` par défaut), retirez-la avant d'installer le nouveau nom, pour ne pas exécuter deux fois les hooks :

```bash
claude plugin uninstall dartlens@dartlens
claude plugin marketplace remove dartlens
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

Pour une installation locale au projet, ajoutez `--scope local` aux commandes du plugin. Les configurations, clés, règles et exclusions historiques restent compatibles ; rien n'est déplacé ou supprimé par le plugin. Le cache et la politique personnelle gardent leur chemin `dartlens`.

## Mise à jour depuis Jev for Flutter 0.3.0

Pour remplacer l'ancienne adresse de la marketplace enregistrée localement :

```bash
claude plugin marketplace remove jev-for-flutter
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
```

Relancez ensuite Claude Code. Le retrait de la marketplace peut retirer les plugins qu'elle fournit ; la dernière commande les réinstalle sous le même nom. Vos réglages de projet et votre clé restent en place.

[Retour au README](../README.md) · [Mesures](MEASURES.md) · [Architecture](ARCHITECTURE.md)
