# STORY-019 : Plugin Uptime Kuma — déploiement + widget status dashboard

**Statut :** TODO
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant qu'Utilisateur, je veux installer le plugin Uptime Kuma pour surveiller la disponibilité de mes services avec un widget de status intégré au dashboard WindFlow afin d'avoir une vue centralisée de la santé de mon infrastructure.

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->
Uptime Kuma est un plugin de type "hybrid" : il déploie un container Docker Uptime Kuma (service) ET ajoute un widget de status sur le dashboard WindFlow (extension). Ce plugin valide le support des plugins hybrides. Doit fonctionner sur arm64.

## Critères d'acceptation (AC)
- [ ] AC 1 : Le plugin installe un container Uptime Kuma fonctionnel accessible via l'UI WindFlow
- [ ] AC 2 : Un widget de status est ajouté au dashboard WindFlow affichant l'état des services monitorés
- [ ] AC 3 : La configuration des services à monitorer est accessible via le formulaire dynamique du plugin
- [ ] AC 4 : Le plugin fonctionne correctement comme type "hybrid" (service + extension)
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
