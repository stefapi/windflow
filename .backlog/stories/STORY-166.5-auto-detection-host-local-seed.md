# STORY-166.5 : Auto-détection du host local au premier démarrage — setting désactivable + alignement du seed (P2-10/C8 — STORY-166 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-166 ([ABANDONED — découpe proactive post-analyse le 2026-10-24](STORY-166-migration-target-vers-host-origin.md))
**Item plan :** P2-10 (axe C8) — ampleur **S-M** *(plus petite qu'annoncé par le plan : le seed existe déjà — divergence n°5 de la mère)*

> **Périmètre (découpe)** : cette sous-story reprend le **volet auto-détection** de STORY-166 (P2-10/C8) — setting de désactivation de l'auto-détection ([`config.py`](../../backend/app/config.py) — aucun n'existe aujourd'hui), alignement du seed existant sur le modèle `Host` (profil canonique `host_baremetal`, trace d'origine), réutilisation du scanner. Couvre la partie **auto-détection de l'AC 4 de la mère**. ⚠️ Divergence n°5 : [`database_seed.py`](../../backend/app/database_seed.py) `_create_localhost_target` **existe déjà** (l.123) — scan via `TargetScannerService.scan_localhost()`, création, `apply_scan_result` avec capacités persistées : la story est plus petite que prévu (setting off + profil canonique + origin).

## Description

En tant qu'administrateur WindFlow, je veux que le premier démarrage détecte automatiquement le host local (avec ses capacités scannées) et que cette détection soit désactivable par setting — afin que toute installation fraiche dispose du substrat local prêt à l'emploi sans configuration manuelle, tout en laissant le choix de la désactiver.

