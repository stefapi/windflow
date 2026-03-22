# STORY-504 : Refactoriser ContainerTerminal.vue → variables CSS thémées (palette VS Code)

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques du composant ContainerTerminal par les variables CSS de la palette terminal VS Code afin d'assurer un affichage cohérent et thémable du terminal.

## Contexte technique
Le composant terminal est critique pour l'expérience développeur. Il doit reproduire fidèlement une expérience de terminal type VS Code avec support des 16 couleurs ANSI.

Fichier à modifier :
- `frontend/src/components/ContainerTerminal.vue`

Variables CSS à utiliser :
- `--color-terminal-bg` pour le fond
- `--color-terminal-fg` pour le texte
- `--color-terminal-cursor` pour le curseur
- `--color-terminal-red/green/yellow/blue/magenta/cyan/white` pour les couleurs ANSI
- `--color-terminal-bright-*` pour les variantes claires

## Critères d'acceptation (AC)
- [ ] AC 1 : Aucune couleur statique dans les `<style>` de ContainerTerminal.vue
- [ ] AC 2 : Le terminal utilise les variables CSS `--color-terminal-*`
- [ ] AC 3 : Les 16 couleurs ANSI sont correctement thémées
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
