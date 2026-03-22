# STORY-508 : Refactoriser toutes les autres views (batch audit - ~15 fichiers)

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques de toutes les views restantes par des variables CSS thémées afin de compléter l'homogénéisation du design system sur l'ensemble de l'application.

## Contexte technique
Cette story traite les views secondaires qui contiennent des couleurs statiques résiduelles (~27 occurrences réparties dans ~15 fichiers).

Fichiers potentiellement concernés (audit à effectuer) :
- `frontend/src/views/Settings.vue`
- `frontend/src/views/Targets.vue`
- `frontend/src/views/Containers.vue`
- `frontend/src/views/Volumes.vue`
- `frontend/src/views/Networks.vue`
- `frontend/src/views/Images.vue`
- `frontend/src/views/VMs.vue`
- `frontend/src/views/Marketplace.vue`
- `frontend/src/views/Plugins.vue`
- `frontend/src/views/Audit.vue`
- `frontend/src/components/SidebarNav.vue`
- Autres composants avec couleurs résiduelles

Approche :
1. Scanner tous les fichiers pour identifier les couleurs statiques restantes
2. Appliquer les règles de migration standard
3. Vérifier le support dark/light theme

## Critères d'acceptation (AC)
- [ ] AC 1 : Audit complet des couleurs statiques résiduelles effectué
- [ ] AC 2 : Aucune couleur statique (hex, rgb, rgba) dans les `<style>` des views traitées
- [ ] AC 3 : Toutes les views utilisent les variables CSS ou classes UnoCSS
- [ ] AC 4 : Le support dark/light theme est validé sur tous les écrans
- [ ] AC 5 : Le build et les tests passent
- [ ] AC 6 : Documentation du guide de style mise à jour

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
