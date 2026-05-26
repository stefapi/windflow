# STORY-004 : Vue Liste Apps — Refonte Compute

**Statut :** TODO
**Epic Parent :** EPIC-010 — Mode App — Navigation & UX Simplifiée

## Description
En tant qu'Utilisateur, je veux voir mes applications sous forme de cards avec un vocabulaire non-technique ("Mes Apps", "Apps autonomes", "Apps détectées") afin de gérer mes applications sans connaissance infrastructure.

## Contexte technique
La vue [`Compute.vue`](frontend/src/views/Compute.vue) est transformée en vue "Apps". Les composants existants ([`ManagedStacksSection`](frontend/src/components/compute/ManagedStacksSection.vue), [`DiscoveredSection`](frontend/src/components/compute/DiscoveredSection.vue), [`StandaloneSection`](frontend/src/components/compute/StandaloneSection.vue)) sont conservés mais leur vocabulaire est adapté via props ou le composable `useAppVocabulary`.

Chaque app est présentée en card avec : icône (du stack), nom, version, domaine (si disponible), statut, RAM. Actions inline : Ouvrir, Logs, Terminal, Stop, menu contextuel `[⋯ Plus]`. Badge de mise à jour disponible `[⬆]`. Les sections ComputeStatsBanner et filtres avancés sont masquées en Mode App.

Spécification de référence : [`docs/general_specs/11-UI-mockups.md`](docs/general_specs/11-UI-mockups.md) — Écran 2

## Critères d'acceptation (AC)
- [ ] AC 1 : Les sections affichent "Mes Apps", "Apps autonomes", "Apps détectées" au lieu des termes techniques "Managed Stacks", "Standalone", "Discovered"
- [ ] AC 2 : Chaque app est présentée en card avec icône, nom, version, domaine, statut et RAM
- [ ] AC 3 : Les actions inline (Ouvrir, Logs, Terminal, Stop, menu contextuel `[⋯ Plus]`) fonctionnent sur chaque card
- [ ] AC 4 : La recherche et le filtre par nom/statut fonctionnent ; les filtres avancés (type, technologie, target) et ComputeStatsBanner sont masqués en Mode App
- [ ] AC 5 : Build, lint et tests passent

## Dépendances
- STORY-001 (Composable de Vocabulaire Mode App)
- STORY-003 (Menu Contextuel Canonique)

## État d'avancement techniques
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
