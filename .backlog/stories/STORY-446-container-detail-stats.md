# STORY-446 : ContainerDetail — onglet Stats temps réel

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les statistiques temps réel d'un container (CPU, RAM, réseau I/O) dans un onglet dédié afin de monitorer sa consommation de ressources.

## Critères d'acceptation (AC)
- [x] AC 1 : Onglet « Stats » dans ContainerDetail affichant CPU (%), RAM (utilisée/limit), Network I/O (rx/tx)
- [x] AC 2 : Graphiques temps réel (sparklines ou mini-charts) sur les 5 dernières minutes
- [x] AC 3 : Rafraîchissement automatique (WebSocket docker stats stream)
- [x] AC 4 : Barres de progression colorées pour CPU et RAM (réutilise `ResourceBar.vue` — STORY-423)
- [x] AC 5 : Affichage des valeurs numériques précises à côté des barres
- [x] AC 6 : L'onglet est désactivé si le container est en statut stopped
- [x] AC 7 : Les données proviennent de l'API Docker via WebSocket (`/api/v1/ws/docker/containers/{id}/stats`)

## État d'avancement technique
- [x] Vérification/création endpoint API stats par container (stream ou snapshot)
- [x] Composant `ContainerStats.vue` avec barres + mini-charts
- [x] Intégration comme onglet dans ContainerDetail
- [x] WebSocket pour le temps réel
- [x] Désactivation si container stopped
- [x] Tests Vitest (252 tests passent)

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/components/ContainerStats.vue` — Composant principal affichant les stats
- `frontend/src/composables/useContainerStats.ts` — Composable WebSocket pour le streaming
- `frontend/src/views/ContainerDetail.vue` — Intégration de l'onglet Stats
- `backend/app/websocket/container_stats.py` — WebSocket endpoint pour le streaming des stats
- `backend/tests/unit/test_docker/test_container_stats.py` — Tests backend

### Décisions techniques
1. **WebSocket vs Polling** : Utilisation de WebSocket pour le streaming temps réel (plus efficace que le polling)
2. **Sparklines** : Implémentation simple avec des barres CSS (pas de dépendance ECharts pour légèreté)
3. **Historique** : 60 entrées = 5 minutes de données (1 entrée/seconde environ)
4. **ResourceBar** : Réutilisation du composant existant pour les barres de progression

### Fonctionnalités implémentées
- CPU : Pourcentage avec barre colorée (vert < 60%, orange < 85%, rouge >= 85%)
- Mémoire : Pourcentage + détails (utilisé/limite en bytes formatés)
- Réseau : RX/TX en bytes
- Disque : Lecture/Écriture en bytes
- Graphiques ECharts pour CPU (%) et RAM (Ko/Mo/Go) sur les 60 dernières valeurs
- **Autoscale RAM** : Échelle automatique adaptée à la consommation (Ko/Mo/Go) avec unité dynamique
- Indicateur de connexion (tag coloré)
- Auto-refresh toggle et bouton de reconnexion manuelle
- Message d'erreur si échec de connexion

### Dernière mise à jour (20/03/2026)
- Graphique RAM : passage de % vers bytes (Ko/Mo/Go) avec échelle automatique
- Ajout de `memory_used` dans `StatsHistoryEntry` pour l'historique
- Fonction `getOptimalScale()` pour déterminer l'unité optimale
- Fonction `formatBytesAxis()` pour formater les valeurs dans le tooltip
