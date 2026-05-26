# STORY-002 : Refonte Sidebar — Navigation Mode App

**Statut :** TODO
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux une sidebar simplifiée en Mode App (Dashboard, Apps, Marketplace, Plugins, Settings) afin de naviguer dans l'interface avec un vocabulaire non-technique adapté à une expérience grand public.

## Contexte technique
La sidebar actuelle ([`SidebarNav.vue`](frontend/src/components/SidebarNav.vue)) affiche les entrées Infrastructure, Stockage & Réseau, Marketplace, Administration. En Mode App, elle doit afficher : Dashboard, Apps (remplace Compute), Marketplace, Plugins, Settings.

Les entrées techniques (Volumes, Networks, Images, Compute, Targets, Stacks, Deployments, Workflows, Schedules) sont masquées mais restent accessibles via URL directe. Un store Pinia `modeStore` gère l'état du mode (App/Infra) persisté dans `localStorage`.

Le toggle `[🔧 Mode Infra]` en bas de sidebar est présent mais désactivé (grisé) avec tooltip "Bientôt disponible".

Spécification de référence : [`docs/general_specs/11b-workload-families-and-adapters.md`](docs/general_specs/11b-workload-families-and-adapters.md)

## Critères d'acceptation (AC)
- [ ] AC 1 : La sidebar affiche la navigation Mode App (Dashboard, Apps, Marketplace, Plugins, Settings) quand le mode est "App"
- [ ] AC 2 : Les entrées techniques (Volumes, Networks, Images, Targets, Stacks, Deployments, Workflows, Schedules) sont masquées de la sidebar en Mode App mais restent accessibles via URL directe
- [ ] AC 3 : Le toggle Mode Infra est visible mais désactivé avec tooltip "Bientôt disponible"
- [ ] AC 4 : Un store Pinia `modeStore` gère l'état du mode (App/Infra) persisté dans `localStorage`
- [ ] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)

## État d'avancement techniques
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
