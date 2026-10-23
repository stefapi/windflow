# BUG-003 : POST /docker/containers — response_model inadéquat (500 sur création réussie)

**Statut :** DONE
**Gravité :** Majeur

## Reproduction

1. Se connecter avec un compte `admin` (l'endpoint exige `require_admin`).
2. `POST /api/v1/docker/containers` avec un body valide (`name`, `image`, …) et un Docker daemon joignable.
3. Le conteneur est bien créé côté Docker, puis le handler retourne un objet `ContainerDetailResponse`.
4. FastAPI valide la réponse de retour contre `response_model=ContainerResponse` ([`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py:264)) → `ResponseValidationError` → **HTTP 500**.

Le bug est aussi reproductible en test unitaire avec un mock Docker standard (c'est ainsi qu'il a été détecté — cf. notes d'implémentation STORY-162, divergence 5 : le test `container.created` appelle la fonction endpoint directement pour contourner ce 500).

## Comportement attendu

La création d'un conteneur réussie doit retourner **HTTP 201** avec le conteneur créé, sérialisé selon le `response_model` déclaré (contrat OpenAPI cohérent : soit `response_model=ContainerDetailResponse` pour refléter l'objet réellement construit par le handler [`create_container`](../../backend/app/api/v1/docker.py:276), soit un retour `ContainerResponse` — le choix doit aligner déclaration, retour effectif et documentation OpenAPI).

## Comportement actuel

- Déclaration : `response_model=ContainerResponse` ([`docker.py:264`](../../backend/app/api/v1/docker.py:264)).
- Retour effectif : `ContainerDetailResponse(...)` ([`docker.py:325`](../../backend/app/api/v1/docker.py:325)) — schéma détaillé (state, config, host_config, network_settings, mounts…) incompatible avec le modèle déclaré.
- Résultat : `ResponseValidationError` → 500 **systématique** sur le chemin nominal — l'endpoint n'a jamais pu renvoyer 201 avec un vrai Docker ; jamais couvert par les tests existants (`test_docker_rbac.py` ne teste que les 403 RBAC, avant toute E/S Docker).

## Contexte

- Détecté lors de STORY-162 (T6 — émetteur `container.created`) : le nouveau test d'émission ne pouvait pas passer par le chemin HTTP à cause de ce 500 latent ; signalé hors périmètre (divergence 5 des notes d'implémentation) et tracé ici.
- Impact : endpoint de gestion Docker inutilisable en pratique (création affichée en échec côté client alors que le conteneur existe) + contrat OpenAPI mensonger.

---

## Cause racine identifiée (analyse)

**Mismatch `response_model` ↔ valeur de retour : la validation de réponse FastAPI échoue systématiquement sur le chemin nominal.**

- Le décorateur déclare `response_model=ContainerResponse` ([`docker.py:264`](../../backend/app/api/v1/docker.py:264)) mais le handler [`create_container`](../../backend/app/api/v1/docker.py:276) retourne un [`ContainerDetailResponse(...)`](../../backend/app/api/v1/docker.py:325).
- Les deux schémas sont structurellement **incompatibles** :
  - [`ContainerResponse`](../../backend/app/schemas/docker.py:40) exige des champs absents du retour : `image_id`, `command` (str), `status`, et un `state: str` — or [`ContainerDetailResponse.state`](../../backend/app/schemas/docker.py:438) est un objet `ContainerStateInfo`.
  - Réciproquement, [`ContainerDetailResponse`](../../backend/app/schemas/docker.py:430) exige `path`, `args`, `config`, `host_config`, `network_settings` — absents de `ContainerResponse`.
- FastAPI re-sérialise la valeur de retour **via le `response_model` déclaré** : la validation Pydantic échoue (`ResponseValidationError`) → **HTTP 500**, alors que le conteneur a déjà été créé côté Docker (effet de bord irréversible perçu comme un échec par le client).

**Pourquoi le chemin nominal n'était couvert par aucun test** — 3 contournements distincts :

- [`test_container_create.py`](../../backend/tests/unit/test_docker/test_container_create.py:158) : le fixture `app` mute `route.response_model = None` avant montage du router (lignes 158-161).
- [`test_docker_rbac.py::test_admin_200_create_container`](../../backend/tests/unit/test_api/test_docker_rbac.py:334) : mini-app dédiée + `route.response_model = None` temporaire (lignes 375-402).
- [`test_canonical_event_emitters.py`](../../backend/tests/unit/test_services/test_canonical_event_emitters.py:140) (STORY-162, divergence 5) : appel direct de la fonction endpoint — bypass complet de la couche HTTP/FastAPI.

## Contexte technique (analyse)

- **Pattern de référence du module** : `GET /containers/{container_id}` déclare déjà `response_model=ContainerDetailResponse` ([`docker.py:204-205`](../../backend/app/api/v1/docker.py:204)) et retourne le même type — l'alignement du POST sur ce pattern est cohérent avec le module.
- **Client frontend** : `containersApi.create` est typé `ContainerDetail` ([`api.ts:301`](../../frontend/src/services/api.ts:301)) — le frontend a toujours attendu le schéma détaillé. L'option « retourner un `ContainerResponse` » serait breaking côté client et perdrait de l'information.
- **Enveloppe spec 09** : sur l'app réelle, le middleware [`api_response.py`](../../backend/app/middleware/api_response.py:1) enveloppe les réponses 2xx JSON `/api/v1/*` en `{data, message}` ; la validation `response_model` de FastAPI s'applique en amont sur l'objet — la correction est **orthogonale** à l'enveloppe. NB : les mini-apps des tests n'ont pas ce middleware (objet brut), l'app réelle du fixture [`client`](../../backend/tests/conftest.py:508) l'a.
- `ContainerResponse` reste légitimement utilisé par `GET /containers` (liste, [`docker.py:172`](../../backend/app/api/v1/docker.py:172)) — **l'import doit être conservé** après correction.
- **Checklist sécurité (`.roo/rules/40-security.md`)** :
  - Auth/RBAC : endpoint sous `require_admin` ([`docker.py:279`](../../backend/app/api/v1/docker.py:279)) — inchangé par le fix ; 401 (sans token) et 403 (viewer/operator) déjà couverts par les tests existants.
  - Validation d'entrée : `ContainerCreateRequest` (pattern nom Docker, champs typés) — inchangée.
  - Exposition de données : `ContainerDetailResponse.config.env` renvoie les variables d'environnement du conteneur créé — comportement identique à `GET /containers/{id}`, endpoint admin-only : **pas de régression** (point d'attention documenté, pas d'action requise).
  - Événement `container.created` : déjà sans env/labels (STORY-162, rules 40).

## Décision de résolution

**Option A retenue** : aligner la déclaration sur le retour effectif — `response_model=ContainerDetailResponse` (modification d'une ligne, handler inchangé).

Option B écartée (construire un `ContainerResponse` dans le handler) : mapping supplémentaire, perte d'information (`state` détaillé, `config`, `host_config`…), breaking pour le frontend typé `ContainerDetail`, incohérent avec `GET /containers/{id}`.

## Tâches d'implémentation détaillées

1. **Corriger le contrat de l'endpoint** — dans [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py:264) : remplacer `response_model=ContainerResponse` par `response_model=ContainerDetailResponse` dans le décorateur `@router.post("/containers", ...)`. L'import existe déjà (ligne 41) ; **ne pas retirer** l'import `ContainerResponse` (utilisé par `GET /containers`, ligne 172). Objectif : la validation FastAPI passe sur le chemin nominal → 201.
2. **Retirer le contournement dans [`backend/tests/unit/test_docker/test_container_create.py`](../../backend/tests/unit/test_docker/test_container_create.py:147)** : supprimer la mutation `route.response_model = None` du fixture `app` (lignes 158-161) et actualiser les docstrings (module lignes 7-11, fixture lignes 149-154) qui documentent le bug comme « pré-existant ». Objectif : les tests valident la réponse avec le `response_model` actif.
3. **Renforcer le test nominal + test de contrat** — dans le même fichier : `test_create_container_returns_201_authenticated` doit désormais (sans contournement) affirmer la forme `ContainerDetailResponse` : `data["state"]["status"] == "created"`, `data["config"]["image"] == "nginx:latest"`, présence de `host_config`, `network_settings`, `mounts`. Ajouter `test_create_container_route_declares_detail_response_model` (introspection : retrouver la route POST `/containers` dans `router.routes`, assert `route.response_model is ContainerDetailResponse`). Objectif : non-régression directe du bug.
4. **Simplifier le test RBAC admin** — [`backend/tests/unit/test_api/test_docker_rbac.py::test_admin_200_create_container`](../../backend/tests/unit/test_api/test_docker_rbac.py:334) : le contournement (mini-app + mutation `response_model`) n'est plus nécessaire ; réécrire avec le client standard authentifié admin + `patch("app.api.v1.docker.get_docker_client", ...)`, assert 201 et lecture via l'enveloppe spec 09 (`body["data"]["id"]`). Actualiser le docstring. Objectif : couverture RBAC sur le chemin HTTP réel sans hack.
5. **Actualiser le commentaire STORY-162** — [`backend/tests/unit/test_services/test_canonical_event_emitters.py`](../../backend/tests/unit/test_services/test_canonical_event_emitters.py:140) : conserver l'appel direct (périmètre = émission d'event), mais mettre à jour le commentaire/docstring justifiant le bypass par ce bug (divergence 5). Objectif : documentation exacte post-fix.
6. **CHANGELOG** — ajouter une entrée « Fixed » (BUG-003) dans [`CHANGELOG.md`](../../CHANGELOG.md) sous la version en cours. Objectif : traçabilité utilisateur du correctif.

## Tests à écrire

Backend — endpoint (`backend/tests/unit/test_docker/test_container_create.py`, httpx `AsyncClient` + mock Docker — pas de daemon en CI) :

| Cas | Test | Action |
|-----|------|--------|
| Nominal 201 + contrat détail | `test_create_container_returns_201_authenticated` | adapter (tâche 3) — assertions forme `ContainerDetailResponse` |
| Contrat déclaratif | `test_create_container_route_declares_detail_response_model` | **nouveau** (tâche 3) |
| 401 sans token | `test_create_container_returns_401_without_token` | existant — conserver |
| 422 image manquante | `test_create_container_returns_422_missing_image` | existant — conserver |
| 422 pattern nom invalide | `test_create_container_returns_422_invalid_name_pattern` | existant — conserver |
| 409 conflit de nom | `test_create_container_returns_409_name_conflict` | existant — conserver |
| 500 Docker indisponible | `test_create_container_docker_unavailable` | existant — conserver |

Backend — RBAC (`backend/tests/unit/test_api/test_docker_rbac.py`) :

- `test_admin_200_create_container` : réécrit sans contournement — 201 réel via client admin + enveloppe `{data}` (tâche 4).
- `test_viewer_403_create_container` / `test_operator_403_create_container` : existants — conserver (RBAC inchangé par le fix).

Non-régression à lancer (Makefile = source de vérité) :

```bash
poetry run pytest backend/tests/unit/test_docker/test_container_create.py backend/tests/unit/test_api/test_docker_rbac.py backend/tests/unit/test_services/test_canonical_event_emitters.py -v
make backend-lint && make backend-typecheck
```

Pas de nouveau test d'intégration requis : l'endpoint exige un Docker daemon (mock obligatoire en CI) et n'a pas de persistance DB propre (audit/event best-effort).

## État d'avancement technique

- [x] T1. `response_model` aligné sur `ContainerDetailResponse`
- [x] T2. Contournement retiré de `test_container_create.py`
- [x] T3. Test nominal renforcé + test de contrat introspectif
- [x] T4. `test_admin_200_create_container` réécrit sur chemin HTTP réel
- [x] T5. Commentaire STORY-162 actualisé
- [x] T6. CHANGELOG mis à jour
- [x] Tests ciblés verts + lint/typecheck

## Résolution

_(complété en phase treat-story — 2026-10-23)_

### Fichiers modifiés

- [`backend/app/api/v1/docker.py`](../../backend/app/api/v1/docker.py:264) — T1 : `response_model=ContainerResponse` → `ContainerDetailResponse` sur `@router.post("/containers")` (une ligne ; import déjà présent ligne 41, import `ContainerResponse` conservé pour GET liste ligne 172).
- [`backend/tests/unit/test_docker/test_container_create.py`](../../backend/tests/unit/test_docker/test_container_create.py) — T2/T3 : mutation `route.response_model = None` retirée du fixture `app` ; docstrings module + fixture actualisées ; `test_create_container_returns_201_authenticated` renforcé (assertions `state.status`, `config.image`, `host_config`, `network_settings`, `mounts`) ; nouveau `test_create_container_route_declares_detail_response_model` (introspection `router.routes`).
- [`backend/tests/unit/test_api/test_docker_rbac.py`](../../backend/tests/unit/test_api/test_docker_rbac.py:334) — T4 : `test_admin_200_create_container` réécrit sur le chemin HTTP réel (client standard du fixture `client` = app réelle avec enveloppe spec 09), mini-app + mutation `response_model` supprimées, lecture `body["data"]["id"]`.
- [`backend/tests/unit/test_services/test_canonical_event_emitters.py`](../../backend/tests/unit/test_services/test_canonical_event_emitters.py:140) — T5 : docstring du test STORY-162 actualisée (l'appel direct reste justifié par le périmètre « émission d'event », le commentaire ne référence plus le bug comme latent). isort appliqué au passage (écart préexistant).
- [`CHANGELOG.md`](../../CHANGELOG.md) — T6 : entrée « Fixed » BUG-003 sous `[Unreleased]`.

### Décisions techniques

- Option A appliquée à l'identique (alignement déclaration ↔ retour effectif), handler inchangé — conforme à la décision d'analyse.
- Aucune divergence par rapport aux tâches d'analyse.

### Validation

- Tests ciblés : `pytest test_container_create.py test_docker_rbac.py test_canonical_event_emitters.py` → **32 passed** (dont le nouveau test de contrat et le nominal renforcé).
- Non-régression élargie : `pytest backend/tests/unit/test_docker/ backend/tests/unit/test_api/ backend/tests/integration/test_openapi.py backend/tests/integration/test_api_contract.py` → **883 passed, 0 failed** (contrat OpenAPI inchangé sur les autres endpoints).
- Lint fichiers modifiés : `black --check` OK, `flake8` OK, `isort` OK (après fix mineur préexistant sur `test_canonical_event_emitters.py` ; les erreurs isort sur d'autres fichiers du backend sont préexistantes sur main, hors périmètre).
- `mypy app/` : **0 erreur dans `docker.py`** (21 erreurs préexistantes dans 9 autres fichiers non touchés — état main).

### Difficultés rencontrées

- Aucune bloquante. Point d'attention : la sortie isort globale du backend était déjà rouge sur main (divers fichiers) — non corrigé ici (hors périmètre BUG-003), seul le fichier touché a été remis en conformité.

## Clôture (finalise-story — 2026-10-23)

### Definition of Done (règle `.roo/rules/01-Project-management.md` §3.3)

- [x] Bug reproduit et compris
- [x] Cause racine identifiée
- [x] Correction implémentée
- [x] Tests de non-régression écrits
- [x] Section « Résolution » ajoutée

### Re-vérification finale (avant bascule DONE)

`poetry run pytest backend/tests/unit/test_docker/test_container_create.py backend/tests/unit/test_api/test_docker_rbac.py backend/tests/unit/test_services/test_canonical_event_emitters.py -v` → **32 passed, 0 failed** (exit 0) — statut basculé `REVIEW` → `DONE`, kanban mis à jour (colonne ✅ DONE).
