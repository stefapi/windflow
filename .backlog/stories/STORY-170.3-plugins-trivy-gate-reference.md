# STORY-170.3 : Plugins — plugin Trivy de référence : gate `never` réelle + bloquant simulé, matrice de critères et conventions (P2-3, partie extension — STORY-170 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-170 ([ABANDONED — découpe proactive post-analyse le 2026-10-30](STORY-170-plugins-routes-dynamiques-gates.md))
**Item plan :** P2-3 partie extension (axes B5, C6) — volet **plugin Trivy de référence** de la spec 11 — ampleur **S**

> **Périmètre (découpe)** : cette sous-story reprend le **volet C (plugin Trivy de référence)** de STORY-170 — plugin démonstrateur `demo_trivy_gate.py` dans [`backend/app/plugins/examples/`](../../backend/app/plugins/examples/) (pattern `demo_logger_hooks.py` de STORY-163), gate `pre_deploy` mode `never` **réel** + mode bloquant **simulé** documenté, matrice de critères spec 11 exposée dans la config du manifest, conventions codées en constantes + docstrings (image scanner **épinglée par version** jamais `:latest`, volume cache `windflow-plugin-trivy-cache` protégé du prune, flux tag temporaire `<tag>-windflow-pending` simplifié). Couvre l'**AC 4 de la mère**. **Dépend de [STORY-170.2](STORY-170.2-plugins-gates-pre-deploy-pipeline.md)** (SDK gates `DeployContext`/`GateDecision` + `PluginGateService`). Indépendante de [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md) (routes dynamiques).

## Description

En tant que développeur de plugins WindFlow, je veux un **plugin de référence** implémentant la gate pre-deploy Trivy décrite spec 11 (§ Plugin Trivy) — fonctionnant au moins en mode `never` (jamais bloquant) et en mode bloquant simulé, avec la matrice de critères de blocage exposée dans sa config et les conventions de sécurité du scanner (tag temporaire, image épinglée, volume cache protégé) posées comme référence — afin de disposer d'un exemple canonique de gate pour les plugins du catalogue.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §14.1) : aucune gate n'existe à ce jour — le plugin Trivy de référence spec 11 n'a pas d'implémentation, même simplifiée, dans [`backend/app/plugins/examples/`](../../backend/app/plugins/examples/).

## Contexte technique

