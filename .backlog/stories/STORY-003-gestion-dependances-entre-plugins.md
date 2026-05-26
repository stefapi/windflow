# STORY-003 : Gestion des dépendances entre plugins

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que le système de plugins gère les dépendances déclarées entre plugins afin de garantir qu'un plugin ne peut être installé que si ses dépendances sont satisfaites, et qu'un plugin ne peut être désinstallé si d'autres en dépendent.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Le manifest YAML permet de déclarer des dépendances vers d'autres plugins (nom + version). Le système doit résoudre ces dépendances à l'installation, vérifier la compatibilité des versions, et empêcher les désinstallations qui casseraient l'arbre de dépendances.

## Critères d'acceptation (AC)
- [ ] AC 1 : À l'installation, le système vérifie que toutes les dépendances déclarées sont présentes et dans une version compatible
- [ ] AC 2 : À la désinstallation, le système bloque l'opération si d'autres plugins installés dépendent du plugin ciblé
- [ ] AC 3 : L'installation automatique des dépendances manquantes est supportée (résolution transitive)
- [ ] AC 4 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-002 : API REST Plugin Manager — CRUD plugins

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
