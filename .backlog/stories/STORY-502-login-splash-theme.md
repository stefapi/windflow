# STORY-502 : Refactoriser Login.vue + SplashScreen.vue → variables CSS thémées

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques (hex, rgb, rgba) des composants Login.vue et SplashScreen.vue par des variables CSS thémées afin d'assurer la cohérence visuelle et le support dark/light theme.

## Contexte technique
Ces deux composants sont parmi les plus visibles de l'application (~30 occurrences de couleurs statiques). Ils constituent la première impression utilisateur.

Fichiers à modifier :
- `frontend/src/views/Login.vue`
- `frontend/src/views/SplashScreen.vue`

Règles de migration :
- `#0c0e14` → `var(--color-bg-primary)`
- `#1e1e1e` → `var(--color-bg-secondary)`
- `#d4d4d4` → `var(--color-text-primary)`
- `#7c8098` → `var(--color-text-secondary)`

## Critères d'acceptation (AC)
- [ ] AC 1 : Aucune couleur statique (hex, rgb, rgba) dans les `<style>` de Login.vue
- [ ] AC 2 : Aucune couleur statique (hex, rgb, rgba) dans les `<style>` de SplashScreen.vue
- [ ] AC 3 : Les deux composants utilisent les variables CSS ou classes UnoCSS
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
