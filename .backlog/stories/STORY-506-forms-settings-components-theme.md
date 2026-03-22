# STORY-506 : Refactoriser DynamicFormField.vue + composants settings UI

**Statut :** TODO
**Epic Parent :** EPIC-008 — Homogénéisation des couleurs UnoCSS

## Description
En tant que Développeur, je veux remplacer les couleurs statiques des composants de formulaire et de paramétrage par des variables CSS thémées afin d'assurer la cohérence des formulaires dans toute l'application.

## Contexte technique
DynamicFormField.vue est un composant central pour la génération dynamique de formulaires. Les composants settings (dialogues, onglets) sont utilisés dans l'écran de configuration.

Fichiers à modifier :
- `frontend/src/components/DynamicFormField.vue`
- `frontend/src/components/settings/OrganizationDialog.vue`
- `frontend/src/components/settings/UserDialog.vue`
- `frontend/src/components/settings/OrganizationsTab.vue`
- `frontend/src/components/settings/UsersTab.vue`
- `frontend/src/components/settings/BulkDeleteDialog.vue`

Règles de migration :
- Bordures : `#252838` → `var(--color-border)`, `#3a3f54` → `var(--color-border-focus)`
- Backgrounds et textes selon les variables standard

## Critères d'acceptation (AC)
- [ ] AC 1 : Aucune couleur statique dans les `<style>` de DynamicFormField.vue
- [ ] AC 2 : Aucune couleur statique dans les `<style>` des composants settings
- [ ] AC 3 : Les états focus/error utilisent les variables CSS appropriées
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
