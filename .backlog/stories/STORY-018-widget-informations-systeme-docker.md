# STORY-018 : Widget informations système Docker

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux voir les informations système Docker (version, nombre de containers/images, ressources) dans un widget du dashboard afin d'avoir une vue d'ensemble rapide de l'état de l'hôte Docker.

## Contexte technique

**Couches impactées :** Backend API (sécurisation endpoint existant), Frontend Types, Frontend Services, Frontend Composant, Frontend Vue

**Backend existant (pas de création, modification uniquement) :**
- Endpoint `GET /docker/system/info` déjà fonctionnel dans `backend/app/api/v1/docker.py` (ligne 1668)
- Schéma Pydantic `SystemInfoResponse` déjà défini dans `backend/app/schemas/docker.py` (ligne 679) avec 16 champs : id, name, server_version, containers, containers_running, containers_paused, containers_stopped, images, driver, docker_root_dir, kernel_version, operating_system, os_type, architecture, cpus, memory
- Dataclass `SystemInfo` déjà définie dans `backend/app/services/docker_client_service.py` (ligne 234)
- Méthode `system_info()` déjà implémentée dans `docker_client_service.py` (ligne 1363)

**Frontend à créer :**
- Type TypeScript `SystemInfoResponse` absent de `frontend/src/types/api.ts`
- Service API `dockerSystemApi` absent de `frontend/src/services/api.ts`
- Nouveau composant `DockerInfoWidget.vue` à créer dans `frontend/src/components/dashboard/`
- Intégration dans `frontend/src/views/Dashboard.vue`

**Fichiers de référence (patterns) :**
- Widget dashboard → pattern : `frontend/src/components/dashboard/ResourceMetricsWidget.vue` (structure el-card, états loading/error/empty, props typées)
- Service API → pattern : `frontend/src/services/api.ts` section `containersApi` ou `imagesApi`
- Types → pattern : `frontend/src/types/api.ts` section `ImageResponse` ou `VolumeResponse`
- Tests composant → pattern : `frontend/tests/unit/components/dashboard/ResourceMetricsWidget.spec.ts`
- Endpoint authentifié → pattern : `backend/app/api/v1/docker.py` fonction `list_containers` (ligne 74) qui utilise `get_current_active_user`

