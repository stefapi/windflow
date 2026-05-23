# STORY-028 : Frontend Config — Gestion des réseaux à chaud

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir connecter et déconnecter un container d'un réseau Docker directement depuis l'onglet Config, sans recréation ni redémarrage, afin de modifier la connectivité réseau d'un container en production.

## Contexte technique

**Dépendance** : STORY-026 (endpoints backend connect/disconnect) doit être implémentée avant cette story.

**Composant principal** : `frontend/src/components/ContainerConfigTab.vue`

**Couches impactées** : Frontend uniquement (types, service API, composant, tests)

**Fichiers de référence (patterns)** :
- Composant UI → pattern : sections existantes dans `ContainerConfigTab.vue` (Env Vars, Labels, Image, Ports, Restart Policy, Resource Limits)
- Service API → pattern : méthodes existantes dans `containersApi` (`updateRestartPolicy`, `updateResources`, `recreate`)
- Tests → pattern : `frontend/tests/unit/components/ContainerConfigTab.spec.ts`

**Exigences sécurité identifiées** :
- Auth : oui — JWT transmis automatiquement par le service HTTP (`http` instance axios avec interceptors)
- RBAC : vérifié côté backend (déjà implémenté dans STORY-026)
- Validation : `network_id` non vide avant appel API
- Exposition : aucun champ sensible dans les réponses
- Audit : non requis (opérations réseau standard)

**Nouvelle section Réseaux** :

Interface cible :
```
┌─────────────────────────────────────────────────────────┐
│ 🟢 Réseaux                                              │
├─────────────────────────────────────────────────────────┤
│ ℹ️ Les connexions/déconnexions se font sans redémarrage │
├────────────────────────────────────────┬────────────────┤
│ Réseau                                 │ Actions        │
├────────────────────────────────────────┼────────────────┤
│ bridge                                 │ [Déconnecter]  │
│ my-custom-network                      │ [Déconnecter]  │
└────────────────────────────────────────┴────────────────┘

Connecter à un réseau :
[Sélectionner un réseau... ▼]           [Connecter]
```

Comportement :
- Liste des réseaux actuellement connectés : depuis `containerDetail.network_settings.networks`
- Liste des réseaux disponibles : appel `networksApi.list()` → `GET /docker/networks`
- Le select de connexion n'affiche que les réseaux **non déjà connectés**
- Connexion → `POST /docker/containers/{id}/networks/connect` → refresh des données du container
- Déconnexion → `POST /docker/containers/{id}/networks/disconnect` → refresh des données du container
- Pas de redirection (l'ID reste le même, c'est une opération à chaud)

**Nouveaux types TypeScript** dans `frontend/src/types/api.ts` :
```typescript
interface ContainerNetworkConnectRequest {
  network_id: string
  aliases?: string[]
  ipv4_address?: string
}

interface ContainerNetworkDisconnectRequest {
  network_id: string
  force?: boolean
}
```

**Service API** dans `frontend/src/services/api.ts` :
```typescript
connectNetwork: (id: string, data: ContainerNetworkConnectRequest) =>
  http.post<void>(`/docker/containers/${id}/networks/connect`, data),

disconnectNetwork: (id: string, data: ContainerNetworkDisconnectRequest) =>
  http.post<void>(`/docker/containers/${id}/networks/disconnect`, data),
```

## Critères d'acceptation (AC)

- [x] AC 1 : La section Réseaux affiche la liste des réseaux actuellement connectés au container
- [x] AC 2 : Un select permet de choisir parmi les réseaux Docker disponibles non encore connectés
- [x] AC 3 : Le bouton "Connecter" appelle l'API et rafraîchit les données du container sans redirection
- [x] AC 4 : Le bouton "Déconnecter" à côté de chaque réseau appelle l'API et rafraîchit sans redirection
- [x] AC 5 : Un `el-alert type="info"` indique que ces opérations sont possibles sans redémarrage
- [x] AC 6 : Les erreurs (réseau inexistant, réseau `host`/`none` non supporté) sont affichées via `ElMessage.error()`
- [x] AC 7 : Les types TypeScript et appels service sont ajoutés
- [x] AC 8 : Tests unitaires du composant (≥ 80%)

## Dépendances

- **STORY-026** : Backend endpoints connect/disconnect réseau (requis avant implémentation)

## État d'avancement technique