**Problème constaté** ([`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) C8) : l'auto-détection du host local est absente **comme option configurable** — le seed la fait déjà par défaut mais sans setting de désactivation, sans profil canonique ni trace d'origine (divergence n°5).

## Contexte technique

> Extrait de l'analyse STORY-166 (2026-10-24, `analyse-story`) — volet seed/auto-détection, fondé sur le code réel du dépôt.

### État réel du code (exploration mère)

- [`database_seed.py`](../../backend/app/database_seed.py) : `_create_localhost_target` (l.123) **existe déjà** — scan via [`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) `scan_localhost()` (l.70+), création du target local, `apply_scan_result` avec capacités persistées — **à aligner sur `Host`** (166.1/166.3) : profil canonique `host_baremetal`, `origin` (managed ou détection — à arbitrer en analyse), nommage ;
- [`config.py`](../../backend/app/config.py) : **aucun setting d'auto-détection** — à créer (ex. `auto_detect_local_host: bool = True` — pattern des settings bool existants type `disable_auth`, `prometheus_enabled`) ;
- [`services/container_classifier.py`](../../backend/app/services/container_classifier.py) (l.26) : `LOCAL_TARGET_ID = "local"` placeholder — coordination possible avec cette story (résoudre le host local seedé — voir [STORY-166.3](STORY-166.3-services-host-scanners-ws.md)).

### Points d'attention

- Le seed tourne au **premier démarrage** (lifespan) — le setting doit être lu au bon moment et documenté dans `env.example` ;
- Idempotence : le seed ne doit pas dupliquer le host local si déjà présent (comportement actuel à conserver) ;
- Événement `host.added` : émettre ou non au seed — à arbitrer en analyse (bruit vs traçabilité).

### Checklist sécurité (règle 40)

- Le host local seedé appartient à l'organisation par défaut — isolation organisationnelle respectée ;
- Aucun credentials sensible sur le host local (pas de `connection_config`) ; logs du seed sans données sensibles.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie auto-détection de l'AC 4 de la mère)* : **Auto-détection** — premier démarrage → host local présent avec capacités scannées (profil `host_baremetal` + `origin` posé), **désactivable par setting** : test avec setting off → **aucun host créé**.
- [x] AC 2 : Setting documenté ([`config.py`](../../backend/app/config.py) + `env.example`) ; idempotence du seed conservée (redémarrage → pas de doublon) ; non-régression seed existant.
- [x] AC 3 : Couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §2.C C8, §4 P2-10 ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Host (profil `host_baremetal`, `WorkloadOrigin`).

## Dépendances

- **[STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md)** (dur) — modèle `Host` + profils ; **[STORY-166.3](STORY-166.3-services-host-scanners-ws.md)** (dur) — scanner renommé `host_scanner_service` (le seed l'appelle) ;
- Optionnelle : coordination avec l'arbitrage `LOCAL_TARGET_ID` de 166.3 ;
- Aucune dépendance frontend — [STORY-166.6](STORY-166.6-frontend-cli-synchronisation-hosts.md) est indépendante de celle-ci.

## État d'avancement technique

*(à cocher pendant `treat-story` — une case par tâche détaillée ci-dessous)*

- [x] T1. Setting `auto_detect_local_host` (`config.py` + `env.example`)
- [x] T2. Renommage `_create_localhost_target`→`_create_local_host` + profil canonique + `origin`
- [x] T3. Garde du setting dans `seed_database` + logs sans secrets
- [x] T4. Arbitrage `host.added` au seed (non-émission documentée) + idempotence explicite
- [x] T5. Tests seed (setting off/on, idempotence, profil/origin)

## Tâches d'implémentation détaillées

### Tâche 1 : Setting `auto_detect_local_host`
**Objectif :** Ajouter dans `config.py` (pattern des bool settings existants `disable_auth` l.521, `prometheus_enabled` l.439, `auto_load_stack_definitions`) : `auto_detect_local_host: bool = True` avec docstring (« détecte et seed le host local au premier démarrage — scan capacités inclus ; désactivable pour installations sans substrat local ») + section seed dans `env.example` : `WINDFLOW_AUTO_DETECT_LOCAL_HOST=true` (commentaire documentant le comportement off). Vérifier le préfixe env réel de la classe Settings (`env_prefix`) pour le nom exact de la variable.
**Fichiers :**
- `backend/app/config.py` — [Modifier] — nouveau setting (groupe « Database seed / bootstrap »)
- `env.example` — [Modifier] — variable + doc
**Dépend de :** Aucune (mais livrée après 166.1/166.3 pour le scan renommé)

### Tâche 2 : Alignement du seed sur `Host`
**Objectif :** Renommer `_create_localhost_target` (l.123)→`_create_local_host` + aligner : imports sur `HostService`/`HostScannerService`/`host_scan_parsers` (livrés 166.3), `HostCreateRequest` avec `profile=HostProfile.HOST_BAREMETAL` (remplace `type=_default_seed_target_type()` — la fonction l.200-208 devient obsolete : la remplacer par la constante profil, ou la conserver renommée `_default_seed_host_profile()` retournant `HOST_BAREMETAL`), `origin` : **arbitrage d'analyse** → `managed` (le host est seedé/piloté par WindFlow ; `WorkloadOrigin` décrit la provenance du pilotage — cf. arbitrage cohérent 166.4 T5 : la pose `external` serait mensongère, rien n'est importé). `extra_metadata` conserve `{"auto_created": True, "creation_source": "database_seed"}` + ajoute `{"seed_profile": "host_baremetal"}`. Sortie console : « Host: localhost (créé automatiquement) » (l.103-106).
**Fichiers :**
- `backend/app/database_seed.py` — [Modifier] — fonction renommée + imports canoniques + profil/origin (l.123-197, l.200-208)
**Dépend de :** Tâche 1, STORY-166.1, STORY-166.3

### Tâche 3 : Garde du setting dans `seed_database`
**Objectif :** Dans `seed_database` (appelant de `_create_local_host`) : `if not settings.auto_detect_local_host: print("  - Host local: auto-détection désactivée (WINDFLOW_AUTO_DETECT_LOCAL_HOST=false)")` et **return sans scanner** — le scan localhost (`scan_localhost()` l.140) ne doit pas s'exécuter du tout quand le setting est off (économie + aucun host créé — AC 1). Logs/prints sans aucune donnée sensible (règle 40 — le host local n'a pas de credentials : `SSHCredentials(auth_method=LOCAL)` inchangé).
**Fichiers :**
- `backend/app/database_seed.py` — [Modifier] — garde early-return + message
**Dépend de :** Tâches 1, 2

