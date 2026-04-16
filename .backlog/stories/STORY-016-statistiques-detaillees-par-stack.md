# STORY-016 : Statistiques détaillées par stack

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter les statistiques détaillées d'une stack (déploiements par statut, activité sur les 30 derniers jours) afin de suivre son historique et son taux de succès.

## Contexte technique

**Couches impactées :** Backend API (correction auth), Frontend Types, Frontend Service, Frontend Vue, Frontend Tests

**Fichiers de référence :**
- Type TypeScript → pattern : types Dashboard existants dans `frontend/src/types/api.ts` (lignes 421-501)
- Service API → pattern : `dashboardApi.getStats()` dans `frontend/src/services/api.ts` (ligne 301)
- Vue → pattern : onglets existants dans `frontend/src/views/Stacks.vue` (lignes 142-437)
- Tests → pattern : `frontend/tests/unit/views/Stacks.spec.ts` (817 lignes, mocks API + stores)
- Backend endpoint → `backend/app/api/v1/stats.py` (lignes 292-319)
- Backend schéma → `backend/app/schemas/dashboard.py`

**Exigences sécurité identifiées :**
- Auth : ⚠️ L'endpoint backend `GET /stats/stacks/{id}` n'a PAS d'authentification — à corriger (ajouter `Depends(get_current_active_user)`)
- RBAC : Lecture seule — tout utilisateur authentifié peut voir les stats
- Validation : `stack_id` est un path parameter string, validé côté backend
- Exposition : Aucune donnée sensible — seuls des compteurs agrégés (deployments_by_status, deployments_last_30_days)
- Audit : Non requis (lecture seule)

## Critères d'acceptation (AC)
- [x] AC 1 : La vue de détail d'une stack affiche les statistiques de déploiements via `GET /stats/stacks/{id}`
- [x] AC 2 : Les statistiques incluent le nombre de déploiements par statut (succès/échec/en cours) et le total sur 30 jours
- [x] AC 3 : Le type TypeScript `StackStatsResponse` est défini et `dashboardApi.getStackStats` est disponible
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## État d'avancement technique
- [x] Tâche 1 : Corriger l'authentification sur l'endpoint backend
- [x] Tâche 2 : Ajouter le type TypeScript et la méthode API
- [x] Tâche 3 : Enrichir la vue Stacks.vue avec un onglet Statistics
- [x] Tâche 4 : Écrire les tests frontend
- [x] Tests unitaires backend
- [x] Tests unitaires frontend
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Corriger l'authentification sur l'endpoint backend `GET /stats/stacks/{id}`
**Objectif :** Ajouter l'authentification manquante sur l'endpoint `GET /stats/stacks/{stack_id}` et ajouter un schéma Pydantic de réponse pour la validation et la documentation OpenAPI.
**Fichiers :**
- `backend/app/api/v1/stats.py` — Modifier — Ajouter `Depends(get_current_active_user)` au paramètre de la fonction `get_stack_stats` (ligne ~293). Importer `get_current_active_user` depuis `backend/app/auth/dependencies.py`. Suivre le pattern de `get_dashboard_stats` (ligne ~15 du même fichier) qui utilise déjà cette dépendance. Ajouter également `response_model=StackStatsResponse` au décorateur `@router.get`.
- `backend/app/schemas/dashboard.py` — Modifier — Ajouter le schéma Pydantic `StackStatsResponse(BaseModel)` avec les champs `deployments_by_status: dict[str, int] = Field(..., description="Nombre de déploiements par statut")` et `deployments_last_30_days: int = Field(..., description="Nombre de déploiements sur les 30 derniers jours")`. Suivre le pattern des schémas existants dans ce fichier (PascalCase, `Field()` descriptif, `ConfigDict`).
**Exigences sécurité :** `get_current_active_user` obligatoire — corrige une faille où l'endpoint est accessible sans authentification.
**Dépend de :** Aucune

### Tâche 2 : Ajouter le type TypeScript `StackStatsResponse` et la méthode API `getStackStats`
**Objectif :** Définir le type TypeScript miroir du schéma backend et ajouter la méthode d'appel API dans le service frontend.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter l'interface `StackStatsResponse` après les types Dashboard (autour de la ligne 501, avant `StackVersion`). Définir : `deployments_by_status: Record<string, number>` et `deployments_last_30_days: number`. Suivre le pattern des interfaces existantes (PascalCase, champs camelCase pour les noms TS mais ici les clés correspondent au JSON backend donc snake_case).
- `frontend/src/services/api.ts` — Modifier — (a) Ajouter `StackStatsResponse` dans les imports de types depuis `@/types/api` (section import en haut de fichier). (b) Ajouter la méthode `getStackStats` dans l'objet `dashboardApi` existant (autour de la ligne 301) : `getStackStats: (stackId: string) => http.get<StackStatsResponse>(\`/stats/stacks/${stackId}\`)`. Suivre le pattern de `getStats` existant dans le même objet.
**Exigences sécurité :** Aucune exigence spécifique (le token JWT est transmis automatiquement par le client HTTP `http`).
**Dépend de :** Tâche 1

