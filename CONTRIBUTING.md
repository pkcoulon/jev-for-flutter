# Contribuer à Jev for Flutter

Le code du plugin se trouve dans `plugins/jev-for-flutter`, son module Python dans `lib/jev_flutter`. Python 3.9+, macOS ou Linux ; pas de dépendance Python à installer pour l'utiliser. Le helper Dart est facultatif.

Avant de proposer un changement :

```bash
python3 -m compileall -q plugins/jev-for-flutter/lib plugins/jev-for-flutter/hooks plugins/jev-for-flutter/mcp
python3 plugins/jev-for-flutter/bin/jev-flutter --help
python3 bench/run.py --check-tasks
claude plugin validate .
claude plugin validate plugins/jev-for-flutter
```

Ces commandes ne font pas d'appel Jev ni de session LLM. Les scripts de campagne peuvent en faire : fixer un budget avant de les lancer. Ne pas inclure de clé, de source privée ou de transcript personnel dans une contribution.

Documenter séparément pertinence des résultats, qualité de la réponse finale, tokens Claude, tokens Jev, coût combiné et durée. Conserver les échecs dans les totaux. Une sélection courte ou un coût inférieur ne suffit pas si le résultat est incomplet.

Les graphiques sont générés depuis les JSON dans `docs/` avec `docs/readme_charts.py` et Matplotlib 3.9.4. Ils doivent rester lisibles en thème clair et sombre. Les licences du paquet doivent rester identiques aux fichiers `LICENSE` et `THIRD_PARTY_NOTICES.md` à la racine.

[Architecture](docs/ARCHITECTURE.md) · [Protocole et résultats publics](docs/PUBLIC-PROJECTS.md) · [Licence MIT](LICENSE)
