---
name: write-acceptance-tests
description: Prépare les tests observables de bugs et comportements critiques depuis les AC et contrats publics, avant l'implémentation ; s'applique aussi aux epics directes, sans TDD universel ni verrou automatique.
---

# write-acceptance-tests

Lire le [protocole commun](../../../docs/dev/protocole-execution.md), la règle
[35](../../../.roo/rules/35-testing-quality-gates.md) et le contrat cible. Utiliser cette
skill pour une demande explicite, un bug ou les comportements critiques retenus
par l'analyse : droits, transitions, déploiements, rejeux. Une correction visuelle
ou documentaire simple ne nécessite pas cette phase.

## Écrire depuis le comportement attendu

Identifier les AC stables et contrats publics, avec les exigences et décisions
applicables ; ne pas renuméroter les AC. Pour une epic directe, écrire les
preuves dans l'epic (section « Exécution directe ») sans story miroir. Pour une
parente découpée, préparer les tests des unités responsables et les scénarios
d'intégration du parent.

Définir situation, action et résultat observable, cas de refus et limites selon
le risque. Choisir API (`backend/tests/unit/test_api/`), domaine/service public,
composant ou parcours selon le comportement, sans imposer un test unique par AC.
Les tests n'inspectent pas les détails internes pour reproduire le plan
d'implémentation. Une passe distincte reçoit les AC et contrats publics sans les
tâches détaillées lorsque pertinent.

Les attendus sensibles sont proposés en brouillon au propriétaire avant leur
usage d'acceptation. Ne jamais déduire l'attendu du code à valider ni mocker
l'unité dont on prétend vérifier le comportement. Pour un endpoint, les cas
systématiques de `35` §5 s'appliquent (401/403/422/404, isolation, champs
sensibles) ; pour un canal WebSocket, les droits du canal (`21` §7).

## Exécuter et conserver la preuve

Écrire les tests dans les emplacements normaux de `35`, sans suite cachée ni
répertoire exclu. Pour un bug ou une capacité manquante, vérifier l'échec sur le
comportement attendu : une fixture cassée, un import absent, une infrastructure
indisponible ou un skip ne constitue pas cette preuve. Un comportement déjà
vert devient une non-régression documentée, sans le faire échouer artificiellement.

Consigner AC, scénarios/fichiers, commande, environnement, référence et résultat
réel dans le contrat. Cette skill écrit les tests, pas le code applicatif ; une
interface publique encore indéfinie appelle une conception avant sa réalisation.
Ne pas exposer de stub applicatif pour contourner un échec d'infrastructure.

L'implémentation autorisée poursuit ensuite `treat-story`. À l'acceptation,
les tests requis passent sur la référence évaluée. Un attendu erroné ou devenu
incompatible avec le besoin fait l'objet d'un arbitrage tracé avant modification ;
aucune assertion affaiblie pour rendre le code conforme. Aucun verrou de fichiers
ou commit rouge séparé n'est imposé par cette skill.
