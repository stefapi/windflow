# STORY-030 : Frontend Config — Implémentation réelle env vars et labels (recréation)

**Statut :** TODO
**Epic Parent :** EPIC-009 — Refonte et édition complète de la page ContainerDetail

---

## Description

En tant qu'utilisateur, je veux que les sections "Variables d'environnement" et "Labels" de l'onglet Config soient **pleinement fonctionnelles** et permettent une édition effective (ajout, modification, suppression), afin de pouvoir reconfigurer un conteneur sans le recréer manuellement.

Actuellement ces sections affichent un message "Fonctionnalité à venir" (stub). Cette story remplace ce stub par une vraie implémentation connectée à l'endpoint `POST /containers/{id}/recreate`.

Ces modifications nécessitent la **recréation du conteneur**. Après recréation, la vue redirige vers le nouvel ID de conteneur.

---

## Critères d'acceptation (AC)

- [ ] **AC1** — La section "Variables d'environnement" affiche la liste des env vars actuelles sous forme de tableau éditaable (clé / valeur), pré-rempli depuis `containerDetail.Config.Env`.
- [ ] **AC2** — L'utilisateur peut ajouter une nouvelle paire clé/valeur via un bouton "+ Ajouter une variable".
- [ ] **AC3** — L'utilisateur peut supprimer une variable existante via une icône poubelle sur chaque ligne.
- [ ] **AC4** — La section "Labels" affiche la liste des labels actuels sous forme de tableau éditaable (clé / valeur), pré-rempli depuis `containerDetail.Config.Labels`.
- [ ] **AC5** — L'utilisateur peut ajouter un nouveau label (clé/valeur) via un bouton "+ Ajouter un label".
- [ ] **AC6** — L'utilisateur peut supprimer un label existant via une icône poubelle sur chaque ligne.
- [ ] **AC7** — Le message "Fonctionnalité à venir" est supprimé des deux sections.
- [ ] **AC8** — Un bouton "Appliquer les modifications (recréation)" déclenche une confirmation ElMessageBox avant d'appeler `recreateContainer()` avec les env vars et labels modifiés.
- [ ] **AC9** — Après recréation réussie, la vue redirige vers `/containers/<new_id>`.
- [ ] **AC10** — En cas d'erreur lors de la recréation, un message d'erreur est affiché via ElMessage (type error).
- [ ] **AC11** — Les sections Variables d'environnement et Labels utilisent le design el-card avec header coloré (gris/neutre pour les deux) conformément à la charte EPIC-009.
- [ ] **AC12** — Les clés sont validées : non vides, pas de doublons dans chaque section.

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

---

## Dépendances

- **STORY-025** — Backend endpoint `POST /containers/{id}/recreate` (doit être DONE)
- **STORY-027** — Ajout des types TS ContainerRecreateRequest et du service `recreateContainer()` (doit être DONE)
- **STORY-029** — Édition volumes et sécurité (recommandé avant pour avoir la structure complète du formulaire)

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
