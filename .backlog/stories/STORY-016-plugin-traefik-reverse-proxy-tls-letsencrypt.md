# STORY-016 : Plugin Traefik — reverse proxy + TLS automatique Let's Encrypt

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux installer le plugin Traefik pour configurer un reverse proxy avec TLS automatique via Let's Encrypt afin d'exposer mes services avec des domaines et certificats HTTPS automatiques.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Traefik est un plugin de type "service" qui déploie un container Docker Traefik. Il doit supporter la configuration des entrypoints, providers Docker, certificats Let's Encrypt (challenge HTTP/TLS), et les middlewares courants. C'est le premier plugin validant le système de bout en bout. Doit fonctionner sur arm64.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le plugin installe un container Traefik fonctionnel configuré comme reverse proxy avec provider Docker
- [ ] AC 2 : Le TLS automatique via Let's Encrypt est configuré et fonctionne avec un domaine valide
- [ ] AC 3 : La configuration du plugin (entrypoints, email ACME, domaines) est accessible via formulaire dynamique dans l'UI
- [ ] AC 4 : Le plugin fonctionne sur arm64 et amd64
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
