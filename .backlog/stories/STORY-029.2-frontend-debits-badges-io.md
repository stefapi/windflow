# STORY-029.2 : Frontend — Affichage débits, badges et graphiques enrichis Network/Disk I/O

**Statut :** DONE

**Story Parente :** STORY-029 — Backend + Frontend — Métriques Network I/O et Disk I/O dans Stats

**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description

En tant qu'utilisateur, je veux voir dans l'onglet Stats les débits réseau et disque en temps réel (KB/s ou MB/s), les compteurs cumulatifs, les mini-graphiques temporels sur 60 secondes, et des badges warning pour les erreurs et drops réseau, afin de surveiller efficacement l'activité I/O du container.

## Critères d'acceptation (AC)

- [x] AC 3 : L'onglet Stats affiche une section **Network I/O** avec : débit montant (↑ tx) et débit descendant (↓ rx) en KB/s ou MB/s, calculés par delta entre deux échantillons
- [x] AC 4 : L'onglet Stats affiche une section **Disk I/O** avec : lecture (↓ read MB/s) et écriture (↑ write MB/s), calculées par delta entre deux échantillons
- [x] AC 5 : Les métriques I/O sont affichées sous forme de mini-graphiques temporels (au moins les 60 dernières secondes) en plus des valeurs instantanées
- [x] AC 6 : Les compteurs cumulatifs (total bytes depuis le démarrage) sont aussi affichés (ex: "Total: ↑ 2.4 GB ↓ 890 MB")
- [x] AC 7 : Si le container est arrêté, les sections I/O affichent "Non disponible"
- [x] AC 8 : Les erreurs et drops réseau sont affichés en surbrillance si > 0 (badge warning)

## Contexte technique

### Fichiers existants à modifier

- `frontend/src/composables/useContainerStats.ts` — Interface `ContainerStats` et `StatsHistoryEntry`, parsing WebSocket
- `frontend/src/components/ContainerStats.vue` — Sections Network I/O et Disk I/O du template, graphiques ECharts
- `frontend/src/utils/format.ts` — Fonction `formatBytes()` déjà existante
- `frontend/tests/unit/components/ContainerStats.spec.ts` — Tests composant (si existant)

### État actuel du frontend

Le composable `useContainerStats.ts` reçoit déjà via WebSocket :

```typescript
network_rx_bytes: data.network?.rx_bytes ?? 0
network_tx_bytes: data.network?.tx_bytes ?? 0
block_read_bytes: data.block_io?.read_bytes ?? 0
block_write_bytes: data.block_io?.write_bytes ?? 0
```

Ces valeurs sont **cumulatives** (total depuis le démarrage du container). Les graphiques historiques affichent ces cumuls, pas des débits.

### Ce qui manque

1. **Calcul des débits** : Il faut calculer le delta entre deux échantillons consécutifs pour obtenir des KB/s ou MB/s
2. **Données per-interface/per-device** : Après STORY-029.1, le backend envoie des données détaillées qu'il faut consommer
3. **Badges warning** : Afficher les errors/drops en surbrillance
4. **Graphiques de débit** : Les graphiques Network et Disk doivent afficher des débits (rate) au lieu de cumuls

### Patterns existants

- ECharts est déjà configuré avec `vue-echarts` et les composants nécessaires (LineChart, GridComponent, etc.)
- Les graphiques utilisent un système d'autoscale (`getOptimalScale()`)
- Le composable gère déjà l'historique avec `MAX_HISTORY_LENGTH = 60`

## Dépendances

- STORY-029.1 : Le backend doit fournir les métriques enrichies (interfaces, devices, errors, drops, IOPS) pour que le frontend puisse les afficher

## Tâches d'implémentation détaillées

