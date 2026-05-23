# STORY-029 : Frontend Config — Édition volumes et sécurité (recréation)

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte et édition complète de la page ContainerDetail

---

## Description

En tant qu'utilisateur, je veux pouvoir modifier les **volumes montés** et les **paramètres de sécurité** (privilege, readonly rootfs, capabilities) d'un conteneur directement depuis l'onglet Config de la page ContainerDetail, afin de personnaliser le comportement du conteneur sans avoir à le recréer manuellement en ligne de commande.

Ces modifications nécessitent la **recréation du conteneur** (via l'endpoint `POST /containers/{id}/recreate` créé dans STORY-025). Après recréation, la vue doit rediriger vers le nouvel ID de conteneur.

---

## Critères d'acceptation (AC)

- [x] **AC1** — Une section "Volumes" est affichée dans l'onglet Config avec un tableau éditable : colonnes Type (bind/volume/tmpfs), Source, Destination (mount point), Mode (ro/rw).
- [x] **AC2** — L'utilisateur peut ajouter une nouvelle entrée volume via un bouton "+ Ajouter un volume".
- [x] **AC3** — L'utilisateur peut supprimer une entrée volume existante via une icône poubelle sur chaque ligne.
- [x] **AC4** — Une section "Sécurité" est affichée avec : toggle Privileged, toggle ReadonlyRootfs, input tags Cap Add, input tags Cap Drop.
- [x] **AC5** — Les valeurs initiales des champs volumes et sécurité sont pré-remplies depuis les données du conteneur courant (`containerDetail`).
- [x] **AC6** — Un bouton "Appliquer les modifications (recréation)" déclenche une confirmation ElMessageBox avant d'appeler `recreateContainer()`.
- [x] **AC7** — Après recréation réussie, la vue redirige vers `/containers/<new_id>`.
- [x] **AC8** — En cas d'erreur lors de la recréation, un message d'erreur est affiché via ElMessage (type error).
- [x] **AC9** — Les sections Volumes et Sécurité utilisent le design el-card avec header coloré (vert pour Volumes, rouge pour Sécurité) conformément à la charte EPIC-009.
- [x] **AC10** — Les champs sont correctement validés (destination de volume non vide, pas de doublon de destination).

---

## Contexte technique

### Fichiers concernés

- `frontend/src/components/ContainerConfigTab.vue` (557 lignes) — fichier principal à modifier
- `frontend/src/types/api.ts` — types TypeScript (ContainerRecreateRequest déjà ajouté dans STORY-027)
- `frontend/src/services/api.ts` — service API (recreateContainer déjà ajouté dans STORY-027)

### Données source dans containerDetail

Les informations volumes proviennent de `containerDetail.HostConfig.Binds` (liste de strings `"source:dest:mode"`) et `containerDetail.Mounts` (objets avec Type, Source, Destination, Mode).

Les informations sécurité proviennent de :
- `containerDetail.HostConfig.Privileged` (boolean)
- `containerDetail.HostConfig.ReadonlyRootfs` (boolean)
- `containerDetail.HostConfig.CapAdd` (string[] | null)
- `containerDetail.HostConfig.CapDrop` (string[] | null)

### Design attendu (el-card)

```
┌─────────────────────────────────────────────────┐
│ 🟢 Volumes                              [+ Add] │  ← border-bottom: 3px solid #67c23a
│─────────────────────────────────────────────────│
│ Type    │ Source        │ Destination │ Mode │ ✕ │
│ bind    │ /host/path    │ /container  │ rw   │ 🗑 │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ 🔴 Sécurité                                     │  ← border-bottom: 3px solid #f56c6c
│─────────────────────────────────────────────────│
│ Privileged      [ toggle ]                      │
│ Readonly Rootfs [ toggle ]                      │
│ Cap Add         [ tag-input ]                   │
│ Cap Drop        [ tag-input ]                   │
└─────────────────────────────────────────────────┘
```

### Pattern de volume pour ContainerRecreateRequest

```typescript
// Volume entry dans le formulaire local
interface VolumeEntry {
  type: 'bind' | 'volume' | 'tmpfs'
  source: string
  destination: string
  mode: 'ro' | 'rw'
}

// Conversion en Binds pour ContainerRecreateRequest
// type 'bind': "source:destination:mode"
// type 'volume': "name:destination:mode"
```

### Attention

STORY-027 a déjà ajouté un bouton "Appliquer les modifications (recréation)" pour les ports et l'image. La section volumes et sécurité doit s'intégrer dans **le même formulaire de recréation** (même bouton de soumission), en enrichissant le `ContainerRecreateRequest` avec les champs volumes et sécurité.

### Fichiers de référence (patterns)

- **Composant UI** → pattern : sections existantes dans `ContainerConfigTab.vue` (Ports pour le tableau éditable, Image pour le pattern recreate, Networks pour les toggles)
- **Service API** → `containersApi.recreate()` déjà existant dans `frontend/src/services/api.ts` (ligne 381)
- **Types** → `ContainerRecreateRequest` déjà existant dans `frontend/src/types/api.ts` (ligne 1137) avec champs `mounts`, `privileged`, `readonly_rootfs`, `cap_add`, `cap_drop`
- **Types données source** → `ContainerMount` (ligne 697), `ContainerHostConfigInfo` (ligne 592) avec `binds`, `cap_add`, `cap_drop`, `privileged`, `readonly_rootfs`
- **Tests** → pattern : `frontend/tests/unit/components/ContainerConfigTab.spec.ts`

### Exigences sécurité identifiées

- **Auth** : oui — JWT transmis automatiquement par le service HTTP (axios interceptors)
- **RBAC** : vérifié côté backend (déjà implémenté dans STORY-025)
- **Validation** : destination de volume non vide, pas de doublon de destination (AC10)
- **Exposition** : aucun champ sensible dans les réponses
- **Audit** : non requis (opérations standard de recréation)

---

## Dépendances

- **STORY-025** — Backend endpoint `POST /containers/{id}/recreate` (doit être DONE)
- **STORY-027** — Ajout des types TS ContainerRecreateRequest et du service `recreateContainer()` (doit être DONE)

---

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter l'interface VolumeEntry et les refs réactives pour volumes et sécurité
**Objectif :** Déclarer les types et l'état réactif nécessaires pour les sections Volumes et Sécurité dans le `<script setup>`
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Dans la section `<script setup>`, après les refs Networks (après ligne ~669), ajouter :
  - Interface `VolumeEntry { type: 'bind' | 'volume' | 'tmpfs'; source: string; destination: string; mode: 'ro' | 'rw' }`
  - `const volumeEntries = ref<VolumeEntry[]>([])`
  - `const privileged = ref(false)`
  - `const readonlyRootfs = ref(false)`
  - `const capAdd = ref<string[]>([])`
  - `const capDrop = ref<string[]>([])`
  - `const newCapAdd = ref('')`
  - `const newCapDrop = ref('')`
  - Fonctions utilitaires : `addVolumeEntry()`, `removeVolumeEntry(index)`, `addCapAdd()`, `removeCapAdd(index)`, `addCapDrop()`, `removeCapDrop(index)`
**Exigences sécurité :** Aucune exigence spécifique (déclaration d'état uniquement)
**Dépend de :** Aucune

### Tâche 2 : Ajouter les sections template Volumes (🟢) et Sécurité (🔴)
**Objectif :** Créer les deux nouvelles sections el-card dans le template, entre la section Resources et la section Networks
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Dans le `<template>`, insérer après la section Resources (après `</el-card>` ligne ~499) et avant la section Networks (ligne ~501) :
  - **Section Volumes** (pattern : section Ports existante) :
    - `el-card` avec `class="config-card card-config-volumes"` et `shadow="hover"`
    - Header : `<div class="card-header header-green">` avec icône `Coin` (ou `FolderOpened`) et texte "Volumes"
    - `el-alert type="warning"` : "⚠️ Modifier les volumes nécessite de recréer le container."
    - `el-table` bindée sur `volumeEntries` avec colonnes :
      - Type : `el-select` (options : bind, volume, tmpfs)
      - Source : `el-input` placeholder "Chemin hôte ou nom du volume"
      - Destination : `el-input` placeholder "Point de montage dans le container"
      - Mode : `el-select` (options : rw, ro)
      - Actions : `el-button` icône poubelle `Delete` → `removeVolumeEntry($index)`
    - Bouton "+ Ajouter un volume" (`CirclePlus`)
    - Bouton "Appliquer" (`type="primary"`, `:loading="loadingRecreate"`, `@click="applyVolumesAndSecurity"`)
  - **Section Sécurité** (pattern : section Resources existante) :
    - `el-card` avec `class="config-card card-config-security"` et `shadow="hover"`
    - Header : `<div class="card-header header-red">` avec icône `Lock` et texte "Sécurité"
    - `el-alert type="warning"` : "⚠️ Ces modifications nécessitent de recréer le container."
    - `el-descriptions` avec :
      - Ligne "Mode privilégié" : `el-switch` bindé sur `privileged`
      - Ligne "Read-only rootfs" : `el-switch` bindé sur `readonlyRootfs`
    - Zone "Capabilities ajoutées (cap_add)" :
      - `el-tag` (closable) pour chaque entrée de `capAdd` → `removeCapAdd(index)`
      - `el-input` + bouton "Ajouter" → `addCapAdd()`
    - Zone "Capabilities retirées (cap_drop)" :
      - `el-tag` (closable) pour chaque entrée de `capDrop` → `removeCapDrop(index)`
      - `el-input` + bouton "Ajouter" → `addCapDrop()`
    - Bouton "Appliquer les modifications (recréation)" (`type="primary"`, `:loading="loadingRecreate"`, `@click="applyVolumesAndSecurity"`)
  - Ajouter l'import de l'icône `Lock` et `Coin` (ou `FolderOpened`) depuis `@element-plus/icons-vue`
**Exigences sécurité :** Aucune exigence spécifique (UI uniquement)
**Dépend de :** Tâche 1

### Tâche 3 : Ajouter la logique de peuplement (watch), validation et fonction applyVolumesAndSecurity
**Objectif :** Peupler les champs volumes et sécurité depuis les données du container, valider les entrées, et envoyer la requête de recréation
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Dans le `<script setup>` :
  - **Watch** (dans le `watch(() => props.detail)` existant, après la section Resources ~ligne 810) :
    - Volumes : parser `detail.mounts` (tableau d'objets avec `Type`, `Source`, `Destination`, `Mode`) en `VolumeEntry[]`. Si `mounts` est vide/null, vérifier aussi `detail.host_config.binds` (format `"source:dest:mode"`)
    - Sécurité : `privileged.value = detail.host_config?.privileged ?? false`, `readonlyRootfs.value = detail.host_config?.readonly_rootfs ?? false`, `capAdd.value = detail.host_config?.cap_add ?? []`, `capDrop.value = detail.host_config?.cap_drop ?? []`
  - **Fonction `parseMounts(mounts, binds)`** : convertir les mounts Docker en `VolumeEntry[]`
  - **Fonction `buildMountsPayload()`** : convertir `volumeEntries` en `Array<Record<string, unknown>>` au format Docker (`{ Type, Source, Target, ReadOnly? }`)
  - **Fonction `validateVolumes()`** : vérifier destination non vide + pas de doublon de destination. Retourne `string | null` (message d'erreur ou null)
  - **Fonction `applyVolumesAndSecurity()`** (pattern : `applyPortBindings` existante) :
    1. Valider les volumes via `validateVolumes()`. Si erreur → `ElMessage.error()` + return
    2. `ElMessageBox.confirm()` avec message "Modifier les volumes et/ou la sécurité nécessite de recréer le container. Le layer writable sera perdu. Continuer ?"
    3. Construire le payload `ContainerRecreateRequest` avec `mounts: buildMountsPayload()`, `privileged`, `readonly_rootfs`, `cap_add`, `cap_drop`
    4. Appeler `containersApi.recreate(props.detail.id, payload)`
    5. Succès → `ElMessage.success('Container recréé avec succès')` + `emit('recreate-success', response.data.new_container_id)`
    6. Erreur → `ElMessage.error(message)`
    7. `loadingRecreate` géré dans finally
**Exigences sécurité :** Validation des entrées (destination non vide, pas de doublon) — AC10
**Dépend de :** Tâche 1

### Tâche 4 : Ajouter les styles CSS pour les nouvelles cards
**Objectif :** Ajouter les couleurs de bordure pour les cards Volumes (vert) et Sécurité (rouge)
**Fichiers :**
- `frontend/src/components/ContainerConfigTab.vue` — Modifier — Dans la section `<style scoped>`, après les styles existants (ligne ~1147) :
  - `.card-config-volumes :deep(.el-card__header) { border-bottom: 3px solid var(--el-color-success); }` (vert)
  - `.card-config-security :deep(.el-card__header) { border-bottom: 3px solid var(--el-color-danger); }` (rouge)
  - `.cap-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }` (layout tags capabilities)
  - `.cap-input-row { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }` (layout input + bouton)
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 2

### Tâche 5 : Mettre à jour les tests unitaires
**Objectif :** Couvrir les nouvelles sections Volumes et Sécurité avec des tests unitaires complets
**Fichiers :**
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` — Modifier — Ajouter les tests suivants :
  - **Rendu** :
    - `should render 9 config cards` (7 existantes + 2 nouvelles : Volumes + Sécurité) — mettre à jour le test existant "should render 7 config cards"
    - `should render Volumes card header with green color` — vérifier le titre "Volumes" dans le header
    - `should render Security card header with red color` — vérifier le titre "Sécurité" dans le header
    - `should render volume table with columns Type, Source, Destination, Mode` — vérifier les colonnes
    - `should render security toggles for Privileged and ReadonlyRootfs` — vérifier les switches
    - `should render cap_add and cap_drop tag input zones` — vérifier les zones de tags
  - **Peuplement initial** :
    - `should populate volume entries from containerDetail.mounts` — vérifier que les mounts sont parsés
    - `should populate security fields from containerDetail.host_config` — vérifier privileged, readonly_rootfs, cap_add, cap_drop
    - `should handle null mounts and security fields gracefully` — cas où tout est null
  - **Interactions** :
    - `should add a new volume entry on button click` — cliquer "+ Ajouter un volume"
    - `should remove a volume entry on delete button click` — cliquer icône poubelle
    - `should add a cap_add tag` — saisir + ajouter
    - `should remove a cap_add tag on close` — cliquer le × du tag
    - `should add a cap_drop tag` — saisir + ajouter
    - `should remove a cap_drop tag on close` — cliquer le × du tag
  - **Validation** :
    - `should show error when volume destination is empty` — valider avec destination vide
    - `should show error when duplicate volume destination exists` — valider avec doublon
  - **Recréation** :
    - `should call recreate API with volumes and security payload on apply` — appel API avec bon payload
    - `should emit recreate-success with new container ID` — vérifier l'emit
    - `should show error message when recreate fails` — cas d'erreur API
    - `should not recreate when user cancels confirmation` — annulation ElMessageBox
  - **Mise à jour du mock `baseDetail`** : ajouter `mounts` avec des données de test et des valeurs non-null pour `cap_add`, `cap_drop`, `privileged`, `readonly_rootfs` dans `host_config`
  - **Mise à jour des stubs** : ajouter les stubs pour `el-switch`, `el-tag` si nécessaire
**Exigences sécurité :** Tests de validation (destination vide, doublon)
**Dépend de :** Tâches 1-4

---

## Tests à écrire

> Patterns détaillés : `.clinerules/35-testing-quality-gates.md`
> Tests sécurité obligatoires : `.clinerules/40-security.md`

### Unitaires Frontend
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts`
  - **Rendu** :
    - `should render 9 config cards` — 7 existantes + Volumes + Sécurité
    - `should render Volumes card header` — titre "Volumes" présent
    - `should render Security card header` — titre "Sécurité" présent
    - `should render volume table with editable columns` — colonnes Type/Source/Destination/Mode
    - `should render security toggles` — switches Privileged + ReadonlyRootfs
    - `should render cap_add and cap_drop tag zones` — zones de saisie de capabilities
  - **Peuplement initial** :
    - `should populate volume entries from containerDetail.mounts` — données pré-remplies (AC5)
    - `should populate security fields from host_config` — privileged, readonly_rootfs, cap_add, cap_drop pré-remplis (AC5)
    - `should handle null mounts gracefully` — mounts null → tableau vide
    - `should handle null security fields gracefully` — cap_add/cap_drop null → tableaux vides
  - **Interactions volumes** :
    - `should add empty volume entry on + button click` — AC2
    - `should remove volume entry on delete click` — AC3
  - **Interactions sécurité** :
    - `should toggle privileged switch` — AC4
    - `should toggle readonlyRootfs switch` — AC4
    - `should add cap_add tag` — saisir + ajouter
    - `should remove cap_add tag on close` — cliquer ×
    - `should add cap_drop tag` — saisir + ajouter
    - `should remove cap_drop tag on close` — cliquer ×
  - **Validation** :
    - `should show error on empty volume destination` — AC10
    - `should show error on duplicate volume destination` — AC10
  - **Recréation** :
    - `should call containersApi.recreate with mounts and security payload` — payload correct
    - `should emit recreate-success with new ID after successful recreate` — AC7
    - `should show ElMessage.error on recreate failure` — AC8
    - `should not call recreate when user cancels confirmation` — AC6 annulation
    - `should show loading state during recreate` — bouton loading

### Commandes de validation
```bash
# Frontend
cd frontend && pnpm test -- tests/unit/components/ContainerConfigTab
cd frontend && pnpm build && pnpm lint
```

---

## État d'avancement technique
- [x] Tâche 1 : Interface VolumeEntry + refs réactives volumes et sécurité
- [x] Tâche 2 : Sections template Volumes (🟢) et Sécurité (🔴)
- [x] Tâche 3 : Watch peuplement + validation + applyVolumesAndSecurity()
- [x] Tâche 4 : Styles CSS cards Volumes et Sécurité
- [x] Tâche 5 : Tests unitaires
- [x] Build & lint OK

---

## Notes d'implémentation

**Date :** 2026-05-23

### Fichiers modifiés/créés
- `frontend/src/components/ContainerConfigTab.vue` : Ajout des sections Volumes (🟢) et Sécurité (🔴) avec interface `VolumeEntry`, refs réactives, peuplement depuis `detail.mounts` et `detail.host_config`, validation des volumes, fonctions `addCapAdd/removeCapAdd/addCapDrop/removeCapDrop`, et fonction `applyVolumesAndSecurity()` appelant `containersApi.recreate()`
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` : Ajout de 30 tests couvrant le rendu, le peuplement, les interactions (add/remove volumes et capabilities), la validation, et la recréation

### Décisions techniques
- Utilisation de `Record<string, unknown>` pour le payload recreate afin de satisfaire `noPropertyAccessFromIndexSignature` du tsconfig strict
- Les mounts sont parsés depuis `detail.mounts` (format Docker inspect) en priorité, avec fallback sur `detail.host_config.binds` (format "source:dest:mode")
- Les capabilities sont normalisées en majuscules lors de l'ajout pour cohérence
- Les tags cap_add/cap_drop vides ne sont pas inclus dans le payload recreate (undefined)

### Divergences par rapport à l'analyse
- Aucune divergence significative

### Tests ajoutés
- `frontend/tests/unit/components/ContainerConfigTab.spec.ts` : 99 tests au total (30 nouveaux pour STORY-029)
  - Volumes rendering : 2 tests
  - Volumes pre-fill : 3 tests
  - Volumes add/remove : 2 tests
  - Volumes validation : 3 tests
  - Security rendering : 2 tests
  - Security pre-fill : 2 tests
  - Security capabilities add/remove : 5 tests
  - Volumes & Security apply (recreate) : 7 tests
