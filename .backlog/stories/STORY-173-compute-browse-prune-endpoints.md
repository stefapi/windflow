# STORY-173 : Compute `browse`/`prune` — endpoints manquants, prune protégé (superadmin + confirmation + dry-run + audit) et rapprochement de la surface `/compute` avec l'existant `/docker` (P2-11 + P2-14 partie tests — axes D1, F3, C9)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-11 (axes D1, F3, rapports §1/§5) + contribution P2-14 (C9 — couverture des zones tests liées) — ampleur **M**

## Description

En tant qu'administrateur WindFlow, je veux que la surface `/compute/*` (Mode Infra) gagne les endpoints manquants — **`browse`** (inventaire détaillé paginé et filtrable, dont le browse des volumes) et **`prune`** Docker (images/volumes/conteneurs stoppés, avec sémantique protégée) — le prune étant réservé au **superadmin avec confirmation explicite** et exposable en **dry-run**, afin de compléter la surface Compute spécifiée en réutilisant l'inventaire Docker existant plutôt qu'en créant un nouveau runtime.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §3.7-3.8, §13.4) : le router [`compute.py:25`](../../backend/app/api/v1/compute.py:25) n'expose que `stats` et `global` — ni `browse`, ni `prune`, ni la sous-surface volumes du spec 09 ; parallèlement le module [`docker.py:69`](../../backend/app/api/v1/docker.py:69) porte 40 endpoints riches (dont prune-ish) — le rapprochement des deux surfaces (arbitrage F3 : incorporation des surfaces HORS SPEC dans la spec 09) est à documenter ; les tests compute sont partiels (§13.4).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Réutilisation, pas nouveau runtime** : `browse`/`prune` sont des **sur-fonctions de l'inventaire existant** — [`compute_service.py:58`](../../backend/app/services/compute_service.py:58) (`get_compute_stats`/`get_compute_global`), [`container_classifier.py:61`](../../backend/app/services/container_classifier.py:61), [`container_builder.py:99`](../../backend/app/services/container_builder.py:99), [`docker_client_service.py:312`](../../backend/app/services/docker_client_service.py:312) (dataclasses VolumeInfo/ImageInfo + accès socket) — s'y brancher ;
- **`browse` volumes** : contrat spec 09 § Volumes — `GET /compute/volumes` (liste, filtre host), `GET /compute/volumes/{id}/browse` (contenu), `browse/{path}` (fichier/dossier), + upload/download si périmètre raisonnable (sinon noté différé) ; minimum viable : listing paginé du contenu d'un volume ;
- **`prune` — sémantique protégée spec 09** : s'applique aux **volumes orphelins** et **images inutilisées** (+ conteneurs stoppés) : « inutilisé = sans aucun utilisateur, **y compris un container arrêté** » ; **liste protégée par convention de nommage** `windflow-plugin-*` (caches plugins — bases de vulnérabilités, state des helpers) **épargnée** ; suppression **unitaire, sans force** — un volume devenu utilisé entre la liste et la suppression échoue et est **passé** ; **rapport explicite** : supprimés / épargnés (protégés) / échecs ; l'espace libéré n'est **pas fabriqué** pour les volumes (l'API Docker ne fournit pas la taille par volume), réellement rapporté pour les images ; `dangling=true` par défaut pour les images ;
- **Protection** : `prune` réservé **superadmin** (`require_role("super_admin")` ou `require_superuser` selon l'état STORY-122), **confirmation explicite** (paramètre `confirm=true` requis), **dry-run** (liste ce qui serait supprimé sans supprimer), **audit** (ligne d'audit STORY-125 sur exécution réelle) ;
- **Rapprochement `/compute` ↔ `/docker` (F3)** : documenter la correspondance des endpoints dupliqués/voisins (ex. prune volumes/images des deux côtés) et faire converger vers la nomenclature cible `/compute` (le double nommage style targets→hosts de STORY-166 sert de modèle si nécessaire) ; **aucune suppression d'endpoint Docker** (garde-fou §2.G) ;
- **Hors périmètre noté (D1)** : le check-updates (digest sans pull, semver, pending-updates) et le **graphe de dépendances complet** `/compute/graph` restent hors périmètre (Roadmap Phase 5 / §6 du plan) ;
- Endpoints nouveaux = enveloppes (STORY-126) + pagination (STORY-128) dès l'ouverture.

