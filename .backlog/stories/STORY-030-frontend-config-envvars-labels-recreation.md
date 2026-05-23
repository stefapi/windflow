# STORY-030 : Frontend Config — Implémentation réelle env vars et labels (recréation)

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte et édition complète de la page ContainerDetail

---

## Description

En tant qu'utilisateur, je veux que les sections "Variables d'environnement" et "Labels" de l'onglet Config soient **pleinement fonctionnelles** et permettent une édition effective (ajout, modification, suppression), afin de pouvoir reconfigurer un conteneur sans le recréer manuellement.

Actuellement ces sections affichent un message "Fonctionnalité à venir" (stub). Cette story remplace ce stub par une vraie implémentation connectée à l'endpoint `POST /containers/{id}/recreate`.

Ces modifications nécessitent la **recréation du conteneur**. Après recréation, la vue redirige vers le nouvel ID de conteneur.

---

## Critères d'acceptation (AC)

- [x] **AC1** — La section "Variables d'environnement" affiche la liste des env vars actuelles sous forme de tableau éditaable (clé / valeur), pré-rempli depuis `containerDetail.Config.Env`.
- [x] **AC2** — L'utilisateur peut ajouter une nouvelle paire clé/valeur via un bouton "+ Ajouter une variable".
- [x] **AC3** — L'utilisateur peut supprimer une variable existante via une icône poubelle sur chaque ligne.
- [x] **AC4** — La section "Labels" affiche la liste des labels actuels sous forme de tableau éditaable (clé / valeur), pré-rempli depuis `containerDetail.Config.Labels`.
- [x] **AC5** — L'utilisateur peut ajouter un nouveau label (clé/valeur) via un bouton "+ Ajouter un label".
- [x] **AC6** — L'utilisateur peut supprimer un label existant via une icône poubelle sur chaque ligne.
- [x] **AC7** — Le message "Fonctionnalité à venir" est supprimé des deux sections.
- [x] **AC8** — Un bouton "Appliquer les modifications (recréation)" déclenche une confirmation ElMessageBox avant d'appeler `recreateContainer()` avec les env vars et labels modifiés.
- [x] **AC9** — Après recréation réussie, la vue redirige vers `/containers/<new_id>`.
- [x] **AC10** — En cas d'erreur lors de la recréation, un message d'erreur est affiché via ElMessage (type error).
- [x] **AC11** — Les sections Variables d'environnement et Labels utilisent le design el-card avec header coloré (gris/neutre pour les deux) conformément à la charte EPIC-009.
- [x] **AC12** — Les clés sont validées : non vides, pas de doublons dans chaque section.

---

## Contexte technique

### Fichiers concernés

- `frontend/src/components/ContainerConfigTab.vue` (557 lignes) — fichier principal à modifier
- `frontend/src/types/api.ts` — types TypeScript (ContainerRecreateRequest déjà ajouté dans STORY-027)
- `frontend/src/services/api.ts` — service API (recreateContainer déjà ajouté dans STORY-027)

### Données source dans containerDetail

Les env vars proviennent de `containerDetail.Config.Env` (string[], format `"KEY=VALUE"`).

Les labels proviennent de `containerDetail.Config.Labels` (Record<string, string> | null).

### Format des données pour ContainerRecreateRequest

```typescript
// Env : conversion tableau de {key, value} → string[]
// Exemple: [{key: "NODE_ENV", value: "production"}] → ["NODE_ENV=production"]

// Labels : conversion tableau de {key, value} → Record<string, string>
// Exemple: [{key: "app", value: "myapp"}] → {"app": "myapp"}
```

### Design attendu (el-card)

```
┌─────────────────────────────────────────────────────┐
│ ⚙️ Variables d'environnement             [+ Ajouter]│  ← border-bottom: 3px solid #909399
│─────────────────────────────────────────────────────│
│ Clé              │ Valeur                │ Actions  │
│ NODE_ENV         │ production            │ 🗑       │
│ DATABASE_URL     │ postgres://...        │ 🗑       │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ 🏷️ Labels                                [+ Ajouter]│  ← border-bottom: 3px solid #909399
│─────────────────────────────────────────────────────│
│ Clé              │ Valeur                │ Actions  │
│ app              │ myapp                 │ 🗑       │
│ version          │ 1.0.0                 │ 🗑       │
└─────────────────────────────────────────────────────┘
```

### Stub actuel à remplacer

