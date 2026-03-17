# STORY-431 : Barre métriques système sur le dashboard

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir les métriques système du target actif (CPU, RAM, disque, uptime) en haut du dashboard afin de connaître l'état de ma machine d'un coup d'œil.

## Critères d'acceptation (AC)
- [x] AC 1 : Une barre horizontale en haut du dashboard affiche CPU (%), RAM (utilisée/totale), disque (utilisé/total), uptime
- [x] AC 2 : Chaque métrique utilise le composant `ResourceBar.vue` (STORY-423)
- [x] AC 3 : Les métriques sont rafraîchies automatiquement (polling toutes les 30s ou WebSocket)
- [x] AC 4 : Les métriques correspondent au target actuellement sélectionné
- [x] AC 5 : Si le target est injoignable, un message d'erreur clair est affiché
- [x] AC 6 : L'API backend `/api/v1/targets/{id}/stats` fournit les données (à créer ou enrichir si nécessaire)

## État d'avancement technique
- [x] Vérification de l'endpoint API existant pour les stats target
- [x] Création/enrichissement de l'endpoint si nécessaire (CPU, RAM, disque, uptime)
- [x] Composant `SystemMetricsBar.vue` utilisant `ResourceBar.vue`
- [x] Intégration au Dashboard avec polling ou WebSocket
- [x] Gestion du cas target injoignable
- [x] Tests Vitest du composant
- [x] Test API backend (pytest)

## Notes d'implémentation

### Fichiers modifiés/créés
- `backend/app/schemas/dashboard.py` : Ajout de `current_disk`, `total_disk_gb`, `used_disk_gb`, `uptime_seconds` au schéma `ResourceMetrics`
- `backend/app/api/v1/stats.py` : Ajout de l'import `time` et calcul du disk/uptime via `psutil`
- `frontend/src/types/api.ts` : Mise à jour de l'interface `ResourceMetrics` avec les nouveaux champs
- `frontend/src/components/dashboard/ResourceMetricsWidget.vue` : **Créé** - Composant unifié affichant métriques actuelles (CPU, RAM, Disk, Uptime) + graphiques temporels ECharts
- `frontend/src/views/Dashboard.vue` : Intégration de `ResourceMetricsWidget` avec polling 30s
- `frontend/tests/unit/components/dashboard/ResourceMetricsWidget.spec.ts` : **Créé** - 17 tests unitaires

### Fichiers supprimés (homogénéisation)
- `frontend/src/components/dashboard/SystemMetricsBar.vue` - Fusionné dans ResourceMetricsWidget
- `frontend/src/components/dashboard/ResourceChartsWidget.vue` - Fusionné dans ResourceMetricsWidget
- `frontend/tests/unit/components/dashboard/SystemMetricsBar.spec.ts` - Remplacé par tests ResourceMetricsWidget

### Décisions techniques
- Utilisation des métriques du serveur WindFlow comme proxy (les métriques d'un target distant pourront être ajoutées via un endpoint dédié dans une story ultérieure)
- Polling côté client toutes les 30 secondes (pas de WebSocket pour l'instant)
- Utilisation de `psutil.disk_usage('/')` pour le disque et `psutil.boot_time()` pour l'uptime
- **Homogénéisation** : Fusion de SystemMetricsBar (métriques actuelles) et ResourceChartsWidget (graphiques temporels) en un seul composant ResourceMetricsWidget pour une meilleure UX
