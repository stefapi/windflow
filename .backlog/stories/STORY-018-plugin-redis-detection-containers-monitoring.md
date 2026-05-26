# STORY-018 : Plugin Redis — détection containers, monitoring clés/stats

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux installer le plugin Redis pour surveiller mes instances Redis (clés, statistiques, mémoire) afin de simplifier le monitoring et la gestion de mon cache dans WindFlow.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Redis est un plugin de type "service" qui déploie un container Docker Redis. Il doit détecter les containers Redis existants, offrir un dashboard de monitoring (clés, hit/miss ratio, mémoire utilisée, connexions), et permettre les opérations courantes (flush, config). Doit fonctionner sur arm64.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le plugin installe un container Redis fonctionnel avec configuration initiale (port, password, maxmemory)
- [ ] AC 2 : L'UI affiche un dashboard de monitoring avec les métriques clés (mémoire, clés, hit ratio, connexions)
- [ ] AC 3 : Le plugin détecte les containers Redis existants sur le host et propose de les monitorer
- [ ] AC 4 : Les opérations courantes (FLUSHDB, CONFIG GET/SET) sont accessibles via l'UI
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
