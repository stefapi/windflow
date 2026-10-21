# STORY-131.3 : Anti-MITM TOFU runtime — helper de connexion et intégration aux 5 sites SSH (P1-9)

**Statut :** DONE
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Story Parent (split) :** STORY-131 ([ABANDONED — découpe proactive post-analyse le 2026-10-16](STORY-131-ssh-keys-empreintes-anti-mitm.md))
**Item plan :** P1-9 (axe A7, rapports §4/§7) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet runtime anti-MITM + intégration + validation transverse** (phases C+D de l'analyse STORY-131) — tâches 12→19 de la mère **hors la partie `TARGET_SSH_FINGERPRINT_ACCEPTED` de la tâche 13** (portée par 131.2). Couvre l'AC 3, la partie « flux `commands.py` inchangé » de l'AC 4, et l'AC 5 (validation globale). Pré-requis : [STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) (modèles/FK) et [STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md) (service/acceptation).

## Description

En tant qu'administrateur de cibles distantes WindFlow, je veux que **toute session SSH ouverte par WindFlow vérifie l'empreinte de la clé d'hôte du serveur** (politique TOFU : empreinte inconnue → session bloquée avec demande d'acceptation explicite — jamais d'ajout silencieux ; empreinte divergente → connexion bloquée avec message explicite et ré-acceptation délibérée), afin de me protéger contre les attaques MITM sur les connexions aux cibles.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §7) : les 5 sites d'ouverture de session `asyncssh` du dépôt passent tous `known_hosts: None` — acceptation silencieuse de la clé serveur = faille MITM. La spec 15 exige : première connexion → empreinte présentée pour acceptation explicite ; divergence → connexion bloquée avec message explicite.

## Contexte technique

> Extrait de l'analyse STORY-131 (2026-10-16, `analyse-story`) — volets phases C+D. Fondée sur le code réel du dépôt (fichiers et lignes cités). Aucun code modifié.

### Inventaire réel des sessions SSH — toutes en auto-accept MITM

Cinq sites ouvrent une session `asyncssh`, **tous avec `known_hosts: None`** (acceptation silencieuse de la clé serveur = faille MITM ciblée par l'AC 3 de la mère) :

| # | Site | Fichier | Rôle |
|---|------|---------|------|
| 1 | `scan_remote` | [`target_scanner_service.py:108`](../../backend/app/services/target_scanner_service.py) | Scan d'une cible distante (credentials directs) |
| 2 | `_full_scan_remote` | [`target_scanner_service.py:215`](../../backend/app/services/target_scanner_service.py) | Scan d'une Target persistée (via `decrypted_credentials`) |
| 3 | `_run_standard_scan` (fallback) | [`target_scanner_service.py:340`](../../backend/app/services/target_scanner_service.py) | Double scan sans sudo |
| 4 | `_test_ssh_connection` | [`connectivity.py:363`](../../backend/app/api/v1/targets/connectivity.py) | `POST /targets/test-connection` — doit **capter** l'empreinte, jamais l'ajouter |
| 5 | `_detect_access_profile` | [`scanning.py:415`](../../backend/app/api/v1/targets/scanning.py) | `POST /targets/discover` |

La construction des kwargs est dupliquée : [`_build_ssh_kwargs`](../../backend/app/services/target_scanner_service.py:261) (scanner, sites 1-3) et inline dans [`connectivity.py:348`](../../backend/app/api/v1/targets/connectivity.py) / [`scanning.py:400`](../../backend/app/api/v1/targets/scanning.py). La story impose de factoriser en un helper unique appliquant la vérification d'empreinte.

[`SSHCommandExecutor`](../../backend/app/services/commands.py:167) reçoit une `asyncssh.SSHClientConnection` **déjà établie** : sa signature et son comportement ne changent pas (AC 4 de la mère) — toute la vérification TOFU se joue à l'établissement de la connexion, en amont.

### Patterns et briques à réutiliser

- **Modèles** : `HostSSHFingerprint`, `SSHKey.decrypted_private_key`, `targets.ssh_key_id` — posés par [STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) ;
- **Service** : `SSHKeyService.touch_last_used()` (throttlé 60 s) et `resolve_for_target()` — posés par [STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md) ;
- **Events** : [`EventType`](../../backend/app/core/events.py:18) + [`EventBus.emit`](../../backend/app/core/events.py:200) (STORY-164 consommera les nouveaux événements) ;
- **Audit** : [`AuditService.log`](../../backend/app/services/audit_service.py:131) ;
- **Exceptions** : hiérarchie [`WindFlowException`](../../backend/app/core/exceptions.py:36).

### Points d'intégration & contraintes

- **Vérification d'hôte asyncssh** : `asyncssh.connect(..., server_host_key_verify=<callback async>)` — le callback reçoit `(host, addr, port, key, algorithm)` ; STRICT : comparaison base + blocage ; COLLECT (test-connection) : capture sans persistance (AC 3 « jamais d'ajout silencieux ») ;
- **AC 3 « déploiement bloqué »** : il n'existe **pas de déploiement SSH runtime en P1** (le workload adapter distant = STORY-174, P2). La garantie anti-MITM s'applique donc aux 5 sessions existantes (scan, discovery, test) via le helper centralisé — le contrat TOFU sera posé pour P2 qui consommera le même helper ;
- **Backoff anti-tempête** (spec 15 § compteur d'échecs) : confirmé **reporté** hors périmètre (la story mère l'autorise explicitement — « à trancher en analyse ») ; le compteur d'échecs SSH sera traité avec le durcissement P2/P3 si requis ;
- **Non-breaking** : l'extension de [`ConnectionTestResponse`](../../backend/app/schemas/target.py:139) par champs optionnels (`host_fingerprint`, `fingerprint_status`) ne casse pas les clients (enveloppes STORY-126 déjà en place).

### Risques identifiés

- **R2 — Régression scanner** : les 3 sites du scanner partagent `_build_ssh_kwargs` → tests existants du scanner à mettre à jour (mock du helper) ;
- **R3 — Blocage opérationnel** : après activation STRICT, tout scan d'une cible non acceptée échoue → l'endpoint d'acceptation + événements PENDING doivent être disponibles — dans le contexte découpé, [STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md) (endpoint d'acceptation) doit être livrée **avant** le passage STRICT ; la phase C de cette sous-story est livrée **entière** (helper + 5 sites ensemble) ;
- **R4 — asyncssh** : `server_host_key_verify` remplace `known_hosts` — ne plus passer `known_hosts=None` nulle part (grep de non-régression à prévoir en test).

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 3 de la story mère)* : **Anti-MITM** : empreinte **inconnue** → session bloquée + ligne PENDING créée (`accepted=False` — jamais d'ajout silencieux) + événement de confirmation émis (acceptation explicite requise ; le test de connexion n'ajoute jamais silencieusement — il capte sans persister) ; empreinte **divergente** → connexion bloquée avec message explicite et ré-acceptation délibérée ; vérification appliquée sur **toutes** les sessions SSH (asyncssh) — zéro `known_hosts: None` résiduel (R4).
- [x] AC 2 *(reprend la partie applicable de l'AC 4 de la story mère)* : le flux [`commands.py`](../../backend/app/services/commands.py:167) est **inchangé côté appelants** (test de non-régression des commandes existantes) ; les cibles référencent leur clé (`ssh_key_id` accepté en create/update, exposé en réponse, `credentials.ssh_private_key` déprécié).
- [x] AC 3 *(reprend l'AC 5 de la story mère — validation globale)* : `make lint` + `make backend-test` verts ; couverture ≥ 80 % sur les modules touchés ; grep de non-régression R4 vérifié. *(cf. Notes d'implémentation : 35 échecs préexistants hors périmètre, confirmés par test stash sur le commit de base)*

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité réseau → Hosts distants (SSH) : empreintes known_hosts et anti-MITM (TOFU, divergence bloquée), compteur d'échecs/backoff (reporté, cf. contexte) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités d'accès distant (SSH) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7 (critique SSH) ; [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-9, §2.A A7, §3 F4 étape 1, §5 chaîne critique n°2.

## Dépendances

- **[STORY-131.1](STORY-131.1-modeles-migrations-ssh-keys.md) — pré-requis obligatoire** : modèles `HostSSHFingerprint`/`SSHKey`, FK `targets.ssh_key_id` (le helper lit les lignes d'empreintes et `decrypted_private_key`).
- **[STORY-131.2](STORY-131.2-service-api-gestion-cles-ssh.md) — pré-requis (ordre de traitement conseillé : 131.1 → 131.2 → 131.3)** : le helper consomme `SSHKeyService.touch_last_used()`/`resolve_for_target()` et le cycle TOFU complet (acceptation API → STRICT) ; risque R3 sinon (blocage opérationnel sans voie d'acceptation). À défaut, les tests STRICT « acceptée+matching » peuvent insérer les lignes acceptées directement en base — mais l'intégration service est la voie canonique.
- **STORY-103/122/126** (faits ✅ : SecretManager, RBAC, enveloppes). **Services externes** : aucun nouveau.
- **Conditionne** : STORY-164 (EPIC-013 — canal WS `ssh`, qui consommera les `EventType` PENDING/DIVERGENCE) et STORY-174 (P2 — workload adapter, qui consommera le helper `ssh_connection`).

## État d'avancement technique

*(cochage progressif pendant treat-story ; correspondance avec l'analyse mère — phases C+D — indiquée par tâche)*

- [x] Tâche 1 — *(mère : tâche 12 / C1)* Exceptions SSH dédiées (`core/exceptions.py`)
- [x] Tâche 2 — *(mère : tâche 13, partie / C2 partie)* `EventType` PENDING + DIVERGENCE ajoutés (`ACCEPTED` porté par 131.2)
- [x] Tâche 3 — *(mère : tâche 14 / C3)* Helper `ssh_connection.py` (modes STRICT/COLLECT)
- [x] Tâche 4 — *(mère : tâche 15 / C4)* Refactor des 5 sites `asyncssh.connect` (zéro `known_hosts: None` résiduel)
- [x] Tâche 5 — *(mère : tâche 16 / C6)* `ConnectionTestResponse` étendue (empreinte capturée, non persistée)
- [x] Tâche 6 — *(mère : tâche 17 / C5)* Intégration `ssh_key_id` côté cible (schémas/targets + `TargetService`) et scanner
- [x] Tâche 7 — *(mère : tâche 18 / C2 partie émission)* Événements + audit aux points de blocage
- [x] Tâche 8 — *(mère : tâche 19 / D1-D3)* Validation transverse + grep de non-régression R4
- [x] Tests — *(mère : C7)* Tests TOFU (pending/divergence/accepté/collect) + non-régression `commands.py`

## Tâches d'implémentation détaillées

> Séquence reprise des phases C+D de l'analyse STORY-131 (tâches 12→19, partie 13), renumérotée. Périmètre backend uniquement (API-first).

### Tâche 1 : Exceptions SSH dédiées

*(mère : tâche 12)*

**Objectif :** typage métier des blocages TOFU (AC 1).

**Fichiers :**
- `backend/app/core/exceptions.py` — **Modifier** : `SSHHostKeyNotAcceptedError(WindFlowException)` (empreinte inconnue non acceptée — connexion bloquée, ré-essai après acceptation) et `SSHHostKeyMismatchError(WindFlowException)` (divergence — message explicite « hôte reconfiguré ou usurpation/MITM », ré-acceptation délibérée requise). Messages français conformes spec 15, sans donnée sensible.

**Dépend de :** Aucune (dans cette sous-story)

### Tâche 2 : `EventType` empreintes PENDING/DIVERGENCE

*(mère : tâche 13 — partie ; la partie `TARGET_SSH_FINGERPRINT_ACCEPTED` est portée par STORY-131.2, tâche 4)*

**Objectif :** events système du cycle TOFU runtime.

**Fichiers :**
- `backend/app/core/events.py` — **Modifier** : `TARGET_SSH_FINGERPRINT_PENDING = "target.ssh_fingerprint_pending"`, `TARGET_SSH_FINGERPRINT_DIVERGENCE = "target.ssh_fingerprint_divergence"` — émis via `EventBus.emit` (payload : target_id, hostname, port, key_type, fingerprint — jamais de secret). (L'émission effective aux points de blocage se fait tâches 3 et 7.)

**Dépend de :** Aucune

### Tâche 3 : Helper `ssh_connection.py` (STRICT/COLLECT)

*(mère : tâche 14)*

**Objectif :** helper unique de connexion remplaçant les kwargs inline dupliqués et appliquant la vérification d'empreinte (cœur de l'AC 1).

**Fichiers :**
- `backend/app/services/ssh_connection.py` — **Créer** :
  - `build_ssh_kwargs(db, *, target=None, host, port, username, ssh_key_id=None, credentials=None, mode)` ;
  - **Résolution de l'authentification** : si `ssh_key_id` (ou `target.ssh_key_id`) → `SSHKey.decrypted_private_key` en `client_keys` + `touch_last_used()` throttlé ; sinon fallback credentials (`password` / `ssh_private_key` résiduel) — compat totale pendant la transition ;
  - **`server_host_key_verify`** (remplace tout `known_hosts: None`) :
    - mode **STRICT** (scan, discovery, sessions opérationnelles) : lookup `(host_id, hostname, port, key_type)` → pas de ligne → **capture en PENDING (`accepted=False` — jamais silencieux)** + event PENDING + `SSHHostKeyNotAcceptedError` ; ligne non acceptée → idem ; fingerprint divergent → event DIVERGENCE + `SSHHostKeyMismatchError` ; accepté+matching → session (mise à jour `last_used_at` de la clé le cas échéant) ;
    - mode **COLLECT** (test-connection uniquement) : capture l'empreinte présentée **sans rien persister**, la retourne au caller pour affichage/acceptation explicite (AC 1).

**Dépend de :** Tâches 1-2, STORY-131.1 (modèles), STORY-131.2 (service `touch_last_used`/`resolve_for_target`)

### Tâche 4 : Refactor des 5 sites SSH

*(mère : tâche 15)*

**Objectif :** appliquer la vérification sur toutes les sessions (AC 1 « toutes les sessions », R2, R4).

**Fichiers :**
- `backend/app/services/target_scanner_service.py` — **Modifier** : [`_build_ssh_kwargs`](../../backend/app/services/target_scanner_service.py:261) délègue au helper → couvre sites 1-3 (STRICT) ;
- `backend/app/api/v1/targets/connectivity.py` — **Modifier** : [`_test_ssh_connection`](../../backend/app/api/v1/targets/connectivity.py:342) passe COLLECT ;
- `backend/app/api/v1/targets/scanning.py` — **Modifier** : [`_detect_access_profile`](../../backend/app/api/v1/targets/scanning.py:383) passe STRICT ;
- gérer les exceptions nouvelles dans les handlers existants (scan → `CommandExecutionError` wrapping ou propagation typée ; test-connection → réponse structurée). **Contrat AC 2** : signature/comportement de [`SSHCommandExecutor`](../../backend/app/services/commands.py:167) inchangés (il reçoit la connexion établie).

**Dépend de :** Tâche 3

### Tâche 5 : `ConnectionTestResponse` étendue

*(mère : tâche 16)*

**Objectif :** exposer l'empreinte capturée par le test de connexion sans la persister (AC 1 « jamais silencieux »).

**Fichiers :**
- `backend/app/schemas/target.py` — **Modifier** : étendre [`ConnectionTestResponse`](../../backend/app/schemas/target.py:139) avec champs optionnels `host_fingerprint: str|None` et `fingerprint_status: Literal["unknown","accepted","mismatch"]|None` — le test retourne l'empreinte capturée pour acceptation, **rien n'est persisté**. Mettre à jour les exemples OpenAPI de [`connectivity.py`](../../backend/app/api/v1/targets/connectivity.py).

**Dépend de :** Tâche 4 (COLLECT branché)

### Tâche 6 : Intégration de la référence clé côté cible

*(mère : tâche 17)*

**Objectif :** voie canonique d'authentification par clé référencée (AC 2).

**Fichiers :**
- `backend/app/schemas/target.py` — **Modifier** : [`TargetCreate/TargetUpdate`](../../backend/app/schemas/target.py:205) acceptent `ssh_key_id: str|None` (validé : existence sinon 404/422, clé non supprimée) ; [`TargetResponse`](../../backend/app/schemas/target.py:236) expose `ssh_key_id` ;
- `backend/app/services/target_service.py` — **Modifier** : `create/update` persistent `ssh_key_id` ; le scanner résout la clé via le helper (tâche 3) ;
- `credentials.ssh_private_key` devient déprécié à la création (warning loggé si fourni — la voie canonique est la clé référencée).

**Dépend de :** Tâche 3, STORY-131.1 (FK)

### Tâche 7 : Événements et audit aux points de blocage

*(mère : tâche 18)*

**Objectif :** traçabilité des blocages TOFU (observabilité, rules 45).

**Fichiers :**
- Helper (tâche 3) — compléter l'émission : PENDING/DIVERGENCE via EventBus ; audit `target.fingerprint_divergence` (alerte sécurité persistée). Corrélation : inclure `correlation_id` quand disponible.

**Dépend de :** Tâches 2-4

### Tâche 8 : Validation transverse

*(mère : tâche 19)*

**Objectif :** validation globale (AC 3) — y compris le périmètre des sous-stories 131.1/131.2 livrées précédemment.

**Fichiers :**
- Validation : `make lint` ; `make backend-test-unit` puis `make backend-test-all` ; couverture ≥ 80 % sur `models/ssh_key.py`, `models/host_ssh_fingerprint.py`, `services/ssh_key_service.py`, `services/ssh_connection.py`, `api/v1/ssh_keys.py`, `api/v1/targets/fingerprints.py` ; grep de non-régression : plus aucun `known_hosts` à `None` dans `backend/app` (R4).

**Dépend de :** Tâches 1-7

## Tests à écrire

> Règles 35/40 : mock d'asyncssh (pas de réseau réel), httpx `AsyncClient` + `ASGITransport`. Cibles : `backend/tests/unit/`. Extrait de l'analyse STORY-131 — familles 5, 9, 10, 11, 12.

### Backend — unitaires

5. **`backend/tests/unit/test_services/test_ssh_connection.py`** (mock `asyncssh.connect` / callback `server_host_key_verify`) : STRICT sans empreinte → ligne PENDING `accepted=False` créée + `SSHHostKeyNotAcceptedError` + event PENDING émis ; STRICT avec divergence → `SSHHostKeyMismatchError` + event DIVERGENCE + **aucun écrasement de l'empreinte acceptée** ; STRICT acceptée+matching → session OK ; COLLECT → empreinte retournée, **rien persisté** (aucune ligne, AC 1 « jamais silencieux ») ; résolution via `ssh_key_id` → `client_keys` depuis la clé déchiffrée + `last_used_at` maj ; fallback credentials password.
9. **`backend/tests/unit/test_api/test_test_connection_tofu.py`** : `POST /targets/test-connection` (mock asyncssh) → réponse contient `host_fingerprint` + `fingerprint_status="unknown"` et **aucune ligne en base après l'appel** (AC 1) ; cas mismatch simulé → `fingerprint_status="mismatch"` + connexion refusée.
10. **`backend/tests/unit/test_api/test_targets_crud_ssh_key_ref.py`** : create/update avec `ssh_key_id` valide → persisté + exposé dans `TargetResponse` ; `ssh_key_id` inconnu → 404/422 ; `TargetResponse` n'expose jamais de credentials (non-régression).
11. **`backend/tests/unit/test_services/test_commands.py`** (compléter l'existant si présent) : `SSHCommandExecutor.run` inchangé (signature, wrapping sudo, `CommandResult`, erreurs) — le refactor ne touche que l'établissement de connexion en amont ; tests scanner existants mis à jour : `_build_ssh_kwargs` délègue au helper (mock `ssh_connection.build_ssh_kwargs`), comportements préservés.
12. **Grep de non-régression** (test ou vérification CI locale, R4) : `backend/app` ne contient plus aucun `known_hosts` (ni `known_hosts: None`) hors helper `ssh_connection.py`.

### Commandes de validation

```bash
poetry run pytest backend/tests/unit/test_services/test_ssh_connection.py backend/tests/unit/test_services/test_commands.py -v
poetry run pytest backend/tests/unit/test_api/test_test_connection_tofu.py backend/tests/unit/test_api/test_targets_crud_ssh_key_ref.py -v --tb=short
make lint && make backend-test-unit
```

## Notes d'implémentation

*(clôture treat-story — 2026-10-21)*

### Fichiers modifiés/créés (session de clôture)

Cette session a repris une implémentation laissée `IN_PROGRESS` (tâches 1-7 codées, tests écrits mais non validés). Travaux de la session :

- [`backend/app/services/target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) — **correction de bug** : construction des kwargs SSH déplacée **dans** le bloc `try` des sites 1 (`scan_remote`) et 2 (`_full_scan_remote`) — un blocage TOFU (`SSHHostKeyNotAcceptedError`/`SSHHostKeyMismatchError`) levé par le helper à la construction des kwargs est désormais wrappé en `CommandExecutionError` (exit 255, message explicite) conformément au contrat « scan → `CommandExecutionError` wrapping » de la tâche 4 et à la docstring de `scan_remote` ; auparavant l'exception technique remontait brute aux appelants.
- [`backend/tests/unit/test_services/test_commands.py`](../../backend/tests/unit/test_services/test_commands.py) — **2 tests corrigés** (divergence vs contrat réel) :
  - `test_run_wraps_sudo_prefix_and_stdin` : le préfixe sudo historique est `sudo -S -p '' -u <user>` (lecture password stdin, prompt vide) et non `sudo -u <user>` — vérifié inchangé via `git log` sur `commands.py` (AC 2 : flux inchangé, c'est le test qui était faux) ;
  - `test_run_ssh_error_raises_255` : `asyncssh.Error(code, reason)` exige deux arguments positionnels — mock corrigé en `asyncssh.Error(asyncssh.DISC_CONNECTION_LOST, "connection lost")`.

### Fichiers créés/modifiés (implémentation globale de la story, tâches 1-7)

- **Créés** : `backend/app/services/ssh_connection.py` (helper STRICT/COLLECT, callback `server_host_key_verify`, résolution auth `ssh_key_id` → clé déchiffrée + `touch_last_used` → fallback credentials), `backend/tests/unit/test_services/test_ssh_connection.py`, `backend/tests/unit/test_api/test_test_connection_tofu.py`, `backend/tests/unit/test_api/test_targets_crud_ssh_key_ref.py`, `backend/tests/unit/test_services/test_commands.py`.
- **Modifiés** : `core/exceptions.py` (SSHHostKeyNotAcceptedError/SSHHostKeyMismatchError), `core/events.py` (PENDING/DIVERGENCE), `services/target_scanner_service.py` (sites 1-3 STRICT), `api/v1/targets/connectivity.py` (COLLECT), `api/v1/targets/scanning.py` (STRICT), `schemas/target.py` (ConnectionTestResponse étendue + `ssh_key_id` Create/Update/Response), `services/target_service.py` (persistance + validation `ssh_key_id`, dépréciation loggée `credentials.ssh_private_key`).

### Tests et validation (tâche 8)

| Validation | Résultat |
|---|---|
| Tests story (`test_ssh_connection.py` 22, `test_commands.py` 8, `test_test_connection_tofu.py`, `test_targets_crud_ssh_key_ref.py` 11) | ✅ 41 passed |
| Non-régression modules touchés (scanner, ssh_key service/api/helpers, target_service, fingerprints, targets RBAC, modèle fingerprint) | ✅ 159 passed |
| `make backend-lint` (isort + black + flake8 + mypy + bandit) | ✅ exit 0 |
| Couverture ciblée modules story (`ssh_key.py` 100 %, `host_ssh_fingerprint.py` 100 %, `ssh_key_service.py` 97 %, `ssh_connection.py` 97 %, `api/v1/ssh_keys.py` 100 %, `api/v1/targets/fingerprints.py` 100 % — total **98,29 %** ≥ 80 %) | ✅ `--cov-fail-under=80` atteint |
| Grep R4 : `known_hosts` dans `backend/app` (`.py`) | ✅ zéro occurrence active (docstrings uniquement) + test automatisé `test_kwargs_never_contains_known_hosts` |
| Suite unitaire complète | 1783 passed / 35 failed — **35 échecs préexistants hors périmètre** (test_stack_actions 19, test_stacks_archive 9, test_users 3, test_auth_isolation 2, test_stacks_duplicate 1, test_debug_story1033 1), confirmés identiques sur le commit de base sans les changements STORY-131.x (vérification par `git stash`) — non liés à la story, à traiter séparément |

### Divergences par rapport à l'analyse

- Aucune divergence d'architecture. Deux tests de la famille 11 divergeaient du contrat réel (préfixe sudo historique, signature `asyncssh.Error`) : corrigés côté tests avec justification (AC 2 « flux inchangé » fait autorité).
- Bug d'implémentation corrigé en clôture : wrapping TOFU → `CommandExecutionError` manquant sur les sites 1-2 du scanner (kwargs construits hors `try`).

### Difficultés rencontrées

- La config `addopts` de `pyproject.toml` écrase les cibles `--cov` en ligne de commande : la mesure de couverture ciblée exige `-o addopts=""`.
- Échecs préexistants (35) dans la suite globale rendent le signal « suite complète verte » inatteignable en l'état — non bloquant pour la story (hors périmètre, preuve de préexistence fournie).
