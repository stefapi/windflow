# 35 — Tests, couverture et quality gates

## 1. Pyramide

Surtout des tests unitaires (services, schémas, composables) ; puis des tests d'intégration (API et base réelle) ; peu de tests de bout en bout, réservés aux parcours critiques.

- Backend : `unit/` + `integration/` uniquement (pas de `e2e/`).
- Frontend : `tests/unit/`, `tests/integration/`, `tests/e2e/` (Playwright).

## 2. Outillage

| Niveau | Backend | Frontend |
| --- | --- | --- |
| Unitaires | pytest + pytest-asyncio, pytest-mock, pytest-xdist, pytest-timeout, pytest-benchmark, faker, factory-boy, freezegun, aioresponses | Vitest + `@vue/test-utils ^2.4.6` + `@pinia/testing ^1.0.2`, jsdom `^26.0.0` |
| Intégration | pytest + DB réelle + Redis | Vitest + mocks HTTP |
| E2E | — | Playwright `^1.56.0` (chromium, firefox, webkit) |

Client HTTP de test : httpx `AsyncClient` avec `ASGITransport` pour les tests d'endpoint API. Toutes les commandes sont dans le `Makefile` (`50` §1).

## 3. Couverture

| Périmètre | Seuil |
| --- | --- |
| Backend global | 80 % (`--cov-fail-under=80` dans `make ci-test-backend`) |
| Tout nouveau composant | 80 % minimum |
| Chemins critiques (auth, déploiement, RBAC) | viser 95 % |
| Frontend | aucun seuil configuré dans `vitest.config.ts` — viser la couverture des chemins critiques |

Les « zones zéro » historiques sont comblées (WebSocket ~94 % STORY-164/165, matrice RBAC STORY-122.7, round-trip migrations STORY-120.3, enveloppes/pagination STORY-126/128). Recompter avant de citer une volumétrie (décision D2).

## 4. Données de test

- **Interdit** : toute donnée réelle (hosts, credentials, clés API) dans les tests, fixtures, captures ou journaux. Construire un cas fictif équivalent.
- Fixtures partagées dans `backend/tests/conftest.py`, documentées par leur docstring.

## 5. Cas systématiques par famille

| Famille | Cas obligatoires |
| --- | --- |
| Endpoint REST (par verbe) | 401 sans token, 403 rôle insuffisant, 422 body invalide, 404 introuvable ; 201+objet créé pour POST ; 409 conflit si applicable ; pagination pour les listes |
| Sécurité | isolation des ressources par utilisateur/organisation ; champs sensibles absents des réponses |
| WebSocket | droits du canal (`ensure_role_ws`), reprise après coupure (`21` §7) |
| Composant/vue | rendu initial (vide, chargement, données), interactions, états d'erreur, accès conditionnel selon rôle ; route protégée sans auth → redirection `/login` |
| Migrations | montée et descente (round-trip upgrade/downgrade) sur base de test |
| Bus/async | publication après validation seulement ; relance après erreur transitoire sans double effet |
| Calculs/droits/transitions | exemples métier préparés avant l'implémentation ; TDD ciblé |

- **Un bug commence par un test qui le reproduit** (en échec avant le correctif, vert après).
- Un test existant n'est jamais modifié pour passer, sauf accord écrit du propriétaire mentionné dans le commit.
- Les scénarios métier sont préparés avant le code, en langage lisible (situation, action, attendu, refus/limite pertinents) ; la skill `write-acceptance-tests` décrit cette étape pour les bugs et comportements critiques.

## 6. Commandes

Source de vérité : le `Makefile` (`50` §1).

```bash
make backend-test-unit                     # tests unitaires backend
make frontend-test-unit                    # tests unitaires frontend
make ci-test-backend                       # backend complet + couverture ≥ 80 %
make ci-fast                               # retour intermédiaire local (sans couverture)
make check                                 # portes complètes avant acceptation
```

Ciblé pendant le développement :

```bash
uv run pytest backend/tests/unit/test_api/test_xxx.py -v --tb=short
cd frontend && pnpm test -- tests/unit/components/XxxComponent
```

## 7. Revue distincte et acceptance

- Pendant le développement : exécuter les contrôles ciblés et impactés. Avant acceptation : les portes applicables restent requises (`01` §7, [matrice de validation](../../docs/dev/controles-validation.md)).
- Réutiliser les preuves encore valides ; tout changement susceptible d'invalider une preuve exige une nouvelle vérification. Une suite vide, ignorée ou indisponible ne prouve rien.
- Pour un changement structurant ou sensible, obtenir une revue distincte par un second agent quand l'outil le permet, sinon une revue distincte humaine avec la limite consignée. Le relecteur reçoit contrat, faits, diff et preuves, sans conclusion imposée. La revue technique ne remplace pas les validations humaines de `02` §7.
- Ne pas qualifier un échec de « préexistant » sans preuve sur la référence de départ dans un environnement comparable.

## 8. Conclure sans avoir exécuté les tests

Un contrôle requis non exécuté bloque l'acceptation, sauf dérogation explicite avec décideur, motif, périmètre et expiration ; il reste marqué non exécuté. Le travail peut être présenté en revue avec ses limites. Un agent n'affirme jamais qu'un test passe sans l'avoir exécuté. S'il n'a pas pu exécuter des tests, il indique lesquels, pourquoi, et la commande exacte à lancer (`60-output-format.md` §4).