## Critères d'acceptation (AC)

- [ ] AC 1 : `browse` est exposé de façon **paginée et filtrable** (vue détaillée de l'inventaire compute : filtres par type/Host/statut, recherche libre ; listing du contenu d'un volume via `GET /compute/volumes/{id}/browse`) — tests : liste vide, liste avec données, filtres, enveloppe `pagination{}`, 401/403 (RBAC lecture viewer+) /422.
- [ ] AC 2 : `prune` (images/volumes/conteneurs stoppés) respecte la **sémantique protégée** : les éléments `windflow-plugin-*` sont **épargnés** ; un volume monté par un container **arrêté** n'est **pas** éligible ; la suppression est unitaire — un échec n'interrompt pas la file ; le **rapport** liste supprimés / épargnés / échecs sans valeur fabriquée (tailles volumes absentes du rapport).
- [ ] AC 3 : `prune` est **protégé** : réservé superadmin (403 pour admin/operator/viewer), **confirmation explicite** requise (sans `confirm=true` → 400/422 avec message), **dry-run** disponible (aucune suppression, rapport prévisionnel), exécution réelle **auditée** (STORY-125) ; tests 401/403/400.
- [ ] AC 4 : Le **rapprochement `/compute` ↔ `/docker` est documenté** (table de correspondance des endpoints, décision de convergence sans suppression d'endpoint Docker) ; la spec 09 (incorporation F3) est mise à jour sur ces surfaces — livré dans les corrections de specs (coordination P3-4 si non fusionné).
- [ ] AC 5 : Tests complémentaires sur compute (contribution P2-14 : couverture de la zone `compute` ≥ 80 % avec les nouveaux endpoints) ; non-régression des 40 endpoints Docker et de `/compute/stats|global` ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — **§ Volumes — `/api/v1/compute/volumes/`** (endpoints browse/upload/download, **§ Prune des volumes — sémantique protégée** complète), **§ Images** (prune dangling, liste protégée, espace réellement libéré), § Vue Compute (surface `/compute/*` Mode Infra) ;
- [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md) — § Vue Compute (Mode Infra — onglets, filtres), § Actions par type d'objet (Volume Browser ✓ containers) ;
- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Plugin Trivy (volumes `windflow-plugin-trivy-*` protégés du prune — justification de la liste protégée) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Prunes planifiés (actions `compute.images.prune`/`compute.volumes.prune` — la sémantique protégée est spécifiée ch. 09 et servira STORY-160) ;
- [`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — (renvoi) matrice : opérations destructrices globales = Super Admin ;
- `.roo/rules/35-testing-quality-gates.md` — cas obligatoires par verbe (dont DELETE : 401/403/404) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-11 (+ P2-14 pour les tests), §2.D D1, §2.A A16/F3, §5 chaîne critique n°1 et n°4 (RBAC + enveloppes/pagination avant élargissement) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.7-3.8 (compute/docker), §5 (compute_service, classifier, builder), §13.4 (compute API partiel).

## Dépendances

- **STORY-121/122** (RBAC — dépendance explicite du plan) et **STORY-126/128** (enveloppes + pagination — le plan exige P1-5/6 avant l'élargissement) ; idéalement après **STORY-166** (entité Host pour les filtres par Host).
- Interagit avec **STORY-160** (action `compute.docker.prune` du registre scheduler) et **STORY-125** (audit du prune) ; ses tests complémentaires contribuent à l'objectif P2-14 (couverture des zones zéro, coordination avec STORY-165 pour websocket et avec les zones organizations/users/discovery/import_export/stats à couvrir au fil des vagues).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
