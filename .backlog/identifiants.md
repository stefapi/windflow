# Registre durable des identifiants

> **Registre rétro-alimenté le 2026-11-01 à partir des fichiers existants et de l'historique Git — motif : mise en place du registre (inspiration previimmo).**

## Politique

Ce registre est la **source de vérité unique** pour l'attribution des identifiants du backlog (epics, stories, sous-stories, bugs).

1. **Inscription obligatoire et simultanée** : tout numéro attribué ou réservé DOIT être inscrit dans ce registre **dans le même changement** que la création du contrat (fichier epic/story/bug). L'entrée comporte au minimum : identifiant, chemin, date d'attribution, motif.
2. **Entrée jamais retirée** : une entrée inscrite n'est JAMAIS supprimée du registre. Un abandon ou une annulation se traduit par une mise à jour du statut (ex: `ABANDONED`), jamais par le retrait de la ligne.
3. **Numéro jamais réutilisé** : un identifiant attribué — même si le contrat est abandonné, supprimé ou erroné — n'est JAMAIS réattribué.
4. **Réservations sans contrat** : une réservation sans fichier de contrat créé est conservée avec le statut « **Réservation sans contrat** » et le motif de la réservation.
5. **Contrat manquant = anomalie** : un identifiant inscrit dont le fichier est absent est une **anomalie à traiter** (restauration via Git ou inscription explicite de l'abandon), jamais un numéro re-disponible.
6. **Suite de numérotation** : la numérotation continue au **plus haut numéro déjà attribué + 1**, par type (epic / story / bug). Les sous-stories `STORY-XXX.N` utilisent un compteur `N` propre à chaque parent, démarrant à 1.

## Epics

| Identifiant | Chemin | Date d'attribution | Statut actuel |
|---|---|---|---|
| EPIC-001 | .backlog/epics/EPIC-001-plugin-system-marketplace.md | 2026-03-13 | TODO |
| EPIC-002 | .backlog/epics/EPIC-002-vm-management.md | 2026-03-13 | TODO |
| EPIC-003 | .backlog/epics/EPIC-003-security-gitops-multitarget.md | 2026-03-13 | TODO |
| EPIC-004 | — | — | **Jamais attribué — écart historique, ne pas combler sans décision** |
| EPIC-005 | .backlog/epics/EPIC-005-backend-integration-tests.md | 2026-03-18 | TODO |
| EPIC-006 | .backlog/epics/EPIC-006-frontend-integration-tests.md | 2026-03-18 | TODO |
| EPIC-007 | .backlog/epics/EPIC-007-test-mocks-infrastructure.md | 2026-03-18 | TODO |
| EPIC-008 | .backlog/epics/EPIC-008-frontend-api-coverage.md | 2026-03-23 | DONE |
| EPIC-009 | .backlog/epics/EPIC-009-container-detail-refonte-edition-complete.md | 2026-04-07 | DONE |
| EPIC-010 | .backlog/epics/EPIC-010-mode-app-navigation-ux.md | 2026-05-24 | DONE |
| EPIC-011 | .backlog/epics/EPIC-011-remediation-p0-securite-bloquante.md | 2026-08-30 | DONE |
| EPIC-012 | .backlog/epics/EPIC-012-remediation-p1-socle-structurant.md | 2026-08-30 | DONE |
| EPIC-013 | .backlog/epics/EPIC-013-remediation-p2-conformite-fonctionnelle.md | 2026-08-30 | DONE |
| EPIC-014 | .backlog/epics/EPIC-014-remediation-p3-finitions-purge.md | 2026-08-30 | DONE — clôturée le 2026-11-07 (revue finale de conformité STORY-254) |
| EPIC-015 | .backlog/epics/EPIC-015-compute-clusters-apps-k8s.md | 2026-09-05 | TODO |

**Prochaine épic : EPIC-016** (plus haut attribué = EPIC-015).

## Stories

| Identifiant | Chemin | Date d'attribution | Statut actuel |
|---|---|---|---|
| STORY-100 | — (fichiers supprimés à la clôture EPIC-011 le 2026-09-07) | 2026-08-30 | DONE — trace : CHANGELOG l.95 + rapport finalisation EPIC-011 — **rétro-inscrite le 2026-11-07 (F3, STORY-254.3)** |
| STORY-101 | — (fichiers supprimés à la clôture EPIC-011 le 2026-09-07) | 2026-08-30 | DONE — trace : CHANGELOG l.96 + rapport finalisation EPIC-011 — **rétro-inscrite le 2026-11-07 (F3, STORY-254.3)** |
| STORY-102 | — (fichiers supprimés à la clôture EPIC-011 le 2026-09-07) | 2026-08-30 | DONE — trace : CHANGELOG l.97 + rapport finalisation EPIC-011 — **rétro-inscrite le 2026-11-07 (F3, STORY-254.3)** |
| STORY-103 | — (fichiers supprimés à la clôture EPIC-011 le 2026-09-07) | 2026-08-30 | DONE — trace : CHANGELOG l.98 + rapport finalisation EPIC-011 — **rétro-inscrite le 2026-11-07 (F3, STORY-254.3)** |
| STORY-104 | — (fichiers supprimés à la clôture EPIC-011 le 2026-09-07) | 2026-08-30 | DONE — trace : CHANGELOG l.99 + rapport finalisation EPIC-011 — **rétro-inscrite le 2026-11-07 (F3, STORY-254.3)** |
| STORY-120 | .backlog/stories/STORY-120-alembic-baseline-migrations.md | 2026-08-30 | DONE |
| STORY-120.1 | .backlog/stories/STORY-120.1-alembic-infra-baseline.md | 2026-09-08 | DONE |
| STORY-120.2 | .backlog/stories/STORY-120.2-retrait-createall-migrations-demarrage.md | 2026-09-08 | DONE |
| STORY-120.3 | .backlog/stories/STORY-120.3-makefile-ci-tests-migrations.md | 2026-09-08 | DONE |
| STORY-121 | .backlog/stories/STORY-121-modele-user-organizations-roles.md | 2026-08-30 | DONE |
| STORY-121.1 | .backlog/stories/STORY-121.1-enum-role-modele-user-organizations.md | 2026-09-09 | DONE |
| STORY-121.2 | .backlog/stories/STORY-121.2-endpoints-gestion-membres.md | 2026-09-09 | DONE |
| STORY-121.3 | .backlog/stories/STORY-121.3-migration-donnees-bascule-lectures.md | 2026-09-09 | DONE |
| STORY-122 | .backlog/stories/STORY-122-dependances-rbac-require-role.md | 2026-08-30 | DONE |
| STORY-122.1 | .backlog/stories/STORY-122.1-socle-rbac-require-role-cache-ttl.md | 2026-09-13 | DONE |
| STORY-122.2 | .backlog/stories/STORY-122.2-rbac-module-docker.md | 2026-09-13 | DONE |
| STORY-122.3 | .backlog/stories/STORY-122.3-rbac-stacks-deployments-schedules-isolation.md | 2026-09-13 | DONE |
| STORY-122.4 | .backlog/stories/STORY-122.4-rbac-organizations-users-escalade.md | 2026-09-13 | DONE |
| STORY-122.5 | .backlog/stories/STORY-122.5-rbac-plugins-registry-targets-lectures.md | 2026-09-13 | DONE |
| STORY-122.6 | .backlog/stories/STORY-122.6-rbac-admin-websockets.md | 2026-09-13 | DONE |
| STORY-122.7 | .backlog/stories/STORY-122.7-rbac-matrice-transverse-non-regression-couverture.md | 2026-09-13 | DONE |
| STORY-123 | .backlog/stories/STORY-123-refresh-tokens-revocables.md | 2026-08-30 | DONE |
| STORY-123.1 | .backlog/stories/STORY-123.1-modele-refresh-token-migration-config.md | 2026-09-13 | DONE |
| STORY-123.2 | .backlog/stories/STORY-123.2-service-refresh-jwt-opaque.md | 2026-09-13 | DONE |
| STORY-123.3 | .backlog/stories/STORY-123.3-endpoints-auth-persistance-refresh-rotation-logout.md | 2026-09-13 | DONE |
| STORY-123.4 | .backlog/stories/STORY-123.4-purge-expires-tests-securite-transverses.md | 2026-09-13 | DONE |
| STORY-124 | .backlog/stories/STORY-124-cles-api-wf-ak.md | 2026-08-30 | DONE |
| STORY-124.1 | .backlog/stories/STORY-124.1-modele-api-key-migration.md | 2026-09-25 | DONE |
| STORY-124.2 | .backlog/stories/STORY-124.2-service-api-key-hash-schemas.md | 2026-09-25 | DONE |
| STORY-124.3 | .backlog/stories/STORY-124.3-endpoints-auth-par-cle.md | 2026-09-25 | DONE |
| STORY-124.4 | .backlog/stories/STORY-124.4-tests-transverses-securite.md | 2026-09-25 | DONE |
| STORY-125 | .backlog/stories/STORY-125-audit-trail-table-emission-retention.md | 2026-08-30 | ABANDONED — découpée en STORY-125.1/125.2/125.3 |
| STORY-125.1 | .backlog/stories/STORY-125.1-modele-audit-migration-service-schemas.md | 2026-09-27 | DONE |
| STORY-125.2 | .backlog/stories/STORY-125.2-emission-audit-actions-critiques.md | 2026-09-27 | DONE |
| STORY-125.3 | .backlog/stories/STORY-125.3-endpoint-admin-purge-retention.md | 2026-09-27 | DONE |
| STORY-126 | .backlog/stories/STORY-126-enveloppes-reponse-api.md | 2026-08-30 | ABANDONED — découpée en STORY-126.1/126.2/126.3 |
| STORY-126.1 | .backlog/stories/STORY-126.1-socle-enveloppes-schemas-handler.md | 2026-09-28 | DONE |
| STORY-126.2 | .backlog/stories/STORY-126.2-activation-tests-contrat.md | 2026-09-28 | DONE |
| STORY-126.3 | .backlog/stories/STORY-126.3-clients-frontend-cli.md | 2026-09-28 | DONE |
| STORY-127 | .backlog/stories/STORY-127-hierarchie-exceptions-api.md | 2026-08-30 | DONE |
| STORY-128 | .backlog/stories/STORY-128-pagination-generalisee.md | 2026-08-30 | DONE |
| STORY-129 | .backlog/stories/STORY-129-system-ready-et-password.md | 2026-08-30 | DONE |
| STORY-130 | .backlog/stories/STORY-130-purge-celery-arbitrage-argon2.md | 2026-08-30 | ABANDONED — découpée en STORY-130.1/130.2 |
| STORY-130.1 | .backlog/stories/STORY-130.1-argon2id-migration-hash.md | 2026-10-03 | DONE |
| STORY-130.2 | .backlog/stories/STORY-130.2-purge-references-celery.md | 2026-10-03 | DONE |
| STORY-131 | .backlog/stories/STORY-131-ssh-keys-empreintes-anti-mitm.md | 2026-08-30 | ABANDONED — découpée en STORY-131.1/131.2/131.3 |
| STORY-131.1 | .backlog/stories/STORY-131.1-modeles-migrations-ssh-keys.md | 2026-10-21 | DONE |
| STORY-131.2 | .backlog/stories/STORY-131.2-service-api-gestion-cles-ssh.md | 2026-10-21 | DONE |
| STORY-131.3 | .backlog/stories/STORY-131.3-anti-mitm-tofu-runtime.md | 2026-10-21 | DONE |
| STORY-160 | .backlog/stories/STORY-160-moteur-scheduler-asyncio.md | 2026-08-30 | ABANDONED — découpée en STORY-160.1/160.2/160.3 |
| STORY-160.1 | .backlog/stories/STORY-160.1-modele-registre-actions-api-schedules.md | 2026-10-23 | DONE |
| STORY-160.2 | .backlog/stories/STORY-160.2-moteur-runtime-asyncio.md | 2026-10-23 | DONE |
| STORY-160.3 | .backlog/stories/STORY-160.3-actions-core-triggers-evenement.md | 2026-10-23 | DONE |
| STORY-161 | .backlog/stories/STORY-161-scheduled-task-executions-historique.md | 2026-08-30 | DONE |
| STORY-162 | .backlog/stories/STORY-162-bus-evenements-canonique.md | 2026-08-30 | DONE |
| STORY-163 | .backlog/stories/STORY-163-consommateurs-plugins-bus-evenements.md | 2026-08-30 | DONE |
| STORY-164 | .backlog/stories/STORY-164-canaux-websocket-manquants-durcissement.md | 2026-08-30 | ABANDONED — découpée en STORY-164.1/164.2/164.3 |
| STORY-164.1 | .backlog/stories/STORY-164.1-protocole-heartbeat-expiration-ack.md | 2026-10-24 | DONE |
| STORY-164.2 | .backlog/stories/STORY-164.2-canaux-ws-ssh-journal-batch.md | 2026-10-24 | DONE |
| STORY-164.3 | .backlog/stories/STORY-164.3-reconnexion-unifiee-client-type.md | 2026-10-24 | DONE |
| STORY-165 | .backlog/stories/STORY-165-tests-websocket-complets.md | 2026-08-30 | DONE |
| STORY-166 | .backlog/stories/STORY-166-migration-target-vers-host-origin.md | 2026-08-30 | ABANDONED — découpée en STORY-166.1/166.2/166.3/166.4/166.5/166.6 |
| STORY-166.1 | .backlog/stories/STORY-166.1-modele-host-enums-migration-alembic.md | 2026-10-30 | DONE |
| STORY-166.2 | .backlog/stories/STORY-166.2-api-hosts-alias-targets-evenements.md | 2026-10-30 | DONE |
| STORY-166.3 | .backlog/stories/STORY-166.3-services-host-scanners-ws.md | 2026-10-30 | DONE |
| STORY-166.4 | .backlog/stories/STORY-166.4-origin-environments-git-url.md | 2026-10-30 | DONE |
| STORY-166.5 | .backlog/stories/STORY-166.5-auto-detection-host-local-seed.md | 2026-10-30 | DONE |
| STORY-166.6 | .backlog/stories/STORY-166.6-frontend-cli-synchronisation-hosts.md | 2026-10-30 | DONE |
| STORY-167 | .backlog/stories/STORY-167-table-deployment-events-structuree.md | 2026-08-30 | DONE |
| STORY-168 | .backlog/stories/STORY-168-cache-fallback-memoire.md | 2026-08-30 | DONE |
| STORY-169 | .backlog/stories/STORY-169-plugins-installation-reelle.md | 2026-08-30 | ABANDONED — découpée en STORY-169.1/169.2/169.3/169.4 |
| STORY-169.1 | .backlog/stories/STORY-169.1-plugins-package-download-checksum-extraction.md | 2026-10-30 | DONE |
| STORY-169.2 | .backlog/stories/STORY-169.2-plugins-validation-manifest-arch-ressources.md | 2026-10-30 | DONE |
| STORY-169.3 | .backlog/stories/STORY-169.3-plugins-install-compose-hooks-rollback.md | 2026-10-30 | DONE |
| STORY-169.4 | .backlog/stories/STORY-169.4-plugins-configure-chiffrement-durcissement.md | 2026-10-30 | DONE |
| STORY-170 | .backlog/stories/STORY-170-plugins-routes-dynamiques-gates.md | 2026-08-30 | ABANDONED — découpée en STORY-170.1/170.2/170.3 |
| STORY-170.1 | .backlog/stories/STORY-170.1-plugins-routes-api-dynamiques.md | 2026-10-31 | DONE |
| STORY-170.2 | .backlog/stories/STORY-170.2-plugins-gates-pre-deploy-pipeline.md | 2026-10-31 | DONE |
| STORY-170.3 | .backlog/stories/STORY-170.3-plugins-trivy-gate-reference.md | 2026-10-31 | DONE |
| STORY-171 | .backlog/stories/STORY-171-unification-validation-stacks.md | 2026-08-30 | DONE |
| STORY-172 | .backlog/stories/STORY-172-observabilite-prometheus-reelle.md | 2026-08-30 | DONE |
| STORY-173 | .backlog/stories/STORY-173-compute-browse-prune-endpoints.md | 2026-08-30 | DONE |
| STORY-174 | .backlog/stories/STORY-174-workload-adapter-docker-recreate-securise.md | 2026-08-30 | DONE |
| STORY-174.1 | .backlog/stories/STORY-174.1-socle-workload-adapter-bascule-deploiement.md | 2026-10-31 | DONE |
| STORY-174.2 | .backlog/stories/STORY-174.2-recreate-securise-rebase-rollback-secrets.md | 2026-10-31 | DONE |
| STORY-250 | .backlog/stories/STORY-250-purge-code-mort-residus.md | 2026-08-30 | DONE |
| STORY-250.1 | .backlog/stories/STORY-250.1-purge-code-mort-backend.md | 2026-10-31 | DONE |
| STORY-250.2 | .backlog/stories/STORY-250.2-deprecation-auth-me-migration-consommateurs.md | 2026-10-31 | DONE |
| STORY-251 | .backlog/stories/STORY-251-circuitbreaker-cabler-ou-supprimer.md | 2026-08-30 | DONE |
| STORY-252 | .backlog/stories/STORY-252-corrections-consolidees-specifications.md | 2026-08-30 | DONE |
| STORY-253 | .backlog/stories/STORY-253-mise-a-jour-documentaire-post-remediation.md | 2026-08-30 | DONE |
| STORY-254 | .backlog/stories/STORY-254-revue-finale-conformite.md | 2026-08-30 | DONE — clôturée via 254.1-254.4 ; plan de remédiation certifié conforme |
| STORY-254.1 | .backlog/stories/STORY-254.1-audit-domaines-specs-code.md | 2026-11-07 | DONE — audit domaines livré (journal 15 sections, écart n°2 résorbé) |
| STORY-254.2 | .backlog/stories/STORY-254.2-croisement-plan-backlog.md | 2026-11-07 | DONE — croisement livré (35/36 + 17/17 reportés, écart n°8 P2-15) |
| STORY-254.3 | .backlog/stories/STORY-254.3-ecrans-controle-arbitrage-ecarts.md | 2026-11-07 | DONE — écrans exécutés, 4 bugs créés (BUG-011→014), arbitrage consigné |
| STORY-254.4 | .backlog/stories/STORY-254.4-rapport-conformite-final.md | 2026-11-07 | DONE — rapport de conformité final publié (docs/backend_conformity_report.md) |

**Écarts de séquence constatés lors de la rétro-inscription** : aucune trace d'attribution pour les plages STORY-132→159 et STORY-175→249 (aucun fichier, aucune mention Git/CHANGELOG). Ces plages sont traitées comme **jamais attribuées** ; par prudence, la numérotation continue néanmoins au plus haut attribué + 1.

**Prochaine story : STORY-255** (plus haut attribué = STORY-254).

## Bugs

Le dossier `.backlog/bugs/` a longtemps été vide : les identifiants BUG-001→009 sont cités dans `CHANGELOG.md` (section `[Unreleased]`) sans fichier de contrat (**fichier absent du dépôt — trace historique CHANGELOG uniquement**). BUG-010 est le premier bug doté d'un contrat complet sur disque.

| Identifiant | Chemin | Date d'attribution | Statut actuel |
|---|---|---|---|
| BUG-001 | — | — | Aucune trace (non cité au CHANGELOG, fichier absent) — rétro-inscription 2026-11-01 |
| BUG-002 | — | — | Aucune trace (non cité au CHANGELOG, fichier absent) — rétro-inscription 2026-11-01 |
| BUG-003 | — (cité dans CHANGELOG.md) | 2026-10-23 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-004 | — (cité dans CHANGELOG.md) | 2026-10-23 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-005 | — (cité dans CHANGELOG.md) | 2026-11-01 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-006 | — (cité dans CHANGELOG.md) | 2026-11-01 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-007 | — (cité dans CHANGELOG.md) | 2026-11-01 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-008 | — (cité dans CHANGELOG.md) | 2026-11-01 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-009 | — (cité dans CHANGELOG.md) | 2026-11-01 | Fichier absent du dépôt — trace historique CHANGELOG uniquement — corrigé (Fixed) |
| BUG-010 | .backlog/bugs/BUG-010-launch-backend-pydantic-core.md | 2026-11-02 | DONE — Correctif lancement backend : sanitation PYTHONPATH + module path uvicorn dans Makefile |
| BUG-011 | .backlog/bugs/BUG-011-garde-fou-rbac-vs-metrics-sans-auth.md | 2026-11-07 | DONE — écart n°1 revue conformité STORY-254.3 : garde-fou RBAC vs /metrics sans auth (résidu STORY-172) — exemption explicite PUBLIC_PATHS (rules 45), corrigé 2026-11-07 |
| BUG-012 | .backlog/bugs/BUG-012-helper-security-bcrypt-orphelin.md | 2026-11-07 | DONE — écart n°3 revue conformité STORY-254.3 : helper/security.py bcrypt orphelin (signalement STORY-252 n°1) — purge helper + dépendance bcrypt + schème, corrigé 2026-11-07 |
| BUG-013 | .backlog/bugs/BUG-013-docstrings-expires-in-1800-auth.md | 2026-11-07 | DONE — écart n°4 revue conformité STORY-254.3 : docstrings expires_in 1800 mensongers (signalement STORY-252 n°2) — exemples OpenAPI alignés sur 900 s (F5), corrigé 2026-11-07 |
| BUG-014 | .backlog/bugs/BUG-014-env-example-variables-non-consommees.md | 2026-11-07 | DONE — écart n°5 revue conformité STORY-254.3 : env.example variables non consommées (signalement STORY-252 n°4) — inventaire croisé exhaustif + settings réels (JWT_*/CACHE_URL/VAULT_ENABLED), corrigé 2026-11-07 |

**Prochain bug : BUG-015** (plus haut attribué = BUG-014). Les dates BUG-003/004 correspondent à leur première apparition dans l'historique Git du CHANGELOG ; BUG-005→009 sont apparus le 2026-11-01.
