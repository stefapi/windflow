# STORY-131.2 : Service & API de gestion des clés SSH et des empreintes hôtes (P1-9)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story Parent (split) :** STORY-131 ([ABANDONED — découpe proactive post-analyse le 2026-10-16](STORY-131-ssh-keys-empreintes-anti-mitm.md))
**Item plan :** P1-9 (axe A7, rapports §4/§7) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet service & API de gestion** (phase B de l'analyse STORY-131) — tâches 7→11 de la mère **plus la partie `TARGET_SSH_FINGERPRINT_ACCEPTED` de la tâche 13** (EventType nécessaire à l'endpoint d'acceptation ; les événements PENDING/DIVERGENCE restent portés par 131.3). Couvre l'AC 2 et la partie « endpoints protégés + aucun secret exposé » de l'AC 4 de la mère. Le volet modèles est porté par [STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) (pré-requis) ; le volet runtime anti-MITM par [STORY-131.3](STORY-131.3-anti-mitm-tofu-runtime.md).

## Description

En tant qu'administrateur de cibles distantes WindFlow, je veux **gérer les clés SSH réutilisables** (génération serveur ed25519, import, partage par N cibles, suppression contrôlée) et **accepter explicitement les empreintes d'hôtes** (consultation, acceptation TOFU, reset) via une API REST protégée par RBAC, afin d'administrer le socle posé par STORY-131.1 sans jamais exposer de clé privée.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §7) : il n'existe aucune surface de gestion des clés SSH ; la spec 15 exige un cycle d'acceptation explicite des empreintes (jamais d'ajout silencieux).

## Contexte technique

> Extrait de l'analyse STORY-131 (2026-10-16, `analyse-story`) — volet phase B. Fondée sur le code réel du dépôt (fichiers et lignes cités). Aucun code modifié.

### Patterns existants à réutiliser (directs)

- **Service métier de cycle de vie de clés** : [`api_key_service.py`](../../backend/app/services/api_key_service.py) (STORY-124.2) — création/validation/suppression contrôlée, `last_used_at` throttlé, logs sans secret ;
- **Modèles & FK** : posés par [STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) (`SSHKey`, `HostSSHFingerprint`, `targets.ssh_key_id`) ;
- **Audit** : [`AuditService.log`](../../backend/app/services/audit_service.py:131) — best-effort, `_sanitize_details` masque `key`/`password`/`credential` ;
- **RBAC** : [`require_admin`](../../backend/app/auth/rbac.py) (credentials = Admin+ selon spec 08) ; pattern isolation org `_get_target_for_org` dans [`targets/crud.py`](../../backend/app/api/v1/targets/crud.py) ;
- **Pagination/enveloppes** : `PaginatedResponse` ([`schemas/common.py`](../../backend/app/schemas/common.py)) + [`PaginationQuery/build_meta`](../../backend/app/helper/pagination.py) (STORY-128) ;
- **Exceptions** : hiérarchie [`WindFlowException`](../../backend/app/core/exceptions.py:36) → `APIError` (NotFound/Conflict/InvalidInput…) ;
- **Events** : [`EventType`](../../backend/app/core/events.py:18) + [`EventBus.emit`](../../backend/app/core/events.py:200) (STORY-164 consommera les nouveaux événements).

### Points d'intégration & contraintes (arbitrages d'analyse)