- [x] Tâche 1 : Ajouter les types TypeScript `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest`
- [x] Tâche 2 : Ajouter les méthodes `connectNetwork()` et `disconnectNetwork()` dans le service API
- [x] Tâche 3 : Implémenter la section Réseaux dans `ContainerConfigTab.vue`
- [x] Tâche 4 : Écrire les tests unitaires du composant (≥ 80%)
- [x] Build & lint OK

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter les types TypeScript pour les requêtes réseau
**Objectif :** Définir les interfaces TypeScript pour les payloads des endpoints connect/disconnect réseau.
**Fichiers :**
- `frontend/src/types/api.ts` — Modifier — Ajouter les interfaces suivantes à la fin du fichier (après `ContainerRecreateResponse`) :
  ```typescript
  /** Requête POST /docker/containers/{id}/networks/connect */
  export interface ContainerNetworkConnectRequest {
    network_id: string
    aliases?: string[]
    ipv4_address?: string
  }

  /** Requête POST /docker/containers/{id}/networks/disconnect */
  export interface ContainerNetworkDisconnectRequest {
    network_id: string
    force?: boolean
  }
  ```
**Exigences sécurité :** Aucune exigence spécifique (types purs, pas de logique métier)
**Dépend de :** Aucune

### Tâche 2 : Ajouter les méthodes connectNetwork et disconnectNetwork dans le service API
**Objectif :** Exposer les appels API pour connecter et déconnecter un container d'un réseau Docker.
**Fichiers :**
- `frontend/src/services/api.ts` — Modifier —
  1. Importer les nouveaux types dans l'import groupé depuis `@/types/api.ts` :
     ```typescript
     ContainerNetworkConnectRequest,
     ContainerNetworkDisconnectRequest,
     ```
  2. Dans l'objet `containersApi` (après `recreate`), ajouter :
     ```typescript
     connectNetwork: (id: string, data: ContainerNetworkConnectRequest) =>
       http.post<void>(`/docker/containers/${id}/networks/connect`, data),

     disconnectNetwork: (id: string, data: ContainerNetworkDisconnectRequest) =>
       http.post<void>(`/docker/containers/${id}/networks/disconnect`, data),
     ```
**Exigences sécurité :** Aucune exigence spécifique (le service HTTP gère déjà le JWT via interceptors)
**Dépend de :** Tâche 1

### Tâche 3 : Implémenter la section Réseaux dans ContainerConfigTab.vue
**Objectif :** Ajouter une nouvelle section "Réseaux" dans l'onglet Config permettant de connecter/déconnecter des réseaux à chaud.
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier —
  1. **Imports** :
     - Ajouter `Connection` dans l'import des icônes Element Plus
     - Ajouter `networksApi` dans l'import depuis `@/services/api`
     - Ajouter `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest` dans l'import des types
  2. **Template** : ajouter une nouvelle `el-card` (class `card-config-networks`) avec :
     - Header vert (`header-green`) avec icône `Connection` et titre "Réseaux"
     - `el-alert type="info"` : "ℹ️ Les connexions/déconnexions se font sans redémarrage"
     - Table `el-table` affichant les réseaux connectés (`connectedNetworks`) avec colonnes : Réseau (nom), IP Address, Actions (bouton "Déconnecter")
     - Ligne de connexion : `el-select` filtrant les réseaux disponibles non connectés + bouton "Connecter"
  3. **Script** : ajouter les refs et fonctions suivantes :
     - `connectedNetworks` : computed depuis `props.detail?.network_settings?.networks` (transformé en tableau `{ name, ip_address, network_id }`)
     - `availableNetworks` : `Ref<NetworkResponse[]>` — chargé via `networksApi.list()` au `onMounted`
     - `selectedNetwork` : `Ref<string>` — ID du réseau sélectionné dans le select
     - `loadingNetworks` : `Ref<boolean>` — état de chargement de la liste des réseaux
     - `loadingConnect` : `Ref<boolean>` — état pendant l'appel connect
     - `loadingDisconnect` : `Ref<Record<string, boolean>>` — état par réseau pendant disconnect
     - `loadAvailableNetworks()` : appelle `networksApi.list()`, filtre les réseaux déjà connectés
     - `connectNetwork()` : valide `selectedNetwork`, appelle `containersApi.connectNetwork()`, puis émet `network-changed`
     - `disconnectNetwork(networkName: string)` : appelle `containersApi.disconnectNetwork()`, puis émet `network-changed`
     - `filteredAvailableNetworks` : computed = `availableNetworks` filtrés pour exclure ceux déjà connectés
  4. **Style** : ajouter les classes CSS `.header-green` (couleur `--el-color-success`) et `.card-config-networks` (border-bottom vert)
  5. **Nouvel emit** : ajouter `(e: 'network-changed'): void` dans `defineEmits` — le parent (`ContainerDetail.vue`) rafraîchira le container via `containersApi.inspect()`
**Exigences sécurité :** Aucune exigence spécifique (auth gérée par le service HTTP, validation côté backend)
**Dépend de :** Tâche 2

