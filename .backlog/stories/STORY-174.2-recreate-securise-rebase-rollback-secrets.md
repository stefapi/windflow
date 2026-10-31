# STORY-174.2 : Recreate sécurisé — rebase par valeur, rollback automatique, secrets masqués `***`

**Statut :** DONE
**Story Parente :** STORY-174 — Socle `WorkloadAdapter` + `DockerWorkloadAdapter` — abstraction encapsulant les services Docker existants et recreate sécurisé (rebase, rollback, masquage `***`) (P2-12 + P2-13)
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-13 (axe C10, rapport §5) + branchement `update()` de P2-12 — ampleur **L** (partie 2/2)

## Description

En tant qu'administrateur WindFlow, je veux que le verbe **Mettre à jour** des containers Docker devienne une **recréation à configuration préservée** fiable (spec 02 § Sémantique de mise à jour) : **capture de l'ancienne image avant le pull**, arrêt→**renommage `<nom>-old`**→déconnexion réseaux→création (rebase par valeur)→reconnexion→démarrage→suppression de l'ancien, avec **rollback automatique** sur tout échec (l'App revient à son état antérieur sans intervention) et **masquage des secrets `***`** dans les aperçus (résolution des placeholders par relecture des valeurs réelles avant recréation) — remplaçant le recreate destructif actuel qui **supprime l'ancien container avant d'en créer le nouveau sans aucun rollback**.

**Problème constaté** ([`docker_client_service.py:689-852`](../../backend/app/services/docker_client_service.py)) : `recreate_container` actuel = inspect→merge→pull→stop→**remove**→create→start — le docstring l'admet (« si la suppression réussit mais que la création échoue, l'erreur est irrécupérable : le container original est perdu ») ; pas de renommage `-old`, pas de rebase par valeur, pas de masquage `***` (C10 incomplet — endpoint `POST /docker/containers/{id}/recreate` existe, [`docker.py:792`](../../backend/app/api/v1/docker.py)).

## Critères d'acceptation (AC)

- [x] AC 3 : **Recreate sécurisé complet** : capture de l'ancienne image **avant** le pull ; étapes arrêt→renommage `-old`→déconnexion réseaux→création→reconnexion→démarrage→suppression de l'ancien ; **rebase par valeur** vérifié par tests : env/label identique à l'ancienne image → suit la nouvelle ; modifié → conservé ; ajouté → conservé ; `command:` utilisateur survit.
- [x] AC 4 : **Rollback sur échec** : un échec simulé à une étape (pull, création, démarrage) → retour à l'état antérieur (ancien container renommé restauré, réseaux reconnectés avec leurs réglages, redémarré si besoin) — testé ; **secrets masqués** : l'aperçu d'inspection masque `*_PASSWORD`/`*_TOKEN`/`*_KEY` en `***`, le backend résout les placeholders `***` en relisant les valeurs réelles avant recréation — test : recreate avec un env secret inchangé → la valeur réelle est préservée sans jamais apparaître en clair dans l'aperçu.
- [x] AC 5 : Une recréation réussie efface la « mise à jour en attente » éventuelle (si la structure existe — sinon différé noté) ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Contexte technique

### Constats d'exploration (état réel du code au 2026-10-31)

