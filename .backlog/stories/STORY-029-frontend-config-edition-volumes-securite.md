# STORY-029 : Frontend Config — Édition volumes et sécurité (recréation)

**Statut :** TODO
**Epic Parent :** EPIC-009 — Refonte et édition complète de la page ContainerDetail

---

## Description

En tant qu'utilisateur, je veux pouvoir modifier les **volumes montés** et les **paramètres de sécurité** (privilege, readonly rootfs, capabilities) d'un conteneur directement depuis l'onglet Config de la page ContainerDetail, afin de personnaliser le comportement du conteneur sans avoir à le recréer manuellement en ligne de commande.

Ces modifications nécessitent la **recréation du conteneur** (via l'endpoint `POST /containers/{id}/recreate` créé dans STORY-025). Après recréation, la vue doit rediriger vers le nouvel ID de conteneur.

---

## Critères d'acceptation (AC)

- [ ] **AC1** — Une section "Volumes" est affichée dans l'onglet Config avec un tableau éditaable : colonnes Type (bind/volume/tmpfs), Source, Destination (mount point), Mode (ro/rw).
- [ ] **AC2** — L'utilisateur peut ajouter une nouvelle entrée volume via un bouton "+ Ajouter un volume".
- [ ] **AC3** — L'utilisateur peut supprimer une entrée volume existante via une icône poubelle sur chaque ligne.
- [ ] **AC4** — Une section "Sécurité" est affichée avec : toggle Privileged, toggle ReadonlyRootfs, input tags Cap Add, input tags Cap Drop.
- [ ] **AC5** — Les valeurs initiales des champs volumes et sécurité sont pré-remplies depuis les données du conteneur courant (`containerDetail`).
- [ ] **AC6** — Un bouton "Appliquer les modifications (recréation)" déclenche une confirmation ElMessageBox avant d'appeler `recreateContainer()`.
- [ ] **AC7** — Après recréation réussie, la vue redirige vers `/containers/<new_id>`.
- [ ] **AC8** — En cas d'erreur lors de la recréation, un message d'erreur est affiché via ElMessage (type error).
- [ ] **AC9** — Les sections Volumes et Sécurité utilisent le design el-card avec header coloré (vert pour Volumes, rouge pour Sécurité) conformément à la charte EPIC-009.
- [ ] **AC10** — Les champs sont correctement validés (destination de volume non vide, pas de doublon de destination).

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

---

## Dépendances

- **STORY-025** — Backend endpoint `POST /containers/{id}/recreate` (doit être DONE)
- **STORY-027** — Ajout des types TS ContainerRecreateRequest et du service `recreateContainer()` (doit être DONE)

---

## Tâches d'implémentation détaillées

> *À remplir par `analyse-story`*

---

## Tests à écrire

> *À remplir par `analyse-story`*

---

## État d'avancement technique

> *À cocher pendant `treat-story`*

---

## Notes d'implémentation

> *À remplir à la clôture*
