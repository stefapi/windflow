# STORY-432 : Tuiles compteurs Containers / VMs / Stacks

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux voir des tuiles synthétiques sur le dashboard (Containers, VMs, Stacks) avec le nombre de ressources par statut afin de connaître l'état global de mon infrastructure.

## Critères d'acceptation (AC)
- [x] AC 1 : 3 tuiles compteurs affichées : Containers, VMs, Stacks
- [x] AC 2 : Chaque tuile montre : nombre running (🟢), nombre stopped (🔴), total
- [x] AC 3 : Chaque tuile est cliquable et redirige vers la liste correspondante
- [x] AC 4 : Les tuiles utilisent le composant `CounterCard.vue` (STORY-423)
- [x] AC 5 : La tuile VMs affiche « Coming soon » (badge info) tant qu'EPIC-002 n'est pas livrée
- [x] AC 6 : Les données proviennent de l'API `/api/v1/stats/dashboard` (endpoint existant étendu)
- [x] AC 7 : Les compteurs se mettent à jour automatiquement (polling 30s)
## État d'avancement technique
- [x] Extension endpoint API `/api/v1/stats/dashboard` avec ResourceCounter
- [x] Intégration des 3 `CounterCard.vue` dans le Dashboard
- [x] Liaison clics → routes /containers, /vms, /stacks
- [x] Gestion du cas VMs non disponibles (badge "Coming soon")
- [x] Polling automatique (30s via Dashboard.vue)
- [x] Tests Vitest (15 tests passants)

## Notes d'implémentation

### Fichiers modifiés/créés
- `backend/app/schemas/dashboard.py` — Ajout du schéma `ResourceCounter`
- `backend/app/api/v1/stats.py` — Extension de l'endpoint avec compteurs containers/VMs/stacks
- `frontend/src/types/api.ts` — Ajout des types TypeScript `ResourceCounter` et mise à jour `DashboardStats`
- `frontend/src/stores/dashboard.ts` — Ajout des getters `containers`, `vms`, `stacks`, `vmsAvailable`
- `frontend/src/components/ui/CounterCard.vue` — Ajout des props `runningCount`, `stoppedCount` et de l'affichage des indicateurs
- `frontend/src/views/Dashboard.vue` — Intégration des 3 tuiles avec les nouveaux compteurs
- `frontend/tests/unit/components/ui/CounterCard.spec.ts` — Ajout de 4 tests pour les indicateurs running/stopped

### Décisions techniques
1. **Réutilisation de CounterCard.vue** : Extension du composant existant avec de nouveaux props plutôt que création d'un nouveau composant
2. **VMs en stub** : La tuile VMs affiche un badge "Coming soon" car EPIC-002 n'est pas livrée
3. **Backend gracieux** : L'endpoint retourne des compteurs vides pour les VMs avec `vms_available: false`
4. **Indicateurs visuels** : Utilisation d'emojis 🟢/🔴 pour une reconnaissance visuelle immédiate
