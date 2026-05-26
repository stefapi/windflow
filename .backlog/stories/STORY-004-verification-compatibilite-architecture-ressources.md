# STORY-004 : Vérification compatibilité architecture (arm64/amd64) et ressources

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que le système vérifie la compatibilité d'un plugin avec l'architecture matérielle (arm64/amd64) et les ressources disponibles du host afin de prévenir les installations incompatibles ou insuffisantes.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
WindFlow cible les RPi (arm64) et les serveurs classiques (amd64). Chaque plugin déclare ses architectures supportées et ses ressources minimales dans le manifest. La vérification doit se faire avant l'installation. Les 4 premiers plugins doivent fonctionner sur arm64.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le système détecte l'architecture du host et la compare avec les architectures déclarées dans le manifest du plugin
- [ ] AC 2 : Le système vérifie les ressources disponibles (CPU, RAM, disque) par rapport aux exigences minimales du plugin
- [ ] AC 3 : Un message d'erreur clair est retourné si le plugin est incompatible avec l'architecture ou les ressources
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
