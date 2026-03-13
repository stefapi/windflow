# STORY-446 : ContainerDetail — onglet Stats temps réel

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les statistiques temps réel d'un container (CPU, RAM, réseau I/O) dans un onglet dédié afin de monitorer sa consommation de ressources.

## Critères d'acceptation (AC)
- [ ] AC 1 : Onglet « Stats » dans ContainerDetail affichant CPU (%), RAM (utilisée/limit), Network I/O (rx/tx)
- [ ] AC 2 : Graphiques temps réel (sparklines ou mini-charts) sur les 5 dernières minutes
- [ ] AC 3 : Rafraîchissement automatique (polling 5s ou WebSocket docker stats stream)
- [ ] AC 4 : Barres de progression colorées pour CPU et RAM (réutilise `ResourceBar.vue` — STORY-423)
- [ ] AC 5 : Affichage des valeurs numériques précises à côté des barres
- [ ] AC 6 : L'onglet est désactivé si le container est en statut stopped
- [ ] AC 7 : Les données proviennent de l'API Docker (`/api/v1/docker/containers/{id}/stats`)

## État d'avancement technique
- [ ] Vérification/création endpoint API stats par container (stream ou snapshot)
- [ ] Composant `ContainerStats.vue` avec barres + mini-charts
- [ ] Intégration comme onglet dans ContainerDetail
- [ ] Polling ou WebSocket pour le temps réel
- [ ] Désactivation si container stopped
- [ ] Tests Vitest
