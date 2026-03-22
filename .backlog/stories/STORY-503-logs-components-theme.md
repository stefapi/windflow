# STORY-503 : Refactoriser ContainerLogs.vue + DeploymentLogs.vue → classes UnoCSS

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des composants de logs par les classes UnoCSS dédiées afin d'unifier l'affichage des logs et garantir le support du thème.

## Contexte technique
Ces composants affichent les logs de déploiement et de containers (~50 occurrences de couleurs statiques). Ils utilisent des couleurs spécifiques pour les niveaux de log (error, warning, info, debug).

Fichiers à modifier :
- `frontend/src/components/ContainerLogs.vue`
- `frontend/src/components/DeploymentLogs.vue`

Shortcuts UnoCSS à utiliser :
- `log-error` pour les messages d'erreur
- `log-warning` pour les avertissements
- `log-info` pour les informations
- `log-debug` pour les messages de debug
- `log-line-number` pour les numéros de ligne

## Critères d'acceptation (AC)
- [ ] AC 1 : Aucune couleur statique dans les `<style>` de ContainerLogs.vue
- [ ] AC 2 : Aucune couleur statique dans les `<style>` de DeploymentLogs.vue
- [ ] AC 3 : Les niveaux de log utilisent les classes UnoCSS `log-*`
- [ ] AC 4 : Le rendu visuel des logs est identique en mode light et dark
- [ ] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
