# STORY-029 : Backend + Frontend — Métriques Network I/O et Disk I/O dans Stats

**Statut :** DONE

**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description

En tant qu'utilisateur, je veux voir les métriques Network I/O (débit montant/descendant réseau) et Disk I/O (débit lecture/écriture disque) dans l'onglet Stats du Container Detail afin de pouvoir surveiller l'activité réseau et disque du container en temps réel.

## Contexte technique

L'onglet Stats actuel affiche CPU et Memory. Le backend retourne déjà les données brutes du Docker daemon (networks et blkio_stats). Il faut enrichir le backend pour extraire les métriques par interface/device, et enrichir le frontend pour afficher les débits calculés par delta, les compteurs cumulatifs, les badges warning pour errors/drops, et les mini-graphiques temporels.

## Critères d'acceptation (AC)

- [x] AC 1 : Le schéma de réponse des stats inclut un objet network avec les métriques par interface réseau
- [x] AC 2 : Le schéma de réponse des stats inclut un objet blkio avec les métriques par device
- [x] AC 3 : L'onglet Stats affiche une section Network I/O avec débits en KB/s ou MB/s
- [x] AC 4 : L'onglet Stats affiche une section Disk I/O avec débits en MB/s
- [x] AC 5 : Les métriques I/O sont affichées sous forme de mini-graphiques temporels
- [x] AC 6 : Les compteurs cumulatifs (total bytes depuis le démarrage) sont aussi affichés
- [x] AC 7 : Si le container est arrêté, les sections I/O affichent "Non disponible"
- [x] AC 8 : Les erreurs et drops réseau sont affichés en surbrillance si > 0 (badge warning)

## Sous-stories

- [x] STORY-029.1 : Backend — Enrichissement des métriques Network et Block I/O — Couvre AC 1, AC 2
- [x] STORY-029.2 : Frontend — Affichage débits, badges et graphiques enrichis Network/Disk I/O — Couvre AC 3, AC 4, AC 5, AC 6, AC 7, AC 8

## Dépendances

STORY-029.2 dépend de STORY-029.1

## État d'avancement technique

- [x] Backend : Structurer les métriques network et blkio dans le schéma de stats
- [x] Frontend : Ajouter les sections Network I/O et Disk I/O dans l'onglet Stats
- [x] Frontend : Calculer les débits par delta entre échantillons
- [x] Frontend : Afficher les mini-graphiques temporels
- [x] Frontend : Afficher les compteurs cumulatifs et erreurs

## Tâches d'implémentation détaillées

Voir les sous-stories STORY-029.1 et STORY-029.2 pour les tâches détaillées.

## Tests à écrire

Voir les sous-stories STORY-029.1 et STORY-029.2 pour les tests détaillés.

## Notes d'implémentation

### Fichiers modifiés (backend — STORY-029.1)
- `backend/app/schemas/docker.py` — Ajout `NetworkInterfaceInfo`, `BlkioDeviceStatsInfo`, enrichissement `ContainerStatsResponse`
- `backend/app/services/docker_client_service.py` — Extraction métriques par interface/device, calcul totaux errors/drops/IOPS
- `backend/app/websocket/container_stats.py` — Enrichissement du message WebSocket avec données détaillées
- `backend/tests/unit/test_docker/test_container_stats.py` — Tests backend

### Fichiers modifiés (frontend — STORY-029.2)
- `frontend/src/composables/useContainerStats.ts` — Interfaces `NetworkInterfaceData`, `BlkioDeviceData`, calcul delta rates, parsing enrichi
- `frontend/src/components/ContainerStats.vue` — Sections Network/Disk enrichies, graphiques rates, badges warning
- `frontend/tests/unit/components/ContainerStats.spec.ts` — 15 tests unitaires

### Validation
- type-check : 0 erreur | build : succès | tests : 468/468 passés
