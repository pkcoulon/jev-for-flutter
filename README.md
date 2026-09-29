<div align="center">

# Jev for Flutter

**Le bon code Dart, sans remplir le contexte de Claude.**

Un plugin Claude Code propulsé par [Jev](https://typesafe.ai). Recherche par description, lectures ciblées, conventions du projet.

[Installer](#installation) · [Résultats](docs/READ-RESULTS.md) · [Fonctionnement](docs/ARCHITECTURE.md)

</div>

> « Comment cette application gère-t-elle l'annulation d'un enregistrement ? »

Jev aide Claude à trouver le code utile. Lorsqu'il ouvre un gros fichier Dart, le plugin peut cibler directement la zone qui répond à la question : **pas de commande à rappeler, pas de lecture bloquée**. Claude peut toujours lire le reste.

- **Trouver un comportement** sans deviner le nom des fichiers. Jev examine les fichiers en parallèle.
- **Alléger les grandes lectures** avant qu'elles entrent dans la conversation.
- **Garder les habitudes du projet** grâce aux conventions et à la mémoire existantes.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/read-results-dark.svg">
  <img alt="Trois lectures ciblées : −25 % de tokens Claude, −41 % de coût Claude et Jev, +20 % de durée. Réponses entièrement acceptées : 2 sur 3 avec le plugin, 1 sur 3 sans." src="docs/img/read-results-light.svg" width="960">
</picture>

**Petit lot exploratoire :** trois questions sur des fichiers connus, une session par variante. Les trois passages attendus sont conservés ; les réponses restent imparfaites. Ces gains incluent tous les essais et ne prouvent ni un développement complet moins cher, ni une accélération générale. [Données et critères](docs/READ-RESULTS.md) · [Essais précédents](docs/CONTEXT-RESULTS.md).

## Installation

Claude Code, Python 3.9+ et une [clé TypeSafe](https://typesafe.ai) ; macOS ou Linux. Le dépôt est actuellement privé : votre compte GitHub doit y avoir accès.

```bash
claude plugin marketplace add pkcoulon/dartlens
claude plugin install jev-for-flutter@jev-for-flutter
export TYPE_SAFE_AI_KEY="votre-cle-typesafe"
```

Dans le projet Flutter, créez `.claude/jev-for-flutter.json` :

```json
{"jev": {"enabled": true}}
```

Relancez Claude Code, puis demandez-lui de travailler normalement. `jev-flutter status`, dans son terminal, confirme l'activation. Cette activation autorise l'envoi de la question et du code concerné à TypeSafe ; les exclusions et le masquage des secrets s'appliquent.

```bash
jev-flutter find "où sont gérées les nouvelles tentatives réseau" lib/services
jev-flutter ask "does this retry failed requests?" lib/services
```

Ancien utilisateur de dartlens ? [Migration, clé persistante et réglages](docs/USAGE.md). Les anciennes configurations et commandes restent compatibles. Le contexte automatique en arrière-plan est une option expérimentale.

Inspiré du [plugin Jev de Boris Le Méec](https://github.com/BorisLeMeec/jev), adapté à Dart/Flutter. [Comparaison du code et des benchmarks](docs/JEV-COMPARISON.md) · [MIT](LICENSE).
