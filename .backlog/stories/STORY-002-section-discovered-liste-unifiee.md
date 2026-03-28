# STORY-002 : [ABANDONED] Section Discovered — liste unifiée (containers, compositions, releases Helm)

**Statut :** ABANDONED
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux visualiser dans la vue Compute tous les objets découverts non managés (containers orphelins, compositions Docker Compose, releases Helm) dans une section unifiée afin de détecter et gérer les ressources qui ne sont pas encore sous contrôle WindFlow.

## Contexte technique
- Composant `components/DiscoveredSection.vue` intégré dans la vue Compute
- API : `GET /discovery/items` (remplace les anciens `/discovery/containers` et `/discovery/compositions`)
- Types TypeScript : `DiscoveredItem`, `DiscoveredService`
- Cards expandables avec badge technologie (Docker/Compose/Helm)
- Compteur "N/N running" dans le header de chaque card
- Affichage du `source_path` si disponible (ex: "/home/user/monitoring/docker-compose.yml")
- Actions disponibles par card : [👁 Voir] [↗ Adopter]

## Critères d'acceptation (AC)
- [ ] AC 1 : La section Discovered affiche les items découverts via `GET /discovery/items` avec badge technologie (Docker/Compose/Helm)
- [ ] AC 2 : Chaque card affiche le compteur de services "N/N running" et le `source_path` si disponible
- [ ] AC 3 : Les cards sont expandables pour révéler les services individuels
- [ ] AC 4 : Les actions [Voir] et [Adopter] sont présentes sur chaque card adoptable
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Note d'abandon
Cette story a été découpée en deux stories plus ciblées :
- **STORY-002 (nouvelle)** : Backend — Refactoring des services de listage Docker (`STORY-002-refactoring-services-listage-docker.md`)
- **STORY-022** : Frontend — Refactoring de Compute.vue en sous-composants (`STORY-022-refactoring-compute-vue-sous-composants.md`)

La raison : séparer les préoccupations backend (structuration des services) et frontend (découpage en composants) en stories indépendantes avec une relation de dépendance claire.

## Dépendances
- STORY-001 (Vue globale Compute — la section s'intègre dans cette vue)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