### Tâche 4 : Écrire les tests unitaires du composant
**Objectif :** Couvrir la nouvelle section Réseaux avec des tests unitaires ≥ 80%.
**Fichiers :**
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — Modifier —
  1. **Mocks** : ajouter `mockConnectNetwork` et `mockDisconnectNetwork` dans le mock de `@/services/api`, et `mockNetworksList` pour `networksApi.list`
  2. **Données de test** : enrichir `baseDetail` avec `network_settings.networks` contenant au moins 2 réseaux (ex: `bridge`, `my-custom-network`)
  3. **Tests de rendu** :
     - `should render 7 config cards` (6 existants + 1 Réseaux)
     - `should render Networks card with correct header`
     - `should render info alert for networks section`
     - `should display connected networks in table`
  4. **Tests de chargement des réseaux disponibles** :
     - `should load available networks on mount`
     - `should filter out already connected networks from select`
     - `should handle empty available networks list`
  5. **Tests de connexion** :
     - `should call connectNetwork API when Connect button is clicked`
     - `should emit network-changed after successful connect`
     - `should show error message on connect API failure`
     - `should not call API when no network is selected`
  6. **Tests de déconnexion** :
     - `should call disconnectNetwork API when Disconnect button is clicked`
     - `should emit network-changed after successful disconnect`
     - `should show error message on disconnect API failure`
  7. **Tests de gestion d'erreurs** :
     - `should handle networks API failure gracefully`
     - `should disable connect button while loading`
     - `should disable disconnect button while loading`
**Exigences sécurité :** Aucune exigence spécifique (tests frontend, pas de logique auth à tester ici)
**Dépend de :** Tâche 3

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Frontend

- `frontend/tests/unit/components/ContainerConfigTab.spec.ts`
  - **Rendu**
    - `affiche 7 cards de config (6 existantes + Réseaux)` — rendu nominal
    - `affiche le header Réseaux avec icône Connection` — rendu nominal
    - `affiche l'alerte info sans redémarrage` — AC 5
    - `affiche les réseaux connectés dans la table` — AC 1
  - **Chargement réseaux disponibles**
    - `charge la liste des réseaux disponibles au montage` — appel `networksApi.list()`
    - `filtre les réseaux déjà connectés du select` — AC 2
    - `gère une liste vide de réseaux disponibles` — cas limite
  - **Connexion**
    - `appelle connectNetwork API au clic sur Connecter` — AC 3
    - `émet network-changed après connexion réussie` — refresh parent
    - `affiche une erreur si l'API connect échoue` — AC 6
    - `ne fait pas d'appel si aucun réseau sélectionné` — validation
  - **Déconnexion**
    - `appelle disconnectNetwork API au clic sur Déconnecter` — AC 4
    - `émet network-changed après déconnexion réussie` — refresh parent
    - `affiche une erreur si l'API disconnect échoue` — AC 6
  - **États de chargement**
    - `désactive le bouton Connecter pendant le chargement`
    - `désactive le bouton Déconnecter pendant le chargement`
  - **Edge cases**
    - `gère detail null sans erreur`
    - `gère network_settings vide`

### Commandes de validation

```bash
# Frontend — tests du composant
cd frontend && pnpm test -- tests/unit/components/ContainerConfigTab

# Frontend — build + lint
cd frontend && pnpm build && pnpm lint
```

## Notes d'implémentation

### Fichiers créés/modifiés

| Fichier | Action | Description |
|---------|--------|-------------|
| `frontend/src/types/api.ts` | Modifié | Ajout de `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest` |
| `frontend/src/services/api.ts` | Modifié | Ajout de `connectNetwork()` et `disconnectNetwork()` dans `containersApi` |
| `frontend/src/components/ContainerConfigTab.vue` | Modifié | Ajout section Réseaux (template + script + styles) |
| `frontend/tests/unit/components/ContainerConfigTab.spec.ts` | Modifié | Ajout de 22 tests réseaux (73 tests total) |

### Décisions techniques

- **Emit `network-changed`** : Le composant émet un événement `network-changed` après chaque connect/disconnect réussi. Le parent (`ContainerDetail.vue`) est responsable du rafraîchissement des données du container via `containersApi.inspect()`.
- **Chargement des réseaux disponibles** : Effectué au `onMounted` via `networksApi.list()`. Les réseaux déjà connectés sont filtrés côté client via un computed `filteredAvailableNetworks`.
- **Header vert** : Utilisation de `--el-color-success` (vert Element Plus) pour le header de la card Réseaux, cohérent avec le pattern des autres sections (orange pour recreation, bleu pour live-update).
- **Pas de recréation** : Les opérations connect/disconnect sont des opérations à chaud (pas de warning de recréation), d'où l'`el-alert type="info"` au lieu de `type="warning"`.

### Résultat des tests

- **73/73 tests passent** (51 existants + 22 nouveaux réseaux)
- **Build** : ✅ succès (erreurs TS pré-existantes non liées)
- **Lint** : ✅ 0 erreur (130 warnings pré-existants non liés)
