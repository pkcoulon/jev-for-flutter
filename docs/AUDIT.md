# Audit de dartlens — 29 septembre 2026

> Historique : la version 0.3 utilise désormais la lecture native ciblée et garde le contexte automatique en option. Voir [les dernières mesures](READ-RESULTS.md) et [l’architecture actuelle](ARCHITECTURE.md).

**État actuel :** une [refonte du contexte en parallèle](CONTEXT-REDESIGN.md) a suivi cet audit, puis [six nouvelles sessions réelles](CONTEXT-RESULTS.md) dans le plafond cumulé de 5 $. Elle change le déclenchement, le moteur du MCP et la suggestion par défaut. Les contrôles et décisions ci-dessous décrivent la v0.2 auditée avant cette refonte ; leurs résultats ne mesurent pas la nouvelle architecture.

**Verdict : la sélection réduit le volume de code reçu dans les essais archivés. L'économie de tokens, le gain de vitesse et la qualité maintenue sur un travail terminé ne sont pas démontrés.** Le plugin est installable et ses mécanismes sont vérifiables ; annoncer la promesse complète comme acquise serait prématuré.

Audit du dépôt à `0de8979`, version déclarée `0.2.0`, puis des corrections locales décrites ci-dessous. Les corrections de cet audit ne sont pas encore publiées sur la marketplace. La première phase a été réalisée hors ligne, sans appel réel ni build. Après autorisation de 5 $, [quatre sessions réelles](EXPERIMENT-5USD.md) ont complété l'audit pour 1,31 $, sans nouveau build ni publication.

## Périmètre

Relecture des manifestes, hooks, commandes et skill, serveur MCP, politique d'envoi, client Jev, parseur Dart, découpage, recherche, conventions, mémoire et mesure des usages. Contrôles sur fichiers synthétiques et serveur HTTP Jev local ; recalcul séparé des archives de vrais essais déjà payés. La [carte d'architecture](ARCHITECTURE.md) décrit les entrées, flux de données, délais et replis.

Les contrôles actuels ont été exécutés sur macOS avec Python 3.9.6 et Claude Code 2.1.284 pour la validation des manifestes. La position des déclarations Dart a été vérifiée avec le helper déjà compilé en cache, sans nouveau build. L'installation dans le compte GitHub d'un tiers et l'exécution sous Linux n'ont pas été testées.

## Défauts reproduits et corrigés

| Défaut | Conséquence | Correction et vérification |
|---|---|---|
| Aucun ajout des exécutables au `PATH` de Claude | Une installation neuve recommande `lens` alors que la commande reste introuvable | Le hook de démarrage écrit le `PATH` dans `CLAUDE_ENV_FILE`. Vérification depuis `/usr/bin:/bin`, découverte des trois commandes et exécution des aides. Les noms de fichiers avec espaces sont aussi protégés dans la suggestion. |
| Plafond vérifié sans verrou global | Des lectures simultanées de fichiers différents peuvent toutes passer le contrôle avant la création des marqueurs | Verrou par session autour du décompte et de la création. Avant : huit refus avec une limite de trois sous entrelacement contrôlé. Après : trois sur douze demandes parallèles, et toujours un seul refus pour un même fichier. |
| Un dépôt exclu imbriqué était accepté par `sendable` | La CLI pouvait soumettre son code depuis le parent autorisé | Vérification des remotes des dépôts englobants pour chaque chemin. Cas synthétique refusé, lien symbolique extérieur refusé, politique invalide refusée. Aucun dépôt client utilisé pour ce contrôle. |
| Clé privée PEM masquée uniquement à son en-tête | Le corps pouvait subsister, notamment dans les blocs suivants ou leur étiquette | Masquage du bloc complet avant découpage, positions préservées, étiquettes des passages masqués neutralisées. Vérification sur trois blocs et sur des lignes géantes. Cela reste un filtre de formats connus, pas une garantie universelle contre les secrets. |
| Des réponses Jev présentes mais invalides déclenchaient la suite de `find` | Requêtes supplémentaires inutiles, compteur de fichiers jugés trompeur | Il faut désormais au moins un score valide pour poursuivre ; le compteur suit les scores réellement exploitables. Huit réponses invalides entraînent le repli sans poursuivre les candidats. |
| Tokens de sortie Jev absents du journal commun | Mesure future incomplète de sa consommation | Journalisation de l'entrée et de la sortie telles que fournies par l'API. Les anciennes valeurs manquantes ne sont pas remplacées par zéro. |
| `dart-outline` ignorait `DARTLENS_OUTLINE_NO_BUILD` | La commande pouvait compiler le helper malgré la désactivation demandée | Le flag est transmis aux deux chemins du helper et refuse `--build` explicitement. Correction incluse dans le plugin figé avant les quatre sessions réelles. |

## Contrôles exécutés

**56 contrôles locaux réussis**, dans deux scripts temporaires conservés avec les preuves de l'audit, sans ajouter de suite de tests au dépôt :

