# Rapprochement `/compute` ↔ `/docker` — table de correspondance (STORY-173)

> **Statut** : livré par STORY-173 (item P2-11, arbitrage F3 — incorporation
> des surfaces HORS SPEC dans la spec 09). La consolidation rédactionnelle
> des spécifications reste coordonnée avec **STORY-252 / P3-4**.
>
> **Décision explicite (garde-fou §2.G du plan de remédiation)** : **aucune
> suppression d'endpoint Docker**. Les deux surfaces coexistent ; la
> convergence vers la nomenclature cible `/compute` se fera par dépréciation
> progressive (modèle du double nommage `targets`→`hosts` de STORY-166 :
> alias avec headers `Deprecation`/`Sunset`, arbitrage de retrait hors
> story), jamais par retrait unilatéral.

## Contexte

- **`/api/v1/docker`** (35 endpoints, STORY-122.2) : surface historique
  riche orientée *opérations Docker brutes* (containers, images, volumes,
  networks, système). Source de vérité opérationnelle depuis la P1.
- **`/api/v1/compute`** (7 endpoints après STORY-173) : surface *vue
  Compute* du Mode Infra (spec 09 § Vue Compute) — agrégée, classifiée
  (managed/discovered/standalone), scopée organisation, paginée.
- La spec 09 cible `/compute` comme **surface canonique** pour la vue
  Infra ; `/docker` reste la surface d'administration bas niveau.

## Table de correspondance

### Volumes

| Opération | `/docker` (historique) | `/compute` (canonique cible) | Statut |
|---|---|---|---|
| Liste paginée | `GET /docker/volumes` | `GET /compute/volumes` | **les deux actifs** |
| Détail | — | `GET /compute/volumes/{name}` | **seul compute** |
| Création | `POST /docker/volumes` (admin) | — *(différé, non spécifié compute)* | seul docker |
| Suppression | `DELETE /docker/volumes/{name}` (admin) | — *(via prune protégé)* | seul docker |
| Contenu (browse) | — | `GET /compute/volumes/{name}/browse` | **seul compute** (STORY-173) |
| Upload/download de fichiers | — | — | **différé — Roadmap Phase 5** |
| Écriture `browse/{path}` | — | — | **différé — Roadmap Phase 5** |
| Prune orphelins protégé | — | `POST /compute/prune {resource: volumes}` | **seul compute** (STORY-173) |

### Images

| Opération | `/docker` (historique) | `/compute` (canonique cible) | Statut |
|---|---|---|---|
| Liste | `GET /docker/images` | — | seul docker |
| Pull / build / import | `POST /docker/images/…` | — | seul docker |
| Suppression unitaire | `DELETE /docker/images/{id}` (admin) | — | seul docker |
| Prune dangling protégé | — | `POST /compute/prune {resource: images}` | **seul compute** (STORY-173) |
| Check-updates (digest/semver) | — | — | **différé — Roadmap Phase 5** |

### Containers

| Opération | `/docker` (historique) | `/compute` (canonique cible) | Statut |
|---|---|---|---|
| Liste brute / inspect / logs / stats | `GET /docker/containers…` | — | seul docker |
| Cycle de vie (start/stop/restart/remove) | `POST|DELETE /docker/containers/{id}/…` | — | seul docker |
| Prune stoppés non managés | — | `POST /compute/prune {resource: containers}` | **seul compute** (STORY-173) |
| Vue classifiée (managed/discovered/standalone) | — | `GET /compute/global`, `GET /compute/stats`, `GET /compute/browse` | **seul compute** |
| Graphe de dépendances `/compute/graph` | — | — | **différé — Roadmap Phase 5** |

### Réseaux & système

| Opération | `/docker` | `/compute` | Statut |
|---|---|---|---|
| Networks CRUD | `GET|POST|DELETE /docker/networks…` | — | seul docker |
| Ping / df / info système | `GET /docker/system/…` | — | seul docker |

## Sémantique du prune (STORY-173 — spec 09 § Prune)

Le prune n'existe **que** sous `/compute` (et via l'action scheduler
`compute.docker.prune` — STORY-160, même socle de wrappers, D5) :

- liste protégée `windflow-plugin-*` épargnée **par construction** ;
- un volume monté par un container **arrêté** n'est pas éligible ;
- suppression **unitaire** : un échec n'interrompt pas la file (rapport
  `failed`) ;
- `space_reclaimed_bytes` réel pour les images, **toujours 0 pour les
  volumes** (taille non exposée par l'API Docker — aucune valeur fabriquée) ;
- endpoint : superadmin + `confirm=true` + dry-run + audit
  (`compute.prune`) ; scheduler : `dry_run` défaut + audit acteur système.

## Période de convergence

1. **Maintenant (post-173)** : les deux surfaces coexistent ; `/compute`
   gagne les fonctions de vue et le prune protégé ; `/docker` inchangé
   (35 routes — garde-fou `EXPECTED_ROUTE_COUNTS`).
2. **Court terme** : le frontend/CLI consomment `/compute` pour la vue
   Infra (types générés via `make generate-api`) ; `/docker` reste
   l'administration bas niveau.
3. **Arbitrage ultérieur (hors story, modèle STORY-166)** : si une
   dépréciation de doublons exacts est décidée (ex. liste volumes), elle
   passera par un **alias avec `Deprecation`/`Sunset`** sur `/docker`,
   migration des consommateurs, puis retrait explicite — jamais de
   suppression silencieuse.

## Différés notés (Roadmap Phase 5)

- Upload/download de fichiers de volume (nécessite wrappers
  `get_archive`/`put_archive` + validation binaire).
- Écriture `browse/{path}` (PUT fichier/dossier).
- Check-updates des images (digest sans pull, semver, pending-updates).
- Graphe de dépendances complet `GET /compute/graph`.
