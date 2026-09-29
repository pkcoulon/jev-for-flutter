<div align="center">

# Jev for Flutter

**Le bon code Dart, sans remplir le contexte de Claude.**

Un plugin Claude Code pour les développeurs Flutter, propulsé par [Jev](https://typesafe.ai).

[Installer](#installation) · [Benchmarks](docs/PUBLIC-PROJECTS.md) · [Guide](docs/USAGE.md) · [MIT](LICENSE)

</div>

Claude peut charger un fichier entier alors que votre demande ne concerne qu'une partie de son code. **Jev for Flutter repère les passages utiles avant leur lecture par Claude.** Le fichier complet reste accessible.

- **Lectures automatiques** : le plugin intervient sur les gros fichiers Dart, pendant votre travail habituel avec Claude.
- **Recherche par description** : Jev examine les fichiers par groupes, puis vérifie le code des meilleurs candidats.
- **Préparation en parallèle** : si votre demande indique un fichier, Jev commence son analyse pendant que Claude réfléchit.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/public-read-results-dark.svg">
  <img alt="Trois questions ciblées sur Flutter Form App, LocalSend et AppFlowy : −23 % de tokens Claude, −53 % de coût Claude et Jev, +7 % de temps. Réponses acceptées : 3 sur 3 avec Jev, 2 sur 3 sans." src="docs/img/public-read-results-light.svg" width="960">
</picture>

**Mesures 0.3.2 sur trois projets publics**, du petit exemple Flutter à AppFlowy. Une session par variante, questions sur des fichiers connus, revue selon une grille fixée avant les essais. Le gain vient des gros fichiers ; le petit fichier n'en bénéficie pas. Ces mesures ne prouvent pas une économie sur un développement complet. [Protocole, résultats et limites](docs/PUBLIC-PROJECTS.md).

La recherche groupée réduit aussi le temps de recherche de **74 % sur LocalSend et 82 % sur AppFlowy**, par rapport aux requêtes individuelles. Les douze recherches testées satisfont la même grille dans les deux variantes.

## Installation

Claude Code, Python 3.9+ et une [clé TypeSafe](https://typesafe.ai) ; macOS ou Linux. Le dépôt est actuellement privé : votre compte GitHub doit y avoir accès.

```bash
claude plugin marketplace add pkcoulon/jev-for-flutter
claude plugin install jev-for-flutter@jev-for-flutter
export TYPESAFE_API_KEY="votre-cle-typesafe"
```

Ouvrez une nouvelle session Claude Code dans votre projet Flutter, puis activez Jev :

```text
! jev-flutter init --enable-jev
! jev-flutter doctor
```

L'activation conserve vos réglages et autorise l'envoi de la question et du code concerné à TypeSafe. `doctor` vérifie la configuration sans appel payant. Demandez ensuite votre travail à Claude normalement.

**Plugin libre sous MIT.** Claude et TypeSafe sont des services distincts ; le mode `--local` ne fait aucun appel Jev. [Première installation, dépannage et désinstallation](docs/FIRST-RUN.md) · [Commandes et réglages](docs/USAGE.md).

Inspiré du [plugin Jev de Boris Le Méec](https://github.com/BorisLeMeec/jev), adapté à Dart/Flutter. [Comparaison du code et des benchmarks](docs/JEV-COMPARISON.md) · [MIT](LICENSE).
