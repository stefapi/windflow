# STORY-125 : Audit trail — table `audit_logs`, émission sur actions critiques, `GET /admin/audit`, rétention (P1-4)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-4 (axe A3, rapport §7) — ampleur **M**

## Description

En tant qu'auditeur sécurité de WindFlow, je veux que toute action critique (déploiements, suppressions, modifications de configuration, événements d'authentification, changements de rôles) soit tracée dans une table `audit_logs` avec l'acteur, l'action, la cible, l'IP et le correlation_id, consultable via `GET /admin/audit` paginé et filtrable, afin de répondre à « qui a fait quoi, quand » en cas d'incident.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §7, §14) : aucune table `audit_logs`, aucun service d'audit ; seuls des logs applicatifs existent (non requêtables). La spec 15 exige : « toutes les actions modifiantes sont loggées avec l'utilisateur, l'IP et l'horodatage » — le plan en fait la base du futur endpoint `GET /admin/audit`.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- Schéma cible spec 06 : `audit_logs (id, user_id FK SET NULL, action VARCHAR(50), resource_type VARCHAR(30), resource_id TEXT, details TEXT JSON, ip_address VARCHAR(45), created_at)` + index `user_id`, `action`, `(resource_type, resource_id)`, `created_at` — la story ajoute le **correlation_id** (critère de done P1-4 : ligne avec « user, org, action, cible, correlation_id ») ;
- Catalogue d'actions spec 15 § Audit trail : `user.login`/`user.login_failed`, `user.created`/`user.role_changed`, `stack.deployed`/`stack.rollback`, `container.started`/`container.stopped`, `plugin.installed`/`plugin.removed`, `host.added`/`host.removed`, `settings.changed` — à émettre **en plus** sur : suppressions génériques (DELETE stacks/targets/organizations), modifications de config, auth events (login réussi/échoué, logout, création/révocation de clés API — STORY-124) ;
- Correlation ID existant : middleware [`correlation_middleware`](../../backend/app/middleware) (header `X-Correlation-ID`, présent dans les logs — rules 45) → à propager dans les lignes d'audit ;
- Consultation : `GET /api/v1/admin/audit` (spec 09 § Administration — filtres `user`, `action`, `date`/`since`) — **Super Admin** (matrice spec 08 : Audit consultation = Admin+, administration système = Super Admin ; l'endpoint est sous `/admin/` → `super_admin`) ; réponse **paginée** (format d'enveloppe de STORY-126/128 si fusionnées, sinon pagination simple réalignée ensuite) ;
- Rétention configurable (`AUDIT_RETENTION_DAYS`, défaut : conservation indéfinie ; ex. 90 jours sur RPi) — purge périodique asyncio (cf. cleanup existant), jamais de données sensibles dans `details` (masquer secrets) ;
- Écriture asynchrone non bloquante : l'échec d'écriture d'audit ne doit pas faire échouer l'action métier (log ERROR + métrique) ;
- « Acteur rôle » : dépend de STORY-121 (rôle dans l'org de l'acteur) ; le plugin `audit_logger` WS existant n'est **pas** ce mécanisme (audit applicatif temps réel) — ne pas confondre, ne pas casser.

## Critères d'acceptation (AC)

- [ ] AC 1 : La table `audit_logs` existe via migration Alembic (STORY-120) conformément au schéma spec 06 **+ colonne correlation_id** ; un service d'audit central (`services/audit_service.py`) expose l'écriture (`action`, acteur, org, cible `resource_type/resource_id`, `details` JSON, `ip_address`, `correlation_id`) sans données sensibles.
- [ ] AC 2 : Les **actions critiques** émettent une ligne d'audit : déploiements (création/succès/échec/rollback), suppressions (stacks, targets, organizations, conteneurs), modifications de configuration (settings, config stacks/plugins), événements d'authentification (login réussi/échoué, logout, clés API créées/révoquées), changements de rôles — test de référence : `DELETE` d'une stack → ligne avec **user, org, action, cible, correlation_id** (celui du middleware).
- [ ] AC 3 : `GET /api/v1/admin/audit` répond **paginé** avec filtres (`user_id`, `action`, `since`) ; protégé `super_admin` (STORY-122) : `401` sans token, `403` pour viewer/operator/admin d'org.
- [ ] AC 4 : **Rétention configurable** appliquée : `AUDIT_RETENTION_DAYS` (défaut illimité) purge les entrées au-delà du seuil — test avec valeur courte ; l'écriture d'audit en échec n'interrompt pas l'action métier (test avec injection d'échec).
- [ ] AC 5 : Tests de sécurité : aucune donnée sensible (mot de passe, token, secret) dans `details` des lignes auditées ; `make lint` + `make backend-test` verts.

## Références spécification

- [`docs/general_specs/15-securite.md`](../../docs/general_specs/15-securite.md) — § Audit trail (catalogue d'actions loggées, consultation CLI/API, rétention `AUDIT_RETENTION_DAYS`) ;
- [`docs/general_specs/06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Entités auth et audit → `AuditLog` (schéma SQL) ;
- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Administration → `GET /admin/audit` (filtres user/action/date) ;
- `.roo/rules/45-observability.md` — correlation ID propagé dans toute la chaîne (inclus dans les lignes d'audit) ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §7 (aucun audit trail), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-4, §2.A A3, §7.3 (audit branché avant plugins réels P2 — STORY-162 idéalement après cette story).

## Dépendances

- **STORY-120** (migration de la table `audit_logs`) ; **STORY-121** pour l'acteur et son rôle (dépendance « P1-2 pour l'acteur rôle » du plan) ; s'appuie sur STORY-122 pour la protection `super_admin` du endpoint de consultation (à défaut, `require_superuser` en attendant).
- Est un prérequis recommandé de : STORY-162 (plugins réels, EPIC-013 — audit branché avant l'introduction de la surface d'attaque download/hooks).

## Sous-stories

*(section réservée — ampleur M, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