- démarrage sans configuration personnelle du `PATH`, activation, désactivation, modes de suggestion, reprise d'une lecture, lectures partielles et parallèles ;
- exclusions, liens symboliques, politique illisible, secrets multiligne et maintien des positions ;
- sélection d'extraits via le contrat HTTP simulé, sorties de commande, code de sortie, permissions du fichier brut ;
- recherche sur 170 fichiers : 150 jugements initiaux au plus, vérifications suivantes distinctes ;
- panne 401 : huit tentatives ; panne 529 : 24 avec reprises ; scores invalides : huit puis repli ;
- MCP : initialisation, zéro outil par défaut, activation, arguments invalides, chemin extérieur, recherche locale, fermeture et arrêt d'un groupe de processus ;
- garde : changements successifs, changement annulé, édition devenue obsolète, avis asynchrone, silence sous le seuil et panne ;
- routeur : plafond de trois liens et 700 caractères, abstention, déduplication, routage local de ticket, descriptions limitées ;
- positions du parseur Dart en cache et syntaxe Python des entrées contrôlées.

La marketplace et le plugin passent `claude plugin validate --strict`. `bench/run.py --check-tasks` valide les douze définitions. Cela ne signifie ni que les douze tâches ont été rejouées, ni que leurs critères mesurent suffisamment la qualité. Le faux serveur démontre les échanges et les replis, pas la pertinence sémantique du vrai Jev.

## Ce que les vraies données permettent de dire

**Dernier lot, version locale corrigée :** deux tâches, une session par variante. Coût Claude + Jev : Gambade 0,1958 → 0,2331 $, Pioudex 0,5644 → 0,3120 $. Les deux correctifs Pioudex sont identiques et passent les tests ; les réponses Gambade sont acceptées avec des réserves de précision. La relecture n'est pas indépendante. Aucun appel à `lens` ni refus de grande lecture, donc aucun bénéfice de la sélection démontré par ce lot. [Tokens, durées et preuves](EXPERIMENT-5USD.md).

**Campagnes antérieures :**

Le recalcul de la campagne d'adoption retrouve **476 521 → 157 178 caractères de code Dart**, soit **67,0 % de moins**, avec les échecs inclus. Ces résultats précèdent la version 0.2. Ils ne comptent pas toute la consommation de la conversation.

La seule tâche acceptée dans les trois variantes, le diagnostic, fournit le contre-exemple utile à une promesse trop large :

| Mesure Claude, sur ce diagnostic | Sans plugin | Avec arrêt de lecture |
|---|---:|---:|
| Entrée hors cache | 44 | 46 |
| Écriture de cache 1 h | 89 206 | 131 492 |
| Lecture de cache | 1 791 949 | 2 813 838 |
| Sortie | 5 389 | 7 765 |
| Coût au tarif API enregistré, hors Jev | 0,7692 $ | 1,1665 $ |

Ici, le plugin reçoit moins de code mais la tâche consomme davantage. Une seule répétition ne permet pas de généraliser cette hausse ; elle suffit à montrer pourquoi la réduction de code n'est pas une preuve d'économie globale. Les écritures de cache 5 min sont nulles dans ces deux essais. Les principales et sous-conversations sont comptées dans leurs usages propres.

Le recalcul des anciennes mesures de `lens` retrouve **66/72 sélections complètes avec Jev**, contre **53/72** avec les mots-clés, selon les étiquettes initiales. Jev montre en médiane 10,1 % des lignes, mais six sélections restent incomplètes. Les variantes française et anglaise d'une question ne sont pas des cas indépendants.

Les anciennes sessions `find_code` montrent aussi des réponses incomplètes malgré un coût faible. Dans certains cas, une information fournie par une lecture est ensuite oubliée ; dans d'autres, un fichier proposé n'est pas ouvert. La cause ne se résume donc ni à la langue de la question ni au nombre de résultats.

[Données du graphique](readme-results.json) · [Calcul et limites des mesures](MEASURES.md)

## Décision technique à l'issue de l'audit initial

Conserver `find_code` désactivé par défaut. La méthode de classement de fichiers, même inspirée de Jev, ne vérifie pas la couverture d'un parcours entre services, modèles et interface. Le contrôle de cette couverture est le prochain problème produit ; multiplier les sessions sans le traiter risque de reproduire les mêmes omissions.

Les conventions et la mémoire sont des aides complémentaires, avec une utilité mesurée sur des jeux restreints. Leur présence peut aussi ajouter des appels et du contexte : leurs effets font partie du coût du produit installé.

Le refus unique reste le réglage choisi, avec une issue explicite vers la lecture entière. Les anciennes campagnes démontrent son déclenchement, pas un usage systématique de `lens`. Le nouveau lot confirme qu'il peut ne pas intervenir du tout lorsque Claude lit déjà par plages. Le [protocole](VALIDATION.md) et le [rapport](EXPERIMENT-5USD.md) séparent qualité, tokens Claude et Jev, coût et durée. Le lot autorisé est terminé.

## Points ouverts avant diffusion plus large

- Le dépôt est privé ; les commandes marketplace exigent l'accès GitHub. La correction d'installation doit être publiée avant de bénéficier aux installations distantes.
- Le manifeste annonce MIT, mais aucun fichier `LICENSE` ne fournit actuellement le texte de licence. À compléter lors de la préparation de diffusion ; le README n'affiche pas de badge de licence.
- Pas de garantie de délai global de dix secondes, ni de recherche exhaustive au-delà de la présélection de 150 fichiers.
- Le helper Dart peut se préparer en arrière-plan via la CLI ; ce comportement et sa désactivation sont maintenant documentés.
- Le masquage ne couvre pas tout format de secret ou tout fragment isolé. L'activation par projet et les exclusions restent indispensables.
- Le chargement des hooks, le routeur et la garde ont aussi été observés avec le vrai Claude et le vrai Jev. L'usage spontané de la sélection après les correctifs reste non observé dans le dernier lot.
