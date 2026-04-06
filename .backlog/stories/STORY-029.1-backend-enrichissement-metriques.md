# STORY-029.1 : Backend — Enrichissement des métriques Network et Block I/O

**Statut :** DONE

**Story Parente :** STORY-029 — Backend + Frontend — Métriques Network I/O et Disk I/O dans Stats

**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description

En tant qu'utilisateur, je veux que l'API stats retourne des métriques Network I/O détaillées par interface réseau (rx/tx bytes, packets, errors, drops) et des métriques Block I/O détaillées par device (io_service_bytes_recursive read/write, io_serviced_recursive read/write ops) afin d'avoir une vision complète de l'activité réseau et disque du container.

## Critères d'acceptation (AC)

- [x] AC 1 : Le schéma de réponse des stats inclut un objet `network` avec les métriques par interface réseau : rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors, rx_dropped, tx_dropped
- [x] AC 2 : Le schéma de réponse des stats inclut un objet `blkio` avec les métriques par device : io_service_bytes_recursive (read/write bytes), io_serviced_recursive (read/write ops)

## Contexte technique

### Fichiers existants à modifier

- `backend/app/websocket/container_stats.py` — Fonctions `calculate_network_io()`, `calculate_block_io()`, `format_stats_response()`
- `backend/app/schemas/docker.py` — Schéma `ContainerStatsResponse` (actuellement `network: dict[str, Any]` et `block_io: dict[str, Any]`)
- `backend/tests/unit/test_docker/test_container_stats.py` — Tests existants à compléter

### Structure Docker API brute

**Network (`networks` block) :**

```json
{
  "eth0": {
    "rx_bytes": 123456,
    "tx_bytes": 789012,
    "rx_packets": 100,
    "tx_packets": 80,
    "rx_errors": 0,
    "tx_errors": 0,
    "rx_dropped": 0,
    "tx_dropped": 0
  }
}
```

**Block I/O (`blkio_stats` block) :**

```json
{
  "io_service_bytes_recursive": [
    {"major": 8, "minor": 0, "op": "read", "value": 1048576},
    {"major": 8, "minor": 0, "op": "write", "value": 2097152}
  ],
  "io_serviced_recursive": [
    {"major": 8, "minor": 0, "op": "read", "value": 100},
    {"major": 8, "minor": 0, "op": "write", "value": 50}
  ]
}
```

### Patterns existants

- Les fonctions de calcul sont pures (pas d'async, pas d'I/O) — facilite les tests
- Les schémas Pydantic utilisent `model_config = ConfigDict(populate_by_name=True)`
- Le formatage final passe par `format_stats_response()` qui est le point d'entrée unique

### Contrainte de compatibilité

La réponse WebSocket doit rester **rétro-compatible** pendant la transition :

- Garder `network.rx_bytes` et `network.tx_bytes` (totaux globaux) pour le frontend actuel
- Ajouter les nouvelles données dans des sous-objets (`interfaces`, `devices`)

## Dépendances

- Aucune (première sous-story, indépendante du frontend)

## Tâches d'implémentation détaillées

### Tâche 1 : Créer les sous-modèles Pydantic pour les métriques enrichies
**Objectif :** Ajouter les schémas Pydantic typés pour les métriques network par interface et blkio par device, en plus des totaux globaux existants.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Ajouter les modèles suivants :
  - `NetworkInterfaceStats` : name (str), rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors, rx_dropped, tx_dropped (tous int, default 0)
  - `NetworkStats` : rx_bytes, tx_bytes (totaux globaux, int), total_rx_errors, total_tx_errors, total_rx_dropped, total_tx_dropped (int), interfaces (list[NetworkInterfaceStats])
  - `BlkioDeviceStats` : major (int), minor (int), read_bytes (int), write_bytes (int), read_ops (int), write_ops (int)
  - `BlkioStats` : read_bytes, write_bytes (totaux globaux, int), devices (list[BlkioDeviceStats])
  - Mettre à jour `ContainerStatsResponse` : remplacer `network: dict[str, Any]` par `network: NetworkStats` et `block_io: dict[str, Any]` par `block_io: BlkioStats`
