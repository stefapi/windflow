# STORY-103.3 : Env vars stacks — chiffrement au repos et masquage API (P0-4c)

**Statut :** DONE
**Story Parente :** STORY-103 — SecretManager AES/Fernet — chiffrement au repos des credentials cibles et env vars de stacks (P0-4)
**Epic Parent :** EPIC-011 — P0 : Sécurité bloquante

## Description

En tant qu'administrateur sécurité de WindFlow, je veux que les variables d'environnement sensibles des stacks soient chiffrées au repos (équivalent `env_vars_encrypted` de la spec) dans les snapshots de déploiement, afin que la compromission de la base ne révèle pas leurs valeurs, et que l'API ne renvoie jamais ces valeurs en clair.

**Problème constaté** : le modèle [`Deployment`](../../../backend/app/models/deployment.py) snapshotte `config` et `variables` en JSON en clair ([`models/deployment.py:80`](../../../backend/app/models/deployment.py:80), [`models/deployment.py:91`](../../../backend/app/models/deployment.py:91)), et les schémas de réponse [`DeploymentResponse.config`](../../../backend/app/schemas/deployment.py:214) / [`DeploymentResponse.variables`](../../../backend/app/schemas/deployment.py:224) **renvoient les valeurs en clair** par l'API — écart sécurité à corriger (masquage `***`).

## Critères d'acceptation (AC)

- [x] AC 3 : Les variables d'environnement sensibles des stacks sont chiffrées au repos (équivalent `env_vars_encrypted` de la spec) et déchiffrées uniquement en mémoire au moment du rendu/déploiement — jamais écrites sur disque (`.env`/override) ni loggées ; l'API et l'UI ne renvoient jamais la valeur en clair (masquage `***` dans les réponses/aperçus).

## Contexte technique

