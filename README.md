<div align="center">

# Jev for Flutter

**Le bon code Dart, sans remplir le contexte de Claude.**

Un plugin Claude Code pour les développeurs Flutter, propulsé par [Jev](https://typesafe.ai).

[Installer](#installation) · [Résultats](docs/READ-RESULTS.md) · [Fonctionnement](docs/ARCHITECTURE.md)

</div>

Claude peut charger un fichier entier alors que votre demande ne concerne qu'une partie de son code. **Jev for Flutter repère les passages utiles avant leur lecture par Claude.** Le fichier complet reste accessible.

- **Lectures automatiques** : le plugin intervient sur les gros fichiers Dart, pendant votre travail habituel avec Claude.
- **Recherche par description** : Claude peut trouver un comportement sans connaître le nom du fichier ou de la fonction.
- **Préparation en parallèle** : si votre demande indique un fichier, Jev commence son analyse pendant que Claude réfléchit.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/read-results-dark.svg">
  <img alt="Trois lectures ciblées : −25 % de tokens Claude, −41 % de coût Claude et Jev, +20 % de durée. Réponses entièrement acceptées : 2 sur 3 avec le plugin, 1 sur 3 sans." src="docs/img/read-results-light.svg" width="960">
</picture>

**Mesures de la version 0.3.0 :** trois questions sur des fichiers connus, une session par variante. Les trois passages attendus sont conservés ; les réponses restent imparfaites. Ces résultats précèdent la préparation en parallèle et ne prouvent ni un développement complet moins cher, ni une accélération générale. [Données et critères](docs/READ-RESULTS.md).

## Installation

Claude Code, Python 3.9+ et une [clé TypeSafe](https://typesafe.ai) ; macOS ou Linux. Le dépôt est actuellement privé : votre compte GitHub doit y avoir accès.

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
export TYPE_SAFE_AI_KEY="votre-cle-typesafe"
```

Dans le projet Flutter, créez `.claude/jev-for-flutter.json` :

```json
{"jev": {"enabled": true}}
```

Relancez Claude Code, puis demandez-lui de travailler normalement. `jev-flutter status`, dans son terminal, confirme l'activation. Cette activation autorise l'envoi de la question et du code concerné à TypeSafe ; les exclusions et le masquage des secrets s'appliquent.

[Commandes de recherche, migration et réglages](docs/USAGE.md). Les anciennes configurations restent compatibles. Les conventions et la mémoire du projet sont aussi prises en charge.

Inspiré du [plugin Jev de Boris Le Méec](https://github.com/BorisLeMeec/jev), adapté à Dart/Flutter. [Comparaison du code et des benchmarks](docs/JEV-COMPARISON.md) · [MIT](LICENSE).
