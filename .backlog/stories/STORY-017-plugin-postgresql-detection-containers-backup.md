# STORY-017 : Plugin PostgreSQL — détection containers, create DB/users/grants, backup

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux installer le plugin PostgreSQL pour gérer mes bases de données (création de DB, utilisateurs, grants) avec support du backup afin de simplifier l'administration de mes instances PostgreSQL dans WindFlow.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
PostgreSQL est un plugin de type "service" qui déploie un container Docker PostgreSQL. Il doit détecter les containers PostgreSQL existants, permettre la création de bases de données, d'utilisateurs et de grants via l'UI, et offrir des fonctionnalités de backup/restore. Doit fonctionner sur arm64.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le plugin installe un container PostgreSQL fonctionnel avec configuration initiale (user, password, port)
- [ ] AC 2 : L'UI permet de créer/supprimer des bases de données, des utilisateurs et de gérer les grants
- [ ] AC 3 : Le plugin détecte les containers PostgreSQL existants sur le host et propose de les gérer
- [ ] AC 4 : Les fonctionnalités de backup et restore sont disponibles via l'UI
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-002 : API REST Plugin Manager — CRUD plugins
- STORY-006 : Hooks lifecycle plugins
- STORY-007 : Support 3 types de plugins (service, extension, hybrid)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
