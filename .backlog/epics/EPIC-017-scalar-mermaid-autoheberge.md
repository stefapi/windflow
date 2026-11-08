# EPIC-017 : Scalar + Mermaid auto-hébergés pour la documentation API

**Statut :** TODO
**Priorité :** Haute

## Vision

Remplacer l'intégration Scalar actuelle — bundle chargé depuis le CDN jsdelivr via le paquet `scalar-fastapi` — par un **auto-hébergement complet** des assets de la documentation, avec rendu des **diagrammes Mermaid** dans les guides. Objectif : aucune requête vers une origine externe depuis la page de documentation (CSP `script-src 'self'` respectée, aucune fuite d'adresse IP des développeurs vers les CDN Scalar), et des guides d'utilisation riches incluant des diagrammes d'architecture et de séquence rendus graphiquement.

Inspiré de previimmo EPIC-002 (« Diagrammes Mermaid dans la documentation Scalar »), adapté à windflow : routes `/docs` (Scalar), `/swagger`, `/redoc` existantes, asset download au build Docker, scripts dédiés.

## Description

### Auto-hébergement des assets Scalar

- Script `backend/scripts/download_scalar_assets.py` : télécharge au build (étape builder du `Dockerfile.api`) et localement trois artefacts épinglés, chacun vérifié par empreinte SHA-256 :
  - `scalar.js` — bundle standalone `@scalar/api-reference` (les 14 URL `fonts.scalar.com/*.woff2` du bundle sont neutralisées en `local(system-ui)`) ;
  - `mermaid-plugin.js` — adaptateur du plugin officiel `@scalar/mermaid-plugin` (le paquet npm n'exporte que `mermaidPlugin` en nommé ; l'option standalone exige un export par défaut de fabrique de plugin) ;
  - `mermaid.mjs` + `chunks/` — moteur `mermaid` (build ESM minifié), chargé paresseusement par le plugin via `import('mermaid')` réécrit vers l'artefact same-origin.
- Dépôt sous `backend/app/core/openapi/scalar_assets/` (hors Git, `.gitignore`) ; module `app/core/openapi/scalar_assets.py` : `ASSET_SPECS` (versions épinglées), `scalar_page_html()`, `scalar_asset_response()`, `mermaid_chunk_response()` (validation stricte des noms : pas de traversée).
- Routes de service same-origin : `/docs` (page HTML), `/docs/assets/{filename}`, `/docs/assets/plugin-src/{module}` (liste fermée), `/docs/assets/chunks/{chunk}` — toutes `include_in_schema=False`.
- Retrait de la dépendance `scalar-fastapi` et de `get_scalar_api_reference` (CDN jsdelivr) de `pyproject.toml` après bascule.
- Configuration Scalar durcie, étalée à plat dans l'appel programmatique `Scalar.createApiReference` (précédent previimmo EPIC-004 : une clé `configuration` imbriquée est ignorée par le bundle) : `persistAuth: false`, `hideClientButton: true`, `showDeveloperTools: "never"`, `telemetry: false`, `agent.disabled: true`, `mcp.disabled: true`.
- Initialisation programmatique avec `plugins: [mermaidPlugin()]` (voie documentée ; l'option `pluginUrls` est chargée après le montage dans le bundle publié et n'alimente pas les hooks Markdown) ; résolution des serveurs relatifs en URL absolues sur l'origine de la page (le bundle compare `x-scalar-selected-server` tel quel).

### Guides Markdown avec diagrammes Mermaid