- **Génération/import de clés** : `asyncssh.generate_private_key("ssh-ed25519")` / `asyncssh.import_private_key(pem, passphrase)` ; empreinte normalisée `SHA256:<base64nopad>` (`key.fingerprint`) ;
- **Passphrase** (arbitrage d'analyse) : la spec 06 n'a pas de colonne passphrase sur `ssh_keys` — à l'import, la passphrase sert à lire la clé, puis la clé est **re-stockée dé-passphrasée mais chiffrée** via le SecretManager (comportement gestionnaire de clés standard ; le secret au repos reste protégé AES-256/Fernet) ;
- **Portée des clés** (arbitrage d'analyse) : spec 06 ne définit **pas** d'`organization_id` sur `ssh_keys` (entité globale partagée) — la protection repose sur `require_admin` (rôle global), l'isolation org est inapplicable par conception ;
- **Suppression contrôlée** : jamais de suppression silencieuse — 409 si des targets référencent la clé, sauf `force=True` (déréférencement explicite).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 2 de la story mère)* : **Réutilisabilité** : une même clé est référençable par N cibles (test) ; génération serveur (ed25519) et import fonctionnels ; clé privée affichée **une seule fois** (réponse de création uniquement) ; suppression refusée si des Hosts/cibles l'utilisent (409) ou déréférencement explicite via `force` — jamais de suppression silencieuse.
- [x] AC 2 *(reprend la partie applicable de l'AC 4 de la story mère)* : endpoints de gestion protégés (`401`/`403` selon RBAC STORY-122 — `require_admin`) ; **aucun secret/clé privée dans les réponses API ni les logs** ; endpoints empreintes avec isolation org et cycle TOFU (liste/acceptation explicite/reset).
- [x] AC 3 *(découpe locale de l'AC 5 de la mère, périmètre service/API)* : tests API + service passants (401/403/422/404/409) ; `make lint` vert ; couverture ≥ 80 % sur `services/ssh_key_service.py` et `api/v1/ssh_keys.py` + `api/v1/targets/fingerprints.py`.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité réseau → Hosts distants (SSH) : clés réutilisables (génération/import, affichage unique, suppression contrôlée), acceptation explicite des empreintes ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'accès distant (SSH) : `SSHKey` et `HostSSHFingerprint` ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — surface d'exposition des hôtes et des clés (à confronter à la surface réelle `/targets/*` existante — arbitrage F3/double nommage en P2) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7 (critique SSH) ; [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-9, §2.A A7.

## Dépendances

- **[STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) — pré-requis obligatoire** : modèles `SSHKey`/`HostSSHFingerprint`, FK `targets.ssh_key_id`, migration livrées.
- **STORY-122** (fait ✅ : `require_admin`/`require_operator` disponibles) ; **STORY-126/127/128** (faits ✅ : enveloppes, exceptions, pagination — les nouveaux endpoints les consomment directement) ; **STORY-103** (fait ✅ : SecretManager).
- **Services externes** : aucun nouveau (asyncssh déjà en dépendance `^2.14.0`).
- **Conditionne** : [STORY-131.3](STORY-131.3-anti-mitm-tofu-runtime.md) (le helper TOFU consomme `SSHKeyService.touch_last_used()`/`resolve_for_target()` ; l'acceptation API alimente le cycle STRICT) et STORY-164 (EPIC-013 — consommera `TARGET_SSH_FINGERPRINT_ACCEPTED`).

## État d'avancement technique

*(cochage progressif pendant treat-story ; correspondance avec l'analyse mère — phase B — indiquée par tâche)*

- [x] Tâche 1 — *(mère : tâche 7 / B1)* Schémas Pydantic (`backend/app/schemas/ssh_key.py`)
- [x] Tâche 2 — *(mère : tâche 8 / B2)* Service `SSHKeyService` (`backend/app/services/ssh_key_service.py`)
- [x] Tâche 3 — *(mère : tâche 9 / B3 + partie B5)* Router `/ssh-keys` CRUD paginé + audit (`backend/app/api/v1/ssh_keys.py`)
- [x] Tâche 4 — *(mère : tâche 10 + partie tâche 13 / B4 + partie B5)* Sous-router empreintes targets + `EventType` ACCEPTED (`backend/app/api/v1/targets/fingerprints.py`)
- [x] Tâche 5 — *(mère : tâche 11 / B6)* Montage routers + OpenAPI exemples
- [x] Tests — *(mère : B7)* Tests API + service passants (401/403/422/404/409)

## Tâches d'implémentation détaillées

> Séquence reprise de la phase B de l'analyse STORY-131 (tâches 7→11 + partie 13), renumérotée. Périmètre backend uniquement (API-first) — l'UI de confirmation reste P2 (arbitrage F3 de la mère).

### Tâche 1 : Schémas Pydantic

*(mère : tâche 7)*

**Objectif :** définir les contrats I/O avec validation stricte et zéro champ sensible en sortie.

**Fichiers :**
- `backend/app/schemas/ssh_key.py` — **Créer** : `SSHKeyGenerateRequest {name 1-100, key_type Literal["ssh-ed25519","ssh-rsa"] = "ssh-ed25519"}`, `SSHKeyImportRequest {name, private_key str (PEM), passphrase str|None}`, `SSHKeyCreated` (response + `private_key` en clair — **affichage unique**, pattern `APIKeyCreated` STORY-124), `SSHKeyResponse {id, name, key_type, public_key, fingerprint, last_used_at, created_at, targets_count}` — **aucun champ private_key/encrypted dans les responses** (checklist sécurité : pas de champ sensible), `SSHKeyUpdate {name}` (rename uniquement — la rotation = nouvelle clé), `HostFingerprintResponse {id, hostname, port, key_type, fingerprint, accepted, accepted_at, created_at}`, `FingerprintAcceptRequest {hostname, port, key_type, fingerprint}`. Validation 422 : longueurs, enum key_type, PEM reconnu à l'import.

**Dépend de :** STORY-131.1 (modèles)

### Tâche 2 : Service `SSHKeyService`

*(mère : tâche 8)*

**Objectif :** logique métier de cycle de vie des clés, 100 % hors HTTP.

**Fichiers :**
- `backend/app/services/ssh_key_service.py` — **Créer** (pattern [`api_key_service.py`](../../backend/app/services/api_key_service.py), logique 100 % hors HTTP) : `generate()` (`asyncssh.generate_private_key(key_type)` → export public/private, fingerprint `SHA256:<b64>`), `import_key()` (import + passphrase, **re-stockage dé-passphrasé chiffré** — arbitrage du contexte), `get/list paginé/count`, `rename`, `delete(db, key_id, force=False)` → **409 ConflictError si des targets référencent** sans `force` ; `force=True` → déréférencement explicite (`UPDATE targets SET ssh_key_id = NULL WHERE ...`) puis suppression (jamais de suppression silencieuse — AC 1), `touch_last_used()` throttlé (60 s, pattern STORY-124.2), `resolve_for_target()` (clé → kwargs asyncssh). Doublon de `name` ou de `fingerprint` à la création explicite → 409. **Logs sans secret** (`key_id`/`name` uniquement — jamais private_key ni passphrase).

**Dépend de :** Tâche 1 (schémas), STORY-131.1 (modèles)

### Tâche 3 : Router `/ssh-keys` CRUD

*(mère : tâche 9)*

**Objectif :** exposer la gestion des clés via API REST protégée (AC 1/AC 2).

**Fichiers :**
- `backend/app/api/v1/ssh_keys.py` — **Créer** + montage : `GET /ssh-keys` (paginé `?page&per_page` max 100, enveloppe `PaginatedResponse`, exemples OpenAPI — pattern [`targets/crud.py`](../../backend/app/api/v1/targets/crud.py)), `POST /ssh-keys/generate`, `POST /ssh-keys/import` (201 + `SSHKeyCreated`), `GET /ssh-keys/{id}`, `PUT /ssh-keys/{id}`, `DELETE /ssh-keys/{id}?force=` (204 / 409). **Tous `Depends(require_admin)`** (spec 08 : gestion des credentials = Admin+), `conditional_rate_limiter`, audit `ssh_key.created`/`ssh_key.deleted` (details : name/key_type/fingerprint — sans secret). Enregistrer dans [`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) et [`backend/app/main.py`](../../backend/app/main.py).

**Dépend de :** Tâche 2

### Tâche 4 : Sous-router empreintes + `EventType` ACCEPTED

*(mère : tâche 10 + partie de la tâche 13)*

**Objectif :** cycle de consultation/acceptation explicite/reset des empreintes (TOFU côté API).

**Fichiers :**
- `backend/app/core/events.py` — **Modifier** *(partie de la tâche 13 de la mère)* : ajouter `TARGET_SSH_FINGERPRINT_ACCEPTED = "target.ssh_fingerprint_accepted"` à [`EventType`](../../backend/app/core/events.py:18) — les événements PENDING/DIVERGENCE sont portés par STORY-131.3 (partie restante de la tâche 13) ;
- `backend/app/api/v1/targets/fingerprints.py` — **Créer** (sous-router monté dans [`targets/__init__.py`](../../backend/app/api/v1/targets/__init__.py)) : `GET /targets/{id}/ssh-fingerprints` (liste des empreintes + statut accepted/pending, isolation org via `_get_target_for_org`), `POST /targets/{id}/ssh-fingerprints/accept` (**acceptation explicite TOFU** — ne peut valider qu'une ligne PENDING existante matching `(hostname, port, key_type)` ; payload fingerprint doit correspondre, sinon 409 ; passe `accepted=True` + `accepted_at` + event `TARGET_SSH_FINGERPRINT_ACCEPTED` + audit `target.fingerprint_accepted`), `DELETE /targets/{id}/ssh-fingerprints/{fp_id}` (reset → re-acceptation requise, audit `target.fingerprint_reset`). `require_admin` + isolation org + 401/403/404/422.

**Dépend de :** Tâches 1-2, STORY-131.1 (modèle `HostSSHFingerprint`)

### Tâche 5 : Montage et documentation OpenAPI

*(mère : tâche 11)*

**Objectif :** routers enregistrés et documentation riche (API-first, rules 20).

**Fichiers :**
- Vérifier/finaliser l'enregistrement des routers des tâches 3-4 ([`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py), [`backend/app/main.py`](../../backend/app/main.py), [`backend/app/api/v1/targets/__init__.py`](../../backend/app/api/v1/targets/__init__.py)) ; exemples OpenAPI riches (pattern targets), descriptions mentionnant TOFU/divergence (spec 15).

**Dépend de :** Tâches 3-4

## Tests à écrire

> Règles 35/40 : sécurité obligatoire (401/403/422/404/409 par endpoint), mock d'asyncssh (pas de réseau réel), httpx `AsyncClient` + `ASGITransport`. Cibles : `backend/tests/unit/`. Extrait de l'analyse STORY-131 — familles 4, 6, 7, 8.

### Backend — unitaires

4. **`backend/tests/unit/test_services/test_ssh_key_service.py`** : génération ed25519 (clé publique consultable, fingerprint `SHA256:`, private chiffrée) ; import avec et sans passphrase (re-stockage dé-passphrasé) ; import PEM invalide → 422/`InvalidInputError` ; name dupliqué → 409 ; **suppression refusée si référencée** (ConflictError) ; suppression `force=True` → déréférencement (targets à NULL) puis delete ; `touch_last_used` throttlé ; logs sans secret (assert sur caplog).
6. **`backend/tests/unit/test_services/test_ssh_key_api_helpers.py`** (ou intégré au test du helper dans 131.3) : acceptation explicite — `accept()` sur PENDING matching → `accepted=True`/`accepted_at` ; payload fingerprint ≠ stocké → 409 ; reset → re-acceptation requise.
7. **`backend/tests/unit/test_api/test_ssh_keys.py`** : nominaux (201 generate/import — `private_key` présent **une seule fois** dans la réponse de création, **absent** des GET/list ; 200 list paginée avec enveloppe `pagination{}` ; 200 détail ; 200 rename ; 204 delete) ; **sécurité** : 401 sans token, 403 viewer **et** operator (admin requis — spec 08), 422 (name vide, key_type inconnu, PEM invalide, body manquant), 404 id inconnu, **409 delete référencée / name dupliqué**, `?force=true` → 204 + targets déréférencées ; pas de `private_key`/`private_key_encrypted`/passphrase dans aucune réponse ni log.
8. **`backend/tests/unit/test_api/test_targets_fingerprints.py`** : GET liste (200, isolation : target d'une org étrangère → 404/403, pattern [`test_rbac_isolation.py`](../../backend/tests/unit/test_api/test_rbac_isolation.py)) ; POST accept (200 nominal, 409 si fingerprint ≠ pending, 404 target inconnue, 422 payload incomplet) ; DELETE reset (204) ; **401 sans token / 403 viewer-operator sur les trois verbes** ; audit `target.fingerprint_accepted` écrit (assert base, pattern [`test_audit_emission.py`](../../backend/tests/unit/test_api/test_audit_emission.py)).

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_ssh_key_service.py -v
poetry run pytest backend/tests/unit/test_api/test_ssh_keys.py backend/tests/unit/test_api/test_targets_fingerprints.py -v --tb=short
make lint
```

## Notes d'implémentation

**Date :** 2026-10-16 — clôture `treat-story` (implémentation directe, session du 2026-10-16).

### Fichiers créés

- `backend/app/schemas/ssh_key.py` — schémas `SSHKeyGenerateRequest`, `SSHKeyImportRequest`, `SSHKeyUpdate`, `SSHKeyResponse` (zéro matériau privé), `SSHKeyCreated` (affichage unique, pattern `APIKeyCreated`), `HostFingerprintResponse`, `FingerprintAcceptRequest` (empreinte validée par pattern `^SHA256:[A-Za-z0-9+/]{43}$`).
- `backend/app/services/ssh_key_service.py` — `SSHKeyService` : `generate`/`import_key` (re-stockage dé-passphrasé chiffré, arbitrage d'analyse), dédup name **et** empreinte (409), `list_keys` paginé avec `targets_count` (sous-requête corrélée, pas de N+1), `count`, `rename`, `delete(force=)` (409 si référencée, déréférencement explicite sinon), `touch_last_used` throttlé 60 s, `resolve_for_target` (kwargs asyncssh, fallback credentials legacy STORY-103.2).
- `backend/app/api/v1/ssh_keys.py` — router `/ssh-keys` (6 endpoints, tous `require_admin` + `conditional_rate_limiter`), audit `ssh_key.created` (origin generated/imported) / `ssh_key.deleted` (force + dereferenced_targets), exemples OpenAPI riches.
- `backend/app/api/v1/targets/fingerprints.py` — sous-router empreintes : GET liste (statut TOFU), POST accept (PENDING matching `(hostname, port, key_type)` + empreinte strictement identique sinon 409 ; event `TARGET_SSH_FINGERPRINT_ACCEPTED` ; audit `target.fingerprint_accepted`), DELETE reset (audit `target.fingerprint_reset`). Isolation org via `is_member` (cible étrangère → 404, anti-énumération).
- Tests : `backend/tests/unit/test_services/test_ssh_key_service.py` (famille 4 — 21 tests), `test_ssh_key_api_helpers.py` (famille 6 — 6 tests), `backend/tests/unit/test_api/test_ssh_keys.py` (famille 7 — 17 tests), `test_targets_fingerprints.py` (famille 8 — 16 tests).

### Fichiers modifiés

- `backend/app/core/events.py` — `EventType.TARGET_SSH_FINGERPRINT_ACCEPTED = "target.ssh_fingerprint_accepted"` (PENDING/DIVERGENCE restent à 131.3).
- `backend/app/api/v1/__init__.py` — montage `ssh_keys_router` prefix `/ssh-keys`.
- `backend/app/api/v1/targets/__init__.py` — montage `fingerprints_router`.
- `backend/tests/unit/test_api/test_rbac_exhaustivite.py` — garde-fou §2.G mis à jour explicitement : `targets` 13→16, + `ssh_keys: 6` (pattern STORY-124.3/129 — l'ajout de routes exige une revue consciente).

### Décisions techniques

- **422 sémantique sur PEM illisible / mauvaise passphrase** : le service lève `UnprocessableEntityError` (pas `InvalidInputError`) — la story et le contrat OpenAPI du endpoint import spécifient 422 `VALIDATION_ERROR` ; aligné sur la sémantique spec 09 (« validation sémantique au-delà du schéma »).
- **`SSHKeyService.list_keys`** (pas `list`) : le nom `list` masquait le builtin dans l'annotation de retour et faisait échouer mypy (`valid-type`).
- **`targets_count` injecté après `model_validate`** : colonne calculée absente du modèle ORM — construite par le service, réinjectée dans le payload (défaut 0 en from_attributes).
- **`accept_at` stocké en naive UTC** (convention SQLite du dépôt, cf. `api_key_service`).
- **Divergence asyncssh respectée** : `key.get_fingerprint()` → `SHA256:<base64nopad>` (43 car., vérifié en runtime, pattern de validation posé dans `FingerprintAcceptRequest`).

### Divergences par rapport à l'analyse

- **Famille 6 (helper)** : l'analyse citait `accept()` sur le service ; il n'existe pas de méthode service dédiée — le cycle TOFU (matching + divergence 409 + reset) vit dans le sous-router (la logique métier empreintes est côté endpoints, comme le posait la tâche 10 de la mère). Le test famille 6 atteste la sémantique (accepted/accepted_at, divergence → `ConflictError` 409, reset → re-acceptation) sans dupliquer la logique ; le parcours HTTP complet est couvert par la famille 8. Signalé comme clarification, pas de refactoring imposé.
- Fichier test famille 6 nommé `test_ssh_key_api_helpers.py` (sans répertoire `test_ssh_key_api/`) — cohérent avec l'option « ou intégré au test du helper » de la story.

### Difficultés rencontrées

- Format OpenSSH : `checkint` aléatoire → deux exports d'une même clé diffèrent octet par octet ; les assertions comparent par **empreinte** (le vrai invariant), pas par PEM textuel.
- Bandit B105 se déclenche sur la **clé** dict `"passphrase"` dans les exemples OpenAPI — exemple vaulted retiré du schéma (l'exemple simple suffit, le champ reste documenté par sa description).
- `make backend-test-unit` : 36 échecs au premier passage → +1 vs baseline 35 : le garde-fou `test_router_route_counts_stable` (comptage de routes par router) exige une mise à jour explicite des compteurs (choix assumé du dépôt, §2.G) — corrigé. Second passage : **35 échecs, tous préexistants** (baseline identifiée par `git stash` lors de 131.1), 1750 passés.

### Validation

- Tests ciblés : 60/60 passants (`test_ssh_key_service.py`, `test_ssh_key_api_helpers.py`, `test_ssh_keys.py`, `test_targets_fingerprints.py`).
- Qualité : isort/black/flake8 **0 finding** sur le périmètre ; mypy **0 erreur** sur les 4 fichiers (les erreurs remontées par la commande concernent des fichiers tiers préexistants) ; bandit **0 finding**.
- Couverture (ciblée) : `ssh_key_service.py` **97%**, `api/v1/ssh_keys.py` **100%**, `api/v1/targets/fingerprints.py` **100%**, `schemas/ssh_key.py` **100%** (seuil ≥80% exigé par l'AC 3).
- Non-régression : `make backend-test-unit` → 35 failed / 1750 passed, strictement la baseline préexistante (aucun échec imputable au périmètre).

### Points d'attention pour STORY-131.3

- Consommer `SSHKeyService.resolve_for_target()` (priorité `ssh_key_id` → credentials legacy) et `touch_last_used()` (throttlé 60 s) ; kwargs asyncssh retournés : `{"client_keys": [SSHKey]}`.
- L'enregistrement runtime des empreintes présentées (lignes PENDING) reste à implémenter (131.2 ne couvre que consultation/acceptation/reset) ; l'acceptation ne valide qu'une ligne PENDING existante — 409 sur divergence, jamais d'écrasement.
- EventTypes `TARGET_SSH_FINGERPRINT_PENDING`/`DIVERGENCE` à ajouter (partie restante de la tâche 13 de la mère).
- `accepted_at` en naive UTC ; empreintes au format strict `SHA256:<43 car. base64 nopad>` (pattern partagé dans `schemas/ssh_key.py`).
