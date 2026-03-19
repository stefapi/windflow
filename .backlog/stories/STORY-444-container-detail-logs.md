# STORY-444 : ContainerDetail — onglet Logs

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux consulter les logs d'un container en temps réel dans un onglet dédié afin de diagnostiquer les problèmes sans SSH.

## Critères d'acceptation (AC)
- [x] AC 1 : Onglet « Logs » dans ContainerDetail affichant les logs du container
- [x] AC 2 : Nouveau composant `ContainerLogs.vue` créé (au lieu de réutiliser DeploymentLogs.vue pour séparation des responsabilités)
- [x] AC 3 : Logs en streaming temps réel via WebSocket (`/ws/docker/containers/{id}/logs?token=JWT`)
- [x] AC 4 : Bouton « Télécharger les logs » (export texte brut)
- [x] AC 5 : Option filtrer par niveau (stdout/stderr) - heuristique basée sur mots-clés error/warn/fail
- [x] AC 6 : Auto-scroll en bas avec bouton « Défiler vers le bas » si l'utilisateur a scrollé vers le haut
- [x] AC 7 : Police monospace JetBrains Mono
- [x] AC 8 : Les données proviennent de l'API Docker existante via WebSocket

## État d'avancement technique
- [x] Création du composable `useContainerLogs.ts` pour la gestion WebSocket
- [x] Création du composant `ContainerLogs.vue` avec toutes les fonctionnalités
- [x] Intégration comme onglet dans ContainerDetail.vue
- [x] Streaming WebSocket avec reconnexion automatique
- [x] Bouton téléchargement
- [x] Auto-scroll + bouton « aller en bas »
- [x] Filtre stdout/stderr (heuristique)
- [x] Tests Vitest (ContainerLogs.spec.ts)

## Notes d'implémentation

### Fichiers créés
- `frontend/src/composables/useContainerLogs.ts` — Composable de gestion WebSocket pour les logs
- `frontend/src/components/ContainerLogs.vue` — Composant d'affichage des logs
- `frontend/tests/unit/components/ContainerLogs.spec.ts` — Tests unitaires

### Fichiers modifiés
- `frontend/src/views/ContainerDetail.vue` — Ajout de l'onglet « Logs » utilisant ContainerLogs

### Décisions techniques
1. **Nouveau composant vs réutilisation** : Création d'un nouveau composant `ContainerLogs.vue` au lieu d'adapter `DeploymentLogs.vue` pour :
   - Séparation des responsabilités
   - Streaming temps réel via WebSocket (vs polling pour deployments)
   - Interface spécifique aux containers

2. **Filtrage stdout/stderr** : Implémenté via heuristique (détection de mots-clés error/warn/fail/exception/fatal) car Docker ne tag pas explicitement les lignes de logs

3. **WebSocket** : Connexion à `/api/v1/ws/docker/containers/{container_id}/logs?token=JWT&tail=N` avec :
   - Reconnexion automatique (max 5 tentatives)
   - Heartbeat toutes les 30 secondes
   - Gestion des états (connecting/connected/error/disconnected)

### À noter
- Le drawer logs existant est conservé pour l'instant (accessibilité rapide via bouton header)
- L'onglet Logs est actif par défaut quand l'utilisateur clique sur le bouton « Logs » du header