**Dépend de :** Aucune

### Tâche 2 : Enrichir calculate_network_io() avec métriques par interface
**Objectif :** Modifier la fonction pour retourner un dictionnaire structuré avec les totaux globaux + la liste détaillée par interface (incluant packets, errors, drops).
**Fichiers :**
- `backend/app/websocket/container_stats.py` — Modifier — Remplacer le retour `(total_rx, total_tx)` par un dict structuré :
  ```python
  {
      "rx_bytes": total_rx,
      "tx_bytes": total_tx,
      "total_rx_errors": ...,
      "total_tx_errors": ...,
      "total_rx_dropped": ...,
      "total_tx_dropped": ...,
      "interfaces": [
          {"name": "eth0", "rx_bytes": ..., "tx_bytes": ..., "rx_packets": ..., ...},
          ...
      ]
  }
  ```
  Garder la signature retour compatible : retourner le dict structuré. Les appelants directs (tests existants) seront mis à jour dans la tâche 4.
**Dépend de :** Aucune

### Tâche 3 : Enrichir calculate_block_io() avec métriques par device + IOPS
**Objectif :** Modifier la fonction pour retourner un dictionnaire structuré avec les totaux globaux + la liste détaillée par device (incluant io_serviced_recursive pour IOPS).
**Fichiers :**
- `backend/app/websocket/container_stats.py` — Modifier — Remplacer le retour `(total_read, total_write)` par un dict structuré :
  ```python
  {
      "read_bytes": total_read,
      "write_bytes": total_write,
      "devices": [
          {"major": 8, "minor": 0, "read_bytes": ..., "write_bytes": ..., "read_ops": ..., "write_ops": ...},
          ...
      ]
  }
  ```
  Utiliser `_sum_blkio_entries()` existant pour le cumul global. Créer un helper `_build_device_stats()` pour agréger par (major, minor) à la fois `io_service_bytes_recursive` et `io_serviced_recursive`. Le fallback `throttle_io_service_bytes_recursive` est conservé.
**Dépend de :** Aucune

### Tâche 4 : Mettre à jour format_stats_response() avec les nouvelles données
**Objectif :** Brancher les nouvelles fonctions enrichies dans `format_stats_response()` pour produire la réponse complète incluant interfaces et devices.
**Fichiers :**
- `backend/app/websocket/container_stats.py` — Modifier — Remplacer les appels dans `format_stats_response()` :
  - Remplacer `network_rx, network_tx = calculate_network_io(stats_data)` par `network_data = calculate_network_io(stats_data)`
  - Remplacer `block_read, block_write = calculate_block_io(stats_data)` par `block_data = calculate_block_io(stats_data)`
  - Mettre à jour la construction du dict retourné pour utiliser `network_data` et `block_data`
**Dépend de :** Tâche 2, Tâche 3

### Tâche 5 : Mettre à jour ContainerStatsResponse avec les sous-modèles typés
**Objectif :** Remplacer les `dict[str, Any]` dans `ContainerStatsResponse` par les nouveaux sous-modèles Pydantic typés, garantissant la validation et la documentation OpenAPI.
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Utiliser les modèles créés en Tâche 1 :
  - `network: NetworkStats` au lieu de `network: dict[str, Any]`
  - `block_io: BlkioStats` au lieu de `block_io: dict[str, Any]`
  - Vérifier que la route `get_container_stats` (dans `backend/app/api/v1/docker.py`) utilise bien le schéma mis à jour comme `response_model`
**Dépend de :** Tâche 1, Tâche 4

## Tests à écrire

### Backend
- `backend/tests/unit/test_docker/test_container_stats.py` — Ajouter les classes de test suivantes :

#### TestCalculateNetworkIoEnriched (nouveaux tests)
- `test_calculate_network_io_enriched_single_interface` : Vérifie le dict retourné avec rx_bytes, tx_bytes, interfaces (nom, packets, errors, drops)
- `test_calculate_network_io_enriched_multiple_interfaces` : Vérifie les totaux et le détail par interface
- `test_calculate_network_io_enriched_empty` : Stats vides → totaux à 0, interfaces vides
- `test_calculate_network_io_enriched_with_errors_drops` : Vérifie que errors et drops sont bien agrégés (totaux + par interface)

