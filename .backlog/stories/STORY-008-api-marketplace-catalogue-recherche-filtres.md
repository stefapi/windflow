# STORY-008 : API Marketplace — catalogue, recherche, filtres par catégorie

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux une API Marketplace permettant de parcourir le catalogue de plugins, rechercher et filtrer par catégorie afin de fournir les données nécessaires à l'UI Marketplace et à la CLI.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
L'API Marketplace interroge le registre de plugins (officiel et custom) et expose un catalogue unifié. Les plugins sont organisés par catégories (reverse-proxy, database, monitoring, etc.). La recherche doit supporter le texte libre et les filtres combinés.

## Critères d'acceptation (AC)
- [ ] AC 1 : L'endpoint `GET /marketplace/plugins` retourne la liste paginée des plugins disponibles avec leurs métadonnées
- [ ] AC 2 : Un endpoint de recherche `GET /marketplace/search?q=...&category=...&type=...` supporte la recherche textuelle et les filtres par catégorie et type
- [ ] AC 3 : L'endpoint `GET /marketplace/plugins/{id}` retourne la fiche détaillée d'un plugin (manifest, readme, changelog)
- [ ] AC 4 : Les résultats incluent la distinction officiel vs communautaire et les informations de version
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-013 : Registre officiel (index JSON ou API simple)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
