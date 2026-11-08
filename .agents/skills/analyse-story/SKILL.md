---
name: analyse-story
description: Analyse une story ou une epic directe et écrit un plan proportionné dans son contrat, sans écrire de code.
---

# analyse-story

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Préparer le contrat demandé pour une réalisation vérifiable. Lire le [protocole commun](../../../docs/dev/protocole-execution.md), puis appliquer ses dispositions d'analyse. Les règles du projet font autorité ; cette skill n'écrit aucun code applicatif et n'autorise pas l'implémentation à elle seule.

## Choisir le contrat

- Epic directe : écrire dans l'epic, section « Exécution directe », sans story miroir.
- Epic découpée : vérifier la couverture de ses exigences ; utiliser `create-stories` pour les contrats manquants si la demande le couvre, puis analyser les stories concernées.
- Story ou sous-story : lire aussi les exigences et décisions applicables de son parent ; écrire l'analyse dans le contrat cible.
- Story parente déjà découpée : analyser les unités restantes et leur intégration, sans dupliquer le périmètre des enfants.

Un mode absent est établi selon `01` §2 et justifié. Des stories existantes impliquent par défaut le mode découpé ; conserver contrats, identifiants et preuves. Une cible ambiguë est clarifiée avant d'écrire dans un contrat supposé.

## Résultat de l'analyse

Consigner les faits vérifiés, les exigences couvertes ou manquantes, les hypothèses, les risques pertinents, un plan proportionné et les contrôles attendus. Réutiliser les sections du gabarit existant (Contexte technique, Tâches d'implémentation détaillées, Tests à écrire) ; ne pas recopier les règles ni les mêmes conclusions dans plusieurs tableaux.

Le plan expose les résultats intermédiaires et les dépendances utiles. Les fichiers et signatures sont précisés lorsque le contrat public ou une contrainte technique le nécessite ; ils ne figent pas l'implémentation locale. Évaluer les patterns existants avant de les reprendre. Pour une abstraction ou un moteur envisagé, appliquer la règle d'architecture `20` §9 ; pour une hypothèse invalidée ou une accumulation de correctifs, `01` §12 et le protocole commun.

Appliquer la checklist sécurité de `40` §8 : authentification/autorisation (`require_role(...)`, `ensure_role_ws`), validation Pydantic, exposition de données sensibles, audit, tests de sécurité à spécifier.

Pour les bugs et comportements critiques (droits, transitions, déploiements), prévoir `write-acceptance-tests` à partir des AC et contrats publics ; une vérification documentaire ou visuelle simple reste proportionnée.

Préparer les exemples métier et attendus à faire valider par le propriétaire lorsque nécessaire. Distinguer brouillon, hypothèse et décision acquise ; ne pas présenter les sorties du code comme un oracle métier indépendant.

Une question métier ou un choix structurant non arbitré suspend uniquement le travail dépendant. Les choix locaux restent autonomes selon `01` §12 et le protocole commun. La granularité dépend de la cohérence de livraison, des dépendances, du risque et de la capacité de revue ; utiliser `split-story` si la découpe devient justifiée, sans seuil automatique.

L'analyse seule laisse une unité non commencée à `TODO`. Lors d'une reprise, conserver le statut et les preuves réelles. Conclure avec le contrat enrichi, les décisions nécessaires et les limites de l'analyse.
