# STORY-004 : Actions globales de stack (Start/Stop/Redeploy)

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux démarrer, arrêter et redéployer une stack entière depuis la vue Compute afin de contrôler le cycle de vie de mes stacks managées en un seul clic.

## Contexte technique
- Composant `components/StackActionsBar.vue` intégré dans la vue Compute
- APIs : `POST /stacks/{id}/start`, `POST /stacks/{id}/stop`, `POST /stacks/{id}/redeploy`
- Types TypeScript : `StackActionResponse`, `StackRedeployRequest`
- Icône start/stop avec confirmation avant exécution
- Icône refresh (redeploy) avec choix de stratégie rolling/stop-start
- Indicateur de progression pendant l'opération

## Critères d'acceptation (AC)
- [ ] AC 1 : Les boutons Start/Stop déclenchent `POST /stacks/{id}/start` et `POST /stacks/{id}/stop` avec une confirmation préalable
- [ ] AC 2 : Le bouton Redeploy ouvre un dialog permettant de choisir la stratégie (rolling/stop-start) avant de déclencher `POST /stacks/{id}/redeploy`
- [ ] AC 3 : Un indicateur de progression (spinner/loading) est affiché pendant l'opération en cours
- [ ] AC 4 : Une notification toast confirme le succès ou l'échec de chaque action
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-001 (Vue globale Compute — les actions s'intègrent dans la section Stacks)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