**Exigences sécurité identifiées :**
- Auth : oui — l'endpoint backend `GET /docker/system/info` n'a PAS `get_current_active_user` → à ajouter
- RBAC : lecture seule → tous rôles autorisés (viewer, operator, admin, super_admin) — cf. `doc/general_specs/06-rbac-permissions.md`
- Validation : aucun input utilisateur (GET sans paramètres) → pas de validation spécifique
- Exposition : aucun champ sensible dans `SystemInfoResponse` (pas de secrets/tokens)
- Audit : non requis (lecture seule, pas d'action modifiante)

## Critères d'acceptation (AC)
- [x] AC 1 : Un nouveau widget DockerInfo est visible dans le dashboard et charge les données via `GET /docker/system/info`
- [x] AC 2 : Le widget affiche : version Docker, nombre total de containers (running/paused/stopped), nombre d'images, OS et architecture
- [x] AC 3 : Le type TypeScript `SystemInfoResponse` est défini et `dockerSystemApi.info` est disponible
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Sécuriser l'endpoint backend `GET /docker/system/info` avec authentification
**Objectif :** Ajouter `get_current_active_user` à l'endpoint existant pour exiger une authentification JWT, conformément aux exigences sécurité du projet (`.clinerules/40-security.md`)
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Ajouter le paramètre `current_user: User = Depends(get_current_active_user)` à la signature de la fonction `get_system_info` (ligne 1676). Suivre le pattern de `list_containers` (ligne 74) qui injecte déjà cette dépendance. L'import `get_current_active_user` et `User` sont déjà présents en tête de fichier (lignes 15-18). Ajouter le paramètre entre `request: Request` et le `:` de fermeture de signature.
**Exigences sécurité :** `get_current_active_user` requis — tous rôles autorisés (lecture seule, pas de restriction RBAC supplémentaire)
**Dépend de :** Aucune

### Tâche 2 : Ajouter le type TypeScript `SystemInfoResponse`
**Objectif :** Définir l'interface TypeScript miroir du schéma Pydantic `SystemInfoResponse` backend, pour le typage strict côté frontend
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter l'interface `SystemInfoResponse` dans la section Docker (après les types existants comme `NetworkResponse`). L'interface doit contenir les 16 champs du schéma backend : `id: string`, `name: string`, `server_version: string`, `containers: number`, `containers_running: number`, `containers_paused: number`, `containers_stopped: number`, `images: number`, `driver: string`, `docker_root_dir: string`, `kernel_version: string`, `operating_system: string`, `os_type: string`, `architecture: string`, `cpus: number`, `memory: number`. Suivre le pattern de `VolumeResponse` ou `NetworkResponse` (JSDoc comment, champs en snake_case).
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Aucune

### Tâche 3 : Ajouter le service API `dockerSystemApi`
**Objectif :** Créer le service d'appel HTTP vers `GET /docker/system/info` et l'exporter dans le barrel export
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier — (a) Ajouter `SystemInfoResponse` aux imports depuis `@/types/api` (ligne 70). (b) Ajouter un nouvel objet `dockerSystemApi` après `networksApi` (après ligne 398) avec une méthode `info: () => http.get<SystemInfoResponse>('/docker/system/info')`. (c) Ajouter `dockerSystem: dockerSystemApi` dans l'export default (ligne 448-464).
**Exigences sécurité :** Aucune exigence spécifique (le token JWT est envoyé automatiquement par le client HTTP)
**Dépend de :** Tâche 2

### Tâche 4 : Créer le composant `DockerInfoWidget.vue`
**Objectif :** Créer le widget dashboard affichant les informations système Docker avec gestion des états loading/error/empty
**Fichiers :**
- `frontend/src/components/dashboard/DockerInfoWidget.vue` — Créer — Nouveau composant (pattern : `ResourceMetricsWidget.vue`). Structure :
  - `<script setup lang="ts">` avec imports depuis `vue` et `@element-plus/icons-vue`
  - Props : `loading: boolean` (défaut false)
  - State réactif : `info: ref<SystemInfoResponse | null>(null)`, `error: ref<string | null>(null)`, `loading: ref(false)`
  - Méthode `fetchInfo()` qui appelle `dockerSystemApi.info()` via le service API, avec try/catch
  - Méthode `formatMemory(bytes: number)` pour formater la mémoire (Ko/Mo/Go)
  - `onMounted` → appelle `fetchInfo()`
  - Template `<el-card>` avec `data-testid="docker-info-widget"` :
    - Header : icône + titre "Docker System"
    - État error : `<el-alert type="error">`
    - État loading : `<el-skeleton :rows="3" animated>`
    - État avec données : grille d'informations avec :
      - Version Docker (`server_version`)
      - Containers : total / running / paused / stopped (avec badges colorés)
      - Images : nombre total
      - OS (`operating_system`)
      - Architecture (`architecture`)
      - CPUs (`cpus`)
      - Mémoire totale (`memory` formatée)
      - Kernel (`kernel_version`)
    - État empty : `<el-empty>`
  - Styles scoped avec variables CSS du design system (`var(--color-xxx)`) — cf. `doc/DESIGN-SYSTEM.md`
**Exigences sécurité :** Aucune exigence spécifique (lecture seule, pas de données sensibles)
**Dépend de :** Tâche 3

### Tâche 5 : Intégrer le widget dans `Dashboard.vue`
**Objectif :** Ajouter le `DockerInfoWidget` dans la vue Dashboard existante, dans une nouvelle row dédiée
**Fichiers :**
- `frontend/src/views/Dashboard.vue` — Modifier — (a) Ajouter l'import du composant : `import DockerInfoWidget from '@/components/dashboard/DockerInfoWidget.vue'` (après ligne 160). (b) Ajouter une nouvelle `<el-row>` avec `<el-col :span="12">` contenant `<DockerInfoWidget />` dans le template, idéalement après la section "Métriques système unifiées" (après ligne 75) et avant "Métriques déploiements" (ligne 77). Placer le DockerInfoWidget en span 12 et le ResourceMetricsWidget aussi en span 12 dans la même row pour un affichage côte à côte.
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 4

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Backend
- `backend/tests/unit/test_docker/test_system_info.py`
  - `test_get_system_info_returns_200_authenticated` — cas nominal : retourne SystemInfoResponse avec données valides quand authentifié
  - `test_get_system_info_returns_401_without_token` — **sécurité** : accès sans token JWT → 401 Unauthorized
  - `test_get_system_info_returns_data_shape` — vérifie la présence de tous les champs attendus (server_version, containers, images, os, architecture, cpus, memory)

### Unitaires Frontend
- `frontend/tests/unit/components/dashboard/DockerInfoWidget.spec.ts`
  - `affiche le skeleton pendant le chargement` — rendu initial avec loading=true
  - `affiche les informations système quand les données sont chargées` — rendu nominal avec mock data complète
  - `affiche la version Docker` — vérifie la présence de server_version dans le rendu
  - `affiche les compteurs de containers running/paused/stopped` — vérifie les badges avec les bonnes valeurs
  - `affiche le nombre d images` — vérifie la valeur images
  - `affiche l OS et l architecture` — vérifie operating_system et architecture
  - `affiche la mémoire formatée correctement` — vérifie le formatage (ex: 16 Go pour 17179869184 bytes)
  - `affiche un message d erreur si l API échoue` — état d'erreur avec el-alert
  - `affiche l état empty si aucune donnée` — état vide avec el-empty
  - `appelle fetchInfo au montage du composant` — vérifie l'appel API dans onMounted

### Commandes de validation
```bash
# Backend (voir Makefile)
poetry run pytest backend/tests/unit/test_docker/test_system_info.py -v

# Frontend (voir Makefile)
cd frontend && pnpm test -- tests/unit/components/dashboard/DockerInfoWidget
cd frontend && pnpm build && pnpm lint
```

## État d'avancement technique
- [x] Tâche 1 : Sécuriser l'endpoint backend avec authentification
- [x] Tâche 2 : Ajouter le type TypeScript SystemInfoResponse
- [x] Tâche 3 : Ajouter le service API dockerSystemApi
- [x] Tâche 4 : Créer le composant DockerInfoWidget.vue
- [x] Tâche 5 : Intégrer le widget dans Dashboard.vue
- [x] Tests unitaires backend (sécurité auth)
- [x] Tests unitaires frontend (composant DockerInfoWidget)
- [x] Build & lint OK

## Notes d'implémentation

### Fichiers modifiés
- `backend/app/api/v1/docker.py` — Ajout de `current_user: User = Depends(get_current_active_user)` à la signature de `get_system_info` (ligne 1676)
- `frontend/src/types/api.ts` — Ajout de l'interface `SystemInfoResponse` (16 champs) après `NetworkResponse`
- `frontend/src/services/api.ts` — Ajout de `SystemInfoResponse` aux imports, création de `dockerSystemApi.info()`, ajout au barrel export
- `frontend/src/views/Dashboard.vue` — Import de `DockerInfoWidget`, intégration côte à côte avec `ResourceMetricsWidget` (span 12 + span 12)

### Fichiers créés
- `frontend/src/components/dashboard/DockerInfoWidget.vue` — Nouveau composant widget avec états loading/error/empty, grille d'informations Docker, formatage mémoire
- `backend/tests/unit/test_docker/test_system_info.py` — 3 tests backend (200 authentifié, 401 sans token, vérification data shape)
- `frontend/tests/unit/components/dashboard/DockerInfoWidget.spec.ts` — 10 tests frontend (skeleton, données, version, containers, images, OS, mémoire, erreur, empty, fetchInfo au montage)

### Décisions techniques
- Le widget est placé côte à côte avec `ResourceMetricsWidget` dans une `el-row` avec deux `el-col :span="12"` pour un affichage compact
- Le composant gère son propre état de chargement (pas de props loading du parent) car il appelle l'API directement dans `onMounted`
- Les badges containers utilisent `el-tag` avec types colorés (success/warning/danger) pour running/paused/stopped
- Le formatage mémoire utilise les unités binaires (Ko, Mo, Go, To)

### Divergences
- Aucune divergence par rapport au plan initial. Toutes les tâches ont été implémentées exactement comme décrit.

### Tests ajoutés
- **Backend** : 3 tests (200 OK authentifié, 401 sans token, vérification des 16 champs de la réponse avec aliases PascalCase)
- **Frontend** : 10 tests (skeleton loading, données chargées, version Docker, compteurs containers, images, OS/architecture, mémoire formatée, erreur API, état empty, appel fetchInfo au montage)
- **Validation** : `pnpm build` ✅, `pnpm lint` ✅ (0 errors), `pnpm test` ✅ (10/10), `poetry run pytest` ✅ (3/3)
