# STORY-505 : Refactoriser WindFlowLogo.vue + StatusBadge.vue + CounterCard.vue

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des composants UI réutilisables par des variables CSS thémées afin de garantir la cohérence visuelle sur l'ensemble de l'application.

## Contexte technique
Ces composants sont utilisés dans de multiples écrans du dashboard et doivent être parfaitement thémables.

Fichiers à modifier :
- `frontend/src/components/WindFlowLogo.vue`
- `frontend/src/components/StatusBadge.vue`
- `frontend/src/components/CounterCard.vue`

Règles de migration :
- Utiliser les variables de statut (`--color-success`, `--color-error`, `--color-warning`, `--color-info`)
- Utiliser les variables de texte et fond standard

## Critères d'acceptation (AC)
- [ ] AC 1 : Aucune couleur statique dans les `<style>` de WindFlowLogo.vue
- [ ] AC 2 : Aucune couleur statique dans les `<style>` de StatusBadge.vue
- [ ] AC 3 : Aucune couleur statique dans les `<style>` de CounterCard.vue
- [ ] AC 4 : Les statuts utilisent les variables CSS de couleur appropriées
- [ ] AC 5 : Le rendu visuel est identique en mode light et dark
- [ ] AC 6 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
