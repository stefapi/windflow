# STORY-017 : Détection des shells disponibles dans le terminal

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux que le terminal container détecte automatiquement les shells disponibles afin de me connecter avec le shell le plus adapté plutôt qu'une sélection statique prédéfinie.

## Contexte technique
- Composant existant `components/ContainerTerminal.vue`
- API : `GET /docker/containers/{id}/shells`
- Type TypeScript à ajouter : `ContainerShell`
- Remplacement de la liste statique de shells par un dropdown chargé dynamiquement
- Extension de `containersApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : À l'ouverture du terminal, les shells disponibles sont chargés via `GET /docker/containers/{id}/shells`
- [ ] AC 2 : Un dropdown permet de sélectionner le shell parmi ceux détectés (ex: /bin/bash, /bin/sh, /bin/zsh)
- [ ] AC 3 : Si aucun shell n'est disponible ou si l'appel échoue, un fallback sur `/bin/sh` est appliqué
- [ ] AC 4 : Le type TypeScript `ContainerShell` est défini et `containersApi.getShells` est disponible
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
