# STORY-431 : Barre métriques système sur le dashboard

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les métriques système du target actif (CPU, RAM, disque, uptime) en haut du dashboard afin de connaître l'état de ma machine d'un coup d'œil.

## Critères d'acceptation (AC)
- [ ] AC 1 : Une barre horizontale en haut du dashboard affiche CPU (%), RAM (utilisée/totale), disque (utilisé/total), uptime
- [ ] AC 2 : Chaque métrique utilise le composant `ResourceBar.vue` (STORY-423)
- [ ] AC 3 : Les métriques sont rafraîchies automatiquement (polling toutes les 30s ou WebSocket)
- [ ] AC 4 : Les métriques correspondent au target actuellement sélectionné
- [ ] AC 5 : Si le target est injoignable, un message d'erreur clair est affiché
- [ ] AC 6 : L'API backend `/api/v1/targets/{id}/stats` fournit les données (à créer ou enrichir si nécessaire)

## État d'avancement technique
- [ ] Vérification de l'endpoint API existant pour les stats target
- [ ] Création/enrichissement de l'endpoint si nécessaire (CPU, RAM, disque, uptime)
- [ ] Composant `SystemMetricsBar.vue` utilisant `ResourceBar.vue`
- [ ] Intégration au Dashboard avec polling ou WebSocket
- [ ] Gestion du cas target injoignable
- [ ] Tests Vitest du composant
- [ ] Test API backend (pytest)
