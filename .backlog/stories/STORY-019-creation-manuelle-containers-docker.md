# STORY-019 : Création manuelle de containers Docker

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux créer manuellement un container Docker depuis l'interface afin de lancer rapidement des containers sans passer par une stack ou un déploiement.

## Contexte technique
- Vue existante `views/Containers.vue`
- API : `POST /docker/containers`
- Formulaire complet : nom, image, variables d'environnement, ports, volumes, labels
- Extension de `containersApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : Un bouton "Créer un container" ouvre un formulaire avec les champs : nom, image, variables d'environnement (clé/valeur), ports (host:container), volumes
- [ ] AC 2 : La création appelle `POST /docker/containers` et le nouveau container apparaît dans la liste
- [ ] AC 3 : Les erreurs de création (image inexistante, port déjà utilisé) sont affichées clairement
- [ ] AC 4 : `containersApi.create` est disponible dans `services/api.ts`
- [ ] AC 5 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
