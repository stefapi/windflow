# STORY-007 : Support 3 types de plugins (service, extension, hybrid)

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Développeur, je veux que le système supporte 3 types de plugins (service, extension, hybrid) afin de couvrir les différents cas d'usage : services avec containers Docker, extensions pures de l'UI/API, et hybrides combinant les deux.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
- **Service** : plugin qui déploie un container Docker (ex: Traefik, PostgreSQL)
- **Extension** : plugin qui étend l'UI ou l'API sans container (ex: thème, dashboard widget)
- **Hybrid** : plugin combinant un service et une extension (ex: Uptime Kuma avec widget dashboard)
Le type est déclaré dans le manifest et influence le cycle de vie et les hooks disponibles.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le type de plugin est validé dans le manifest et influence le comportement du Plugin Manager
- [ ] AC 2 : Les plugins de type "service" gèrent un cycle de vie lié au container Docker (create/start/stop/remove)
- [ ] AC 3 : Les plugins de type "extension" s'enregistrent dans l'UI/API sans gestion de container
- [ ] AC 4 : Les plugins de type "hybrid" combinent correctement les deux comportements
- [ ] AC 5 : Build/lint/tests passent avec couverture ≥ 80%

## Dépendances
- STORY-001 : Format manifest YAML (spécification + validation Pydantic)
- STORY-002 : API REST Plugin Manager — CRUD plugins
- STORY-006 : Hooks lifecycle plugins

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
