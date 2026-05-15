# STORY-020 : Page informations système Docker

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'administrateur, je veux accéder à une page dédiée aux informations système Docker (version de l'API, Go version, température système, ping) afin de diagnostiquer les problèmes de connectivité et connaître les capacités exactes de l'hôte Docker.

## Contexte technique

**Couches impactées :** Backend API (sécurisation endpoints existants), Frontend Types, Frontend Services, Frontend Vue, Frontend Router, Frontend Navigation

**Backend existant (modification uniquement, pas de création) :**
- Endpoint `GET /docker/system/version` déjà fonctionnel dans `backend/app/api/v1/docker.py` (ligne 1713) — **SANS authentification** (`get_current_active_user` absent)
- Endpoint `GET /docker/system/ping` déjà fonctionnel dans `backend/app/api/v1/docker.py` (ligne 1751) — **SANS authentification** (`get_current_active_user` absent)
- Schéma Pydantic `SystemVersionResponse` déjà défini dans `backend/app/schemas/docker.py` (ligne 714) avec 9 champs : version, api_version, min_api_version, git_commit, go_version, os, arch, kernel_version, build_time
- Schéma Pydantic `PingResponse` déjà défini dans `backend/app/schemas/docker.py` (ligne 732) avec 2 champs : available, message
- Méthode `system_version()` déjà implémentée dans `backend/app/services/docker_client_service.py` (ligne 1377)
- Méthode `ping()` déjà implémentée dans `backend/app/services/docker_client_service.py` (ligne 1348)

**Frontend à créer/modifier :**
- Types TypeScript `SystemVersionResponse` et `PingResponse` absents de `frontend/src/types/api.ts`
- Service API `dockerSystemApi` existant dans `frontend/src/services/api.ts` (ligne 406) — à étendre avec `version()` et `ping()`
- Nouvelle vue `SystemInfo.vue` à créer dans `frontend/src/views/`
- Route `/system-info` à ajouter dans `frontend/src/router/index.ts`
- Entrée de navigation à ajouter dans `frontend/src/components/SidebarNav.vue` (section Administration)

**Fichiers de référence (patterns) :**
- Endpoint authentifié → pattern : `backend/app/api/v1/docker.py` fonction `get_system_info` (ligne 1676) qui utilise `get_current_active_user`
- Types TS → pattern : `frontend/src/types/api.ts` section `SystemInfoResponse` (ligne 1076)
- Service API → pattern : `frontend/src/services/api.ts` section `dockerSystemApi` (ligne 406)
- Vue page → pattern : `frontend/src/views/Settings.vue` (page admin avec `el-card`)
- Test backend → pattern : `backend/tests/unit/test_docker/test_system_info.py` (STORY-018)
- Test vue frontend → pattern : `frontend/tests/unit/views/Settings.spec.ts`
- Navigation → pattern : `frontend/src/components/SidebarNav.vue` section `administrationItems` (ligne 377)

