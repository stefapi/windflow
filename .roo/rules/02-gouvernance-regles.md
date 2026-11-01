# Gouvernance du corpus de règles

## 1. Objet

Cette règle gouverne le corpus `.roo/rules/` : elle définit les sources de vérité, l'ordre de priorité en cas de conflit entre règles, le plan de numérotation, le processus d'évolution et les interdits courants. Toute autre règle (`00` à `60`) est subordonnée à la présente pour tout ce qui touche à la cohérence du corpus lui-même.

Corpus actuel : `00-project-context.md`, `01-Project-management.md`, `02-gouvernance-regles.md` (la présente), `05-tech-stack.md`, `20-architecture-and-api.md`, `30-code-standards.md`, `35-testing-quality-gates.md`, `40-security.md`, `45-observability.md`, `50-dev-workflow.md`, `55-project-structure.md`, `60-output-format.md`, présentées dans `README.md`.

## 2. Ordre de priorité en cas de conflit

En cas de contradiction entre deux règles ou entre une règle et une autre instruction, la source de plus haute priorité l'emporte :

1. **Sécurité** — `40-security.md` (et, pour l'observabilité de sécurité, `45-observability.md`). Aucune autre règle ne peut justifier un contournement : ni la productivité, ni la cohérence de code, ni une demande de story.
2. **Décisions explicites du propriétaire** — toute décision issue d'un échange consigné (issue, story, section « Notes d'implémentation », arbitrage documenté comme l'arbitrage F6 dans `20-architecture-and-api.md`). Une décision non consignée n'a pas valeur de règle.
3. **Sources de vérité de domaine** — `05-tech-stack.md` (stack et dépendances), `20-architecture-and-api.md` (architecture, API-first, bus d'événements), `35-testing-quality-gates.md` (seuils de couverture, patterns de tests), `50-dev-workflow.md` (cibles Makefile), `55-project-structure.md` (arborescence).
4. **Autres règles** — `00-project-context.md`, `01-Project-management.md`, `30-code-standards.md`, `45-observability.md`, `60-output-format.md`.
5. **Instructions de mode** — les consignes du mode actif (Code, Architect, etc.) s'appliquent tant qu'elles ne contredisent pas les niveaux 1 à 4.
6. **Habitudes générales** — conventions implicites, pratiques héritées du legacy, préférences personnelles. Jamais opposables à un niveau supérieur.

**Exemples windflow concrets :**

- Une story demande d'ajouter `structlog` « pour de meilleurs logs » → conflit avec `45-observability.md` (niveau 4) ET `05-tech-stack.md` (niveau 3, `logging` standard JSON) → refuser sauf décision consignée du propriétaire (niveau 2).
- `30-code-standards.md` tolère une fonction de 40 lignes, mais `40-security.md` exige la validation Pydantic de tous les inputs → la validation s'impose (niveau 1 > niveau 4).
- Un mode demande une sortie verbeuse multi-étapes, mais `60-output-format.md` impose le format Plan/Act → suivre `60-output-format.md` (niveau 4 > niveau 5).
- Le code legacy utilise `requirements.txt` mais `05-tech-stack.md` impose Poetry + pnpm → la règle prime sur l'habitude (niveau 3 > niveau 6).

## 3. Plages numériques par famille

Chaque règle porte un préfixe numérique correspondant à sa famille. Toute nouvelle règle prend le premier numéro disponible dans sa famille :

| Plage | Famille | Règles existantes |
|-------|---------|-------------------|
| 00-09 | Contexte projet / gouvernance | `00-project-context.md`, `01-Project-management.md`, `02-gouvernance-regles.md` |
| 10-19 | Exigences produit | *(réservé, inutilisé actuellement)* |
| 20-29 | Architecture / API | `20-architecture-and-api.md` |
| 30-39 | Code / tests | `30-code-standards.md`, `35-testing-quality-gates.md` |
| 40-49 | Sécurité / observabilité | `40-security.md`, `45-observability.md` |
| 50-59 | Workflow / structure | `50-dev-workflow.md`, `55-project-structure.md` |
| 60-69 | Format de sortie | `60-output-format.md` |

**Règles :**
- Le **renommage d'une règle existante est interdit** sans accord explicite consigné du propriétaire : les skills (notamment `update-rules`, `.roo/skills/update-rules/SKILL.md`) référencent les chemins `.roo/rules/XX-*.md` en dur.
- Une règle ne change pas de famille par simple édition ; sa relocation est un renommage et suit la même interdiction.
- La plage 10-19 reste réservée aux futures exigences produit ; ne pas la consommer pour autre chose.

## 4. Évolution des règles

- Toute modification du corpus `.roo/rules/` passe par la skill **`update-rules`** (`.roo/skills/update-rules/SKILL.md`), qui analyse le code réel (backend, frontend, CLI) avant d'écrire.
- **Ne jamais abaisser la norme pour coller au code** sans décision consignée du propriétaire. Avant toute modification, distinguer trois situations :
  - **Doc périmée** : la règle décrit un état qui n'existe plus (ex : une cible Makefile renommée) → corriger la doc pour refléter la réalité, via `update-rules`.
  - **Obligation non respectée** : le code viole la règle (ex : couverture < 80 % sur un nouveau module) → le code est en tort, créer une story de mise en conformité, ne pas toucher la règle.
  - **Cible non implémentée** : la règle décrit un état cible assumé mais pas encore réalisé (ex : OpenTelemetry « prévu mais pas encore implémenté » dans `45-observability.md`) → conserver la mention explicite de l'écart ; l'implémentation passe par une story du backlog.
- Les gabarits de contrats du backlog (`.backlog/_models/`) suivent la même discipline : évolution par gabarit, jamais par édition directe d'un contrat existant (voir `01-Project-management.md` §7 — on ne supprime jamais un fichier de backlog).

## 5. Outil de contrôle de chaque règle

Toute règle vérifiable doit nommer l'outil qui la contrôle. Référence de correspondance :

| Règle contrôlée | Outil / commande |
|-----------------|------------------|
| Formatage & lint (`30-code-standards.md`, `05-tech-stack.md`) | `make lint`, `make format` (black, isort, flake8, mypy, ESLint, Prettier, Stylelint) |
| Types (`30-code-standards.md`) | `make typecheck` (mypy + tsc strict) |
| Tests & couverture ≥ 80 % (`35-testing-quality-gates.md`) | `make test`, cibles `ci-test-backend` (`--cov-fail-under=80`) |
| Sécurité (`40-security.md`) | `make ci-security-backend` (bandit + safety), `make ci-security-frontend` (pnpm audit) |
| Workflows & builds (`50-dev-workflow.md`) | `make ci-full`, `make ci-quick` |
| Cohérence backlog (registre, kanban, gabarits — `01-Project-management.md`, présente) | `make backlog` (invariants puis régénération du kanban), `make backlog-check` (lecture seule), `make check-harness` (liens, skills, modes, gabarits), `make harness-test` (tests unittest des garde-fous) |

Une nouvelle règle sans outil de contrôle doit être explicitement marquée « à revue humaine » (voir §7).

## 6. Interdits courants et alternatives conformes

| Interdit | Alternative conforme |
|-----------|---------------------|
| Éditer `.backlog/kanban.md` à la main pour réorganiser le board | Modifier les contrats (statuts dans les fichiers story/bug/epic) puis régénérer via `make backlog` ; contrôler avec `make backlog-check` — l'édition manuelle du kanban est interdite |
| Supprimer un fichier de backlog | Changer le statut en `ABANDONED` dans le titre + note explicative (règle d'or, `01-Project-management.md` §7) |
| Créer une dépendance sans justification | `pyproject.toml` (Poetry) côté Python et `pnpm` côté frontend uniquement, avec justification claire (`05-tech-stack.md`) |
| Introduire Redis Streams | Bus canonique `Bus` (`backend/app/core/events.py`), `RedisPubSubEventBus` optionnel — Redis Streams hors périmètre par arbitrage F6 (`20-architecture-and-api.md`) |
| Utiliser `structlog` | `logging` standard Python avec format JSON configurable (`45-observability.md`) |
| Modifier les tables en base manuellement | Migrations Alembic dans `backend/alembic/versions/` |
| Renommer/déplacer une règle `.roo/rules/` sans accord | Créer un nouveau numéro dans la bonne famille (§3) et consigner la décision |
| Bypasser la validation Pydantic côté backend pour « aller vite » | Schémas `*Request`/`*Response` systématiques (`40-security.md`, `20-architecture-and-api.md`) |

## 7. Zones à revue humaine obligatoire

Les zones suivantes ne peuvent être validées par les seuls outils automatisés ; une revue humaine est **obligatoire** avant fusion, même si `make lint` et `make test` passent :

- **Migrations Alembic** (`backend/alembic/versions/`) — irréversibles en production, round-trip upgrade/downgrade à vérifier.
- **Sécurité (RBAC / authentification)** — toute modification de `backend/app/auth/`, des dépendances `require_role(...)` / `ensure_role_ws`, des hashes de mots de passe ou des tokens (voir `40-security.md` et `docs/general_specs/07-authentification.md`, `docs/general_specs/08-rbac-permissions.md`).
- **Déploiement Docker production** — `infrastructure/docker/`, `docker-compose.prod.yml`, `.env.prod.example`.
- **Modifications du harness lui-même** — toute évolution des règles `.roo/rules/`, des skills `.roo/skills/` ou des gabarits `.backlog/_models/` : ces fichiers pilotent l'exécution de tous les travaux futurs, une régression y est silencieuse et systémique.
