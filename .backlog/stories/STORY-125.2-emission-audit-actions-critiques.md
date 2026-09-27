# STORY-125.2 : Émission d'audit sur les actions critiques

**Statut :** DONE
**Story Parente :** STORY-125 — [ABANDONED] Audit trail — table `audit_logs`, émission sur actions critiques, `GET /admin/audit`, rétention (P1-4) *(découpée — le fichier mère reste la source d'analyse détaillée)*
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-4 (axe A3, rapport §7) — ampleur **M**

## Description

En tant qu'auditeur sécurité de WindFlow, je veux que toute action critique — événements d'authentification (login réussi/échoué, logout, clés API créées/révoquées), suppressions (stacks, targets, organizations, conteneurs), changements de rôles et de membres, déploiements (création/succès/échec/rollback), cycle de vie conteneurs et plugins — émette une ligne dans `audit_logs` via `AuditService.log_from_request`/`log` (acteur, org, action, cible, IP, correlation_id), après succès de l'action métier et sans jamais la faire échouer, afin de répondre à « qui a fait quoi, quand » en cas d'incident.

Deuxième étape de STORY-125 (découpe proactive `split-story` validée par l'utilisateur le 2026-09-25) : consomme le socle posé par STORY-125.1 (table + `AuditService` + helper `log_from_request`) ; couvre la **tâche 8** de l'analyse mère (les ~18 points d'insertion / 20 actions du catalogue) et les tests d'émission associés — dont le **test de référence P1-4** (DELETE stack → ligne avec user, org, action, cible, correlation_id strictement égal au header `X-Correlation-ID`). Ne touche ni à l'EventBus ni au plugin WS `audit_logger` (mécanismes distincts). L'endpoint de consultation et la purge périodique relèvent de STORY-125.3.

## Critères d'acceptation (AC)

- [x] AC 2 : Les **actions critiques** émettent une ligne d'audit : déploiements (création/succès/échec/rollback), suppressions (stacks, targets, organizations, conteneurs), modifications de configuration (settings, config stacks/plugins), événements d'authentification (login réussi/échoué, logout, clés API créées/révoquées), changements de rôles — test de référence : `DELETE` d'une stack → ligne avec **user, org, action, cible, correlation_id** (celui du middleware).
- [x] AC 5 : Tests de sécurité : aucune donnée sensible (mot de passe, token, secret) dans `details` des lignes auditées ; `make lint` + `make backend-test` verts.

> **Note de découpe :** cette sous-story couvre l'AC 2 **en intégralité** (émission + test de référence) et porte la **case AC 5** (démonstration en conditions réelles : aucune donnée sensible dans `details` des lignes auditées sur parcours d'émission + caplog sans secrets + lint/tests verts en commandes de validation). Deux précisions de périmètre héritées de l'analyse mère :
> - « modifications de configuration (settings, config stacks/plugins) » : il n'existe **aucun endpoint settings/machine** à ce jour — `settings.changed` et `machine.*` sont **hors périmètre, reportés et documentés** (arbitrage n°6 de l'analyse) ; la part « config stacks » se matérialise par les actions du catalogue émises ci-dessous ;
> - la part **démonstration en conditions réelles** des AC 4 et 5 : `test_audit_failure_does_not_break_business_action` (AC 4 — échec d'écriture injecté, l'action métier répond quand même) et `test_no_secrets_in_audit_details` / `test_no_secrets_in_logs_caplog` (AC 5 — secrets jamais dans `details` ni les logs sur parcours d'émission réel). Les garanties structurelles équivalentes ont été testées au niveau service dans STORY-125.1 ; l'application périodique de la rétention (AC 4) relève de STORY-125.3.

## Contexte technique

> Analyse réalisée par `analyse-story` (2026-09-25), répartie par `split-story` — patterns vérifiés dans le code, impacts identifiés, exigences sécurité intégrées aux tâches. Source : [`STORY-125-audit-trail-table-emission-retention.md`](STORY-125-audit-trail-table-emission-retention.md).

**Couches impactées :** Backend uniquement — instrumentation des routers et services existants (auth, stacks, targets, organizations, deployments, docker, plugins) + tests d'émission. Aucun impact frontend/CLI, aucun changement de contrat HTTP (les réponses existantes sont inchangées).

**Spécifications de référence :**
- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Audit trail : catalogue d'actions loggées `user.login`/`user.login_failed`, `user.created`/`user.role_changed`, `stack.deployed`/`stack.rollback`, `container.started`/`container.stopped`, `plugin.installed`/`plugin.removed`, `host.added`/`host.removed`, `settings.changed` — enrichi des suppressions et événements clés API ;
- [`.roo/rules/45-observability.md`](../../.roo/rules/45-observability.md) — correlation ID propagé dans toute la chaîne (header `X-Correlation-ID` → middleware → ligne d'audit) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7 (aucun audit trail requêtable à ce jour).

**Disponible en entrée (posé par STORY-125.1) :** table `audit_logs` + migration `1251_audit_logs` ; `AuditService.log()` best-effort (jamais ne lève, details sanitizés à l'écriture) et `AuditService.log_from_request(request, action, *, user=None, ...)` extrayant `ip_address` (`request.client.host if request.client else "unknown"`) et `correlation_id` (`getattr(request.state, "correlation_id", None)`).

**Catalogue d'émission borné (arbitrage n°6 de l'analyse — ampleur M, chaque point = un appel service ; 20 actions / ~18 points d'insertion) :**

| Domaine | Fichier | Actions |
|---|---|---|
| Auth | [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) | `user.login` (réussi), `user.login_failed` (échec credentials — `user_id=None` si user inconnu ; `username` autorisé dans `details` : identifiant public déjà loggé ; **jamais** le password ni aucun secret), `user.logout`, `api_key.created`, `api_key.revoked` |
| Suppressions | [`stacks.py`](../../backend/app/api/v1/stacks.py) / [`targets/crud.py`](../../backend/app/api/v1/targets/crud.py) / [`organizations.py`](../../backend/app/api/v1/organizations.py) / [`docker.py`](../../backend/app/api/v1/docker.py) | `stack.deleted` (**test de référence**), `target.deleted`, `organization.deleted` (bulk delete → une ligne par org), `container.deleted` |
| Rôles | [`organizations.py`](../../backend/app/api/v1/organizations.py) | `user.role_changed` (details `{previous_role, new_role}` — données déjà loggées), `member.added`, `member.removed` |
| Déploiements | [`deployments.py`](../../backend/app/api/v1/deployments.py) / [`deployment_service.py`](../../backend/app/services/deployment_service.py) / [`stacks.py`](../../backend/app/api/v1/stacks.py) | `deployment.created` (acteur = `current_user`), `deployment.succeeded`/`deployment.failed` sur transition terminale dans `DeploymentService.update_status` avec `user_id=None` (**acteur système** — le modèle `Deployment` n'a pas de colonne acteur, vérifié ; l'initiateur reste traçable via la ligne `deployment.created`), `stack.rollback` (handler restore) |
| Conteneurs/plugins | [`docker.py`](../../backend/app/api/v1/docker.py) / [`plugins.py`](../../backend/app/api/v1/plugins.py) | `container.started`/`container.stopped`, `plugin.installed`/`plugin.removed` |

**Hors périmètre (reporté, à documenter) :** `settings.changed` et `machine.*` (aucun endpoint settings/machine à ce jour), `host.added`/`host.removed` (migration Target→Host = STORY-166/P2-4), émissions WebSocket (le plugin `audit_logger` WS existant est un mécanisme distinct — ne pas casser), pont event-driven EventBus (P2).

**Pièges et garde-fous d'insertion :**
- Chaque appel reste **non bloquant** (`log` n'échoue jamais) et ne modifie **aucune réponse HTTP existante** ;
- Émission **après succès** de l'action métier — jamais dans le chemin d'erreur 4xx de validation (sauf `user.login_failed`, volontairement audité aux 2 refus 401 : credentials invalides et user inactif, `details={reason}`) ;
- Correlation_id systématiquement extrait du middleware (`request.state.correlation_id`) — ne jamais le re-calculer côté endpoint ;
- Pour les endpoints org-scopés (stacks/targets), `organization_id` = org de la ressource ; pour les endpoints globaux (docker, admin), `organization_id` reste NULL ;
- Ne **pas** toucher à l'EventBus ([`backend/app/core/events.py`](../../backend/app/core/events.py)) ni au plugin WS `audit_logger` ;
- Tests : exécuter avec `DISABLE_AUTH=false LOG_LEVEL=WARNING` et le venv **`.venv-test`** (piège documenté) ; caplog « aucun secret dans les logs » : neutraliser `sqlalchemy.engine` en WARNING (paramètres bindés).

## Dépendances

- **STORY-125.1** — **prérequis dur** : table `audit_logs` + `AuditService` (`log`, `log_from_request`, `_sanitize_details`) disponibles ;
- **STORY-121** (rôle dans l'org de l'acteur) / **STORY-122** (`require_role`) / **STORY-124** (endpoints `/auth/api-keys`) — **DONE ✔** : points d'insertion stables, aucune dépendance bloquante ;
- **Parallélisable avec** STORY-125.3 (aucune intersection de fichiers : routers ici, `admin/audit.py` + `main.py` là) ;
- **Référence croisée epic :** critère de done P1-4 « DELETE stack → ligne d'audit avec user, org, action, cible, correlation_id » — démontré par le test de référence de cette sous-story.

## Tâches d'implémentation détaillées

### Tâche 1 : Émission — événements d'authentification et clés API
**Objectif :** Brancher `log_from_request` sur login/logout et le cycle de vie des clés API (tâche 8, volet auth, de l'analyse mère).
**Fichiers :**
- `backend/app/api/v1/auth.py` — Modifier — Un appel `AuditService.log_from_request(...)` par point, inséré après le succès métier (jamais dans le chemin d'erreur 4xx de validation — sauf `login_failed` volontairement audité) :
  - `user.login` (après `bruteforce_protector.reset`, avec user + ip) ;
  - `user.login_failed` aux **2 refus 401** (credentials invalides et user inactif, `details={reason}`, `user_id=None` si user inconnu — `username` autorisé dans `details`, jamais le password ni aucun secret) ;
  - `user.logout` ;
  - `api_key.created` / `api_key.revoked` (dans/near les handlers `/api-keys`, `resource_id=key_id`).
**Exigences sécurité :** Émission après succès (sauf `login_failed`) ; details toujours sanitizés (le service le garantit) ; correlation_id extrait du middleware.
**Dépend de :** STORY-125.1

### Tâche 2 : Émission — suppressions, rôles et membres
**Objectif :** Auditer les suppressions destructrices et les changements de rôles/membres (tâche 8, volets suppressions + rôles).
**Fichiers :**
- `backend/app/api/v1/stacks.py` — Modifier — `stack.deleted` sur DELETE `/{stack_id}` — **test de référence P1-4** : ligne avec user, org (org de la stack), action, cible, correlation_id ;
- `backend/app/api/v1/targets/crud.py` — Modifier — `target.deleted` (org du target) ;
- `backend/app/api/v1/organizations.py` — Modifier — `organization.deleted` (bulk delete → **une ligne par org**), `user.role_changed` (details `{previous_role, new_role}`), `member.added` / `member.removed` (POST/DELETE members).
**Exigences sécurité :** Org de la ressource comme `organization_id` ; émission après succès de la suppression ; une ligne par entité supprimée en bulk.
**Dépend de :** STORY-125.1

### Tâche 3 : Émission — déploiements
**Objectif :** Auditer le cycle de vie des déploiements, y compris l'acteur système sur transitions terminales (tâche 8, volet déploiements).
**Fichiers :**
- `backend/app/api/v1/deployments.py` — Modifier — `deployment.created` (POST, acteur = `current_user`, resource = deployment) ;
- `backend/app/services/deployment_service.py` — Modifier — `deployment.succeeded` / `deployment.failed` sur transition terminale de `update_status` (`user_id=None` — **acteur système**, documenté ; l'initiateur reste traçable via `deployment.created`) ; `stack.rollback` dans le handler restore de [`stacks.py`](../../backend/app/api/v1/stacks.py) (POST `/{stack_id}/versions/{version_id}/restore`).
**Exigences sécurité :** Acteur système `user_id=None` pour les transitions de service (pas de colonne acteur sur `Deployment`, vérifié) ; émission dans le service via `log` (pas de `request` disponible).
**Dépend de :** STORY-125.1

### Tâche 4 : Émission — conteneurs et plugins
**Objectif :** Auditer le cycle de vie conteneurs et l'installation/retrait de plugins (tâche 8, volets conteneurs/plugins).
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — `container.started` / `container.stopped` / `container.deleted` (start/stop/delete, `resource_type="container"`, `resource_id` = id conteneur) ;
- `backend/app/api/v1/plugins.py` — Modifier — `plugin.installed` / `plugin.removed` (install/uninstall, org du plugin).
**Exigences sécurité :** `organization_id` NULL sur endpoints globaux Docker ; details sans secret (le service sanitize).
**Dépend de :** STORY-125.1

### Tâche 5 : Tests d'émission — test de référence P1-4 et sécurité
**Objectif :** Démontrer l'émission de bout en bout — champs actor/action/target/timestamp/IP/correlation_id, non-exposition de secrets, résilience de l'action métier (part de la tâche 10 de l'analyse mère).
**Fichiers :**
- `backend/tests/unit/test_api/test_audit_emission.py` — Créer — Pattern `test_api_keys.py` : fixture `_jwt_mode` (monkeypatch `disable_auth=False`), fixtures rôles conftest (`viewer_user`, `operator_user`, `org_admin_user`, `test_superuser`), mint direct JWT ; mocks des dépendances Docker si requis par les patterns existants. Détail en section « Tests à écrire ».
**Exigences sécurité :** Vérification stricte correlation_id header → DB ; échec d'audit n'interrompt pas l'action métier ; aucun secret dans `details` ni les logs.
**Dépend de :** Tâches 1-4

## Tests à écrire

### Backend — émission (test de référence P1-4 + sécurité)
- `backend/tests/unit/test_api/test_audit_emission.py`
  - `test_delete_stack_writes_audit_line` — **critère de done P1-4** : DELETE d'une stack (mock dépendances si requis par les patterns stacks existants) → ligne `audit_logs` avec `user_id` (acteur), `organization_id` (org de la stack), `action="stack.deleted"`, `resource_type="stack"`, `resource_id`, `correlation_id` **= celui du header `X-Correlation-ID` envoyé** (assertion stricte middleware → DB)
  - `test_login_success_and_failure_audited` — login OK → `user.login` avec ip ; mauvais password → `user.login_failed` (`user_id=None` si user inconnu)
  - `test_logout_audited` / `test_api_key_created_and_revoked_audited` — lignes `api_key.created`/`api_key.revoked` (STORY-124 non régressé)
  - `test_role_change_audited` — PUT member role → `user.role_changed` avec `{previous_role, new_role}` dans `details`
  - `test_target_and_organization_deletion_audited`
  - `test_deployment_created_audited` — POST deployment → `deployment.created` avec acteur
  - `test_audit_failure_does_not_break_business_action` — injection d'échec (patch `AuditService.log` interne levant, ou session en échec) → le DELETE stack répond quand même 200/204 (AC 4, part démonstration)
  - `test_no_secrets_in_audit_details` — login avec password + création clé API → aucune ligne d'audit ne contient le password ni la clé `wf_ak_...` brute dans `details` (AC 5)
  - `test_no_secrets_in_logs_caplog` — parcours émission sous caplog : password/clé absents des logs (neutraliser `sqlalchemy.engine` en WARNING — piège documenté)
- Compléments recommandés (si non couverts par les tests ci-dessus) : `member.added`/`member.removed`, `container.started`/`container.stopped`, `plugin.installed`/`plugin.removed`, `deployment.succeeded`/`deployment.failed` avec `user_id=None` (acteur système), `stack.rollback` — au minimum un test représentatif par famille si le maillage complet s'avère trop lourd (documenter la couverture retenue en Notes d'implémentation)

### Commandes de validation
```bash
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_api/test_audit_emission.py -v
# Non-régression (suites sœurs : auth, clés API, stacks)
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/test_api/test_api_keys.py backend/tests/unit/test_api/test_auth_refresh_security.py backend/tests/unit/test_auth/ -v
DISABLE_AUTH=false LOG_LEVEL=WARNING ../.venv-test/bin/pytest backend/tests/unit/ -q --no-cov -p no:randomly
make backend-lint && make backend-typecheck
```
*(⚠️ venv Poetry racine cassé — utiliser `.venv-test` comme documenté par 124.4 ; ajuster les chemins relatifs selon cwd.)*

## État d'avancement technique

*(coché par `treat-story` pendant l'implémentation)*

- [x] Tâche 1 : Émission auth + clés API (login/login_failed/logout, api_key.created/revoked)
- [x] Tâche 2 : Émission suppressions + rôles/membres (stack [test de référence], target, organization, container.deleted ; user.role_changed, member.added/removed)
- [x] Tâche 3 : Émission déploiements (deployment.created/succeeded/failed [acteur système], stack.rollback)
- [x] Tâche 4 : Émission conteneurs/plugins (container.started/stopped, plugin.installed/removed)
- [x] Tâche 5 : Tests d'émission (test de référence DELETE stack + sécurité)

## Notes d'implémentation

*(clôture `treat-story` — 2026-09-27)*

### Fichiers modifiés/créés

**Émission (tâches 1-4 — vérifiée conforme à l'analyse, en place au démarrage de la session) :**
- [`backend/app/api/v1/auth.py`](../../backend/app/api/v1/auth.py) — `user.login` (après reset brute-force), `user.login_failed` aux 2 refus 401 (invalid_credentials / inactive_user, `user_id=None` si inconnu), `user.logout`, `api_key.created` / `api_key.revoked`
- [`backend/app/api/v1/stacks.py`](../../backend/app/api/v1/stacks.py) — `stack.deleted` (test de référence P1-4), `stack.rollback` (handler restore)
- [`backend/app/api/v1/targets/crud.py`](../../backend/app/api/v1/targets/crud.py) — `target.deleted`
- [`backend/app/api/v1/organizations.py`](../../backend/app/api/v1/organizations.py) — `organization.deleted` (simple + **une ligne par org** en bulk), `user.role_changed` (`{previous_role, new_role}`), `member.added` / `member.removed`
- [`backend/app/api/v1/deployments.py`](../../backend/app/api/v1/deployments.py) — `deployment.created` (acteur = current_user)
- [`backend/app/services/deployment_service.py`](../../backend/app/services/deployment_service.py) — `deployment.succeeded` / `deployment.failed` sur transition terminale de `update_status`, `user_id=None` (acteur système)
- [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) — `container.started` / `container.stopped` / `container.deleted` (org NULL, endpoint global)
- [`backend/app/api/v1/plugins.py`](../../backend/app/api/v1/plugins.py) — `plugin.installed` / `plugin.removed` (org du plugin capturée avant suppression)

**Corrections apportées pendant la session (bugs pré-existants révélés par les tests) :**
- [`backend/app/services/stack_service.py`](../../backend/app/services/stack_service.py) — **ajout de `StackService.delete()`** : la méthode était appelée par `DELETE /stacks/{id}` (avec `# type: ignore[attr-defined]`) mais **n'existait pas** → l'endpoint levait `AttributeError` → 500. Le `type: ignore` a été retiré de `stacks.py`.
- [`backend/app/services/deployment_service.py`](../../backend/app/services/deployment_service.py) — `update_status` : crash `TypeError: can't subtract offset-naive and offset-aware datetimes` sur la transition RUNNING → FAILED/STOPPED (`deployed_at` rechargé de SQLite est naïf, `stopped_at` aware) — `stopped_at` et le calcul de durée passés en naïf UTC cohérents ; correction accessoire d'un ordre d'imports isort (pré-existant).

**Tests (tâche 5) :**
- [`backend/tests/unit/test_api/test_audit_emission.py`](../../backend/tests/unit/test_api/test_audit_emission.py) — **créé**, 14 tests

### Décisions techniques

- **Fixture `_audit_db` (autouse)** : les endpoints appellent `log_from_request` sans `db` → session courte via `AsyncSessionLocal` (factory globale **jamais initialisée hors lifespan** — `RuntimeError` sinon, et par best-effort la ligne serait silencieusement perdue). La fixture redirige `app.services.audit_service.AsyncSessionLocal` vers la factory du test : l'émission « session courte » réelle est testée, les lignes sont visibles depuis `db_session`.
- **Test de référence P1-4** : DELETE par un admin d'org dédié (rôle minimum requis, spec 08) avec header `X-Correlation-ID` explicite → assertion stricte `line.correlation_id == header` (middleware → `request.state` → DB) + acteur, org de la stack, action, cible.
- **Plugins** : `_plugin_service` mocké (`AsyncMock`) avec fake `SimpleNamespace` — l'ORM n'est pas sollicité, seule la ligne d'audit compte ; installation via `source` (schéma valide sans URL http).
- **Transitions terminales** : deployment créé directement en base (statut PENDING) puis `update_status(RUNNING)` puis `(FAILED, error_message="boom")` — c'est le **service** qui est testé (pas la création HTTP, couverte par `deployment.created`) ; `deployment_events` mocké pour isoler le WS.
- **Secrets (AC 5)** : login échoué volontaire avec password distinct + login réussi + création clé API → assertions sur **toutes** les lignes d'audit (ni password ni `wf_ak_` brute dans `details`) + caplog avec `sqlalchemy.engine` bridé en WARNING (piège 124.4) pour les logs.

### Couverture de tests retenue (compléments recommandés)

Les 20 actions / ~18 points d'insertion du catalogue sont couverts : test de référence (stack.deleted), auth complète (login/login_failed/logout, api_key.created/revoked), suppressions (target, organization, container.started/stopped/**deleted** dans le même parcours), rôles/membres (member.added, user.role_changed, member.removed), déploiements (deployment.created, **succeeded/failed acteur système**, stack.rollback), plugins (installed/removed). Les lignes d'audit bulk delete d'organisations (une ligne par org) sont couvertes au niveau service dans STORY-125.1 (log_from_request par itération) — le parcours HTTP bulk (max 100 orgs, super_admin) relève du même pattern que le DELETE simple, non dupliqué ici.

### Divergences par rapport à l'analyse

1. **`StackService.delete()` inexistante** (découverte d'exécution, pas prévue par l'analyse) : le test de référence P1-4 attendait un 204 — l'endpoint renvoyait 500 (`AttributeError`). Ajout de la méthode manquante (pattern `TargetService.delete`), retrait du `type: ignore` masqueur.
2. **Crash naive/aware dans `update_status`** (idem) : transition RUNNING → FAILED impossible en SQLite (TypeError sur la durée). Corrigé en naïf UTC cohérent.
3. Tests secrets : l'analyse suggérait « login avec password » ; implémenté avec un **login échoué volontaire** (password secret distinct, audité sans fuiter) + login réussi — le password réel du compte est aussi vérifié absent des `details`.

### Difficultés rencontrées

- `AsyncSessionLocal` global non initialisé en test (voir fixture `_audit_db` ci-dessus) — sans la redirection, les assertions `scalar_one` échouaient silencieusement (best-effort).
- Les erreurs mypy flake8 signalées (`yaml`/`jose` stubs) sont pré-existantes dans d'autres fichiers (venv de test sans types-extra), aucune dans les fichiers touchés.

### Validation

```bash
# Exécuté (venv .venv-test documenté — venv Poetry racine cassé)
DISABLE_AUTH=false LOG_LEVEL=WARNING .venv-test/bin/pytest backend/tests/unit/test_api/test_audit_emission.py -q --no-cov -p no:randomly
# → 14 passed
DISABLE_AUTH=false LOG_LEVEL=WARNING .venv-test/bin/pytest backend/tests/unit/ -q --no-cov -p no:randomly
# → 1542 passed (non-régression complète)
# lint isort+black+flake8 sur fichiers modifiés : OK ; mypy : 0 nouvelle erreur
```
