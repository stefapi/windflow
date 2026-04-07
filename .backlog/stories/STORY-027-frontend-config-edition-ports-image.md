# STORY-027 : Frontend Config — Édition des ports et mise à jour de l'image

**Statut :** TODO
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir modifier l'image et les ports exposés d'un container directement depuis l'onglet Config de la page ContainerDetail afin de mettre à jour ces paramètres sans intervention manuelle sur le daemon Docker.

## Contexte technique

**Dépendance** : STORY-025 (endpoint `/recreate`) doit être implémentée côté backend avant cette story.

**Composant principal** : `frontend/src/components/ContainerConfigTab.vue`

**Nouvelle section Image** — interface :
- Input text pré-rempli avec l'image actuelle (ex: `ghcr.io/open-webui/open-webui:latest`)
- Checkbox "Puller la nouvelle image avant recréation" (`pull_image`)
- Bouton "Mettre à jour l'image" → confirmation → appel `POST /docker/containers/{id}/recreate` avec `{ image: newImage, pull_image: true/false }`
- Après succès : redirect vers la nouvelle URL `/containers/<new_id>` (l'ID change après recréation)

**Nouvelle section Ports** — interface :
```
┌──────────┬──────────┬──────────────┬──────────┬────────┐
│ Host IP  │ Host Port│ Container Port│ Protocole│ Action │
├──────────┼──────────┼──────────────┼──────────┼────────┤
│ 0.0.0.0  │ 8080     │ 80           │ TCP      │ [🗑️]   │
└──────────┴──────────┴──────────────┴──────────┴────────┘
[+ Ajouter un port]                              [Appliquer]
```

Validation des ports :
- Host port : entier 1–65535
- Container port : entier 1–65535
- Protocole : `tcp` ou `udp`
- Pas de doublon sur le couple `hostIp:hostPort`

Format de la requête vers `/recreate` :
```typescript
port_bindings: {
  "80/tcp": [{ HostIp: "0.0.0.0", HostPort: "8080" }]
}
```

**Nouveaux types TypeScript** à ajouter dans `frontend/src/types/api.ts` :
```typescript
interface ContainerRecreateRequest {
  image?: string
  pull_image?: boolean
  env?: string[]
  labels?: Record<string, string>
  port_bindings?: Record<string, Array<{ HostIp: string; HostPort: string }>>
  mounts?: Array<Record<string, unknown>>
  privileged?: boolean
  readonly_rootfs?: boolean
  cap_add?: string[]
  cap_drop?: string[]
  stop_timeout?: number
}

interface ContainerRecreateResponse {
  success: boolean
  message: string
  old_container_id: string
  new_container_id: string
  container: ContainerDetail
  warnings: string[]
}
```

**Nouveau service API** dans `frontend/src/services/api.ts` :
```typescript
recreate: (id: string, data: ContainerRecreateRequest) =>
  http.post<ContainerRecreateResponse>(`/docker/containers/${id}/recreate`, data)
```

**Gestion post-recréation** : après succès, rediriger vers `/containers/<new_container_id>` car l'ID du container change.

## Critères d'acceptation (AC)

- [ ] AC 1 : Une section "Image" est présente dans l'onglet Config avec l'image actuelle pré-remplie
- [ ] AC 2 : L'opérateur peut modifier l'image et déclencher la recréation avec confirmation
- [ ] AC 3 : L'option "Puller la nouvelle image" est disponible (checkbox)
- [ ] AC 4 : La section "Ports" affiche les ports actuels dans un tableau éditable
- [ ] AC 5 : L'opérateur peut ajouter/supprimer des mappings de ports avec validation
- [ ] AC 6 : Cliquer "Appliquer" sur les ports déclenche la recréation après confirmation
- [ ] AC 7 : Après une recréation réussie, l'utilisateur est redirigé vers la nouvelle URL du container (`/containers/<new_id>`)
- [ ] AC 8 : Un `el-alert type="warning"` indique explicitement que ces actions nécessitent la recréation du container
- [ ] AC 9 : Les types TypeScript `ContainerRecreateRequest` et `ContainerRecreateResponse` sont ajoutés dans `api.ts`
- [ ] AC 10 : Le service `containersApi.recreate()` est ajouté dans `services/api.ts`
- [ ] AC 11 : Tests unitaires du composant (≥ 80%)

## Dépendances

- **STORY-025** : Backend endpoint `/recreate` (requis avant implémentation)

## État d'avancement technique

- [ ] Ajouter les types TypeScript dans `frontend/src/types/api.ts`
- [ ] Ajouter `containersApi.recreate()` dans `frontend/src/services/api.ts`
- [ ] Ajouter la section Image dans `ContainerConfigTab.vue`
- [ ] Ajouter la section Ports dans `ContainerConfigTab.vue`
- [ ] Implémenter la logique de redirect après recréation
- [ ] Écrire les tests unitaires

## Tâches d'implémentation détaillées

<!-- À remplir par analyse-story -->

## Tests à écrire

<!-- À remplir par analyse-story -->
