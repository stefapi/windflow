# STORY-028 : Frontend Config — Gestion des réseaux à chaud

**Statut :** TODO
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir connecter et déconnecter un container d'un réseau Docker directement depuis l'onglet Config, sans recréation ni redémarrage, afin de modifier la connectivité réseau d'un container en production.

## Contexte technique

**Dépendance** : STORY-026 (endpoints backend connect/disconnect) doit être implémentée avant cette story.

**Composant principal** : `frontend/src/components/ContainerConfigTab.vue`

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

- [ ] AC 1 : La section Réseaux affiche la liste des réseaux actuellement connectés au container
- [ ] AC 2 : Un select permet de choisir parmi les réseaux Docker disponibles non encore connectés
- [ ] AC 3 : Le bouton "Connecter" appelle l'API et rafraîchit les données du container sans redirection
- [ ] AC 4 : Le bouton "Déconnecter" à côté de chaque réseau appelle l'API et rafraîchit sans redirection
- [ ] AC 5 : Un `el-alert type="info"` indique que ces opérations sont possibles sans redémarrage
- [ ] AC 6 : Les erreurs (réseau inexistant, réseau `host`/`none` non supporté) sont affichées via `ElMessage.error()`
- [ ] AC 7 : Les types TypeScript et appels service sont ajoutés
- [ ] AC 8 : Tests unitaires du composant (≥ 80%)

## Dépendances

- **STORY-026** : Backend endpoints connect/disconnect réseau (requis avant implémentation)

## État d'avancement technique

- [ ] Ajouter les types `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest` dans `types/api.ts`
- [ ] Ajouter `connectNetwork()` et `disconnectNetwork()` dans `services/api.ts`
- [ ] Ajouter la section Réseaux dans `ContainerConfigTab.vue`
- [ ] Intégrer `networksApi.list()` pour la liste des réseaux disponibles
- [ ] Écrire les tests unitaires

## Tâches d'implémentation détaillées

<!-- À remplir par analyse-story -->

## Tests à écrire

<!-- À remplir par analyse-story -->
