# STORY-015 : Visualisation des réseaux Docker

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter la liste des réseaux Docker sur mes targets afin de comprendre la topologie réseau de mes containers et diagnostiquer les problèmes de connectivité.

## Contexte technique
- Vue existante `views/Networks.vue` (actuellement StubPage — à implémenter)
- API : `GET /docker/networks`
- Type TypeScript à ajouter : `NetworkResponse` dans `types/api.ts`
- Table avec colonnes : ID (court), Nom, Driver, Scope, Subnet, Gateway, Interne
- Ajout de `networksApi` dans `services/api.ts`

## Critères d'acceptation (AC)
- [ ] AC 1 : La vue Networks affiche la liste des réseaux via `GET /docker/networks` dans un tableau avec colonnes (Nom, Driver, Scope, Subnet/Gateway)
- [ ] AC 2 : Un badge distingue les réseaux internes (`internal: true`) des réseaux externes
- [ ] AC 3 : Le type TypeScript `NetworkResponse` est défini et `networksApi.list` est disponible
- [ ] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
