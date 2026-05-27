# STORY-006.2 : Frontend — UI d'affichage des logs d'exécution des hooks

**Statut :** TODO
**Story Parente :** STORY-006 — Hooks lifecycle plugins (on_install, on_configure, on_start, on_stop, on_uninstall)
**Epic Parent :** EPIC-001 — Système de Plugins & Marketplace

## Description
En tant que Utilisateur, je veux voir les logs d'exécution des hooks lifecycle dans l'interface de détail d'un plugin afin de diagnostiquer les problèmes d'installation, configuration ou suppression des plugins.

## Critères d'acceptation (AC)
- [ ] AC 3 : Les logs d'exécution des hooks sont capturés et accessibles via l'API et l'UI

## Contexte technique

### Prérequis (implémenté dans STORY-006.1)
- Endpoint API `GET /api/v1/plugins/{plugin_id}/hooks/logs` retourne `List[HookLogSummaryResponse]`
- Chaque log contient : hook_name, status, exit_code, started_at, completed_at, duration_ms, error_message

### Stack frontend
- Vue 3 Composition API (`<script setup lang="ts">`)
- TypeScript strict
- Element Plus pour les composants UI
- Pinia pour le store
- Axios pour les appels HTTP

### Patterns à suivre
- **Composable** : pattern `use*.ts` dans `frontend/src/composables/`
- **Service** : un fichier par domaine dans `frontend/src/services/`
- **Types** : centralisés dans `frontend/src/types/`
- **Tests** : Vitest + @vue/test-utils dans `frontend/tests/unit/`

## Dépendances
- STORY-006.1 : Backend — Service d'exécution des hooks lifecycle

## Tâches d'implémentation détaillées

### Tâche 1 : Types TypeScript pour les hooks logs
**Objectif :** Définir les types TypeScript correspondant aux schemas backend HookLogSummaryResponse et HookLogResponse.
**Fichiers :**
- `frontend/src/types/plugin.ts` — Modifier — Ajouter les interfaces PluginHookLog et HookLogStatus (enum)
**Pattern de référence :** Types existants dans `frontend/src/types/`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 2 : Service API pour les hooks logs
**Objectif :** Créer le service d'appels HTTP vers l'endpoint hooks/logs.
**Fichiers :**
- `frontend/src/services/plugin.ts` — Modifier — Ajouter la fonction fetchPluginHookLogs(pluginId: string, params?: { skip?: number, limit?: number }) → Promise<PluginHookLog[]>
**Pattern de référence :** Services existants dans `frontend/src/services/`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 1

### Tâche 3 : Composable usePluginHookLogs
**Objectif :** Créer le composable pour gérer l'état de chargement et les données des hooks logs.
**Fichiers :**
- `frontend/src/composables/usePluginHookLogs.ts` — Créer — Composable avec ref réactif pour les logs, loading state, error state, et fonction fetchLogs()
**Pattern de référence :** Composables existants dans `frontend/src/composables/`
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

### Tâche 4 : Composant PluginHookLogs — Affichage des logs
**Objectif :** Créer le composant Vue 3 affichant la liste des exécutions de hooks dans le détail plugin.
**Fichiers :**
- `frontend/src/components/plugins/PluginHookLogs.vue` — Créer — Tableau Element Plus avec colonnes : hook_name, status (badge coloré), exit_code, duration_ms, started_at, bouton détail. Dialog de détail avec stdout/stderr.
**Pattern de référence :** Composants existants dans `frontend/src/components/`
**Exigences sécurité :** Ne pas afficher de secrets/tokens dans les logs (assertion `not.toContain` dans les tests)
**Dépend de :** Tâche 3

### Tâche 5 : Tests unitaires frontend
**Objectif :** Tester le composable et le composant d'affichage des hooks logs.
**Fichiers :**
- `frontend/tests/unit/composables/usePluginHookLogs.spec.ts` — Créer — Tests : chargement nominal, gestion erreur API, état loading
- `frontend/tests/unit/components/plugins/PluginHookLogs.spec.ts` — Créer — Tests : rendu du tableau avec données, rendu état vide, rendu état erreur, pas de secret dans le DOM
**Pattern de référence :** Tests existants dans `frontend/tests/unit/`
**Exigences sécurité :** Test "pas de secret/token visible dans le DOM" obligatoire
**Dépend de :** Tâche 4

## Tests à écrire

### Frontend — Tests composable
- `frontend/tests/unit/composables/usePluginHookLogs.spec.ts`
  - `test_fetches_logs_successfully` — Retourne les logs depuis l'API
  - `test_handles_api_error` — Error state renseigné en cas d'erreur
  - `test_shows_loading_state` — Loading à true pendant le fetch

### Frontend — Tests composant
- `frontend/tests/unit/components/plugins/PluginHookLogs.spec.ts`
  - `test_renders_logs_table_with_data` — Affiche les logs dans un tableau
  - `test_renders_empty_state` — Message quand aucun log
  - `test_renders_error_state` — Message d'erreur si API en échec
  - `test_does_not_expose_secrets_in_dom` — Pas de token/secret visible

### Commandes de validation
```bash
# Frontend - Tests composable
pnpm test -- tests/unit/composables/usePluginHookLogs.spec.ts

# Frontend - Tests composant
pnpm test -- tests/unit/components/plugins/PluginHookLogs.spec.ts

# Frontend - Tous les tests
pnpm test -- tests/unit/composables/usePluginHookLogs.spec.ts tests/unit/components/plugins/PluginHookLogs.spec.ts
```

## État d'avancement technique
- [ ] Tâche 1 : Types TypeScript pour les hooks logs
- [ ] Tâche 2 : Service API pour les hooks logs
- [ ] Tâche 3 : Composable usePluginHookLogs
- [ ] Tâche 4 : Composant PluginHookLogs
- [ ] Tâche 5 : Tests unitaires frontend

## Notes d'implémentation
<!-- Ajoutées à la clôture par treat-story -->
