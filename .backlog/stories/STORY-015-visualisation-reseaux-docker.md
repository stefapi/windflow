# STORY-015 : Visualisation des réseaux Docker

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend

## Description
En tant qu'utilisateur DevOps, je veux consulter la liste des réseaux Docker sur mes targets afin de comprendre la topologie réseau de mes containers et diagnostiquer les problèmes de connectivité.

## Contexte technique

### Backend — déjà existant (aucune modification nécessaire)
- **Endpoint** `GET /docker/networks` — [`backend/app/api/v1/docker.py:1616`](backend/app/api/v1/docker.py:1616)
  - Retourne `List[NetworkResponse]`
  - Rate limité à 100 req/60s
  - Pas de dépendance `get_current_active_user` (pattern cohérent avec les autres endpoints Docker : containers, volumes, images)
- **Schéma Pydantic** [`NetworkResponse`](backend/app/schemas/docker.py:659) — champs : `id`, `name`, `driver`, `scope`, `internal`, `attachable`, `ingress`, `created`, `subnet`, `gateway`

### Frontend — à implémenter
- **Vue** [`Networks.vue`](frontend/src/views/Networks.vue) — actuellement `StubPage`, à remplacer par un tableau complet
- **Route** déjà configurée dans [`router/index.ts`](frontend/src/router/index.ts:97) — `/networks`, `requiresAuth: true`
- **Type** `NetworkResponse` à ajouter dans [`types/api.ts`](frontend/src/types/api.ts:1029) (après `VolumeCreateRequest`)
- **Service** `networksApi` à ajouter dans [`services/api.ts`](frontend/src/services/api.ts:383) (après `volumesApi`)
- **Table avec colonnes** : ID (12 premiers caractères), Nom, Driver, Scope, Subnet, Gateway, Interne (badge)
- **Fonctionnalités** : recherche par nom, état loading, état vide

### Patterns de référence
- **Type** : pattern [`VolumeResponse`](frontend/src/types/api.ts:1015) dans `types/api.ts`
- **Service API** : pattern [`volumesApi`](frontend/src/services/api.ts:374) dans `services/api.ts`
- **Vue** : pattern [`Volumes.vue`](frontend/src/views/Volumes.vue:1) (table + search + loading + empty)
- **Tests** : pattern [`Volumes.spec.ts`](frontend/tests/unit/views/Volumes.spec.ts:1)

### Exigences sécurité
- **Authentification** : Route frontend protégée par `requiresAuth: true` (guard global router). L'endpoint backend n'exige pas `get_current_active_user` (pattern Docker read-only existant).
- **Rôles** : Tous les utilisateurs authentifiés peuvent consulter les réseaux (lecture seule, aucune donnée sensible).
- **Isolation** : Pas de données utilisateur spécifiques — les réseaux Docker sont globaux.
- **Injection** : Aucun input utilisateur transmis au backend (GET sans paramètres).
- **Champs sensibles** : Aucun champ sensible dans `NetworkResponse`.
- **Logging** : Pas de données sensibles dans les logs (ID réseau, nom uniquement).
- **Audit** : Opération lecture seule, pas de traçabilité nécessaire.

## Critères d'acceptation (AC)
- [x] AC 1 : La vue Networks affiche la liste des réseaux via `GET /docker/networks` dans un tableau avec colonnes (Nom, Driver, Scope, Subnet/Gateway)
- [x] AC 2 : Un badge distingue les réseaux internes (`internal: true`) des réseaux externes
- [x] AC 3 : Le type TypeScript `NetworkResponse` est défini et `networksApi.list` est disponible
- [x] AC 4 : Build, lint et tests frontend passent sans erreur

## Dépendances
- Aucune

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter le type TypeScript `NetworkResponse`
**Objectif :** Définir l'interface TypeScript miroir du schéma Pydantic `NetworkResponse` backend pour le typage frontend.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter `NetworkResponse` après `VolumeCreateRequest` (fin de fichier)
**Référence :** Pattern [`VolumeResponse`](frontend/src/types/api.ts:1015)
**Exigences sécurité :** Aucune (type lecture seule, aucun champ sensible)
**Dépend de :** Aucune