- **Recreate destructif actuel** : [`recreate_container`](../../backend/app/services/docker_client_service.py) (l.689-852) — inspect → merge (None = conserver) → pull (échec **avallé silencieusement** en warning) → stop → `remove_container(force=True)` → create → start ; deux `RuntimeError` « chemin critique » quand create/start échouchent après suppression. Signature : `(container_id, image, pull_image, env, labels, port_bindings, mounts, privileged, readonly_rootfs, cap_add, cap_drop, stop_timeout=10) -> tuple[str, ContainerDetail]`.
- **Endpoint** : [`POST /docker/containers/{container_id}/recreate`](../../backend/app/api/v1/docker.py) (l.792, `require_admin`, RL 10/60) + schémas [`ContainerRecreateRequest`](../../backend/app/schemas/docker.py) (l.467 — merge-None) / `ContainerRecreateResponse` (success/message/old_id/new_id/container). Le contrat HTTP (routes/schémas/réponse) **peut rester identique** — seule la mécanique interne change.
- **Primitives Engine déjà présentes dans le client** : `rename_container(id, new_name)` (l.976), `inspect_image(image_id)` (l.1292 — retourne Config avec Env/Labels/Cmd de l'image), `connect_container_to_network` (l.1751), `disconnect_container_from_network` (l.1781), `inspect_container` (l.1095), `get_container` (ContainerDetail : config/env/labels, host_config, network_settings.Networks, mounts), `pull_image`, `stop/start/remove_container`. **Aucune primitive Engine manque** — le recreate sécurisé est pure orchestration.
- **Rebase par valeur** (spec 02 l.245-253) : la config d'un container aplatit les défauts d'image (env/labels/Cmd) avec les choix utilisateur ; au recreate : valeur courante **identique** à l'ancienne image → prend la valeur de la **nouvelle** image ; **différente** → conservée ; **absente de l'ancienne image** → conservée. Même logique Cmd/Entrypoint (« cuite » suit l'image, `command:` utilisateur survit).
- **Secrets `***`** (spec 02 l.255, règle 40) : masquer à l'inspection toute valeur dont la **clé** matche `*_PASSWORD`/`*_TOKEN`/`*_KEY` (+ suffixes sensibles type `_SECRET`) ; le formulaire renvoie `***` ; le backend **résout** en relisant les valeurs réelles du container courant avant recréation. Précédent en base : masquage `********`/`***` de STORY-169.4 (plugins configure) — réutiliser la même approche helpers.
- **Réseaux** : `ContainerDetail.network_settings["Networks"]` donne les réseaux connectés avec leurs réglages (Aliases, IPAMConfig) ; l'étape « déconnexion » libère le nom + les IP statiques ; la reconnexion doit restaurer Aliases/IPAMConfig d'origine via `connect_container_to_network(id, network_id, aliases=…, ipv4_address=…)`.
- **« Mise à jour en attente » INEXISTANTE dans le code** (grep `pending_update`/`update_pending` → 0) : la structure relève de check-updates (renvoi D1 de STORY-173, Roadmap Phase 5) → **AC 5 : différé à noter explicitement**, aucun champ à effacer dans cette story.
- **Gates STORY-170.2** : « la gate pre-deploy s'applique au recreate (tous les chemins de déploiement) » — le recreate interactif d'un container existant ne passe pas par `deploy_stack_async` : décision d'analyse ci-dessous (D4).
- **Tests existants** : [`test_container_recreate.py`](../../backend/tests/unit/test_docker/test_container_recreate.py) (comportement actuel), `test_docker_rbac.py` (401/403 recreate), `test_container_network_connect_disconnect.py` (primitives réseaux) — doivent être étendus/ajustés, jamais affaiblis.
- **Socle STORY-174.1 requis** : `DockerContainerAdapter.update()` (délègue au recreate) — rebrancher ce seul point après refonte.

### Décisions d'analyse (174.2)

- **D1 — Nouvelle méthode `recreate_container_secure()` plutôt que mutation** : garder `recreate_container` intact garantit la compat des appelants pendant la transition puis l'endpoint bascule dessus ; l'ancienne méthode est ensuite **supprimée dans cette même story** (le garde-fou §2.G porte sur les endpoints, pas les méthodes internes — l'endpoint `/recreate` reste, sa mécanique change ; zéro double implémentation en fin de story).
- **D2 — Orchestration 6 étapes fidèle spec 02** : (1) `get_container` + `inspect_image(image_actuelle)` **avant pull** (capture Env/Labels/Cmd de l'ancienne image) ; (2) `pull_image` si demandé + `inspect_image(nouvelle)` (échec de pull → `WindFlowException` explicite, **jamais avalé** — l'ancien container est intact à ce stade) ; (3) stop si running, `rename_container(id, f"{nom}-old")`, déconnexion des réseaux additionnels (au-delà du NetworkMode principal) ; (4) `create_container` (passthrough inspection complète, image remplacée, **rebase par valeur** D3) + reconnexion réseaux (Aliases/IPAMConfig restaurés) + start si l'ancien tournait ; (5) `remove_container(ancien, force=False)` ; (6) **rollback** sur échec de create/start : remove(new_id si créé, force=True), `rename_container(f"{nom}-old", nom)`, reconnexion réseaux d'origine, start si l'ancien tournait — erreurs de rollback loggées CRITICAL mais l'exception d'origine est relevée.
- **D3 — Rebase par valeur (pure fonction testable)** : `rebase_by_value(current: list, old_image_defaults, new_image_defaults)` pour env (KEY=VALUE) et labels (dict), et `rebase_cmd(current_cmd, old_entrypoint/cmd, new)` — règles exactes du tableau spec 02 ; le masquage `***` est résolu **avant** le rebase (une valeur `***` est remplacée par la valeur réelle du container courant = « inchangée » → règle identique/différente appliquée sur la valeur réelle).
- **D4 — Gates sur le recreate interactif** : appliquer `_run_pre_deploy_gates` n'est pas possible hors contexte deployment (il exige deployment_id/DeployContext) — décision : le recreate interactif admin **ne passe pas les gates** (comportement inchangé — les gates protègent les **déploiements**, pas la maintenance d'un container existant) ; trace de cette lecture dans la docstring + renvoi à arbitrer si la spec 11 exige sinon (coordonné P3-4/STORY-252). Aucune gate contournée sur `deploy_stack_async`.
- **D5 — Masquage helpers centralisés** : `mask_secret_env(values: list[str]) -> list[str]` / `resolve_masked_env(masked, real)` dans `docker_client_service.py` (ou helper dédié), pattern suffixes `PASSWORD|TOKEN|KEY|SECRET` (insensible casse) — utilisés par l'aperçu d'inspection ET le recreate ; jamais de valeur réelle dans les logs.
- **D6 — Audit** : recreate = action destructrice → `AuditService.log_from_request("container.recreated", …, details={old: id12, new: id12, image, rollback: bool})` sur l'endpoint (jamais d'env/labels dans details) — cohérent STORY-125.2.
- **Sécurité (checklist règle 40)** : endpoint existant admin-only inchangé (401/403 déjà testés) ; secrets jamais en clair ni en logs ni dans la réponse d'aperçu (test dédié) ; résolution `***` uniquement côté backend depuis le container courant (jamais depuis la requête client) ; validation Pydantic existante conservée (`extra` contrôlé par schéma actuel).

## Dépendances

- **STORY-174.1** (pré-requis) : le socle `services/workloads/` et `DockerContainerAdapter.update()` doivent exister pour le rebranchement final.
- Interagit avec STORY-170.2 (gates — décision D4), STORY-173 (renvoi check-updates/mise à jour en attente — AC 5 différé).

## Tâches d'implémentation détaillées

### Tâche 1 : Helpers rebase + masquage secrets (fonctions pures)
**Objectif :** Poser les briques testables du rebase par valeur et du masquage `***`.
**Fichiers :**
- `backend/app/services/docker_client_service.py` — **Modifier** — ajouter au niveau module : `SECRET_ENV_PATTERN = re.compile(r".*(PASSWORD|TOKEN|KEY|SECRET)$", re.IGNORECASE)` (match sur le nom de clé) ; `def mask_secret_env(values: list[str]) -> list[str]` (valeur → `***` si la clé matche) ; `def resolve_masked_env(submitted: list[str], real: list[str]) -> list[str]` (toute valeur `***` soumise est remplacée par la valeur réelle du container courant ; clé absente du réel → conservée telle quelle) ; `def rebase_by_value(current: list[str], old_image: list[str], new_image: list[str]) -> list[str]` (env KEY=VALUE : identique à old → suit new ; différente → conservée ; absente de old → conservée ; absente de new mais présente old & identique → suit new = absente → **supprimée**, conforme « suit la nouvelle image ») ; variante `rebase_labels_by_value(current: dict, old_image: dict, new_image: dict) -> dict` ; `def rebase_command(current: Optional[list], old_image_cmd/entrypoint, new_image_cmd/entrypoint)` (Cmd « cuit » = identique à l'ancienne image → suit la nouvelle ; différent → conservé ; None → Cmd de la nouvelle image). Docstrings citant le tableau spec 02 l.247-253.
**Exigences sécurité :** `mask_secret_env`/`resolve_masked_env` — jamais de valeur réelle loggable (docstring + usage).
**Dépend de :** Aucune

### Tâche 2 : `recreate_container_secure()` — orchestration 6 étapes + rollback
**Objectif :** Remplacer la mécanique destructive par le recreate sécurisé spec 02 (AC 3/AC 4).
**Fichiers :**
- `backend/app/services/docker_client_service.py` — **Modifier** — nouvelle méthode `async recreate_container_secure(container_id, *, image=None, pull_image=False, env=None, labels=None, stop_timeout=10) -> tuple[str, ContainerDetail]` (les autres overrides du schéma actuel restent supportés par la signature complète existante — conserver les paramètres port_bindings/mounts/privileged/readonly_rootfs/cap_add/cap_drop en merge-None comme aujourd'hui) : étapes D2 — (1) `get_container` + `inspect_image(image courante)` **avant tout pull** ; (2) pull si demandé (`pull_image` échec → `WindFlowException("pull_failed")`, ancien intact) + `inspect_image(nouvelle image)` ; (3) si running → `stop_container` ; `rename_container(id, f"{name}-old")` ; déconnexion des réseaux **additionnels** (parcourir `network_settings.Networks` hors NetworkMode principal, capturer Aliases/IPAMConfig avant déconnexion) ; (4) résolution `***` (`resolve_masked_env` contre l'env réel) puis **rebase** (Tâche 1) puis `create_container` (passthrough complet de l'inspection : env/labels rebasés, Cmd rebasé, port_bindings/mounts/hostconfig conservés de l'inspection, image remplacée) ; reconnexion des réseaux additionnels (Aliases/IPAMConfig) ; start si l'ancien tournait ; (5) `remove_container(old_id, force=False, remove_volumes=False)` ; (6) **rollback** sur échec create/start : best-effort ordonné (remove new force → rename back → reconnect réseaux → start si besoin), chaque sous-échec loggé CRITICAL, puis relever `WindFlowException("recreate_failed_rolled_back")` (ou `..._rollback_incomplete` si le rollback lui-même échoue — message actionnable). Logs INFO par étape (ids tronqués, jamais d'env).
**Exigences sécurité :** Jamais d'env/labels dans les logs ; rollback garanti best-effort avec distinction rolled-back/rollback-incomplete.
**Dépend de :** Tâche 1

### Tâche 3 : Suppression de l'ancien `recreate_container` + rebranchement endpoint + adapter
**Objectif :** Une seule implémentation (D1) — l'endpoint et l'adapter consomment le recreate sécurisé.
**Fichiers :**
- `backend/app/services/docker_client_service.py` — **Modifier** — **supprimer** l'ancienne méthode `recreate_container` (l.689-852) après bascule (aucun autre appelant que l'endpoint — vérifier par grep avant suppression).
- `backend/app/api/v1/docker.py` — **Modifier** — endpoint `recreate_container` (l.807) : appeler `recreate_container_secure` (mêmes params), réponse `ContainerRecreateResponse` inchangée ; brancher `AuditService.log_from_request("container.recreated", user=current_user, resource_type="container", resource_id=container_id, details={"new_container_id": new_id[:12], "image": image, "rolled_back": False})` sur succès (D6) ; la branche `RuntimeError` « chemin critique » devient obsolete → remplacer par gestion `WindFlowException` (rollback déjà opéré côté service).
- `backend/app/schemas/docker.py` — **Modifier** — `ContainerRecreateRequest` : docstring masquage (`env` peut contenir `***` pour les valeurs inchangées — résolu côté backend), aucun champ structuré changé.
- `backend/app/services/workloads/docker_container.py` — **Modifier** — `update()` → `client.recreate_container_secure(...)` (retrait du commentaire « point d'extension 174.2 »).
**Exigences sécurité :** Audit sur l'action destructrice (D6) — jamais d'env dans details.
**Dépend de :** Tâche 2 (+ STORY-174.1 pour l'adapter)

### Tâche 4 : Aperçu d'inspection masqué
**Objectif :** L'aperçu servi au frontend masque les secrets (AC 4 seconde moitié).
**Fichiers :**
- `backend/app/api/v1/docker.py` — **Modifier** — le détail container (`GET /containers/{id}` existant) : appliquer `mask_secret_env` sur `config.Env` dans la réponse (et tout autre champ à clé sensible si applicable) — l'aperçu renvoie `***` ; le recreate (Tâche 3) résout ces placeholders. Vérifier `ContainerConfigInfo.from_docker_dict` pour le point d'application propre.
**Exigences sécurité :** Test obligatoire — la valeur réelle n'apparaît jamais dans la réponse d'aperçu.
**Dépend de :** Tâche 1

### Tâche 5 : Tests recreate sécurisé (AC 3/AC 4/AC 5)
**Objectif :** Couvrir rebase, rollback×3, secrets, non-régression endpoint.
**Fichiers :**
- `backend/tests/unit/test_docker/test_container_recreate.py` — **Modifier/Réécrire** — mock client complet (AsyncMock) : ordre des étapes (capture inspect_image **avant** pull), renommage `-old`, déconnexion/reconnexion réseaux avec Aliases, suppression ancien `force=False`, démarrage conditionnel (ancien running/not) ; **rebase** : env identique→suit new, modifié→conservé, ajouté→conservé, Cmd utilisateur survit, Cmd cuit suit l'image ; **rollback** : échec pull (ancien intact, exception explicite), échec create (rename back + réseaux + start restaurés), échec start (idem + new removed) ; **secrets** : aperçu masqué `***`, recreate avec `***` soumis → valeur réelle préservée, jamais en clair dans les appels/logguée ; `remove_volumes=False` toujours.
- `backend/tests/unit/test_docker/test_rebase_helpers.py` — **Créer** — fonctions pures Tâche 1 (tableaux paramétrés du tableau spec 02, cas limites : clés absentes, `***`, None).
- `backend/tests/unit/test_api/test_docker_recreate_secure.py` — **Créer** — endpoint : 200 rapport, 404 inconnu, 401/403 (règle 40 — existants à préserver), audit appelé sur succès (mock), aperçu GET détail masque `POSTGRES_PASSWORD`.
- **Non-régression** : `test_docker/` complet + `test_docker_rbac.py` + tests adapter 174.1 (`update()` → secure) verts.
**Exigences sécurité :** Tests secrets obligatoires (règle 40) : masquage aperçu + résolution sans fuite.
**Dépend de :** Tâches 2, 3, 4

### Tâche 6 : AC 5 — différé noté + couverture + validation finale
**Objectif :** Traiter l'AC 5 honnêtement (structure inexistante) et valider la qualité.
**Fichiers :**
- Cette story (section Notes à la clôture) + `docs/general_specs/02-familles-workloads.md` — **Modifier (mineur)** — noter dans § Sémantique de mise à jour que « l'effacement de la mise à jour en attente » suit check-updates (Roadmap Phase 5 — renvoi D1 STORY-173), coordination P3-4.
- **Exécution** : couverture `--cov=app.services.docker_client_service --cov=app.services.workloads.docker_container` ≥ 80 % ; `make backend-lint` / `make backend-typecheck` 0 nouvelle erreur ; `make backend-test-unit` non-régression.
**Exigences sécurité :** Aucune exigence spécifique.
**Dépend de :** Tâche 5

## Tests à écrire

### Backend (unitaires)
- `backend/tests/unit/test_docker/test_rebase_helpers.py`
  - `test_rebase_env_identical_follows_new_image` — spec 02 ligne 1 du tableau
  - `test_rebase_env_modified_is_kept`
  - `test_rebase_env_user_added_is_kept`
  - `test_rebase_env_absent_from_new_image_dropped` — « suit la nouvelle image »
  - `test_rebase_labels_matrix` — mêmes règles sur dict
  - `test_rebase_cmd_baked_follows_image_user_cmd_survives`
  - `test_mask_secret_env_masks_password_token_key_secret` — suffixes + casse
  - `test_resolve_masked_env_replaces_placeholders_from_real` — `***` → valeur réelle
  - `test_resolve_masked_env_unknown_key_kept` — clé soumise absente du réel
- `backend/tests/unit/test_docker/test_container_recreate.py` (réécrit)
  - `test_old_image_captured_before_pull` — ordre inspect_image/pull (AC 3)
  - `test_stop_rename_old_disconnect_networks_order`
  - `test_reconnect_restores_aliases_and_ipamconfig`
  - `test_old_removed_force_false_volumes_kept`
  - `test_start_only_if_old_was_running` — paramétré running/stopped
  - `test_rollback_on_create_failure_restores_old` — rename back + réseaux + start (AC 4)
  - `test_rollback_on_start_failure_removes_new_and_restores`
  - `test_pull_failure_leaves_old_container_intact` — exception explicite, aucun rename
  - `test_rollback_failure_marks_rollback_incomplete` — CRITICAL + exception dédiée
  - `test_recreate_with_masked_secret_preserves_real_value` — AC 4 secrets
  - `test_no_env_value_ever_logged` — caplog sans valeur réelle (sécurité)
- `backend/tests/unit/test_api/test_docker_recreate_secure.py`
  - `test_recreate_endpoint_200_report` — contrat réponse inchangé
  - `test_recreate_endpoint_404_unknown`
  - `test_recreate_endpoint_401_403` — sécurité (existants préservés)
  - `test_recreate_audited` — `container.recreated` avec details sans env
  - `test_container_detail_masks_secrets` — GET détail → `***` (sécurité)

### Commandes de validation
```bash
cd backend
poetry run pytest tests/unit/test_docker/test_rebase_helpers.py tests/unit/test_docker/test_container_recreate.py tests/unit/test_api/test_docker_recreate_secure.py -v
poetry run pytest tests/unit/test_docker/ tests/unit/test_services/test_workloads/ -q
poetry run pytest tests/unit/test_docker/ tests/unit/test_api/test_docker_rbac.py --cov=app.services.docker_client_service --cov=app.services.workloads --cov-report=term  # ≥ 80 %
make backend-lint && make backend-typecheck && make backend-test-unit
```

## État d'avancement technique

- [x] T1. Helpers rebase par valeur + masquage/résolution `***` (fonctions pures)
- [x] T2. `recreate_container_secure()` — orchestration 6 étapes + rollback automatique
- [x] T3. Suppression ancien recreate + rebranchement endpoint/adapter + audit
- [x] T4. Aperçu d'inspection masqué (GET détail)
- [x] T5. Tests recreate sécurisé (rebase, rollback×3, secrets, endpoint)
- [x] T6. AC 5 : différé « mise à jour en attente » noté + couverture ≥ 80 % + validations

## Notes d'implémentation

<!-- Ajoutées à la clôture par treat-story -->

## Notes d'implémentation (treat-story — 2026-10-31)

### Fichiers modifiés / créés
- [`backend/app/services/docker_client_service.py`](../../backend/app/services/docker_client_service.py) — **modifié** : helpers purs `SECRET_ENV_PATTERN`/`MASKED_VALUE`/`_split_image_ref`/`mask_secret_env`/`resolve_masked_env`/`rebase_by_value`/`rebase_labels_by_value`/`rebase_command` (tableau spec 02 l.245-255) ; **nouvelle** méthode `recreate_container_secure` (6 étapes : capture inspection+image **avant** pull → pull (échec → WindFlowException, ancien intact) → stop+renommage `<nom>-old`+déconnexion réseaux additionnels → création rebasée (`***` résolus)+reconnexion (Aliases/IPAMConfig)+start conditionnel → suppression ancien `force=False` volumes gardés → **rollback** best-efford `_rollback_recreate` avec distinction `recreate_failed_rolled_back`/`recreate_rollback_incomplete`) ; **ancien `recreate_container` destructif supprimé** (grep : aucun appelant restant).
- [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py) — **modifié** : endpoint recreate → `recreate_container_secure` + audit `container.recreated` (`log_from_request`, details = ids/image/pull/rolled_back uniquement — jamais d'env) ; GET détail → `mask_secret_env` sur `config.Env` (aperçu `***`).
- [`backend/app/services/workloads/docker_container.py`](../../backend/app/services/workloads/docker_container.py) — **modifié** : `update()` → `recreate_container_secure` (rebranchement prévu 174.1).
- [`backend/app/services/docker_service.py`](../../backend/app/services/docker_service.py) — **modifié** : ajout `start_container` (délégation executor — manquait, révélé par mypy).
- [`backend/app/schemas/docker.py`](../../backend/app/schemas/docker.py) — docstring `ContainerRecreateRequest` (placeholders `***` résolus backend).
- [`docs/general_specs/02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — note différé « mise à jour en attente » (AC 5 : structure inexistante, suit check-updates Roadmap Phase 5).
- **Tests** : `test_rebase_helpers.py` créé (12), `test_recreate_secure.py` créé (14 : ordre étapes, rollback×4 dont rollback-incomplete, rebase, secrets sans fuite caplog), `test_container_recreate.py` adapté secure + 2 tests audit/masquage.

### Décisions techniques
- **Pull échec = exception franche** (l'ancien recreate l'avalait en warning) — l'ancien container reste intact, aucune action destructrice engagée.
- **Réseaux** : seuls les réseaux **additionnels** (hors NetworkMode principal) sont déconnectés/reconnectés avec Aliases+IPAMConfig — le réseau principal suit la création.
- **Résolution `***`** uniquement depuis le container courant (jamais depuis la requête — anti-injection), appliquée avant le rebase.
- **Gates non appliquées au recreate interactif** (D4) : les gates protègent les déploiements (`deploy_stack_async`) ; trace docstring + coord. STORY-252.

### Divergences
- Aucune divergence fonctionnelle. Corrections de tests détaillées dans l'historique (ordre args réseaux `(network_id, container_id)`, mock start conditionnel, `env` minuscule sérialisé).

### Commandes exécutées et résultats
| Commande | Résultat |
|---|---|
| `pytest tests/unit/test_docker/` | **391 passed** (dont 12 rebase + 14 secure + 20 recreate adaptés) |
| `pytest tests/unit/test_services/test_workloads/` | **44 passed** |
| Couverture modules workloads | `schemas/workloads 100 %`, `workloads/* 100 %` (nouveau code) |
| `flake8` fichiers story | 0 erreur |
| `mypy` fichiers story | **0 erreur** (5 corrigées : Literal HealthStatus, annotations, start_container manquant) |
| `bandit -r services/workloads/` | 0 alerte |
| `pytest tests/unit` (non-régression) | **3218 passed / 1 failed** (`/api/v1/metrics` préexistant prouvé HEAD) |