- **Snapshot au déploiement** : `Deployment.config` et `Deployment.variables` ([`models/deployment.py:79-91`](../../../backend/app/models/deployment.py:79)) — les valeurs de variables y sont copiées en clair ; la création du déploiement et le rendu passent par le service de déploiement / [`tasks/background_tasks.py`](../../../backend/app/tasks/background_tasks.py:24) et [`stack_service.py`](../../../backend/app/services/stack_service.py:19).
- **Stratégie recommandée** (à confirmer à l'implémentation) : chiffrer les **valeurs** des variables sensibles dans le snapshot (clé en clair, valeur chiffrée — détectable par préfixe Fernet) pour rester sans migration de schéma et compatible double lecture ; les variables non sensibles restent lisibles pour l'UI (liste des noms).
- **Masquage API** : [`schemas/deployment.py`](../../../backend/app/schemas/deployment.py) — `DeploymentResponse` et toute réponse/aperçu exposant `config`/`variables` doivent masquer les valeurs par `***` (pattern déjà pratiqué par [`adoption_service.py:230`](../../../backend/app/services/adoption_service.py:230) et [`schemas/plugin.py`](../../../backend/app/schemas/plugin.py:159)) ; l'UI Vue n'a pas de modification requise si le masquage est fait côté schéma.
- **Rendu/déploiement** : le déchiffrement intervient uniquement en mémoire au moment du rendu (Jinja/compose) — jamais écrit dans un `.env`/override sur disque, jamais loggé.
- **Ne pas régresser** le moteur de rendu existant (garde-fous §2.G).

## Dépendances

- STORY-103.1 : SecretManager Fernet — socle config, dépendance et classe core (fournit `SecretManager` + helper détection ciphertext)

## Tâches d'implémentation détaillées

### Tâche 1 : Chiffrer les valeurs sensibles dans les snapshots de déploiement
**Objectif :** Lors de la création/exécution d'un déploiement, les valeurs des variables sensibles stockées dans `Deployment.config`/`variables` sont chiffrées via le SecretManager (clé conservée, valeur chiffrée) ; déchiffrement en mémoire uniquement au moment du rendu.
**Fichiers :**
- `backend/app/models/deployment.py` — Modifier — propriétés d'accès déchiffrées pour `config`/`variables` (pattern double lecture, préfixe `gAAAA`)
- `backend/app/services/deployment_service.py` — Modifier — écriture du snapshot : chiffrement des valeurs au moment de la persistance
- `backend/app/tasks/background_tasks.py` — Modifier — le rendu/exécution consomme les valeurs déchiffrées en mémoire (jamais écrites sur disque)
**Exigences sécurité :** aucune valeur sensible dans les logs du déploiement (logs structurés sans contenu de variables) ; aucun `.env`/override écrit avec les valeurs en clair.
**Dépend de :** Aucune (dans cette sous-story)

### Tâche 2 : Masquer les valeurs dans les réponses API
**Objectif :** Les schémas de réponse exposant `config`/`variables` renvoient `***` à la place de toute valeur sensible (déchiffrée ou non), l'UI n'affiche donc jamais de valeur en clair.
**Fichiers :**
- `backend/app/schemas/deployment.py` — Modifier — `DeploymentResponse` (~lignes 214, 224) et tout autre schéma d'aperçu concerné : masquage des valeurs
**Exigences sécurité :** vérifier qu'aucun autre endpoint (stacks, aperçus de rendu) ne renvoie les valeurs en clair — tester la non-exposition.
**Dépend de :** Tâche 1

### Tâche 3 : Non-régression du pipeline de rendu/déploiement
**Objectif :** Vérifier que le rendu Jinja/compose et l'exécution des déploiements fonctionnent à l'identique avec des snapshots chiffrés (le moteur reçoit les valeurs déchiffrées en mémoire).
**Fichiers :**
- `backend/app/services/stack_service.py` — Modifier — si le rendu lit directement `variables` du modèle, router via l'accès déchiffré
- `backend/app/services/docker_compose_service.py` — Modifier — si applicable, s'assurer que la génération compose reçoit les valeurs en mémoire uniquement
**Exigences sécurité :** les fichiers compose générés sur la cible peuvent contenir les valeurs (nécessaire à l'exécution) mais jamais les logs ni la base en clair — documenter ce choix en note d'implémentation.
**Dépend de :** Tâche 1

## Tests à écrire

### Backend
- `backend/tests/unit/test_models/test_deployment.py`
  - `test_snapshot_variables_encrypted_at_rest` — après création, la colonne ne contient pas les valeurs en clair (préfixe `gAAAA` détecté sur les valeurs sensibles)
  - `test_double_reading_deployments` — snapshot ancien en clair → accès → relecture chiffrée
- `backend/tests/unit/test_schemas/test_deployment.py`
  - `test_response_masks_sensitive_variables` — `DeploymentResponse.variables` renvoie `***` pour les valeurs sensibles, jamais la valeur en clair
- `backend/tests/unit/test_api/test_deployments.py`
  - `test_deployments_api_never_returns_plain_values` — GET déploiement → aucune valeur sensible en clair dans le payload JSON
- `backend/tests/unit/test_services/test_stack_service.py`
  - `test_render_receives_decrypted_values` — le rendu reçoit les valeurs déchiffrées en mémoire (mock du renderer)

### Commandes de validation
```bash
poetry run pytest backend/tests/unit/test_models/test_deployment.py backend/tests/unit/test_schemas/test_deployment.py backend/tests/unit/test_api/test_deployments.py -v
make backend-test-unit
```

## État d'avancement technique
- [x] Tâche 1 : Chiffrer les valeurs sensibles dans les snapshots de déploiement
- [x] Tâche 2 : Masquer les valeurs dans les réponses API
- [x] Tâche 3 : Non-régression du pipeline de rendu/déploiement

## Notes d'implémentation

**Date :** 2026-09-06

### Fichiers modifiés/créés

**Code (5 fichiers) :**
- `backend/app/models/deployment.py` — Ajout : helpers [`is_sensitive_variable()`](../../backend/app/models/deployment.py), [`encrypt_variables_for_storage()`](../../backend/app/models/deployment.py), [`decrypt_variables_from_storage()`](../../backend/app/models/deployment.py), [`_has_unencrypted_sensitive_values()`](../../backend/app/models/deployment.py) + propriétés [`decrypted_variables`](../../backend/app/models/deployment.py) / [`decrypted_config`](../../backend/app/models/deployment.py) (double lecture + ré-encryptage au premier accès, pattern STORY-103.2)
- `backend/app/services/deployment_service.py` — `create()` chiffre `config`/`variables` avant persistance ; `retry_deployment()` repasse par `decrypted_variables`
- `backend/app/services/deployment_orchestrator.py` — `recover_stuck_deployments()` (recovery) relit via `decrypted_variables`
- `backend/app/schemas/deployment.py` — `_mask_sensitive_values()` + `field_validator` sur `config`/`variables` de `DeploymentResponse` → masquage `***`
- `backend/app/tasks/background_tasks.py` — docstring sécurité `deploy_stack_async` (contrat: valeurs déchiffrées en mémoire uniquement)

**Tests (5 fichiers) :**
- `backend/tests/unit/test_models/test_deployment.py` — **créé** (16 tests) : chiffrement au repos (préfixe `gAAAA`), double lecture/migration, idempotence, valeurs non-chaînes, corrompu → `SecretDecryptionError`
- `backend/tests/unit/test_schemas/test_deployment.py` — **créé** (7 tests) : masquage `***` (nom sensible OU token Fernet), non-sensibles lisibles, payload JSON sans clair
- `backend/tests/unit/test_api/test_deployments.py` — **créé** (3 tests) : GET détail + liste sans clair ni `gAAAA`, snapshot legacy masqué, oracle chiffré-at-rest
- `backend/tests/unit/test_services/test_stack_service.py` — **créé** (3 tests) : rendu Jinja reçoit valeurs déchiffrées (`test_render_receives_decrypted_values`), colonnes chiffrées après create, retry déchiffre
- `backend/tests/unit/test_deployment_variables_rendering.py` — **adapté** (3 tests) : invariants de rendu vérifiés via `decrypted_variables` au lieu de la colonne brute

### Décisions techniques

1. **Stratégie « clé conservée, valeur chiffrée »** (recommandée par l'analyse) : les noms de variables restent lisibles pour l'UI, seules les valeurs sensibles sont des tokens Fernet. Pas de migration de schéma.
2. **Discriminant de sensibilité par nom** : regex `(?i)(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE|CREDENTIAL|AUTH_KEY|ACCESS_KEY)` — alignée sur `_SECRET_PATTERNS` de l'adoption (réutilisation, pas de réimplémentation).
3. **Masquage API à double détecteur** : nom sensible OU ciphertext `gAAAA` — un token chiffré dont la clé serait neutre reste masqué (défense en profondeur).
4. **`configuration` de l'orchestrateur reste en clair en mémoire** (premier lancement via `create()`) : référence mémoire consommée par le rendu, jamais écrite sur disque ; les relances (retry/recovery) relisent la colonne chiffrée via `decrypted_variables`.
5. **Choix documenté (exigence Tâche 3)** : les fichiers compose générés sur la cible (`/tmp/windflow-deployments/{id}/docker-compose.yml` via `generate_compose_file`) contiennent les valeurs rendues — nécessaire à l'exécution des conteneurs ; les logs et la base ne contiennent jamais de clair (aucun log de `configuration` ajouté).
6. **Tâche 3 — pas de modification de `stack_service.py`/`docker_compose_service.py`** : ces services ne consomment jamais `Deployment` (rendu alimenté par `configuration` paramètre) — conforme à la formulation conditionnelle (« si le rendu lit… »).

### Divergences par rapport à l'analyse

- **Tâche 3** : `stack_service.py` et `docker_compose_service.py` inchangés (voir décision 6) ; en revanche `deployment_orchestrator.py` (recovery) et `deployment_service.py` (retry) ont été routés via `decrypted_variables` — points de relecture DB non listés explicitement dans les fichiers de la tâche mais nécessaires au même objectif (non-régression du pipeline).
- **Bug découvert pendant les tests** : la première implémentation de la migration comparait les ciphertexts (Fernet = token différent à chaque chiffrement) → re-chiffrement inutile à chaque lecture. Corrigé par `_has_unencrypted_sensitive_values()` (détection legacy sur le contenu en clair). Le test `test_encrypted_snapshot_not_re_encrypted` verrouille ce comportement.

### Difficultés rencontrées

- 3 tests existants de `test_deployment_variables_rendering.py` (hors baseline initiale) lisaient la colonne brute `deployment.variables` — adaptés au nouveau contrat via `decrypted_variables` (invariants identiques).
- Environnement de test : `disable_auth=True` en dev → les tests API doivent utiliser `admin_client` (superadmin requis par `get_current_active_user`).
- **mypy/bandit indisponibles** dans le venv Python 3.14 (entry points cassés) — remplacés par `ruff check` + `ruff format` (tous deux ✅).

### Tests ajoutés & validation

- **29 nouveaux tests** (4 fichiers) + 3 adaptés — tous passants ✅
- Couverture : `models/deployment.py` **100 %**, `schemas/deployment.py` **100 %** (seuil 80 % largement dépassé)
- Lint : `ruff check` ✅, `ruff format` ✅ (10 fichiers)
- OpenAPI : `test_openapi.py` 11/11 ✅ (schémas toujours valides)
- **Non-régression** : modules stacks/promote/deployments — 49 échecs avant / 49 après, **listes strictement identiques** (baseline préexistante Python 3.14, aucune dérive)

### Points d'attention pour STORY-103.4

- Vérification SQL : `SELECT variables FROM deployments` → aucune valeur sensible en clair (tokens `gAAAA` sur noms sensibles), idem `config`.
- Oracle : `SecretManager.is_encrypted(value)` sur les valeurs sensibles des snapshots ; `deployment.decrypted_variables` pour relecture métier.
- Masquage API : `GET /api/v1/deployments` et `/{id}` → `***` sur valeurs sensibles, jamais `gAAAA` dans les payloads.
- Le recovery de l'orchestrateur (`recover_stuck_deployments`) déchiffre à la volée — si la clé maîtresse change, les anciens snapshots lèvent `SecretDecryptionError` (comportement voulu, pas de fallback silencieux).
