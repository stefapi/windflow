# EPIC-019 : Bac à sable de l'API (mock backend servi par le contrat OpenAPI)

**Statut :** TODO
**Priorité :** Moyenne

## Vision

Offrir un **backend de mock** intégré : une route technique `/api/v1/sandbox/{path}` répond à toute opération du contrat OpenAPI servi (`app.openapi()`) avec des réponses fictives tirées des exemples documentés — sans base de données, sans Redis, sans Docker, sans secret. Le « Try it » de Scalar cible ce bac à sable par défaut (`x-scalar-selected-server`), permettant d'explorer et d'appeler l'API entière depuis la documentation sans installer quoi que ce soit. Comportement repris du mock server de Scalar (`@scalar/mock-server`) tel qu'implémenté chez previimmo (EPIC-004), en module Python natif.

## Description

### Route technique

- `backend/app/core/openapi/sandbox.py` : `register_sandbox_route(app)` monte `/api/v1/sandbox/{path:path}` (GET/POST/PUT/PATCH/DELETE), `include_in_schema=False`.
- Résolution : mise en correspondance du chemin de requête contre les patterns du document servi (paramètres `{id}` etc.), puis de la méthode ; 405 si méthode absente du contrat, 404 si chemin inconnu.

### Choix de la réponse

- **Réponse par défaut** : premier statut 2xx documenté et son exemple (`example`, à défaut le premier de `examples`), sinon valeur dérivée du schéma (`_from_schema` : `format` → échantillons uuid/date/date-time/email/uri, `type` → échantillons de base, récursion bornée `_MAX_DEPTH = 8`, respect de `required`/`properties`/`items`).
- **En-tête `Prefer`** : `code=<statut>` et `example=<nom>` choisissent la réponse documentée ; un statut non documenté est refusé (422). L'enveloppe de réponse windflow (`data`/`message`/`pagination`, STORY-126) est respectée si l'exemple la porte.

### Authentification simulée & contrôle

- Une opération protégée (JWT/API Key au contrat) exige un `Authorization: Bearer` non vide ou un `X-API-Key` non vide — **valeur ignorée** ; sinon 401.
- Contrôle de la requête : paramètres requis présents, corps JSON requis présent et valide (pas de validation complète contre le schéma) ; corps limité à 1 Mio, refusé avant lecture (413).
- RBAC **non simulé** : le bac à sable ne fait aucune vérification de rôle (aucune DB) — un guide précise les limites.

### Hygiène & intégration

- En-têtes `Cache-Control: no-store` + `X-Sandbox: true` sur toute réponse ; erreurs via les handlers d'exceptions windflow (`WindFlowException`).
- Aucune écriture, aucun effet de bord : le mock ne touche ni DB, ni Redis, ni Docker, ni bus d'événements.
- Déclaration `servers` dans le document : serveur réel en `servers[0]` (URL de base des clients générés), bac à sable en second ; `x-scalar-selected-server` pointe le bac à sable (Try it).
- Montage dans [`main.py`](../../backend/app/main.py) après les routers ; le module d'init Scalar (EPIC-017) résout serveurs relatifs et serveur sélectionné sur l'origine de la page avant passage en `content`.
- Exclusion des chemins techniques du mock : `/health`, `/api/v1/metrics` (Prometheus, nu), `/docs`, `/swagger`, `/redoc`, WebSocket — le sandbox ne sert que les opérations JSON du contrat v1.
- Documentation : section dédiée dans le guide transverse (EPIC-018) « Bac à sable : explorer l'API sans installation » (limites : pas de persistance, pas de RBAC, réponses déterministes).

## Liste des Stories liées

*À créer ultérieurement via `create-stories`*

- [ ] STORY-XXX : Module `sandbox.py` — résolution de route, choix de réponse (exemples puis dérivation de schéma), en-tête `Prefer` (code/example), 413/422/404/405
- [ ] STORY-XXX : Authentification simulée (Bearer/X-API-Key non vides) + contrôle des paramètres/corps requis + montage `main.py` + serveurs `x-scalar-selected-server`
- [ ] STORY-XXX : Tests d'intégration (GET/POST nominaux, Prefer, 401/404/405/413/422, isolation DB/Redis/Docker, en-têtes X-Sandbox/no-store) + doc guide transverse

