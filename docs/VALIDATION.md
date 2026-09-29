# Valider le bénéfice sur un travail terminé

> Historique : la version 0.3 utilise désormais la lecture native ciblée et garde le contexte automatique en option. Voir [les dernières mesures](READ-RESULTS.md) et [l’architecture actuelle](ARCHITECTURE.md).

La comparaison ci-dessous a été exécutée **avant** la [refonte du contexte en parallèle](CONTEXT-REDESIGN.md). Les six sessions suivantes, leurs versions figées et leurs résultats sont dans le [bilan de la refonte](CONTEXT-RESULTS.md). Le dernier correctif passe les contrôles des deux côtés, mais le plugin augmente tokens et coût sur cette paire. Une simple présence dans la carte ne valide pas la réponse finale ; les cas de localisation incomplets restent dans les résultats.

**Statut : lot exploratoire de 5 $ terminé le 29 septembre 2026, pour 1,31 $ Claude et Jev compris.** [Rapport complet](EXPERIMENT-5USD.md). Plan respecté : Gambade chaleur, sans puis avec plugin (0,65 $ de plafond par session) ; Pioudex diagnostic XP, avec puis sans (1,25 $). Une répétition, aucune relance ni relecture externe payante. Les résultats sont contrastés et aucune session n'utilise `lens` : pas de preuve d'économie à qualité égale. La relecture effectuée par Astra dans la session principale n'est ni indépendante ni aveugle. Aucun lot supplémentaire lancé.

## Question et comparaison

La version locale corrigée de dartlens, avec ses réglages par défaut, permet-elle de terminer une tâche correcte avec moins de tokens, moins de temps et un coût inférieur à Claude Code seul ?

Comparer deux variantes, sans changer le prompt utilisateur :

- **Témoin** : Claude, sans chargement de dartlens ni de ses hooks ou outils MCP.
- **Plugin** : même Claude, dartlens actif, refus unique, garde et mémoire actives lorsqu'elles sont configurées, `find_code` désactivé.

Cela mesure le produit proposé à l'installation. Une comparaison isolant seulement `lens` répondrait à une autre question et serait une expérience distincte. Ne pas ajouter une troisième variante à chaque essai décevant.

## Avant le premier appel

Figer le commit du plugin et les commits des projets personnels, le modèle et ses paramètres, les règles, la mémoire, les autorisations et les versions des outils. Utiliser le vrai exécutable Claude, sans les hooks utilisateur qui ont faussé la première campagne. Ne pas précharger les réponses attendues dans la mémoire ou le prompt.

Préparer des tâches de développement variées, dont une exigeant un parcours entre service, modèle et affichage, et une où lire le fichier entier est justifié. Les douze définitions existantes ont une syntaxe valide ; cela ne garantit pas la qualité de leurs critères. Faire les vérifications de départ et contrôler les réponses de référence avant de les utiliser.

Pour chaque tâche, écrire avant l'essai : résultat attendu, branches nécessaires, faits à expliquer ou comportement à modifier, régressions interdites et vérifications exécutables. Une omission majeure ou une affirmation fausse dans l'explication fait échouer la tâche, même si les anciens quatre points de la grille sont satisfaits. Ne pas corriger la grille pour une seule variante après lecture des réponses.

## Exécution bornée

Un petit budget finance une exploration, pas une preuve statistique générale. Le nombre de tâches et de répétitions est fixé après vérification du coût récent de référence, avec une réserve pour terminer le lot et compter Jev. Un budget qui ne couvre qu'une paire produit seulement une observation appariée.

Alterner l'ordre des variantes, sur des copies jetables et des sessions neuves. Conserver les échecs, les sorties incomplètes et les dépassements. Ne pas arrêter la collecte uniquement parce que le résultat devient favorable. Ne pas réessayer seulement les échecs du plugin.

`--max-budget-usd` limite la session Claude mais peut être dépassé par le dernier appel ; il n'inclut ni Jev ni un relecteur lancé séparément. Ajouter un suivi cumulatif extérieur, garder une réserve, ne plus démarrer de session si le solde ne couvre pas son plafond et cette réserve. Un tarif Jev non confirmé reste une inconnue, pas un coût nul.

## Mesures et décision

| Priorité | Mesure | Règle |
|---|---|---|
| Qualité | Résultat complet et correct, tests et régressions, relecture sans nom de variante | Une réponse incorrecte moins chère est un échec ; aucune promesse d'économie à qualité égale si cette condition manque. |
| Consommation | Entrée Claude sans cache, écriture cache 5 min/1 h, lecture cache, sortie ; entrée et sortie Jev | Inclure principal et sous-agents une seule fois. Conserver les catégories, pas seulement un total de caractères. |
| Coût | Valorisation Claude et Jev avec tarifs datés | Publier les coûts de toutes les tentatives et le nombre de tâches correctes, puis les comparaisons appariées de tâches correctes dans les deux variantes. Ne pas cacher le coût des échecs. |
| Temps | Durée complète jusqu'au résultat et aux vérifications | Inclure le temps de Jev, les recherches et le repli. Annoter les attentes externes sans les retirer arbitrairement d'une seule variante. |
| Adoption | Usage spontané et parcours de lecture | Explique le mécanisme ; ne vaut pas validation de la qualité ou de l'économie. |

Le rapport doit montrer la dispersion et les résultats tâche par tâche. Si le petit lot est ambigu, le verdict est **inconclusif**. Aucune taille d'échantillon arbitraire, ni un seuil de baisse de 15 %, ne garantit une preuve. Une affirmation générale de qualité maintenue demande une marge et une analyse de non-infériorité décidées avant une campagne assez grande ; le besoin de répétitions dépend de la variabilité effectivement observée.

## Obstacle produit à traiter

`lens` et `find` ne donnent pas de certificat de couverture d'un comportement. Les anciens essais montrent qu'un fichier proposé ou une fonction effectivement lue peuvent être absents du raisonnement final. Avant de réactiver `find_code` par défaut, il faut une vérification des parcours et des branches nécessaires sur des tâches indépendantes, puis des sessions complètes. Copier la sélection de fichiers du plugin de Boris ne résout pas à lui seul cette étape.
