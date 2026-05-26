# STORY-001 : Composable de Vocabulaire Mode App

**Statut :** TODO
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant que Développeur, je veux créer un composable `useAppVocabulary` centralisant la traduction des termes techniques en termes Mode App afin de garantir la cohérence du vocabulaire dans toute l'interface sans duplication.

## Contexte technique
Le Mode App est une couche de présentation frontend qui masque le vocabulaire technique (container, compose, stack, volume, network, image) derrière des termes grand public. Ce composable est la fondation utilisée par tous les composants de l'epic.

Mapping de termes : container → app, stack → app, target → serveur. Les termes compose, image, volume, network, deployment sont masqués (non affichés).

Le composable expose les fonctions `getAppStatus()`, `getAppActions()`, `getAppDisplayName()` et le mapping centralisé des termes.

Spécification de référence : [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md)

## Critères d'acceptation (AC)
- [ ] AC 1 : Le composable `useAppVocabulary` expose les fonctions `getAppStatus()`, `getAppActions()`, `getAppDisplayName()` et le mapping de termes techniques → Mode App
- [ ] AC 2 : Le mapping container→app, stack→app, target→serveur est centralisé et les termes masqués (compose, image, volume, network, deployment) ne sont jamais affichés en Mode App
- [ ] AC 3 : Le composable est utilisable par tout composant Vue via import standard et facilitera le futur Mode Infra (il suffira de ne pas appliquer le vocabulaire)
- [ ] AC 4 : Build, lint et tests unitaires passent

## Dépendances
- Aucune (story fondationnelle)

## État d'avancement techniques
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
