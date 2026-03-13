# STORY-441 : Vue Containers — liste avec actions inline

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une vue liste de tous mes containers Docker avec des actions inline (start/stop/restart/logs/supprimer) afin d'agir directement sans ouvrir le détail.

## Critères d'acceptation (AC)
- [ ] AC 1 : La vue `Containers.vue` remplace `Deployments.vue` sur la route `/containers`
- [ ] AC 2 : Tableau affichant : nom, image, statut (badge coloré), ports, actions
- [ ] AC 3 : Actions inline par container : Start (si stopped), Stop (si running), Restart, Logs (ouvre un drawer), Supprimer (avec confirmation)
- [ ] AC 4 : Les actions utilisent le composant `ActionButtons.vue` (STORY-423)
- [ ] AC 5 : Le statut utilise le composant `StatusBadge.vue` (STORY-423)
- [ ] AC 6 : Cliquer sur le nom du container mène au détail (`/containers/:id`)
- [ ] AC 7 : Les données proviennent de l'API Docker existante (`/api/v1/docker/containers`)
- [ ] AC 8 : Les actions appellent les endpoints Docker existants (start/stop/restart/remove)
- [ ] AC 9 : Notification Element Plus après chaque action (succès/erreur)

## État d'avancement technique
- [ ] Création de `frontend/src/views/Containers.vue`
- [ ] Mise à jour du router (remplacer route Deployments par Containers)
- [ ] Intégration tableau Element Plus (el-table)
- [ ] Composant actions inline par ligne
- [ ] Service frontend pour appels API Docker containers
- [ ] Notifications succès/erreur
- [ ] Suppression ou redirection de l'ancienne vue `Deployments.vue`
- [ ] Tests Vitest