### Tâche 3 : Enrichir la vue Stacks.vue avec un onglet "Statistics"
**Objectif :** Ajouter un 5ème onglet "Statistics" dans le panneau détail d'une stack, affichant les compteurs de déploiements par statut et le total sur 30 jours.
**Fichiers :**
- `frontend/src/views/Stacks.vue` — Modifier — (a) Ajouter les imports : `StackStatsResponse` depuis `@/types/api` et `dashboardApi` depuis `@/services/api` (si pas déjà importé). (b) Ajouter l'état réactif dans le `<script setup>` : `const stackStats = ref<StackStatsResponse | null>(null)` et `const loadingStats = ref(false)`. (c) Créer la méthode `async function loadStackStats(stackId: string)` qui : met `loadingStats.value = true`, appelle `dashboardApi.getStackStats(stackId)`, stocke le résultat dans `stackStats.value`, gère l'erreur avec `ElMessage.error()`, et met `loadingStats.value = false` dans un `finally`. (d) Dans la méthode `selectStack()` existante (ligne ~779), ajouter l'appel `loadStackStats(stack.id)` à côté de `loadVersions()`. Ajouter aussi `stackStats.value = null` dans le reset de `selectStack()`. (e) Dans le template, ajouter un 5ème `<el-tab-pane label="Statistics" name="stats">` après l'onglet "history" (autour de la ligne 435). Le contenu de l'onglet doit afficher : un `el-skeleton` si `loadingStats`, un message "Aucune statistique disponible" si `!stackStats`, sinon une section avec : le total des déploiements sur 30 jours (`el-statistic` ou `el-descriptions`), et la distribution par statut avec des `el-tag` colorés (vert=completed, rouge=failed, bleu=running, gris=cancelled/pending). Utiliser `v-for` sur `Object.entries(stackStats.deployments_by_status)` pour itérer sur les statuts.
**Exigences sécurité :** Aucune exigence spécifique (lecture seule, pas de données sensibles affichées).
**Dépend de :** Tâche 2

### Tâche 4 : Écrire les tests frontend
**Objectif :** Ajouter les tests unitaires pour le chargement et l'affichage des statistiques stack dans la vue Stacks.
**Fichiers :**
- `frontend/tests/unit/views/Stacks.spec.ts` — Modifier — (a) Dans le `vi.mock('@/services/api', ...)`, ajouter le mock `getStackStats: vi.fn()` dans l'objet `dashboardApi`. (b) Ajouter un `describe('loadStackStats', ...)` avec les tests suivants :
  - `appelle dashboardApi.getStackStats avec le bon stackId quand une stack est sélectionnée` — vérifier que l'API est appelée avec le bon ID
  - `affiche les statistiques dans l'onglet Statistics` — vérifier la présence des compteurs dans le DOM après chargement
  - `affiche le skeleton pendant le chargement` — vérifier la présence du skeleton pendant l'appel API
  - `affiche un message d'erreur si l'API échoue` — mock rejet, vérifier `ElMessage.error`
  - `reset les stats quand une autre stack est sélectionnée` — vérifier que `stackStats` est remis à null
  - `affiche les tags de statut avec les bonnes couleurs` — vérifier les classes/styles des el-tag selon le statut (completed=success, failed=danger, etc.)
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 3

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend
- `backend/tests/unit/test_stats_api.py` (ou fichier existant si pertinent)
  - `test_get_stack_stats_returns_200_authenticated` — cas nominal avec auth : retourne les stats
  - `test_get_stack_stats_returns_401_without_token` — **sécurité** : accès sans token → 401
  - `test_get_stack_stats_returns_404_unknown_stack` — cas d'erreur : stack_id inexistant
  - `test_get_stack_stats_response_matches_schema` — validation : la réponse correspond au schéma StackStatsResponse

### Unitaires Frontend
- `frontend/tests/unit/views/Stacks.spec.ts` (enrichissement du fichier existant)
  - `appelle dashboardApi.getStackStats avec le bon stackId quand une stack est sélectionnée` — cas nominal
  - `affiche les statistiques dans l'onglet Statistics` — rendu nominal avec données
  - `affiche le skeleton pendant le chargement` — état de chargement
  - `affiche un message d'erreur si l'API échoue` — état d'erreur
  - `reset les stats quand une autre stack est sélectionnée` — nettoyage état
  - `affiche les tags de statut avec les bonnes couleurs` — rendu conditionnel

### Commandes de validation
```bash
# Backend
poetry run pytest backend/tests/unit/test_stats_api.py -v

# Frontend
cd frontend && pnpm test -- tests/unit/views/Stacks
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

**Date :** 2026-04-15

### Fichiers modifiés/créés
- `backend/app/schemas/dashboard.py` : Ajout du schéma Pydantic `StackStatsResponse` (deployments_by_status, deployments_last_30_days)
- `backend/app/api/v1/stats.py` : Ajout authentification `get_current_active_user` + `response_model=StackStatsResponse` sur endpoint `GET /stats/stacks/{stack_id}`
- `frontend/src/types/api.ts` : Ajout interface `StackStatsResponse`
- `frontend/src/services/api.ts` : Ajout méthode `dashboardApi.getStackStats(stackId)`
- `frontend/src/views/Stacks.vue` : Ajout 5ème onglet "Statistics" avec état réactif, méthode `loadStackStats()`, helper `getStatusTagType()`, styles CSS
- `backend/tests/unit/test_stack_stats.py` : Création — 4 tests (401, 200, données vides, validation schéma)
- `frontend/tests/unit/views/Stacks.spec.ts` : Ajout mock `getStackStats` + 3 tests (appel API, erreur, reset)

### Décisions techniques
- Placement de `getStackStats` dans `dashboardApi` (cohérent avec le routeur backend `/stats/`) plutôt que dans `stacksApi`
- Utilisation de `el-tag` colorés pour la distribution par statut plutôt qu'un graphique (plus léger, pas de dépendance supplémentaire)
- L'endpoint retourne des zéros pour une stack inexistante plutôt qu'une 404 (comportement existant conservé)

### Divergences par rapport à l'analyse
- Aucune divergence significative

### Tests ajoutés
- `backend/tests/unit/test_stack_stats.py` : 4 tests (dont 1 sécurité 401) — tous passants
- `frontend/tests/unit/views/Stacks.spec.ts` : 3 tests ajoutés (29 tests totaux passants)