### Tâche 1 : Mettre à jour le composable useContainerStats avec les nouveaux champs et le calcul de débits
**Objectif :** Enrichir les interfaces `ContainerStats` et `StatsHistoryEntry` avec les nouvelles données (per-interface, per-device, errors, drops, IOPS) et ajouter le calcul des débits par delta entre deux échantillons consécutifs.
**Fichiers :**
- `frontend/src/composables/useContainerStats.ts` — Modifier —
  1. Ajouter les interfaces :
     ```typescript
     interface NetworkInterfaceData {
       name: string
       rx_bytes: number; tx_bytes: number
       rx_packets: number; tx_packets: number
       rx_errors: number; tx_errors: number
       rx_dropped: number; tx_dropped: number
     }
     interface BlkioDeviceData {
       major: number; minor: number
       read_bytes: number; write_bytes: number
       read_ops: number; write_ops: number
     }
     ```
  2. Enrichir `ContainerStats` avec :
     - `network_interfaces: NetworkInterfaceData[]`
     - `total_rx_errors: number; total_tx_errors: number; total_rx_dropped: number; total_tx_dropped: number`
     - `blkio_devices: BlkioDeviceData[]`
     - `network_rx_rate: number; network_tx_rate: number` (bytes/s, calculés par delta)
     - `block_read_rate: number; block_write_rate: number` (bytes/s, calculés par delta)
  3. Enrichir `StatsHistoryEntry` avec les champs de rate : `network_rx_rate`, `network_tx_rate`, `block_read_rate`, `block_write_rate`
  4. Ajouter un computed `previousStats` (ref vers l'avant-dernier échantillon) et une logique de calcul de delta dans `addStatsToHistory()` :
     - `rate = (current_bytes - previous_bytes) / (current_timestamp_ms - previous_timestamp_ms) * 1000`
     - Stocker le timestamp de chaque échantillon pour le calcul
  5. Mettre à jour le parsing dans le handler `ws.onmessage` (case 'stats') pour extraire les nouvelles données depuis `data.network.interfaces`, `data.network.total_rx_errors`, etc. et `data.block_io.devices`
**Dépend de :** STORY-029.1 (le backend doit envoyer les nouvelles données)

### Tâche 2 : Mettre à jour la section Network I/O du composant ContainerStats.vue
**Objectif :** Afficher les débits réseau (KB/s ou MB/s), les totaux cumulatifs formatés, et les badges warning pour errors/drops.
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Modifier —
  1. Remplacer l'affichage actuel des Network I/O (2 lignes simples rx/tx bytes) par :
     - **Ligne débit :** `↓ rx_rate` et `↑ tx_rate` en KB/s ou MB/s (formatage dynamique via `formatBytes()` existant, suffixe `/s`)
     - **Ligne totaux cumulatifs :** `Total: ↓ X GB ↑ Y MB` (formatés avec `formatBytes()`)
     - **Badge warning :** Si `total_rx_errors + total_tx_errors + total_rx_dropped + total_tx_dropped > 0`, afficher un badge El-Tag type="warning" avec le nombre total d'erreurs/drops
  2. Ajouter les computed nécessaires : `networkRxRate`, `networkTxRate`, `hasNetworkErrors`, `networkErrorsCount`
  3. Utiliser `formatBytes(rate) + '/s'` pour les débits
**Dépend de :** Tâche 1

### Tâche 3 : Mettre à jour la section Disk I/O du composant ContainerStats.vue
**Objectif :** Afficher les débits disque (MB/s), les totaux cumulatifs, et les IOPS par device.
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Modifier —
  1. Remplacer l'affichage actuel des Disk I/O par :
     - **Ligne débit :** `↓ read_rate` et `↑ write_rate` en KB/s ou MB/s
     - **Ligne totaux cumulatifs :** `Total: ↓ X MB ↑ Y MB`
     - **Ligne IOPS (si devices) :** Afficher les IOPS par device : `Device 8:0 → R: 100 ops/s W: 50 ops/s`
  2. Ajouter les computed nécessaires : `diskReadRate`, `diskWriteRate`
  3. Utiliser `formatBytes(rate) + '/s'` pour les débits
**Dépend de :** Tâche 1

### Tâche 4 : Mettre à jour les graphiques historiques pour afficher des débits (rate) au lieu de cumuls
**Objectif :** Les graphiques Network I/O et Disk I/O affichent actuellement des valeurs cumulatives. Les modifier pour afficher les débits calculés (rate) provenant des `StatsHistoryEntry` enrichis.
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Modifier —
  1. Mettre à jour les options ECharts des graphiques Network et Disk :
     - Remplacer les données `history.map(h => h.network_rx_bytes)` par `history.map(h => h.network_rx_rate)`
     - Remplacer les données `history.map(h => h.block_read_bytes)` par `history.map(h => h.block_read_rate)`
     - Idem pour tx et write
  2. Mettre à jour les labels/formatteurs des graphiques : suffixe `/s` sur les unités
  3. Mettre à jour `getOptimalScale()` si nécessaire pour les nouvelles plages de valeurs (les rates seront en KB/s ou MB/s, pas en GB)
**Dépend de :** Tâche 1

### Tâche 5 : Vérifier et finaliser AC 7 — "Non disponible" si container arrêté
**Objectif :** S'assurer que quand le container est arrêté, les sections Network I/O et Disk I/O affichent correctement "Non disponible" au lieu de valeurs à 0.
**Fichiers :**
- `frontend/src/components/ContainerStats.vue` — Modifier — Vérifier que la condition existante `stats === null` couvre bien le cas container arrêté. Le composable met déjà `stats = null` et `status = 'disconnected'` quand le container est arrêté (via `stream_status: container_stopped`). Si le container est arrêté dès le départ, le WebSocket envoie `initial` avec `container_status !== 'running'` et le composable déconnecte sans stats. Vérifier que le template affiche bien un message "Non disponible" pour les sections I/O dans ce cas.
**Dépend de :** Tâche 2, Tâche 3

## Tests à écrire

### Frontend

#### Tests du composable useContainerStats
- `frontend/tests/unit/composables/useContainerStats.spec.ts` — Créer si n'existe pas :
  - Calcul du delta rate entre deux échantillons : vérifier que `network_rx_rate` est correct (delta_bytes / delta_time * 1000)
  - Premier échantillon (pas de précédent) : rate = 0
  - Parsing des nouvelles données enrichies (interfaces, devices, errors, drops)
  - Historique contient bien les champs rate

#### Tests du composant ContainerStats
- `frontend/tests/unit/components/ContainerStats.spec.ts` — Créer/mettre à jour :
  - Rendu des débits réseau (KB/s, MB/s) avec les bonnes unités
  - Rendu des débits disque avec les bonnes unités
  - Badge warning visible si errors/drops > 0, invisible sinon
  - Affichage IOPS par device
  - Message "Non disponible" si container arrêté (stats = null)
  - Les totaux cumulatifs sont affichés et formatés

### Commandes de validation

```bash
cd /home/stef/workspace/windflow/frontend && pnpm run test:unit -- --run
cd /home/stef/workspace/windflow/frontend && pnpm run type-check
cd /home/stef/workspace/windflow/frontend && pnpm run build
```

## État d'avancement technique

- [x] Tâche 1 : Mettre à jour le composable avec nouveaux champs et calcul de débits
- [x] Tâche 2 : Mettre à jour la section Network I/O (débits + totaux + badges errors/drops)
- [x] Tâche 3 : Mettre à jour la section Disk I/O (débits + totaux + IOPS)
- [x] Tâche 4 : Mettre à jour les graphiques historiques pour afficher des débits (rate)
- [x] Tâche 5 : Vérifier AC 7 — affichage "Non disponible" si container arrêté
- [x] Écrire les tests unitaires

## Notes d'implémentation

### Fichiers modifiés
- `frontend/src/composables/useContainerStats.ts` — Ajout interfaces `NetworkInterfaceData`, `BlkioDeviceData`, enrichissement `ContainerStats` et `StatsHistoryEntry`, calcul delta rates, parsing données enrichies via fonctions dédiées `parseNetworkInterfaces()` et `parseBlkioDevices()`
- `frontend/src/components/ContainerStats.vue` — Sections Network I/O et Disk I/O enrichies (débits, totaux cumulatifs, badges errors/drops, IOPS par device), graphiques historiques passés de cumuls à rates (suffixe /s), ajout computed `hasNetworkErrors`, `networkErrorsCount`, `blkioDevicesWithOps`, fonction `formatRate()`
- `frontend/tests/unit/components/ContainerStats.spec.ts` — 15 tests unitaires couvrant : monteur, sections Network/Disk, badges warning, IOPS, graphiques, contrôles connexion

### Décisions techniques
- Calcul des rates directement dans le handler WebSocket (case 'stats') via delta avec `previousStats`, avant la construction de l'objet `ContainerStats`
- Bracket notation (`iface['name']`) utilisée pour le parsing des données dynamiques du WebSocket (conformité `noPropertyAccessFromIndexSignature` du tsconfig)
- Fonctions de parsing `parseNetworkInterfaces()` et `parseBlkioDevices()` extraites hors du composable pour testabilité
- Badge warning placé dans le header de la section Network (flexbox avec `margin-left: auto`)

### Validation
- `pnpm run type-check` : ✅ 0 erreur
- `pnpm run build` : ✅ succès
- `pnpm run test --run` : ✅ 468 tests passés (31 fichiers, 0 échec)
