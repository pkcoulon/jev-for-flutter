# Deux tâches réelles, quatre sessions — 29 septembre 2026

**Le lot est terminé pour 1,3053 $ sur les 5 $ autorisés. Il ne prouve pas l'efficacité générale de dartlens.** Avec le plugin, le diagnostic coûte moins cher ; la recherche d'information coûte davantage. Aucune session n'utilise `lens`, et aucun refus de grande lecture ne se déclenche. Les écarts ne démontrent donc pas un bénéfice de la sélection de code par Jev.

## Résultats

Une session par tâche et par variante, avec le même prompt. Tous les essais sont conservés, sans relance. Coût Claude **et Jev**, contrôles de connexion inclus :

| Tâche | Sans plugin | Avec dartlens | Écart |
|---|---:|---:|---:|
| Gambade — expliquer le seuil de chaleur | 0,1958 $ | 0,2331 $ | +19 % |
| Pioudex — corriger le calcul d'XP | 0,5644 $ | 0,3120 $ | −45 % |

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/exploratory-results-dark.svg">
  <img alt="Écarts avec dartlens par rapport au témoin sans plugin. Gambade : +27 % de tokens Claude, +19 % de coût, +29 % de temps vérifications comprises. Pioudex : −52 % de tokens, −45 % de coût, +3 % de temps. Une seule session par variante, aucun appel à lens." src="img/exploratory-results-light.svg">
</picture>

Les pourcentages du graphique sont calculés avec `100 × (avec / sans − 1)`, puis arrondis à l'entier. Les deux tâches utilisent la même échelle et le même périmètre : tokens Claude cache compris, coût Claude + Jev, durée de session et contrôles externes. Le temps présenté est celui jusqu'aux vérifications terminées, pas le délai avant le premier mot de la réponse. Aucun pourcentage d'amélioration de qualité n'est établi.

| Durée | Gambade sans / avec | Pioudex sans / avec |
|---|---:|---:|
| Session Claude, outils et tests qu'il lance inclus | 68,5 / 88,7 s | 198,1 / 197,5 s |
| Contrôles automatiques externes après la session | 0 / 0 s | 19,2 / 26,6 s |
| Total jusqu'à la fin de ces contrôles | **68,5 / 88,7 s** | **217,3 / 224,1 s** |

La préparation des copies, la résolution des dépendances et la relecture des réponses sont exclues de ces durées. Les contrôles Gambade portent sur la réponse et le diff, sans commande de test après la session. Le lot ne montre pas de gain de vitesse jusqu'au résultat vérifié.

## Qualité vérifiée

Les quatre réponses sont acceptées par la relecture Astra selon les demandes et les critères figés. Cette relecture est réalisée dans la session principale : **elle n'est ni indépendante ni aveugle**, même si les paquets exportés masquent les variantes. Elle ne démontre pas une qualité équivalente en général.

- **Pioudex :** même correction d'une ligne dans les deux variantes, `Bareme.multiplicateur`, rang 4 rétabli à ×5 ; aucun test modifié. Les traces confirment les **1 067 tests passés** annoncés par chaque réponse. Les contrôles externes passent aussi : célébration, progression, non-régression, analyse et format.
- **Gambade :** les deux réponses donnent le seuil exact de 30 °C ressentis pour le carlin, la décision dans `HeatAdvice.evaluate`, le profil de race et sa source PDSA. Aucun fichier modifié. Réserves : le témoin mélange dans une phrase les consommateurs du drapeau de sensibilité et du niveau calculé ; la réponse avec plugin n'explicite pas le raccordement à l'outil météo de l'assistant. La relecture a vérifié ce raccordement dans le code. L'acceptation des réponses ne fait pas disparaître ces limites de précision.

## Ce qui s'est réellement passé

**Zéro appel à `lens`, `lens find`, `lens which` ou `dart-outline`. Zéro grande lecture refusée.** Sur Gambade, le fichier Dart lu en entier est court. Sur Pioudex, Claude utilise directement des lectures partielles, dans les deux variantes. Le déclencheur de dartlens n'a donc pas de grande lecture à intercepter.

Le plugin démarre dans les deux sessions concernées. Jev traite deux demandes de routage vers les skills et une vérification de conventions ; aucun lien ni avertissement n'est retenu. Les deux autres appels Jev vérifient la connexion avant les sessions. Aucun appel ne sélectionne du code pour Claude.

Sur Pioudex, la session avec plugin fait 15 appels Claude contre 27 pour le témoin, qui explore davantage l'écran avant de corriger le barème. Avec une seule répétition, on ne peut pas séparer l'effet des consignes du plugin de la variabilité du modèle. Sur Gambade, la session avec plugin fait 11 appels contre 9. Une commande Python est refusée par les permissions du banc ; sur Pioudex, le témoin fait une recherche avec une expression régulière invalide. Ces incidents restent dans les coûts et les temps des variantes concernées.

