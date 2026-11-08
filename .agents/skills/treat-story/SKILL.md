---
name: treat-story
description: Implémente une story ou une epic directe à partir de son contrat analysé, avec contrôles et preuves.
---

# treat-story

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Lire le [protocole commun](../../../docs/dev/protocole-execution.md) et appliquer ses dispositions de réalisation. L'objectif et les critères d'acceptation pilotent la réalisation ; le plan technique s'adapte aux faits dans les limites définies par `01` et le protocole commun.

## Router et reprendre

- Epic directe : conserver analyse, réalisation et preuves dans l'epic (section « Exécution directe ») ; terminer la réalisation en `REVIEW`, puis transmettre à `finalise-epic`.
- Epic découpée : utiliser `treat-epic`.
- Story : lire le parent et traiter son périmètre ; après réalisation, utiliser `finalise-story` si la demande inclut sa finalisation.
- Story avec sous-stories : traiter les enfants selon leurs dépendances, réutiliser les preuves valides et vérifier l'intégration de la parente. Ne pas implémenter deux fois leur périmètre.

Établir un mode manquant selon `01` §2 ; ne pas fusionner implicitement les contrats existants. Si l'analyse manque ou n'est plus actuelle, appliquer `analyse-story` dans le cadre d'une demande d'implémentation autorisée. Un prérequis indisponible bloque le travail dépendant ; poursuivre les travaux indépendants autorisés. Ne pas rouvrir une unité `DONE` sans demande couvrant cette reprise.

## Réaliser et contrôler

Préparer les tests observables des bugs et comportements critiques retenus par l'analyse via `write-acceptance-tests`, avant leur implémentation ; réutiliser les tests déjà pertinents et les preuves existantes. Une étape autonome reste interne à la réalisation autorisée, sans confirmation artificielle.

Passer à `IN_PROGRESS` et synchroniser le suivi selon `01` §9 (`make backlog`). Choisir l'ordre des travaux d'après les dépendances et le risque, avec les tests préalables imposés par `35`. Un refactoring local nécessaire peut accompagner le changement selon `01` §12 et le protocole commun ; consigner les décisions utiles, sans créer de story artificielle ni demander une validation répétée.

Appliquer `01` §12 dès que les faits appellent un réexamen, et la règle d'architecture `20` §9 pour concevoir une abstraction. Ne pas poursuivre une accumulation de correctifs sans revoir l'hypothèse. Une modification de besoin ou une décision structurante suit l'arbitrage requis ; le code, les tests et les critères ne sont pas affaiblis pour rendre le résultat conforme.

Points de vigilance windflow pendant la réalisation :
- toute route déclare `require_role(...)` (`40` §3) ; tout canal WebSocket son `ensure_role_ws` (`21` §3) ;
- tout changement du contrat d'API régénère le client TS (`make generate-api`) dans le même changement ;
- tout changement de schéma passe par une migration Alembic relue (`20` §6) ;
- secrets et données sensibles jamais en dur, dans les logs ni les labels de métriques (`40` §5-§6).

Exécuter les contrôles ciblés pendant la réalisation (tests unitaires du module, lint), puis les portes applicables avant acceptation selon `01` §7, `35` et la [matrice de validation](../../../docs/dev/controles-validation.md) (`make check` pour l'applicatif). Maintenir les preuves, l'état de reprise et les notes directement dans le contrat ; les contrôles non exécutés restent visibles. Ajouter l'entrée `CHANGELOG.md` (section « Unreleased »).

Une réalisation prête à auditer passe en `REVIEW`. `finalise-story` décide de la conformité et des transitions d'une story ; `finalise-epic` audite une epic sans la clôturer. La revue distincte et les validations humaines requises ne sont jamais remplacées par la seule déclaration de l'implémenteur.