### Tâche 4 : Arbitrage émission `host.added` au seed + idempotence
**Objectif :** **Décision d'analyse — ne pas émettre `host.added` au seed** : le bus n'est pas encore consommable au bootstrap (le seed tourne dans le lifespan avant la mise disposition de l'API/bus), l'émission serait au mieux un bruit best-effort ; la traçabilité existe déjà via `extra_metadata.creation_source=database_seed`. Documenter l'arbitrage en docstring de `_create_local_host` + Notes d'implémentation. Idempotence : **rendre explicite** la garde existante — vérifier comment `seed_database` évite le doublon aujourd'hui (probablement `HostService.get_by_name(session, org, "localhost")` avant création) ; si la garde repose sur l'échec d'unicité, ajouter le check préalable propre + message « déjà présent, ignoré » (comportement AC 2).
**Fichiers :**
- `backend/app/database_seed.py` — [Modifier] — docstring arbitrage + garde idempotence explicite
**Dépend de :** Tâche 3

### Tâche 5 : Tests seed
**Objectif :** Étendre les tests seed existants (`test_database.py` l.351 et `test_migrations.py` l.1146 patchent déjà `_create_localhost_target` — **chemins de patch à renommer** `_create_local_host`) + nouveaux cas setting off/on/idempotence.
**Fichiers :**
- `backend/tests/unit/test_database.py` — [Modifier] — chemins de patch + classe `TestSeedAutoDetectSetting`
- `backend/tests/integration/test_migrations.py` — [Modifier] — chemin de patch (l.1147)
- `backend/tests/unit/test_database_seed.py` — [Créer] — tests dédiés (si le module n'existe pas ; sinon étendre)
**Dépend de :** Tâches 1-4

## Tests à écrire

### Backend

**`backend/tests/unit/test_database_seed.py`** *(créer/étendre)* :
- **setting off** (`auto_detect_local_host=False`, monkeypatch settings) → `_create_local_host` jamais appelé, **aucun host créé**, `scan_localhost` jamais invoqué (mock scanner — assertion d'absence d'appel) — AC 1 ;
- **setting on** (défaut `True`) → host local présent : `profile == "host_baremetal"`, `origin == "managed"`, capacités persistées (mock scanner → payload fixe), `extra_metadata.creation_source == "database_seed"` ;
- **idempotence** : double exécution de `seed_database` → un seul host localhost (garde explicite) ;
- host local rattaché à l'organisation par défaut (`organization_id` correct) ;
- aucun credentials sur le host seedé (`credentials == {}` en base ou `auth_method == local`) — règle 40 ;
- échec du scan (scanner lève) → seed ne casse pas le démarrage (`target_created=False`, détails renseignés — comportement l.193-197 conservé).

**`backend/tests/unit/test_database.py`** *(étendre)* :
- chemins de patch `_create_localhost_target`→`_create_local_host` (l.351-352) — non-régression des tests seed existants ;
- message console setting off.

**`backend/tests/integration/test_migrations.py`** *(étendre)* :
- chemin de patch renommé (l.1146-1148) — non-régression.

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_database_seed.py backend/tests/unit/test_database.py -v
poetry run pytest backend/tests/integration/test_migrations.py -v
make backend-test-unit
make backend-lint
```

## Notes d'implémentation

*(clôture 2026-10-30 — `treat-story`)*

### Fichiers modifiés/créés

- `backend/app/config.py` — setting `auto_detect_local_host: bool = True` (l.470, groupe seed/bootstrap, docstring comportement off)
- `env.example` — `WINDFLOW_AUTO_DETECT_LOCAL_HOST=true` documenté (l.125)
- `backend/app/database_seed.py` — `_create_localhost_target`→`_create_local_host` (l.133) : profil canonique `HostProfile.HOST_BAREMETAL`, `origin=managed`, `extra_metadata = {"auto_created": True, "creation_source": "database_seed", "seed_profile": "host_baremetal"}`, garde early-return du setting dans `seed_database` (aucun scan quand off), garde d'idempotence explicite (« déjà présent, ignoré »)
- `backend/tests/unit/test_database_seed.py` — créé : 9 tests (setting off sans host ni scan, setting on profil/origin/metadata/org/credentials, idempotence double-seed + garde, échec scan non-fatal, résolution `LOCAL_HOST_ID` par compute + fallback placeholder)
- `backend/tests/unit/test_database.py` — chemins de patch renommés `_create_local_host` + message console setting off
- `backend/tests/integration/test_migrations.py` — chemin de patch renommé (l.1147)

### Décisions techniques

- **Non-émission de `host.added` au seed** (arbitrage T4) : le bus n'est pas encore consommable au bootstrap (seed dans le lifespan avant exposition API/bus) ; traçabilité assurée par `extra_metadata.creation_source = "database_seed"` — documenté en docstring de `_create_local_host`.
- **`origin = managed`** : le host local est seedé/piloté par WindFlow ; poser `external` serait mensongère (rien n'est importé) — cohérent avec l'arbitrage 166.4 T5.
- **Aucun credentials réels** sur le host seedé (`SSHCredentials(auth_method=LOCAL)` inchangé) — règle 40 respectée.

### Résultats validation

| Vérification | Résultat |
|---|---|
| Tests ciblés (`test_database_seed.py` + `test_database.py`) | **17 passed** |
| Intégration migrations | **45 passed, 1 skipped** (skip préexistant) |
| Non-régression `make backend-test-unit` | **2610 passed** |
| Lint périmètre (isort/black/flake8 sur `config.py`, `database_seed.py`, `test_database_seed.py`) | **0 erreur** (isort a réordonné les imports de `test_database_seed.py` à la clôture) |
| mypy fichiers du périmètre | **0 erreur** (6 erreurs préexistantes hors périmètre : `background_tasks.py`, `schemas/deployment.py`, `auth/jwt.py`, `host_scanner_service.py`, `connection_managers.py`) |
| Couverture `app.database_seed` | **80 %** (cible ≥ 80 % ✓) |
| Couverture `app.config` | **88 %** avec `test_config/` existant (cible ≥ 80 % ✓) |

### Divergences

- Aucune divergence fonctionnelle vs analyse. Correction mineure à la clôture : imports de `test_database_seed.py` réordonnés par isort (lint gate).
- Note mesure : la couverture `config.py` mesurée sur les seuls tests seed donne 78 % ; les tests `tests/unit/test_config/test_production_guard.py` existants (garde-fou production) portent le module à 88 % — aucun nouveau code écrit pour la gate.