## Notes de conception

- **Sécurité (règle 40)** : le bac à sable ne doit jamais devenir un bypass d'authentification de l'API réelle — route distincte sous `/api/v1/sandbox/`, `include_in_schema=False`, aucun secret manipulé, aucune donnée réelle servie. À monter **dans tous les environnements** (utile en prod pour la doc publique) ou dev-only : arbitrage à l'analyse de story (previimmo l'a monté dans tous les envs).
- **Rate limiting (règle 40)** : la route reste derrière les middlewares globaux (rate limiting, correlation ID, timing) — pas d'exemption.
- **Enveloppe (STORY-126)** : les exemples documentés par EPIC-018 portent l'enveloppe ; la dérivation de schéma doit la reproduire (`data` au bon type) pour que les réponses mockées restent consommables par le frontend/CLI.
- **Plugins (routes dynamiques)** : le document servi inclut les routes dynamiques des plugins montés — le bac à sable les sert aussi ; l'invalidation de cache OpenAPI par `PluginApiRouterService` est déjà gérée.
- **Observabilité (règle 45)** : pas de métrique dédiée (route technique), mais les requêtes passent par le middleware timing (log des requêtes lentes) — comportement à constater en recette.
- **Tests** : pattern previimmo — client httpx `ASGITransport`, assertions sur statuts/en-têtes/exemples, mock des settings sans DB ; vérifier qu'aucune session DB n'est ouverte (garde d'isolation).

## Critères de succès (Definition of Done)

- [ ] Toute opération GET/POST/PUT/PATCH/DELETE du contrat v1 répond sur `/api/v1/sandbox/...` avec un statut 2xx documenté et son exemple
- [ ] `Prefer: code=404` / `example=<nom>` sélectionnent la réponse documentée ; statut non documenté → 422
- [ ] Opérations protégées → 401 sans jeton non vide ; corps > 1 Mio → 413 ; chemin inconnu → 404 ; méthode absente → 405
- [ ] Aucune dépendance à DB/Redis/Docker pour servir le mock (test d'isolation) ; en-têtes `X-Sandbox: true` + `Cache-Control: no-store` présents
- [ ] `servers` + `x-scalar-selected-server` publiés ; le « Try it » de Scalar cible le bac à sable
- [ ] Tests ≥ 80 % sur le module sandbox ; `make lint` + `make backend-test-unit` au vert

## Risques

| Risque | Impact | Mitigation |
|--------|--------|------------|
| Le mock devienne un vecteur de bypass d'authentification (confusion sandbox/réel) | Élevé | Préfixe distinct `/api/v1/sandbox/`, aucun secret, aucune donnée réelle, en-tête `X-Sandbox: true` permanent, revue sécurité (règle 02 §7) |
| Qualité des réponses dérivées si un schéma n'a pas d'exemple | Moyen | Dérivation `_from_schema` avec échantillons par format/type + récursion bornée ; EPIC-018 maximise les exemples en amont |
| Réponses non enveloppées cassant le frontend/CLI en mode exploration | Moyen | Dérivation respectant l'enveloppe STORY-126 ; test de forme sur une opération paginée |
| Charge abusive du sandbox en prod (énumération de contrat) | Faible | Rate limiting global inchangé ; corps limité 1 Mio ; `Cache-Control: no-store` ; arbitrage envs à l'analyse |
| Conflit de route avec un futur router réel `/sandbox` | Faible | Préfixe réservé sous `/api/v1/` ; garde-fou de non-collision au montage |

## Dépendances

- **Prérequis** : EPIC-017 (module d'init Scalar résolvant serveurs relatifs + `x-scalar-selected-server` ; configuration durcie) et EPIC-018 (exemples par réponse servant de source au mock ; guide transverse où documenter le bac à sable).
- Existant mobilisé : `app.openapi()` (cache invalidé par `PluginApiRouterService`), middlewares globaux (rate limiting, correlation ID), handlers `WindFlowException`.
