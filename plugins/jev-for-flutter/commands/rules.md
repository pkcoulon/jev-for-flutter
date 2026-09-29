---
description: Génère ou met à jour les règles de la garde des conventions (.claude/jev-for-flutter/rules.json) à partir des docs du projet
argument-hint: "[thème ou fichier de doc à privilégier]"
allowed-tools: Read, Glob, Grep, Write, Edit, Bash(jev-flutter rules *), Bash(jev-flutter eval guard *)
---

Génère ou mets à jour `.claude/jev-for-flutter/rules.json`, le fichier que lit la garde des conventions de jev-for-flutter. Après chaque édition, un juge rapide (Jev) répond en arrière-plan à chaque règle par une probabilité, et Claude ne reçoit une note que si une règle dépasse son seuil. $ARGUMENTS

## 1. Sources

Lis, s'ils existent : `CLAUDE.md`, `AGENTS.md`, `.claude/*.md`, les skills du projet (`.claude/skills/*/SKILL.md`, `.github/skills/*/SKILL.md`, `.agents/**/SKILL.md`) et les fiches mémoire de type feedback du projet. Si `.claude/jev-for-flutter/rules.json` existe déjà, pars de lui : garde les `id`, ne supprime pas une règle sans le dire.

Lis aussi `analysis_options.yaml` : son `include:` (very_good_analysis, flutter_lints, lints…), sa section `linter: rules:`, et la configuration DCM s'il y en a une.

## 2. Sélection

Ne retiens une convention que si elle remplit les trois conditions :

1. **Vérifiable sur une seule édition** : le texte modifié et environ 25 lignes autour suffisent pour juger. Écarte ce qui demande un autre fichier, l'historique git, l'exécution ou la vue d'ensemble du projet.
2. **Sémantique** : il faut comprendre l'intention du code. Si une recherche textuelle ou une regex suffit, ce n'est pas une règle pour Jev.
3. **Non couverte par un lint** : vérifie qu'aucune règle de `analysis_options.yaml`, du paquet inclus ou de DCM ne la décide déjà. En cas de doute, cherche le nom de la règle de lint dans le fichier inclus. Une contrainte qu'un lint sait décider n'a pas besoin d'un juge probabiliste. `jev-flutter rules check` signale les recoupements avec les lints actifs, includes compris, mais pas avec DCM.

Vise 10 à 30 règles. Mieux vaut peu de règles nettes que beaucoup de règles floues.

## 3. Format

```json
{
  "version": 1,
  "defaults": {"threshold": 0.85, "applies_to": ["lib/**/*.dart"]},
  "rules": [
    {
      "id": "no-hardcoded-ui-text",
      "question": "Does the change add a user-visible text literal in a widget instead of a localized string?",
      "true": "A string literal shown to the user is introduced in widget code",
      "false": "Visible text comes from the localization API, or the literal is not user-visible (keys, logs, tests)",
      "applies_to": ["lib/ui/**/*.dart"],
      "message": "Texte visible en dur : passer par les traductions (app_fr.arb).",
      "examples": [
        {"after": "Text('Mes chiens')", "violation": true},
        {"after": "Text(context.l10n.dogsTitle)", "violation": false},
        {"after": "debugPrint('dogs loaded');", "context": "Future<void> _load() async {", "violation": false}
      ]
    }
  ]
}
```

Pour chaque règle :

- `id` : kebab-case, stable, unique.
- `question` : **en anglais**, oui/non, atomique (une seule propriété), où **OUI signifie violation**. Parle de ce que « the change » introduit : Jev reçoit la modification (`change`, avec ses numéros de lignes), le code autour (`after_context`) et, quand ils sont repérés, les déclarations qui la contiennent (`enclosing`).
- `true` / `false` : ce que veut dire OUI puis NON, en anglais, courts et contrastés ; y mettre les exceptions (« not for… »).
- `applies_to` : les globs les plus étroits possibles, relatifs à la racine (`lib/ui/**/*.dart`, `test/**/*_test.dart`). Sans cette clé, la règle prend `defaults.applies_to`.
- `threshold` : seulement si la règle doit différer de `defaults.threshold`.
- `message` : en français, une ligne, actionnable ; c'est ce que Claude lira.
- `examples` : 2 à 4, au moins une violation et un cas conforme, courts et réalistes ; `context` si le cas en dépend. Pas de secret, pas de code confidentiel : questions et exemples partent chez Jev.

## 4. Vérification

1. Lance `jev-flutter rules check` et corrige toutes les erreurs. Traite chaque avertissement ou justifie-le en une phrase.
2. Si Jev est accessible, tu peux lancer `jev-flutter rules test <fichier.dart> --change '<ancien>' '<nouveau>'` sur un ou deux cas pour contrôler le branchement ; `--state` montre l'état exact que la garde enverrait. `jev-flutter eval guard --from-rules --sweep` donne une précision et un rappel sur les exemples ; ces chiffres sont optimistes, et sans valeur sur un faux serveur. Les deux commandes appellent Jev comme la garde (délai du hook, sans nouvelle tentative) : un cas en échec est un cas où la garde resterait silencieuse.

## 5. Restitution

Montre la liste à l'utilisateur sous forme de tableau : id, message, `applies_to`, source (fichier de doc et section). Ajoute une ligne pour les conventions écartées et la raison (lint existant, contexte insuffisant, non sémantique). Rappelle que la garde ne s'active que si `jev.enabled` vaut `true` dans `.claude/jev-for-flutter.json` et que le projet n'est pas exclu par `~/.config/jev-for-flutter/policy.json`. Ne modifie ni l'un ni l'autre.
