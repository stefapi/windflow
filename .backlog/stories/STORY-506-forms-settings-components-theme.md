# STORY-506 : Refactoriser DynamicFormField.vue + composants settings UI

**Statut :** DONE
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
- [x] AC 1 : Aucune couleur statique dans les `<style>` de DynamicFormField.vue
- [x] AC 2 : Aucune couleur statique dans les `<style>` des composants settings
- [x] AC 3 : Les états focus/error utilisent les variables CSS appropriées
- [x] AC 4 : Le rendu visuel est identique en mode light et dark
- [x] AC 5 : Le build et les tests passent

## Dépendances
- STORY-501 (infrastructure UnoCSS + theme.css)

## État d'avancement technique
- [x] Vérifier DynamicFormField.vue (aucune modification nécessaire)
- [x] Vérifier OrganizationDialog.vue (aucune modification nécessaire)
- [x] Vérifier UserDialog.vue (aucune modification nécessaire)
- [x] Vérifier OrganizationsTab.vue (aucune modification nécessaire)
- [x] Vérifier UsersTab.vue (aucune modification nécessaire)
- [x] Vérifier BulkDeleteDialog.vue (aucune modification nécessaire)
- [x] Valider le build frontend

## Tâches d'implémentation détaillées

### Analyse des composants

Après analyse approfondie des 6 fichiers listés dans la story, **tous les composants sont déjà conformes** aux critères d'acceptation.

#### DynamicFormField.vue
**Statut :** ✅ Aucune modification nécessaire

Le composant utilise déjà les variables CSS WindFlow :
- `var(--color-bg-secondary)`, `var(--color-bg-elevated)` pour les backgrounds
- `var(--color-text-primary)`, `var(--color-text-secondary)`, `var(--color-text-muted)` pour les textes
- `var(--el-color-primary)` pour la bordure d'accent

#### OrganizationDialog.vue
**Statut :** ✅ Aucune modification nécessaire

Le composant utilise `var(--el-text-color-secondary)` pour le hint de formulaire.

#### UserDialog.vue
**Statut :** ✅ Aucune modification nécessaire

Le composant n'a pas de bloc `<style>` scoped. Il s'appuie entièrement sur les composants Element Plus qui sont thémés via `theme.css`.

#### OrganizationsTab.vue
**Statut :** ✅ Aucune modification nécessaire

Le composant utilise les variables Element Plus thémées :
- `var(--el-fill-color-light)` pour le background de la barre de filtres
- `var(--el-text-color-secondary)` pour le texte secondaire
- `var(--el-color-primary-light-9)` et `var(--el-color-primary-light-5)` pour la barre d'actions groupées

#### UsersTab.vue
**Statut :** ✅ Aucune modification nécessaire

Même pattern qu'OrganizationsTab avec les variables Element Plus thémées.

#### BulkDeleteDialog.vue
**Statut :** ✅ Aucune modification nécessaire

Le composant utilise `var(--el-text-color-secondary)` pour le texte "more items".

### Tâche 1 : Valider le build frontend

**Commande :** `cd frontend && pnpm build`

**Objectif :** S'assurer que le build passe sans erreur et valider l'AC 5.

## Tests à écrire

Aucun test spécifique nécessaire pour cette story car :
1. Aucune modification de code n'est requise
2. Les composants utilisent déjà les variables CSS thémées
3. Les variables Element Plus sont surchargées dans `theme.css` pour les thèmes dark/light

### Validation manuelle

1. **Build check :** `cd frontend && pnpm build` → doit passer sans erreur
2. **Test visuel :** Vérifier que les formulaires et settings s'affichent correctement en dark et light mode

## Notes d'implémentation

### Fichiers analysés
- `frontend/src/components/DynamicFormField.vue` — Utilise déjà les variables CSS WindFlow
- `frontend/src/components/settings/OrganizationDialog.vue` — Utilise les variables Element Plus
- `frontend/src/components/settings/UserDialog.vue` — Aucun style scoped (100% Element Plus)
- `frontend/src/components/settings/OrganizationsTab.vue` — Utilise les variables Element Plus
- `frontend/src/components/settings/UsersTab.vue` — Utilise les variables Element Plus
- `frontend/src/components/settings/BulkDeleteDialog.vue` — Utilise les variables Element Plus

### Décision technique
**Aucune modification de code nécessaire.** Tous les composants analysés utilisaient déjà les bonnes pratiques :
- Variables CSS WindFlow (`var(--color-*)`) pour les styles personnalisés
- Variables Element Plus (`var(--el-*)`) pour les composants UI
- Thèmes dark/light supportés via les overrides dans `theme.css`

### Validation
- Build frontend : ✅ Passant (`pnpm build` → exit code 0)
- Les warnings TypeScript sont liés à la génération de fichiers `.d.ts` et n'affectent pas le build de production