#### TestCalculateBlockIoEnriched (nouveaux tests)
- `test_calculate_block_io_enriched_single_device` : Vérifie le dict retourné avec read_bytes, write_bytes, devices (major, minor, read_bytes, write_bytes, read_ops, write_ops)
- `test_calculate_block_io_enriched_multiple_devices` : Plusieurs devices → vérifie totaux et détail par device
- `test_calculate_block_io_enriched_empty` : Stats vides → totaux à 0, devices vides
- `test_calculate_block_io_enriched_with_iops` : Vérifie que io_serviced_recursive est bien agrégé par device

#### TestFormatStatsResponseEnriched (mise à jour des tests existants)
- `test_format_stats_response_complete` : Mettre à jour pour vérifier la nouvelle structure (network.interfaces, block_io.devices)
- `test_format_stats_response_empty` : Mettre à jour pour vérifier les nouveaux champs par défaut

#### Mise à jour des tests existants
- Les tests `TestCalculateNetworkIo` et `TestCalculateBlockIo` existants doivent être adaptés car le retour change de `tuple` à `dict`. Adapter les assertions pour le nouveau format.

### Commandes de validation

```bash
cd /home/stef/workspace/windflow/backend && python -m pytest tests/unit/test_docker/test_container_stats.py -v
cd /home/stef/workspace/windflow/backend && python -m pytest tests/unit/test_docker/ -v
```

## État d'avancement technique

- [x] Tâche 1 : Créer les sous-modèles Pydantic NetworkInterfaceStats, NetworkStats, BlkioDeviceStats, BlkioStats
- [x] Tâche 2 : Enrichir calculate_network_io() avec métriques par interface
- [x] Tâche 3 : Enrichir calculate_block_io() avec métriques par device + IOPS
- [x] Tâche 4 : Mettre à jour format_stats_response() avec les nouvelles données
- [x] Tâche 5 : Mettre à jour ContainerStatsResponse avec les sous-modèles typés
- [x] Écrire les tests unitaires (adapter existants + ajouter nouveaux)

## Notes d'implémentation

### Fichiers modifiés/créés
- `backend/app/schemas/docker.py` — Ajout de 4 modèles Pydantic (`NetworkInterfaceStats`, `NetworkStats`, `BlkioDeviceStats`, `BlkioStats`) + mise à jour de `ContainerStatsResponse.network` et `.block_io` vers les types structurés
- `backend/app/websocket/container_stats.py` — Refonte de `calculate_network_io()` (tuple → dict avec interfaces), `calculate_block_io()` (tuple → dict avec devices), ajout de `_build_device_stats()`, mise à jour de `format_stats_response()`
- `backend/tests/unit/test_docker/test_container_stats.py` — Réécriture complète : adaptation des tests existants (NetworkIo, BlockIo, FormatStatsResponse) + ajout de nouvelles classes (TestCalculateNetworkIoEnriched, TestCalculateBlockIoEnriched, TestBuildDeviceStats, TestSumBlkioEntries)

### Décisions techniques
- Choix de retourner un dict structuré plutôt qu'un tuple pour `calculate_network_io()` et `calculate_block_io()` — permet d'ajouter les nouveaux champs sans casser la signature
- `_build_device_stats()` combine `io_service_bytes_recursive` (bytes) et `io_serviced_recursive` (IOPS) dans un seul dict par device — agrégation par clé `(major, minor)`
- Rétro-compatibilité assurée : les totaux globaux `rx_bytes/tx_bytes` et `read_bytes/write_bytes` restent au niveau racine des objets network/block_io

### Tests
- 45 tests passés (0 échec), couverture container_stats.py à 52% (parties non couvertes = WebSocket endpoint async)
- Commande : `cd backend && poetry run pytest tests/unit/test_docker/test_container_stats.py -v`