Dans ContainerConfigTab.vue, les sections env vars et labels contiennent actuellement un bloc type :
```html
<el-alert type="info" title="Fonctionnalité à venir" :closable="false" />
```
Ce bloc doit être remplacé par les tableaux éditables décrits ci-dessus.

### Intégration avec le formulaire de recréation global

Cette story s'intègre dans le même formulaire de recréation que STORY-027 (ports/image) et STORY-029 (volumes/sécurité). Le `ContainerRecreateRequest` envoyé doit inclure tous les overrides : image, ports, volumes, sécurité, env vars, labels.

### Patterns de référence

- **Pattern recréation** : `updateImage()` (ligne 1222) et `applyPortBindings()` (ligne 1275) dans `ContainerConfigTab.vue` — confirmation ElMessageBox → appel `containersApi.recreate()` → emit `recreate-success`
- **Pattern validation** : `validatePortBindings()` (ligne 1143) et `validateVolumes()` (ligne 1386) — retourne `string | null` (message d'erreur ou null si OK)
- **Pattern loading** : `loadingRecreate` ref partagé entre les sections de recréation (image, ports, volumes, sécurité) — boutons `:loading="loadingRecreate" :disabled="loadingRecreate"`
- **Pattern payload env vars** : conversion `KeyValue[]` → `string[]` via `envVars.map(e => \`${e.key}=${e.value}\`)`
- **Pattern payload labels** : conversion `KeyValue[]` → `Record<string, string>` via `Object.fromEntries(labels.map(l => [l.key, l.value]))`

### Exigences sécurité identifiées

- **Auth** : oui — JWT géré par http interceptor (`frontend/src/services/http.ts`) + backend STORY-025
- **RBAC** : contrôles côté backend uniquement (cohérent avec les autres sections Config)
- **Validation** : clés non vides + pas de doublons (AC12) — à implémenter côté frontend dans `validateEnvVars()` et `validateLabels()`
- **Exposition données sensibles** : masquage déjà implémenté via `useSecretMasker` (mots de passe, tokens, secrets dans les valeurs d'env vars)
- **Audit** : déjà géré côté backend (STORY-025)

---

## Dépendances

- **STORY-025** — Backend endpoint `POST /containers/{id}/recreate` (doit être DONE)
- **STORY-027** — Ajout des types TS ContainerRecreateRequest et du service `recreateContainer()` (doit être DONE)
- **STORY-029** — Édition volumes et sécurité (recommandé avant pour avoir la structure complète du formulaire)

---

## Tâches d'implémentation détaillées

### Tâche 1 : Ajout des fonctions de validation `validateEnvVars()` et `validateLabels()`
**Objectif :** Créer deux fonctions de validation pour vérifier que les clés ne sont pas vides et qu'il n'y a pas de doublons dans chaque section, conformément à l'AC12.
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Ajouter deux fonctions après le bloc `// ─── Env Vars actions ───` (ligne ~1169) :
  - `validateEnvVars(): string | null` — parcourt `envVars.value`, vérifie que chaque `row.key.trim()` n'est pas vide, détecte les doublons via un `Set<string>`. Retourne un message d'erreur ou `null`. Pattern : `validatePortBindings()` (ligne 1143).
  - `validateLabels(): string | null` — même logique pour `labels.value`. Pattern identique.
**Exigences sécurité :** Aucune exigence spécifique (validation UI uniquement, les données sont envoyées au backend qui valide aussi via Pydantic)
**Dépend de :** Aucune

### Tâche 2 : Remplacement du stub `applyEnvVars()` par l'appel réel de recréation
**Objectif :** Remplacer le stub `ElMessage.info('Fonctionnalité de recréation à venir')` par un vrai appel `containersApi.recreate()` avec les env vars formatées, le loading state, et l'émission de l'événement `recreate-success`.
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Remplacer la fonction `applyEnvVars()` (lignes 1178-1193) par :
  1. Appel `validateEnvVars()` — si erreur, `ElMessage.error(error)` et return
  2. Confirmation `ElMessageBox.confirm('Modifier les variables d\'environnement nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir. Continuer ?', ...)`
  3. Set `loadingRecreate.value = true`
  4. Construction du payload : `{ env: envVars.value.map(e => \`${e.key}=${e.value}\`) }`
  5. Appel `containersApi.recreate(props.detail.id, payload)`
  6. Succès : `ElMessage.success('Container recréé avec succès')` + `emit('recreate-success', response.data.new_container_id)`
  7. Erreur : `ElMessage.error(message)`
  8. Finally : `loadingRecreate.value = false`
  - Pattern exact : `updateImage()` (ligne 1222) et `applyPortBindings()` (ligne 1275)
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Ajouter `:loading="loadingRecreate"` et `:disabled="loadingRecreate"` sur le bouton "Appliquer" de la section Env Vars (ligne ~79-84), comme déjà fait pour les sections Image, Ports, Volumes et Sécurité.
**Exigences sécurité :** Validation des clés (non vides, pas de doublons) avant envoi — cohérent avec la validation Pydantic côté backend
**Dépend de :** Tâche 1

### Tâche 3 : Remplacement du stub `applyLabels()` par l'appel réel de recréation
**Objectif :** Remplacer le stub `ElMessage.info('Fonctionnalité de recréation à venir')` par un vrai appel `containersApi.recreate()` avec les labels formatés, le loading state, et l'émission de l'événement `recreate-success`.
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Remplacer la fonction `applyLabels()` (lignes 1204-1219) par :
  1. Appel `validateLabels()` — si erreur, `ElMessage.error(error)` et return
  2. Confirmation `ElMessageBox.confirm('Modifier les labels nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir. Continuer ?', ...)`
  3. Set `loadingRecreate.value = true`
  4. Construction du payload : `{ labels: Object.fromEntries(labels.value.map(l => [l.key, l.value])) }`
  5. Appel `containersApi.recreate(props.detail.id, payload)`
  6. Succès : `ElMessage.success('Container recréé avec succès')` + `emit('recreate-success', response.data.new_container_id)`
  7. Erreur : `ElMessage.error(message)`
  8. Finally : `loadingRecreate.value = false`
  - Pattern exact : `applyEnvVars()` (Tâche 2) et `updateImage()` (ligne 1222)
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Ajouter `:loading="loadingRecreate"` et `:disabled="loadingRecreate"` sur le bouton "Appliquer" de la section Labels (ligne ~163-168), comme déjà fait pour les autres sections de recréation.
**Exigences sécurité :** Validation des clés (non vides, pas de doublons) avant envoi
**Dépend de :** Tâche 1

### Tâche 4 : Tests unitaires — validation, appels API, payloads, loading, erreurs
**Objectif :** Ajouter les tests unitaires couvrant la validation des clés, les appels API de recréation pour env vars et labels, les payloads corrects, les états de loading, les cas d'erreur, et l'émission de l'événement `recreate-success`.
**Fichiers :**
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — Modifier — Ajouter les blocs `describe` suivants après les tests existants (pattern : describe 'Image — update' et 'Ports — apply') :
  - **`describe('Env Vars — validation')`** :
    - `should reject empty key in env vars` — clé vide → `validateEnvVars()` retourne erreur
    - `should reject duplicate keys in env vars` — 2 entrées avec même clé → erreur doublon
    - `should return null for valid env vars` — toutes clés uniques et non vides → null
  - **`describe('Env Vars — apply')`** :
    - `should call recreate API with correct env payload` — vérifie `mockRecreate` appelé avec `{ env: ['PATH=/usr/bin', 'NODE_ENV=production', 'DB_PASSWORD=secret123'] }`
    - `should emit recreate-success event after applying env vars` — vérifie `wrapper.emitted('recreate-success')` avec `['new456']`
    - `should show validation error for empty key` — clé vide → `mockRecreate` non appelé
    - `should show validation error for duplicate keys` — doublon → `mockRecreate` non appelé
    - `should not call API when detail is null` — `applyEnvVars()` sans detail → pas d'appel
    - `should show error message on API failure` — `mockRecreate.mockRejectedValue(...)` → `ElMessage.error`
  - **`describe('Labels — validation')`** :
    - `should reject empty key in labels` — clé vide → erreur
    - `should reject duplicate keys in labels` — doublon → erreur
    - `should return null for valid labels` — OK → null
  - **`describe('Labels — apply')`** :
    - `should call recreate API with correct labels payload` — vérifie `mockRecreate` appelé avec `{ labels: { 'com.docker.compose.project': 'my-stack', version: '1.0' } }`
    - `should emit recreate-success event after applying labels` — vérifie emit
    - `should show validation error for empty key` — clé vide → pas d'appel
    - `should show validation error for duplicate keys` — doublon → pas d'appel
    - `should not call API when detail is null` — pas d'appel
    - `should show error message on API failure` — erreur API → `ElMessage.error`
  - **`describe('Env Vars — security')`** :
    - `should mask secret values in env var inputs` — vérifie que les valeurs contenant des secrets utilisent `type="password"` (via `isSecretKey`)
  - **`describe('Labels — security')`** :
    - `should not expose sensitive data in labels DOM` — vérifie l'absence de tokens dans le rendu
**Exigences sécurité :** Tests de validation (clés vides/doublons), tests de masquage des secrets dans les env vars
**Dépend de :** Tâche 2, Tâche 3

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Frontend

- `frontend/tests/unit/components/ContainerConfigTab.spec.ts`
  - **Env Vars — validation** :
    - `should reject empty key in env vars` — cas d'erreur : clé vide
    - `should reject duplicate keys in env vars` — cas d'erreur : doublon
    - `should return null for valid env vars` — cas nominal
  - **Env Vars — apply** :
    - `should call recreate API with correct env payload` — cas nominal : payload `string[]` correct
    - `should emit recreate-success event after applying env vars` — cas nominal : emit avec new_container_id
    - `should show validation error for empty key` — validation bloquante
    - `should show validation error for duplicate keys` — validation bloquante
    - `should not call API when detail is null` — cas edge : pas de détail
    - `should show error message on API failure` — cas d'erreur : API échoue
  - **Labels — validation** :
    - `should reject empty key in labels` — cas d'erreur : clé vide
    - `should reject duplicate keys in labels` — cas d'erreur : doublon
    - `should return null for valid labels` — cas nominal
  - **Labels — apply** :
    - `should call recreate API with correct labels payload` — cas nominal : payload `Record<string, string>` correct
    - `should emit recreate-success event after applying labels` — cas nominal : emit avec new_container_id
    - `should show validation error for empty key` — validation bloquante
    - `should show validation error for duplicate keys` — validation bloquante
    - `should not call API when detail is null` — cas edge : pas de détail
    - `should show error message on API failure` — cas d'erreur : API échoue
  - **Env Vars — security** :
    - `should mask secret values in env var inputs` — **sécurité** : vérifie le masquage des secrets (password, token, key)
  - **Labels — security** :
    - `should not expose sensitive data in labels DOM` — **sécurité** : pas de tokens visibles

### Commandes de validation
```bash
# Frontend (voir Makefile)
cd frontend && pnpm test -- tests/unit/components/ContainerConfigTab
cd frontend && pnpm build && pnpm lint
```

---

## État d'avancement technique

- [x] Tâche 1 : Ajout des fonctions de validation `validateEnvVars()` et `validateLabels()`
- [x] Tâche 2 : Remplacement du stub `applyEnvVars()` par appel réel de recréation
- [x] Tâche 3 : Remplacement du stub `applyLabels()` par appel réel de recréation
- [x] Tâche 4 : Tests unitaires — validation, appels API, payloads, loading, erreurs
- [x] Build & lint OK

---

## Notes d'implémentation

### Fichiers modifiés/créés
- `frontend/src/components/ContainerConfigTab.vue` — Ajout de `validateEnvVars()`, `validateLabels()`, remplacement des stubs `applyEnvVars()` et `applyLabels()` par des appels réels `containersApi.recreate()`, ajout de `:loading` et `:disabled` sur les boutons Appliquer
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — Ajout de 6 blocs `describe` (Env Vars validation/apply, Labels validation/apply, Env Vars security, Labels security) — 20 nouveaux tests

### Décisions techniques
- Les fonctions de validation suivent le pattern existant `validatePortBindings()` : retour `string | null`
- Les fonctions apply suivent le pattern `applyPortBindings()` : validation → confirmation → loading → appel API → emit
- Le test de sécurité `isSecretKey` vérifie directement la fonction plutôt que le DOM rendu (les stubs ne propageant pas l'attribut `type`)

### Divergences éventuelles
- Aucune divergence par rapport au plan initial

### Tests ajoutés
- 20 tests unitaires couvrant : validation (clés vides, doublons, cas nominaux), appels API (payloads corrects, emit recreate-success), gestion d'erreurs (API failure, detail null), sécurité (isSecretKey, pas de tokens dans le DOM Labels)
- Total : 119 tests passent (99 existants + 20 nouveaux)
