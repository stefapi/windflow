# STORY-011 : Mise à jour plugins avec affichage changelog

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux mettre à jour mes plugins installés vers la dernière version disponible avec affichage du changelog afin de comprendre les changements avant de procéder à la mise à jour.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Le système doit détecter les mises à jour disponibles en comparant la version installée avec la version disponible dans le registre. Le changelog (extrait du manifest ou fichier CHANGELOG.md du plugin) doit être affiché avant la mise à jour pour informer l'utilisateur.

## Critères d'acceptation (AC)
- [ ] AC 1 : L'UI affiche un badge de mise à jour disponible sur les plugins ayant une nouvelle version dans le registre
- [ ] AC 2 : Le changelog de la nouvelle version est affiché avant confirmation de la mise à jour
- [ ] AC 3 : La mise à jour préserve la configuration existante du plugin (migration si nécessaire)
- [ ] AC 4 : En cas d'échec de la mise à jour, un rollback automatique vers la version précédente est effectué
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-002 : API REST Plugin Manager — CRUD plugins
- STORY-009 : UI Marketplace — catalogue browsable avec fiches plugin

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
