# STORY-507 : Refactoriser Stacks.vue + ContainerDetail.vue (code blocks)

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des vues Stacks et ContainerDetail par les classes UnoCSS et variables CSS afin d'uniformiser l'affichage des blocs de code et informations détaillées.

## Contexte technique
Ces vues affichent des informations techniques avec des blocs de code (~20 occurrences de couleurs statiques). Elles nécessitent l'utilisation des shortcuts `code-block` et `code-console`.

Fichiers à modifier :
- `frontend/src/views/Stacks.vue`
- `frontend/src/views/ContainerDetail.vue`

Shortcuts UnoCSS à utiliser :
- `code-block` pour les blocs de code statiques
- `code-console` pour les sorties console

## Critères d'acceptation (AC)
- [ ] AC 1 : Aucune couleur statique dans les `<style>` de Stacks.vue
- [ ] AC 2 : Aucune couleur statique dans les `<style>` de ContainerDetail.vue
- [ ] AC 3 : Les blocs de code utilisent les classes UnoCSS `code-block` ou `code-console`
- [ ] AC 4 : Le rendu visuel est identique en mode light et dark
- [ ] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