```typescript
// Docker Networks

/** Réseau Docker — miroir du schéma Pydantic NetworkResponse backend */
export interface NetworkResponse {
  id: string
  name: string
  driver: string
  scope: string
  internal: boolean
  attachable: boolean
  ingress: boolean
  created: string
  subnet: string
  gateway: string
}
```

---

### Tâche 2 : Ajouter `networksApi` dans le service API
**Objectif :** Exposer la méthode `networksApi.list()` qui appelle `GET /docker/networks` pour être consommée par la vue.
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier — Ajouter `networksApi` après `volumesApi` (ligne ~383), ajouter l'import de `NetworkResponse` dans les imports existants, et ajouter `networks: networksApi` dans l'export default
**Référence :** Pattern [`volumesApi`](frontend/src/services/api.ts:374)
**Exigences sécurité :** Aucune (GET read-only, pas de paramètres utilisateur)
**Dépend de :** Tâche 1

```typescript
// Docker Networks API
export const networksApi = {
  list: () =>
    http.get<NetworkResponse[]>('/docker/networks'),
}
```

---

### Tâche 3 : Implémenter la vue `Networks.vue`
**Objectif :** Remplacer le `StubPage` par une vue fonctionnelle affichant la liste des réseaux Docker dans un tableau avec recherche, badge interne/externe, et gestion des états (loading, vide, erreur).
**Fichiers :**
- `frontend/src/views/Networks.vue` — Modifier — Remplacer l'intégralité du contenu (actuellement StubPage)
**Référence :** Pattern [`Volumes.vue`](frontend/src/views/Volumes.vue:1)
**Exigences sécurité :** Aucune (lecture seule, pas d'action modifiante)
**Dépend de :** Tâche 2

**Colonnes du tableau :**
1. **ID** — `row.id.substring(0, 12)` avec tooltip sur l'ID complet
2. **Nom** — `row.name`
3. **Driver** — `row.driver`
4. **Scope** — `row.scope`
5. **Subnet** — `row.subnet` (affiché si non vide)
6. **Gateway** — `row.gateway` (affiché si non vide)
7. **Interne** — Badge `el-tag` : `type="warning"` si `internal: true` (texte "Interne"), `type="success"` sinon (texte "Externe")

**Fonctionnalités :**
- `el-input` de recherche par nom (filtrage côté client via `computed`)
- `v-loading` pendant le chargement
- `el-empty` si la liste est vide après chargement
- `ElMessage.error` en cas d'échec API
- Appel `fetchNetworks()` dans `onMounted()`

---

### Tâche 4 : Écrire les tests unitaires de `Networks.vue`
**Objectif :** Couvrir les cas nominaux, les interactions et les exigences sécurité (pas de données sensibles dans le DOM).
**Fichiers :**
- `frontend/tests/unit/views/Networks.spec.ts` — Créer
**Référence :** Pattern [`Volumes.spec.ts`](frontend/tests/unit/views/Volumes.spec.ts:1)
**Exigences sécurité :** Test `test_no_sensitive_data_in_dom` obligatoire
**Dépend de :** Tâche 3

---

## Tests à écrire

### Tests unitaires Frontend — `frontend/tests/unit/views/Networks.spec.ts`

**Mock data :**
```typescript
const mockNetworks: NetworkResponse[] = [
  {
    id: 'abc123def456789',
    name: 'bridge',
    driver: 'bridge',
    scope: 'local',
    internal: false,
    attachable: false,
    ingress: false,
    created: '2025-01-15T10:30:00Z',
    subnet: '172.17.0.0/16',
    gateway: '172.17.0.1',
  },
  {
    id: 'def456abc789012',
    name: 'my-internal-net',
    driver: 'bridge',
    scope: 'local',
    internal: true,
    attachable: true,
    ingress: false,
    created: '2025-01-14T08:00:00Z',
    subnet: '172.18.0.0/16',
    gateway: '172.18.0.1',
  },
  {
    id: 'ghi789jkl012345',
    name: 'host',
    driver: 'host',
    scope: 'local',
    internal: false,
    attachable: false,
    ingress: false,
    created: '2025-01-13T12:00:00Z',
    subnet: '',
    gateway: '',
  },
]
```

**Mock API :**
```typescript
const mockList = vi.fn()
vi.mock('@/services/api', () => ({
  networksApi: {
    list: (...args: unknown[]) => mockList(...args),
  },
}))
```

**Cas de test obligatoires :**

| # | Test | Description |
|---|------|-------------|
| 1 | `affiche les réseaux dans le tableau après chargement` | Vérifie que les 3 réseaux sont affichés |
| 2 | `affiche le nom, driver et scope de chaque réseau` | Vérifie la présence des données textuelles |
| 3 | `affiche l ID tronqué avec 12 caractères` | Vérifie `row.id.substring(0, 12)` |
| 4 | `affiche le subnet et la gateway quand présents` | Vérifie l'affichage conditionnel |
| 5 | `n affiche pas subnet/gateway quand vides` | Vérifie le cas du réseau host |
| 6 | `affiche un badge Interne pour les réseaux internes` | Badge warning avec texte "Interne" |
| 7 | `affiche un badge Externe pour les réseaux externes` | Badge success avec texte "Externe" |
| 8 | `filtre les réseaux par nom` | Saisie dans le champ de recherche |
| 9 | `affiche el-empty si la liste est vide` | Mock retourne `[]` |
| 10 | `affiche ElMessage.error quand le chargement échoue` | Mock rejette |
| 11 | `test_no_sensitive_data_in_dom` | Aucun token/secret/password dans le HTML |

### Commandes de validation

```bash
# Frontend — tests unitaires
cd frontend && pnpm test -- tests/unit/views/Networks.spec.ts

# Frontend — build + lint
cd frontend && pnpm build && pnpm lint

# Frontend — tous les tests (vérifier qu'aucune régression)
cd frontend && pnpm test
```

---

## État d'avancement technique

- [x] Tâche 1 : Type TypeScript `NetworkResponse` ajouté dans `frontend/src/types/api.ts`
- [x] Tâche 2 : `networksApi` ajouté dans `frontend/src/services/api.ts`
- [x] Tâche 3 : Vue `Networks.vue` implémentée (table + recherche + badge interne)
- [x] Tâche 4 : Tests unitaires `Networks.spec.ts` écrits et passent
- [x] Build, lint et tests frontend passent sans erreur

## Notes d'implémentation

### Décisions techniques
- **Type `NetworkResponse`** : ajouté en fin de `frontend/src/types/api.ts` en suivant exactement le pattern `VolumeResponse` — 10 champs, tous non-nullables (conformes au schéma Pydantic backend).
- **`networksApi`** : ajouté après `volumesApi` dans `frontend/src/services/api.ts` ; exposé dans l'export default sous la clé `networks`.
- **`Networks.vue`** : vue lecture-seule (pas d'actions), 7 colonnes (ID tronqué 12 chars avec tooltip, Nom, Driver, Scope, Subnet, Gateway, Interne). Les champs `subnet`/`gateway` vides affichent un tiret `—`. Badge `el-tag` type `warning` pour Interne, `success` pour Externe.
- **Tests** : 11 tests couvrant tous les cas de la story — affichage, troncature ID, subnet/gateway conditionnels, badges, filtrage, empty state, erreur API, sécurité DOM.

### Ajustement test de filtre
Le test "filtre les réseaux par nom" utilisait initialement le terme "internal" mais `my-internal-net` a `driver: 'bridge'`, donc le mot "bridge" restait présent dans le DOM après filtrage. Corrigé en filtrant sur "host" (réseau host, driver host) — ce terme produit un résultat propre sans faux positifs.

### Résultats de validation
- **Tests** : 11/11 ✅ (`pnpm test -- tests/unit/views/Networks.spec.ts`)
- **Build** : ✅ exit 0 (`pnpm build`)
- **Lint** : ✅ exit 0, 0 erreur (`pnpm lint`) — 127 warnings pré-existants dans d'autres fichiers, aucun dans les fichiers STORY-015
