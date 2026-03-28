# STORY-002 : Backend — Refactoring des services de listage Docker

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant que développeur backend, je veux que les services de listage des containers Docker, projets Docker Compose et stacks WindFlow soient correctement structurés selon les principes SOLID/DRY/KISS, afin que le code soit lisible, maintenable et testable unitairement.

## Contexte technique
Le fichier `backend/app/services/compute_service.py` (~350 lignes) est un monolithe qui mélange :
- Classification des containers Docker (logique métier de labels)
- Construction d'objets domaine (`DiscoveredItem`, `StandaloneContainer`, `StackWithServices`)
- Agrégation de statistiques
- Filtrage et grouping
- Helpers utilitaires (`_format_memory`, `_parse_ports`, `_extract_uptime`)

La fonction `get_compute_global()` fait tout : connexion Docker, classification, construction d'objets, filtrage. Elle est difficile à tester unitairement car chaque responsabilité est entremêlée.

**Fichiers de référence :**
- `backend/app/services/compute_service.py` — monolithe à refactorer
- `backend/app/services/docker_client_service.py` — client Docker de bas niveau
- `backend/app/schemas/compute.py` — schémas Pydantic existants
- `backend/app/api/v1/compute.py` — router API existant (inchangé)

## Critères d'acceptation (AC)
- [ ] AC 1 : Le classifier de containers est isolé dans `container_classifier.py` avec des fonctions pures testables unitairement (pas d'I/O, pas d'async)
- [ ] AC 2 : Les builders d'objets domaine sont isolés dans `container_builder.py` (construction de `DiscoveredItem`, `StandaloneContainer`, `StackWithServices`)
- [ ] AC 3 : Les helpers utilitaires sont extraits dans `backend/app/helper/compute_helpers.py`
- [ ] AC 4 : `compute_service.py` est un orchestrateur allégé qui délègue au classifier et aux builders (chaque fonction < 80 lignes)
- [ ] AC 5 : L'API existante (`GET /compute/stats`, `GET /compute/global`) reste inchangée — pas de régression
- [ ] AC 6 : Les tests unitaires existants passent toujours (adaptation des mocks si nécessaire)
- [ ] AC 7 : Nouveaux tests unitaires pour le classifier et les builders (couverture ≥ 85%)

## Dépendances
- Aucune (story autonome, ne modifie que la structure interne du backend)

## État d'avancement technique
- [ ] Tâche 1 : Extraire les helpers utilitaires
- [ ] Tâche 2 : Extraire le classifier de containers
- [ ] Tâche 3 : Extraire les builders d'objets domaine
- [ ] Tâche 4 : Refactorer compute_service.py en orchestrateur
- [ ] Tâche 5 : Tests unitaires du classifier
- [ ] Tâche 6 : Tests unitaires des builders
- [ ] Tâche 7 : Valider que les tests existants passent

## Tâches d'implémentation détaillées
<!-- Section à remplir par la skill analyse-story -->

## Tests à écrire
<!-- Section à remplir par la skill analyse-story -->
