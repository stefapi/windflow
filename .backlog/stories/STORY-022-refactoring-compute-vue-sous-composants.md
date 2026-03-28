# STORY-022 : Frontend — Refactoring de Compute.vue en sous-composants

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant que développeur frontend, je veux que la vue `Compute.vue` soit découpée en sous-composants dédiés, afin que le code soit lisible, maintenable et testable indépendamment selon les principes SOLID et les conventions du projet.

## Contexte technique
Le fichier `frontend/src/views/Compute.vue` (~900 lignes) est un monolithe qui contient :
- 3 sections inline (Managed Stacks / Discovered / Standalone)
- Un mode "Par machine" alternatif
- La logique de filtrage complexe (type, technologie, statut, recherche)
- Les bulk actions standalone
- Tout le template HTML + script + style dans un seul fichier

Chaque section (D, E, F) devrait être un composant autonome dans `frontend/src/components/compute/`.

Le projet utilise déjà ce pattern : les composants UI réutilisables sont dans `components/ui/` (avec un `index.ts` d'export), les composants dashboard sont dans `components/dashboard/`.

**Fichiers de référence :**
- `frontend/src/views/Compute.vue` — monolithe à refactorer
- `frontend/src/components/ui/` — pattern existant de composants UI avec `index.ts`
- `frontend/src/components/dashboard/` — pattern existant de composants par domaine
- `frontend/src/stores/compute.ts` — store Pinia existant
- `frontend/src/types/api.ts` — types TypeScript existants

**Patterns à respecter :**
- Vue 3 Composition API obligatoire (`<script setup lang="ts">`)
- Props typées + emits typés
- Sous-composants dans `components/compute/` avec `index.ts`
- Styles scoped respectant le design system (`doc/DESIGN-SYSTEM.md`)

## Critères d'acceptation (AC)
- [ ] AC 1 : Composant `compute/ManagedStacksSection.vue` extrait de la section D (stacks managées)
- [ ] AC 2 : Composant `compute/DiscoveredSection.vue` extrait de la section E (objets découverts)
- [ ] AC 3 : Composant `compute/StandaloneSection.vue` extrait de la section F (containers standalone avec bulk actions)
- [ ] AC 4 : Composant `compute/TargetGroupView.vue` extrait du mode "Par machine"
- [ ] AC 5 : `Compute.vue` est un orchestrateur allégé qui utilise les 4 sous-composants
- [ ] AC 6 : Fichier `components/compute/index.ts` exporte les 4 composants
- [ ] AC 7 : Chaque sous-composant est testable indépendamment avec ses propres tests unitaires
- [ ] AC 8 : Pas de régression visuelle ou fonctionnelle (même rendu, mêmes interactions)
- [ ] AC 9 : Build, lint et tests existants passent sans erreur

## Dépendances
- STORY-002 : Backend — Refactoring des services de listage Docker (le backend doit être stable avant de refactorer le frontend)

## État d'avancement technique
- [ ] Tâche 1 : Créer le répertoire `components/compute/` avec `index.ts`
- [ ] Tâche 2 : Extraire ManagedStacksSection.vue
- [ ] Tâche 3 : Extraire DiscoveredSection.vue
- [ ] Tâche 4 : Extraire StandaloneSection.vue
- [ ] Tâche 5 : Extraire TargetGroupView.vue
- [ ] Tâche 6 : Refactorer Compute.vue en orchestrateur
- [ ] Tâche 7 : Tests unitaires des 4 sous-composants
- [ ] Tâche 8 : Adapter les tests existants de Compute.spec.ts

## Tâches d'implémentation détaillées
<!-- Section à remplir par la skill analyse-story -->

## Tests à écrire
<!-- Section à remplir par la skill analyse-story -->