- Guides transverses dans `backend/app/core/openapi/guides/` (ordre des noms de fichiers), assemblés dans `info.description` par un `load_guides()` — Scalar en fait des pages de navigation.
- Au moins deux blocs ```mermaid complets publiés **verbatim** (séquence d'authentification JWT + refresh, flux de déploiement d'une stack) — le plugin rend les diagrammes à partir de ces clôtures.
- Les serveurs relatifs (`/` et le futur bac à sable) sont résolus côté module d'init, le contrat publié reste relatif (reproductible, indépendant de l'hôte).

## Liste des Stories liées

*À créer ultérieurement via `create-stories`*

- [ ] STORY-XXX : Auto-hébergement des assets Scalar (script de téléchargement épinglé + SHA-256, module `scalar_assets.py`, routes de service, retrait `scalar-fastapi`)
- [ ] STORY-XXX : Plugin Mermaid officiel + moteur `mermaid.mjs` adaptés same-origin (chunks, import map, init programmatique)
- [ ] STORY-XXX : Guides Markdown transverses assemblés dans `info.description` avec ≥ 2 diagrammes Mermaid verbatim + configuration durcie (télémétrie/agent/MCP off, `persistAuth: false`)
- [ ] STORY-XXX : Intégration Docker/Makefile/CI (download au build `Dockerfile.api`, cible Makefile dédiée, cache builder) + sonde navigateur de recette (0 requête externe, SVG Mermaid rendus)

## Notes de conception

- **Sécurité (règle 40)** : aucun CDN dans la page de documentation ; la CSP `script-src 'self'` du Security headers middleware doit rester sans violation bloquante pour le rendu. La favicon Scalar reste locale (l'URL `https://windflow.io/favicon.ico` actuelle dans `get_scalar_api_reference` disparaît avec le CDN).
- **Reproductibilité** : versions épinglées dans `ASSET_SPECS` (scalar 1.76.4 / mermaid-plugin 0.1.4 / mermaid 12.0.0 au moment de previimmo — re-vérifier les versions au moment de l'implémentation), empreintes SHA-256, échec du build sur artefact non conforme.
- **Précédents previimmo à respecter** : (1) `pluginUrls` inopérant dans le bundle 1.76.4 publié → init programmatique ; (2) configuration étalée à plat, pas imbriquée ; (3) serveurs relatifs réécrits par le bundle mais `x-scalar-selected-server` comparé tel quel → résolution côté module d'init ; (4) neutralisation des fontes `fonts.scalar.com`.
- **Tests** : intégration `test_technical_routes`-like — aucune URL externe dans le HTML de `/docs`, assets servis same-origin (bundle, init, plugin-src, mermaid, un chunk dynamiquement découvert), 404 sur nom inconnu/traversée (`..%2F`), skip si assets non téléchargés ; garde-fou : `/docs` reste absent d'`openapi.json`.
- **Environnement** : Scalar auto-hébergé sur `/docs` pour tous les environnements (remplace le CDN partout) ; la question dev-only vs tous envs est tranchée à l'analyse de story.
- **Plugin API router** : le service `PluginApiRouterService` invalide déjà le cache OpenAPI au montage/démontage — les routes d'assets ne figurent pas au contrat (`include_in_schema=False`), pas d'impact.

## Critères de succès (Definition of Done)

- [ ] La page `/docs` ne référence **aucune URL d'origine externe** (test automatisé + sonde navigateur : 0 requête externe)
- [ ] Les assets (bundle, plugin, moteur, chunks) sont servis same-origin par l'application, versions épinglées, SHA-256 vérifiés au build
- [ ] ≥ 2 diagrammes Mermaid des guides rendus graphiquement dans Scalar (sonde navigateur documentée : régions SVG, aucune violation CSP bloquante)
- [ ] Dépendance `scalar-fastapi` retirée ; `make lint` / `make backend-test-unit` / build Docker au vert
- [ ] Tests de non-régression : `/swagger` et `/redoc` inchangés, garde-fous OpenAPI existants verts

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Une fonctionnalité Scalar documentée est inopérante dans le bundle publié (précédents previimmo : `pluginUrls`, `x-badges`) | Moyen | Sonde empirique en premier geste de chaque story ; constat consigné avant tout contournement ; montée de version du bundle épinglé = choix local |
| Échec de téléchargement des assets au build (réseau, registry npm) | Moyen | Empreintes SHA-256 + message d'erreur explicite ; cible Makefile locale pour pré-remplir le cache builder ; skip de tests si assets absents |
| Croissance de `info.description` (quelques Ko de guides) | Faible | Négligeable, constaté chez previimmo ; le client généré n'est pas affecté par `info.description` |
| Violations CSP préexistantes (`style-src`) confondues avec des régressions | Faible | Sonde comparée à l'état d'avant (baseline), seules les violations **additionnelles** bloquantes sont bloquantes |

## Dépendances

- Aucune dépendance à une autre epic ; **prérequis direct** d'EPIC-018 (guides, mécanisme d'assemblage) et d'EPIC-019 (serveurs relatifs, `x-scalar-selected-server`, configuration durcie posés ici).
- Réutilise l'existant windflow : routes `/docs`//`/swagger`//`/redoc` ([`main.py`](../../backend/app/main.py)), Security headers middleware (CSP), `Dockerfile.api`.
