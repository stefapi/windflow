# STORY-002 : API REST Plugin Manager — CRUD plugins (install/update/uninstall)

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux une API REST complète pour gérer le cycle de vie des plugins (install, update, uninstall, list, get) afin de permettre à l'UI et à la CLI d'interagir avec le système de plugins.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Approche API-first : toutes les opérations plugin sont disponibles via API REST avant UI/CLI. Les endpoints doivent supporter l'installation depuis un registre, la mise à jour vers une nouvelle version, et la désinstallation propre avec nettoyage des ressources.

## Critères d'acceptation (AC)
- [ ] AC 1 : Les endpoints REST couvrent les opérations CRUD complètes : `GET /plugins`, `GET /plugins/{id}`, `POST /plugins/install`, `PUT /plugins/{id}/update`, `DELETE /plugins/{id}/uninstall`
- [ ] AC 2 : L'installation valide le manifest via le schéma Pydantic (STORY-001) avant de procéder
- [ ] AC 3 : Chaque opération retourne des codes HTTP appropriés et des messages d'erreur structurés
- [ ] AC 4 : Les opérations longues (install/update) sont asynchrones avec suivi via WebSocket
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