## Tokens et coût complet

Tokens Claude dédoublonnés par message, sans conversion approximative depuis des caractères :

| Catégorie | Gambade sans | Gambade avec | Pioudex sans | Pioudex avec |
|---|---:|---:|---:|---:|
| Entrée hors cache | 18 | 22 | 54 | 30 |
| Écriture cache 5 min | 0 | 0 | 0 | 0 |
| Écriture cache 1 h | 26 143 | 28 502 | 55 137 | 37 840 |
| Lecture cache | 362 887 | 467 081 | 1 315 135 | 621 559 |
| Sortie | 1 862 | 2 548 | 8 067 | 3 611 |
| **Total Claude** | **390 910** | **498 153** | **1 378 393** | **663 040** |
| Jev, entrée | 0 | 3 376 | 0 | 4 751 |
| Jev, sortie | 0 | 205 | 0 | 284 |

Le total Claude compte le contexte relu à chaque appel, y compris depuis le cache ; ce n'est pas une quantité de texte unique. Les tokens Jev restent séparés, car il s'agit d'un autre modèle et d'un autre tarif.

Valorisation : **1,3049484 $ Claude + 0,000341334 $ Jev = 1,305289734 $**, soit **1,31 $**. Le compteur prudent du budget retient 1,30534 $, car il conserve le maximum entre le coût natif et le score arrondi pour chaque session. Aucun dépassement, arrêt au plafond, appel Jev rejeté, relance ou relecteur payant supplémentaire. Les 3,69 $ restants n'ont pas été utilisés.

Tarifs vérifiés le 29 septembre 2026 : Sonnet 5, par million de tokens, 2 $ en entrée, 2,50 $ en écriture cache 5 min, 4 $ en écriture 1 h, 0,20 $ en lecture cache et 10 $ en sortie ; Jev 1.13, 0,042 $ en entrée et sortie gratuite. [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing) · [TypeSafe](https://docs.typesafe.ai/models). C'est une valorisation API, pas une mesure de la facture ni du quota d'un abonnement Claude.

## Conditions et reproduction

- Claude Code 2.1.284, `claude-sonnet-5`, effort `medium`, sessions neuves, français. Paramètres identiques au sein de chaque paire.
- Version locale corrigée après `0de8979`, empreinte du plugin `1581a817ffe4b4a2`, figée avant le premier appel. Réglages par défaut : refus unique, conventions et routeur actifs, `find_code` désactivé. Pas de compilation du helper Dart.
- Copies jetables : Gambade `fcac6e853a1a1ff70fa56c2eb5ec08b17ac7f10c` ; Pioudex `91036cc5a13a474a3743c56919b598919cd84500`, avec le défaut du barème prévu par la tâche et l'historique masqué. Aucun projet client.
- Ordre figé : Gambade sans puis avec, Pioudex avec puis sans. Plafonds Claude respectifs de 0,65 $ et 1,25 $ par session, plus 0,10 $ maximum Jev et une réserve. Aucun essai ajouté après lecture des résultats.
- Réglages personnels et MCP externes désactivés ; mêmes permissions pour les deux variantes. Le vrai Jev répond via un relais local qui borne la dépense et conserve les usages, sans enregistrer la clé. Aucun faux serveur.

Les [données du graphique](exploratory-results.json) contiennent les usages, les tarifs, les durées, les réserves de relecture et les empreintes des preuves. Régénération des SVG clair/sombre : `python3 docs/readme_charts.py` avec Matplotlib installé. Les archives privées sont conservées dans `~/.cache/dartlens-bench/exploratory-5usd-2026-09-29/` : plan, plugin figé, réponses, diffs, tests, usages et revues.

Recalcul hors ligne de chaque projet, sans nouvel appel payant :

```bash
LOT="$HOME/.cache/dartlens-bench/exploratory-5usd-2026-09-29"
python3 -B bench/score.py "$LOT/results/pioudex" --tasks "$LOT/definitions" \
  --reviews "$LOT/reviews/reviews.json" --key "$LOT/review-key.json"
```

Remplacer `pioudex` par `gambade` pour l'autre paire. Deux tâches déjà connues du banc et une répétition ne permettent ni d'estimer la variabilité, ni de conclure sur d'autres projets. Le prochain travail utile reste la couverture des parcours de code et le choix du bon moment pour utiliser la recherche, sans forcer `lens` lorsque les lectures partielles suffisent déjà.
