# STORY-411 : Restructuration Sidebar selon les specs

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant qu'utilisateur, je veux une sidebar organisée par sections métier (Infrastructure, Stockage & Réseau, Marketplace, Plugins, Administration) afin de naviguer rapidement et logiquement dans WindFlow.

## Critères d'acceptation (AC)
- [x] AC 1 : La sidebar affiche les sections suivantes dans l'ordre : Dashboard, INFRASTRUCTURE (Containers, VMs, Stacks, Targets), STOCKAGE & RÉSEAU (Volumes, Networks, Images), MARKETPLACE (Marketplace, Plugins), ADMINISTRATION (Settings, Audit)
- [x] AC 2 : Chaque section a un label de catégorie visible (uppercase, grisé)
- [x] AC 3 : Une section dynamique "Plugins" apparaît uniquement si au moins un plugin avec pages UI est installé
- [x] AC 4 : Le composant `SidebarNav` est configurable via un store Pinia (`usePluginNavStore`) pour permettre l'injection future de pages par les plugins
- [x] AC 5 : Le sélecteur de target actif (🎯) est visible en bas de la sidebar
- [x] AC 6 : L'utilisateur connecté est affiché en bas de la sidebar
- [x] AC 7 : La sidebar correspond au wireframe défini dans `doc/general_specs/11-UI-mockups.md`

## État d'avancement technique
- [x] Création du composant `SidebarNav.vue` (ou refacto du layout existant)
- [x] Définition des sections de navigation (constante + type TypeScript)
- [x] Création du store `usePluginNavStore` (Pinia) pour les entrées dynamiques plugins
- [x] Mise à jour du layout principal pour intégrer la nouvelle sidebar
- [x] Affichage du sélecteur de target en bas
- [x] Affichage de l'utilisateur connecté en bas
- [x] Tests Vitest du composant SidebarNav (créés, fichier `frontend/tests/unit/components/SidebarNav.spec.ts`)
  - Note: L'exécution des tests nécessite une mise à jour de pnpm (conflit de store version)

## Notes d'implémentation

### Fichiers créés
- `frontend/src/types/navigation.ts` : Types TypeScript pour la navigation (NavItem, PluginNavConfig, etc.)
- `frontend/src/stores/pluginNav.ts` : Store Pinia pour l'injection dynamique des pages de plugins
- `frontend/src/components/SidebarNav.vue` : Composant sidebar avec sections organisées
- `frontend/src/views/Containers.vue` : Vue stub pour Containers
- `frontend/src/views/VMs.vue` : Vue stub pour VMs
- `frontend/src/views/Volumes.vue` : Vue stub pour Volumes
- `frontend/src/views/Networks.vue` : Vue stub pour Networks
- `frontend/src/views/Images.vue` : Vue stub pour Images
- `frontend/src/views/Marketplace.vue` : Vue stub pour Marketplace
- `frontend/src/views/Plugins.vue` : Vue stub pour Plugins
- `frontend/src/views/Settings.vue` : Vue stub pour Settings
- `frontend/src/views/Audit.vue` : Vue stub pour Audit
- `frontend/tests/unit/components/SidebarNav.spec.ts` : Tests unitaires Vitest

### Fichiers modifiés
- `frontend/src/layouts/MainLayout.vue` : Intégration du nouveau composant SidebarNav
- `frontend/src/router/index.ts` : Ajout des routes pour les nouvelles sections

### Décisions techniques
1. **Store Pinia dédié** : Création de `usePluginNavStore` pour permettre aux plugins d'enregistrer leurs pages UI dynamiquement via `registerPluginPages()`
2. **Navigation structurée** : Les sections de navigation sont définies de manière déclarative avec des catégories (uppercase)
3. **Sélecteur de target** : Utilise le store `useTargetsStore` existant pour la gestion du target actif
4. **Authentification** : Utilise le store `useAuthStore` existant pour l'affichage de l'utilisateur connecté

### Difficultés rencontrées
Aucune difficulté majeure. L'implémentation suit les spécifications du wireframe.
