# STORY-441 : Vue Containers — liste avec actions inline

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une vue liste de tous mes containers Docker avec des actions inline (start/stop/restart/logs/supprimer) afin d'agir directement sans ouvrir le détail.

## Critères d'acceptation (AC)
- [x] AC 1 : La vue `Containers.vue` remplace `Deployments.vue` sur la route `/containers`
- [x] AC 2 : Tableau affichant : nom, image, statut (badge coloré), ports, actions
- [x] AC 3 : Actions inline par container : Start (si stopped), Stop (si running), Restart, Logs (ouvre un drawer), Supprimer (avec confirmation)
- [x] AC 4 : Les actions utilisent le composant `ActionButtons.vue` (STORY-423)
- [x] AC 5 : Le statut utilise le composant `StatusBadge.vue` (STORY-423)
- [x] AC 6 : Cliquer sur le nom du container mène au détail (`/containers/:id`)
- [x] AC 7 : Les données proviennent de l'API Docker existante (`/api/v1/docker/containers`)
- [x] AC 8 : Les actions appellent les endpoints Docker existants (start/stop/restart/remove)
- [x] AC 9 : Notification Element Plus après chaque action (succès/erreur)

## État d'avancement technique
- [x] Création de `frontend/src/views/Containers.vue`
- [x] Mise à jour du router (remplacer route Deployments par Containers)
- [x] Intégration tableau Element Plus (el-table)
- [x] Composant actions inline par ligne
- [x] Service frontend pour appels API Docker containers
- [x] Notifications succès/erreur
- [x] Suppression ou redirection de l'ancienne vue `Deployments.vue`
- [x] Tests Vitest

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/types/api.ts` - Ajout des types `Container`, `ContainerPort`, `ContainerLogsResponse`, `ContainerState`
- `frontend/src/services/api.ts` - Ajout de `containersApi` avec méthodes list, get, start, stop, restart, remove, getLogs
- `frontend/src/stores/containers.ts` - Création du store Pinia pour la gestion des containers
- `frontend/src/stores/index.ts` - Export du store containers
- `frontend/src/views/Containers.vue` - Réécriture complète de la vue (stub → vue fonctionnelle)
- `frontend/tests/unit/views/Containers.spec.ts` - Tests unitaires

### Décisions techniques
1. **Store Pinia** : Utilisation du pattern Composition API avec `defineStore` et setup function
2. **Mapping des statuts** : Les états Docker (`running`, `exited`, etc.) sont mappés vers les types `StatusType` du composant `StatusBadge`
3. **Actions conditionnelles** : Les actions start/stop/restart sont désactivées selon l'état du container
4. **Drawer pour logs** : Affichage des logs dans un drawer latéral avec possibilité de rafraîchir et ajuster le nombre de lignes
5. **Dialog de confirmation** : Suppression avec option "forcer" pour les containers en cours d'exécution

### Fonctionnalités implémentées
- Tableau avec colonnes : Nom (cliquable), Image, Statut, État, Ports, Actions
- Badges de compteur dans le header (Running/Stopped)
- Bouton de rafraîchissement avec loading state
- Gestion des erreurs avec alerte dismissable
- Formatage des ports avec tooltip pour les images
- Actions inline avec `ActionButtons` (start, stop, restart, logs, delete)
- Notifications Element Plus pour chaque action (succès/erreur)