> Extrait de l'analyse STORY-170 (2026-10-30, `analyse-story`) — périmètre **C. Plugin Trivy de référence**, redistribué par `split-story`. La tâche détaillée **a déjà été rédigée par l'analyse de la mère** et est reprise ci-dessous (numérotation d'origine indiquée) — exécution directe par `treat-story`, pas de nouvelle phase d'analyse.

### Éléments existants à réutiliser / contraintes

- **Pattern démonstrateur** : [`backend/app/plugins/examples/demo_logger_hooks.py`](../../backend/app/plugins/examples/demo_logger_hooks.py) (STORY-163) — module exemple auto-documenté, hors montage par défaut ;
- **SDK gates (posé par STORY-170.2)** : `DeployContext`/`GateDecision` ([`backend/app/plugins/gates.py`](../../backend/app/plugins/gates.py) — à créer par 170.2 tâche 3) ; enregistrement/exécution via `PluginGateService` (170.2 tâche 5) — la gate Trivy s'écrit **contre ce contrat** et s'y teste ;
- **Matrice de critères spec 11** : `never` (défaut) / `any` / `critical_high` / `critical` / `more_than_current` — exposée dans la config du manifest (`block_criteria`) ;
- **Conventions sécurité scanner** : image du scanner **épinglée par version** (jamais `:latest`), cache dans un volume `windflow-plugin-trivy-*` protégé du prune (pattern `windflow-plugin-*`, STORY-173 / spec 09 § prune), flux protégé par **tag temporaire** `<tag>-windflow-pending` (image candidate tirée puis scannée, image refusée supprimée, tag original restauré à l'approbation) ;
- **Distinction hooks vs gates** : gate = décision bloquante synchrone (`pre_deploy(ctx) -> GateDecision`) ≠ `@on_event` asynchrone non bloquant.

### Divergence héritée de la mère

- **n°5 — Trivy simplifié** : scan réel hors périmètre (AC 4 de la mère) — `never` réel, bloquant simulé ; flux tag temporaire `<tag>-windflow-pending`, image épinglée et volume `windflow-plugin-trivy-cache` **documentés comme conventions** (constants + docstrings), non exécutés à ce stade. Le scan complet (report vulnérabilités) relève du plugin catalogue.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend l'AC 4 de la mère)* : Le **plugin Trivy** (gate de référence) fonctionne au moins en mode `never` (jamais bloquant) et en mode bloquant simulé — la matrice de critères est exposée dans sa config ; le flux tag temporaire et l'image épinglée sont implémentés ou documentés comme simplifiés à ce stade (écart noté pour le plugin catalogue complet) ; le cache scanner vit dans un volume protégé du prune (convention `windflow-plugin-*`).
- [x] AC 2 *(volet qualité de l'AC 5 de la mère)* : Couverture ≥ 80 % du module démonstrateur ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Plugin Trivy (exemple, matrice de critères, flux tag temporaire, image épinglée), § Hooks de déploiement (gates — contrat posé par STORY-170.2) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Prune des images/volumes (liste protégée `windflow-plugin-*`) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité des plugins (isolation, permissions), § Plugin Trivy (blocage optionnel via gate) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-3, §2.B B5, §2.C C6 ;
- [`backend_status.md`](../../docs/backend_status.md) — §5, §14.1.

## Dépendances

- **Dépend de [STORY-170.2](STORY-170.2-plugins-gates-pre-deploy-pipeline.md)** (✔ requis) : SDK gates `plugins/gates.py` (`DeployContext`/`GateDecision`, tâche 3 de 170.2) et `PluginGateService` (tâche 5 de 170.2) — la gate Trivy s'écrit contre ce contrat et s'enregistre via ce service ; les tests l'exercent via `run_gates`.
- **STORY-163** (✔ DONE) : pattern `demo_logger_hooks.py` pour le module démonstrateur dans `plugins/examples/`.
- **STORY-173** (prune épargne `windflow-plugin-*`) : convention documentaire uniquement — aucune interaction de code ici.
- **Indépendante de [STORY-170.1](STORY-170.1-plugins-routes-api-dynamiques.md)** (routes dynamiques).
- **Aucune migration DB** ; **aucun service externe nouveau** : Trivy réellement exécuté = hors périmètre (mode bloquant simulé — divergence n°5 de la mère).

## État d'avancement technique

> Tâche **reprise de l'analyse de la mère** (T10 de STORY-170, renumérotée 1 ci-dessous) — à cocher pendant `treat-story`.

- [x] Tâche 1 : Plugin Trivy de référence — `plugins/examples/demo_trivy_gate.py` (gate never + simulé, matrice, conventions) + tests

## Tâches d'implémentation détaillées

> Reprise de l'analyse STORY-170 (2026-10-30). Exigences sécurité ([`40-security.md`](../../.roo/rules/40-security.md)) : aucune donnée sensible dans les raisons de refus ni les logs ; conventions sécurité scanner codées en constantes.

### Tâche 1 : Plugin Trivy de référence *(originale T10 de STORY-170)*
**Objectif :** Extension plugin démonstrateur dans `backend/app/plugins/examples/` (pattern `demo_logger_hooks.py`) : module `demo_trivy_gate.py` exposant `pre_deploy(ctx) -> GateDecision` — lit `block_criteria` dans la config reçue : `never` (défaut) → `approve()` réel ; tout autre critère → **deny simulé** documenté (AC 1 : `critical_high` simulé par exemple, raison descriptive `"<image> : [SIMULÉ] 2 CRITICAL, 5 HIGH (critère critical_high)"`). Le **manifest fixture** (dans les tests + docstring) expose la matrice complète spec 11 : config `block_criteria` enum `never|any|critical_high|critical|more_than_current`. Conventions codées en constantes + docstrings : `TRIVY_IMAGE = "aquasec/trivy:<version-épinglée>"` (jamais `:latest`), volume cache `windflow-plugin-trivy-cache` (protégé du prune via pattern `windflow-plugin-*`, STORY-173), flux tag temporaire `<tag>-windflow-pending` documenté simplifié (divergence n°5).
**Fichiers :**
- `backend/app/plugins/examples/demo_trivy_gate.py` — Créer — gate de référence + constantes conventions + manifest d'exemple en docstring.
- `backend/tests/unit/test_plugins/test_demo_trivy_gate.py` — Créer — tests (voir § Tests).
**Dépend de :** STORY-170.2 (tâches 3 et 5 — SDK gates + `PluginGateService`)

## Tests à écrire

### Backend

- `backend/tests/unit/test_plugins/test_demo_trivy_gate.py` — Trivy AC 1 : `never` → approve quelle que soit l'image ; `critical_high` simulé → deny avec raison contenant `[SIMULÉ]` et le nom d'image ; critère inconnu → comportement `never` (fail-safe) ; constantes conventions (image épinglée sans `:latest`, volume `windflow-plugin-trivy-cache`).

### Frontend

- Aucun — périmètre backend uniquement (plugin démonstrateur, hors montage par défaut).

### Commandes de validation
```bash
# Tests ciblés (module touché)
poetry run pytest backend/tests/unit/test_plugins/test_demo_trivy_gate.py -v

# Non-régression exemples plugins existants
poetry run pytest backend/tests/unit/test_plugins/ -v

# Quality gates (AC 2)
make backend-test-unit
make lint
make backend-typecheck
poetry run pytest backend/tests/unit/test_plugins/test_demo_trivy_gate.py --cov=backend/app/plugins/examples/demo_trivy_gate.py --cov-fail-under=80
```

## Notes d'implémentation (2026-10-30, `treat-story`)

### Fichiers créés

- [`backend/app/plugins/examples/demo_trivy_gate.py`](../../backend/app/plugins/examples/demo_trivy_gate.py) — gate de référence Trivy : `pre_deploy(ctx) -> GateDecision` contre le SDK STORY-170.2 (`..gates import DeployContext, GateDecision`), matrice complète spec 11 codée en `BLOCK_CRITERIA` (`never|any|critical_high|critical|more_than_current`, défaut `never`), constantes de conventions `TRIVY_IMAGE` (`aquasec/trivy:0.58.1`, épinglée — jamais `:latest`), `CACHE_VOLUME` (`windflow-plugin-trivy-cache`, pattern protégé du prune STORY-173), `PENDING_TAG_SUFFIX` (`-windflow-pending`), `SIMULATED_FINDINGS` (compteurs factices), manifest d'exemple complet en docstring (config select `block_criteria` + `deploy_hooks.pre_deploy`) ;
- [`backend/tests/unit/test_plugins/test_demo_trivy_gate.py`](../../backend/tests/unit/test_plugins/test_demo_trivy_gate.py) — 23 tests : mode `never` réel (4), bloquant simulé par critère (7, raison `[SIMULÉ]` + image + critère + compteurs/totaux), fail-safe critère inconnu (3, dont WARNING + normalisation casse/espaces), intégration `PluginGateService.run_gates` (2, approve + `GATE_DENIED`), conventions constantes (7).

### Décisions techniques

- **Lecture du critère** : via `os.environ["PLUGIN_CONFIG_BLOCK_CRITERIA"]` — convention `PLUGIN_CONFIG_*` déjà posée par le core (hooks lifecycle STORY-169.3, injection compose 169.4) ; le handler ne reçoit que `DeployContext` (sans secret, rules 40), la config arrive par l'environnement du process ;
- **Fail-safe `never`** : critère absent/inconnu → `never` (approve) + WARNING — on n'invente jamais un blocage (cohérent avec « le core ne bloque jamais par défaut ») ;
- **Refus simulé sur la première image** (`ctx.images[0]`) : court-circuit identique au scan réel spec 11 ; critère bloquant + aucune image → approve (rien à scanner) ;
- **Compteurs simulés par critère** : `critical` → « 2 CRITICAL », `critical_high` → « 2 CRITICAL, 5 HIGH », `any` → 4 sévérités, `more_than_current` → « total 49 > 47 (image courante) » — la description respecte sémantiquement le critère ;
- **Docstring manifest** alignée sur le schéma réel `PluginManifest` (`config:` liste directe de `PluginConfigField`, pas de sous-clé `fields`) ;
- **Version Trivy épinglée** `0.58.1` : valeur de référence documentée — la mise à jour est un acte délibéré (docstring).

### Divergences / précisions par rapport à l'analyse

- Aucune divergence fonctionnelle : périmètre respecté (scan réel hors périmètre — divergence n°5 héritée, documentée dans le module). Détails documentaires :
  - la commande de couverture de la story (`--cov=…demo_trivy_gate.py`) entre en conflit avec les `addopts` globaux (`--cov=app`) du `pyproject.toml` — la mesure s'obtient avec le nom de module importable : `--cov=app.plugins.examples.demo_trivy_gate` → **100 %** (40 stmts, 0 missed), seuil 80 % atteint ;
  - `make backend-typecheck` échoue sur **29 erreurs mypy préexistantes** (13 fichiers hors périmètre : `plugin_lifecycle_service` ×9, `demo_logger_hooks` ×4, `config.py` no-redef, etc.) — **0 erreur sur les fichiers de cette story** (vérifié mypy ciblé).

### Difficultés rencontrées

- Instabilité de l'outil d'édition (apply_diff/write_to_file « another editor opened in the meantime », kanban « Assertion Failed » — bug connu) : contourné par scripts Python chirurgicaux (regex + réécriture UTF-8), tel que prévu par les instructions de la story pour kanban ;
- bandit sur le fichier de **tests** ne rapporte que du B101 `assert_used` (bruit standard, niveau Low, Makefile cible `bandit -r backend -ll` → seuil Medium+) : module de production clean.

### Résultats des tests et quality gates

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_plugins/test_demo_trivy_gate.py -v` | **23 passed** |
| `--cov=app.plugins.examples.demo_trivy_gate --cov-fail-under=80` | **100 %** (40 stmts, 0 miss) — AC 2 |
| `pytest test_plugins/ + test_plugin_gate_service + test_deploy_stack_gates + test_plugin_api_router_service + test_plugin_dynamic_routes` | **127 passed** (non-régression 170.1/170.2) |
| `make backend-test-unit` | **2987 passed, 0 failed** (2964 avant + 23 nouveaux) |
| isort/black/flake8 (2 fichiers créés) | **0 erreur** |
| mypy ciblé `demo_trivy_gate.py` | **0 erreur** (29 préexistantes ailleurs, inchangées) |
| bandit module production | **0 issue** (B101 Low sur tests uniquement, sous seuil Makefile `-ll`) |

Commandes non lancées : `make lint` complet et `make frontend-*` (aucun fichier frontend/CLI touché — périmètre strictement backend plugin exemples) ; `make ci-build-docker` (hors story).
