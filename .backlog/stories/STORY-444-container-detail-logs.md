# STORY-444 : ContainerDetail — onglet Logs

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux consulter les logs d'un container en temps réel dans un onglet dédié afin de diagnostiquer les problèmes sans SSH.

## Critères d'acceptation (AC)
- [ ] AC 1 : Onglet « Logs » dans ContainerDetail affichant les logs du container
- [ ] AC 2 : Réutilise le composant existant `DeploymentLogs.vue` (adapté si nécessaire)
- [ ] AC 3 : Logs en streaming temps réel via WebSocket ou SSE
- [ ] AC 4 : Bouton « Télécharger les logs » (export texte brut)
- [ ] AC 5 : Option filtrer par niveau (stdout/stderr) si possible
- [ ] AC 6 : Auto-scroll en bas avec bouton « Défiler vers le bas » si l'utilisateur a scrollé vers le haut
- [ ] AC 7 : Police monospace JetBrains Mono (STORY-422)
- [ ] AC 8 : Les données proviennent de l'API Docker existante (`/api/v1/docker/containers/{id}/logs`)

## État d'avancement technique
- [ ] Adaptation de `DeploymentLogs.vue` en composant réutilisable (props container_id)
- [ ] Intégration comme onglet dans ContainerDetail
- [ ] Streaming WebSocket/SSE
- [ ] Bouton téléchargement
- [ ] Auto-scroll + bouton « aller en bas »
- [ ] Tests Vitest