**Exigences sécurité identifiées :**
- Auth : **oui** — les 2 endpoints backend n'ont PAS `get_current_active_user` → à ajouter (comme fait pour `/system/info` dans STORY-018)
- RBAC : lecture seule → tous rôles autorisés (viewer, operator, admin, super_admin) — cf. `doc/general_specs/06-rbac-permissions.md`
- Validation : aucun input utilisateur (GET sans paramètres) → pas de validation spécifique
- Exposition : aucun champ sensible dans `SystemVersionResponse` ni `PingResponse` (pas de secrets/tokens)
- Audit : non requis (lecture seule, pas d'action modifiante)

## Critères d'acceptation (AC)
- [x] AC 1 : Une page SystemInfo affiche les informations de version Docker via `GET /docker/system/version` (version, API version, Go version, OS, architecture)
- [x] AC 2 : Un indicateur de connectivité est affiché en utilisant `GET /docker/system/ping` (disponible/non disponible)
- [x] AC 3 : Les types TypeScript `SystemVersionResponse` et `PingResponse` sont définis, les méthodes `dockerSystemApi.version` et `dockerSystemApi.ping` sont disponibles
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- STORY-018 (Widget Docker Info — partage les types et l'API `dockerSystemApi`)

## Tâches d'implémentation détaillées

### Tâche 1 : Sécuriser les endpoints backend `GET /docker/system/version` et `GET /docker/system/ping` avec authentification
**Objectif :** Ajouter `get_current_active_user` aux 2 endpoints existants pour exiger une authentification JWT, conformément aux exigences sécurité du projet (`.clinerules/40-security.md`). Suivre le même pattern que `get_system_info` (ligne 1676) sécurisé dans STORY-018.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — (a) Ajouter le paramètre `current_user: User = Depends(get_current_active_user)` à la signature de la fonction `get_version` (ligne 1721). (b) Ajouter le même paramètre à la signature de la fonction `ping` (ligne 1759). Les imports `get_current_active_user` et `User` sont déjà présents en tête de fichier (lignes 15-18). Suivre le pattern de `get_system_info` (ligne 1676) qui injecte déjà cette dépendance.
**Exigences sécurité :** `get_current_active_user` requis — tous rôles autorisés (lecture seule, pas de restriction RBAC supplémentaire)
**Dépend de :** Aucune

### Tâche 2 : Ajouter les types TypeScript `SystemVersionResponse` et `PingResponse`
**Objectif :** Définir les interfaces TypeScript miroir des schémas Pydantic `SystemVersionResponse` et `PingResponse` backend, pour le typage strict côté frontend
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter les interfaces dans la section `// Docker System` (après `SystemInfoResponse`, ligne 1093). (a) `SystemVersionResponse` avec 9 champs : `version: string`, `api_version: string`, `min_api_version: string`, `git_commit: string`, `go_version: string`, `os: string`, `arch: string`, `kernel_version: string`, `build_time: string`. (b) `PingResponse` avec 2 champs : `available: boolean`, `message: string | null`. Suivre le pattern de `SystemInfoResponse` (JSDoc comment, champs en snake_case).
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 3 : Étendre le service API `dockerSystemApi` avec `version()` et `ping()`
**Objectif :** Ajouter les méthodes d'appel HTTP vers `GET /docker/system/version` et `GET /docker/system/ping` dans le service existant `dockerSystemApi`
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier — (a) Ajouter `SystemVersionResponse` et `PingResponse` aux imports depuis `@/types/api` (ligne 71). (b) Étendre l'objet `dockerSystemApi` (ligne 406) avec deux nouvelles méthodes : `version: () => http.get<SystemVersionResponse>('/docker/system/version')` et `ping: () => http.get<PingResponse>('/docker/system/ping')`. Le barrel export (ligne 475) référence déjà `dockerSystem: dockerSystemApi`, pas de modification nécessaire.
**Exigences sécurité :** Aucune exigence spécifique (le token JWT est envoyé automatiquement par le client HTTP)
**Dépend de :** Tâche 2

### Tâche 4 : Créer la vue `SystemInfo.vue`
**Objectif :** Créer la page dédiée aux informations système Docker avec affichage de la version (version, API version, Go version, OS, arch, kernel, build time) et un indicateur de connectivité ping (disponible/non disponible)
**Fichiers :**
- `frontend/src/views/SystemInfo.vue` — Créer — Nouvelle vue (pattern : `Settings.vue` pour la structure de page admin). Structure :
  - `<script setup lang="ts">` avec imports depuis `vue` et `@element-plus/icons-vue`
  - State réactif : `versionInfo: ref<SystemVersionResponse | null>(null)`, `pingResult: ref<PingResponse | null>(null)`, `error: ref<string | null>(null)`, `loading: ref(false)`
  - Méthode `fetchData()` qui appelle en parallèle `dockerSystemApi.version()` et `dockerSystemApi.ping()` via `Promise.allSettled`, avec try/catch
  - `onMounted` → appelle `fetchData()`
  - Template avec `data-testid="system-info-page"` :
    - Titre de page : "Docker System Information" avec icône `Platform`
    - État error : `<el-alert type="error">`
    - État loading : `<el-skeleton :rows="5" animated>`
    - Section Version : `<el-card>` avec header "Version" contenant une grille d'informations :
      - Version Docker (`version`)
      - API Version (`api_version`)
      - Min API Version (`min_api_version`)
      - Go Version (`go_version`)
      - OS (`os`)
      - Architecture (`arch`)
      - Kernel (`kernel_version`)
      - Build Time (`build_time`)
      - Git Commit (`git_commit`)
    - Section Connectivité : `<el-card>` avec header "Connectivity" contenant :
      - Indicateur visuel : `<el-tag type="success">` si `available=true` avec texte "Docker is available", `<el-tag type="danger">` si `available=false` avec texte "Docker is not available"
      - Message optionnel (`message`)
    - État empty : `<el-empty>`
  - Styles scoped avec variables CSS du design system (`var(--color-xxx)`) — cf. `doc/DESIGN-SYSTEM.md`
**Exigences sécurité :** Aucune exigence spécifique (lecture seule, pas de données sensibles)
**Dépend de :** Tâche 3

### Tâche 5 : Ajouter la route `/system-info` et l'entrée de navigation sidebar
**Objectif :** Rendre la page SystemInfo accessible via une route et ajouter une entrée dans la sidebar section Administration
**Fichiers :**
- `frontend/src/router/index.ts` — Modifier — Ajouter une nouvelle route dans les children du layout principal (après la route `audit`, ligne 127) : `{ path: 'system-info', name: 'SystemInfo', component: () => import('@/views/SystemInfo.vue') }`
- `frontend/src/components/SidebarNav.vue` — Modifier — (a) Ajouter l'icône `Monitor` ou `InfoFilled` aux imports depuis `@element-plus/icons-vue` (ligne 315-332) — utiliser `InfoFilled` pour différencier de l'icône VMs. (b) Ajouter une entrée dans le tableau `administrationItems` (ligne 377) : `{ icon: InfoFilled, label: 'System Info', path: '/system-info' }`. Placer après l'entrée Settings et avant Audit.
**Exigences sécurité :** Aucune exigence spécifique (la route est protégée par le guard d'auth global du router)
**Dépend de :** Tâche 4

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend

- `backend/tests/unit/test_docker/test_system_version.py`
  - `test_get_version_returns_200_authenticated` — cas nominal : retourne SystemVersionResponse avec données valides quand authentifié
  - `test_get_version_returns_401_without_token` — **sécurité** : accès sans token JWT → 401 Unauthorized
  - `test_get_version_returns_data_shape` — vérifie la présence de tous les champs attendus (version, api_version, go_version, os, arch, kernel_version, build_time, git_commit, min_api_version)

- `backend/tests/unit/test_docker/test_system_ping.py`
  - `test_ping_returns_200_authenticated` — cas nominal : retourne PingResponse avec `available=true` quand authentifié
  - `test_ping_returns_200_unavailable` — cas nominal : retourne PingResponse avec `available=false` quand Docker indisponible
  - `test_ping_returns_401_without_token` — **sécurité** : accès sans token JWT → 401 Unauthorized

### Unitaires Frontend

- `frontend/tests/unit/views/SystemInfo.spec.ts`
  - `affiche le skeleton pendant le chargement` — rendu initial avec loading=true
  - `affiche les informations de version quand les données sont chargées` — rendu nominal avec mock data complète
  - `affiche la version Docker` — vérifie la présence de `version` dans le rendu
  - `affiche l API version` — vérifie api_version
  - `affiche la version Go` — vérifie go_version
  - `affiche l OS et l architecture` — vérifie os et arch
  - `affiche le kernel et le build time` — vérifie kernel_version et build_time
  - `affiche l indicateur de connectivite disponible` — vérifie el-tag success quand ping available=true
  - `affiche l indicateur de connectivite indisponible` — vérifie el-tag danger quand ping available=false
  - `affiche un message d erreur si l API echoue` — état d'erreur avec el-alert
  - `appelle fetchData au montage du composant` — vérifie l'appel API dans onMounted

### Commandes de validation
```bash
# Backend (voir Makefile)
poetry run pytest backend/tests/unit/test_docker/test_system_version.py -v
poetry run pytest backend/tests/unit/test_docker/test_system_ping.py -v

# Frontend (voir Makefile)
cd frontend && pnpm test -- tests/unit/views/SystemInfo
cd frontend && pnpm build && pnpm lint
```

## État d'avancement technique
- [x] Tâche 1 : Sécuriser les endpoints backend `/system/version` et `/system/ping` avec authentification
- [x] Tâche 2 : Ajouter les types TypeScript SystemVersionResponse et PingResponse
- [x] Tâche 3 : Étendre le service API dockerSystemApi avec version et ping
- [x] Tâche 4 : Créer la vue SystemInfo.vue
- [x] Tâche 5 : Ajouter la route /system-info et l entrée de navigation sidebar
- [x] Tests unitaires backend (sécurité auth version + ping)
- [x] Tests unitaires frontend (vue SystemInfo)
- [x] Build & lint OK

## Notes d'implémentation

### Fichiers modifiés
- `backend/app/api/v1/docker.py` — Ajout de `current_user: User = Depends(get_current_active_user)` aux signatures de `get_version` (ligne 1721) et `ping` (ligne 1759)
- `frontend/src/types/api.ts` — Ajout des interfaces `SystemVersionResponse` (9 champs) et `PingResponse` (2 champs) après `SystemInfoResponse`
- `frontend/src/services/api.ts` — Ajout des imports `SystemVersionResponse` et `PingResponse` + méthodes `version()` et `ping()` dans `dockerSystemApi`
- `frontend/src/router/index.ts` — Ajout de la route `system-info` dans les children du layout principal
- `frontend/src/components/SidebarNav.vue` — Ajout de l'icône `InfoFilled` aux imports + entrée "System Info" dans `administrationItems`

### Fichiers créés
- `frontend/src/views/SystemInfo.vue` — Page complète avec skeleton loading, carte version (el-descriptions), carte connectivité (el-tag success/danger), gestion d'erreur (el-alert), état vide (el-empty)
- `backend/tests/unit/test_docker/test_system_version.py` — 3 tests : 200 authentifié, 401 sans token, vérification data shape
- `backend/tests/unit/test_docker/test_system_ping.py` — 3 tests : 200 disponible, 200 indisponible, 401 sans token
- `frontend/tests/unit/views/SystemInfo.spec.ts` — 11 tests : skeleton, version, api_version, go_version, os/arch, kernel/build_time, connectivité disponible/indisponible, erreur, appel API au montage

### Décisions techniques
- Utilisation de `Promise.allSettled` dans `fetchData()` pour que l'échec de l'appel ping n'empêche pas l'affichage des informations de version
- Utilisation de `el-descriptions` avec `border` pour un affichage structuré des champs de version (pattern plus lisible qu'une grille manuelle)
- Icône `InfoFilled` choisie pour la sidebar (différente de `Monitor` déjà utilisée pour les VMs)
- Aucune divergence par rapport aux instructions de la story
