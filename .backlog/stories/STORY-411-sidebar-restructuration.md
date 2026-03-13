# STORY-411 : Restructuration Sidebar selon les specs

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une sidebar organisée par sections métier (Infrastructure, Stockage & Réseau, Marketplace, Plugins, Administration) afin de naviguer rapidement et logiquement dans WindFlow.

## Critères d'acceptation (AC)
- [ ] AC 1 : La sidebar affiche les sections suivantes dans l'ordre : Dashboard, INFRASTRUCTURE (Containers, VMs, Stacks, Targets), STOCKAGE & RÉSEAU (Volumes, Networks, Images), MARKETPLACE (Marketplace, Plugins), ADMINISTRATION (Settings, Audit)
- [ ] AC 2 : Chaque section a un label de catégorie visible (uppercase, grisé)
- [ ] AC 3 : Une section dynamique "Plugins" apparaît uniquement si au moins un plugin avec pages UI est installé
- [ ] AC 4 : Le composant `SidebarNav` est configurable via un store Pinia (`usePluginNavStore`) pour permettre l'injection future de pages par les plugins
- [ ] AC 5 : Le sélecteur de target actif (🎯) est visible en bas de la sidebar
- [ ] AC 6 : L'utilisateur connecté est affiché en bas de la sidebar
- [ ] AC 7 : La sidebar correspond au wireframe défini dans `doc/general_specs/11-UI-mockups.md`

## État d'avancement technique
- [ ] Création du composant `SidebarNav.vue` (ou refacto du layout existant)
- [ ] Définition des sections de navigation (constante + type TypeScript)
- [ ] Création du store `usePluginNavStore` (Pinia) pour les entrées dynamiques plugins
- [ ] Mise à jour du layout principal pour intégrer la nouvelle sidebar
- [ ] Affichage du sélecteur de target en bas
- [ ] Affichage de l'utilisateur connecté en bas
- [ ] Tests Vitest du composant SidebarNav
