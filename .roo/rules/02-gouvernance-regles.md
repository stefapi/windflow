# 02 — Gouvernance des règles

## 1. Portée

Ce corpus (`.roo/rules/` et `.roo/rules-<mode>/`) régit tout travail sur le dépôt, humain ou agent. Roo Code lit les fichiers par ordre alphabétique : cet ordre n'est pas un ordre de priorité.

Corpus actuel : `00-project-context.md`, `01-Project-management.md`, `02-gouvernance-regles.md` (la présente), `03-glossary.md`, `05-tech-stack.md`, `06-frontend-vue3.md`, `07-python-uv.md`, `20-architecture-and-api.md`, `21-realtime-websocket.md`, `25-ai-llm-mcp.md`, `30-code-standards.md`, `35-testing-quality-gates.md`, `40-security.md`, `45-observability.md`, `46-performance-resilience.md`, `50-dev-workflow.md`, `55-project-structure.md`, `60-output-format.md`.

## 2. Priorité en cas de conflit

1. `40-security.md` : aucune règle ne peut affaiblir une règle de sécurité. Aucune autre règle ne peut justifier un contournement : ni la productivité, ni la cohérence de code, ni une demande de story.
2. **Décisions écrites du propriétaire** : toute décision issue d'un échange consigné (issue, story, section « Notes d'implémentation », arbitrage documenté comme l'arbitrage F6 dans `20-architecture-and-api.md`). Une décision non consignée n'a pas valeur de règle.
3. **Sources de vérité de domaine**, qui priment sur toute mention du même sujet dans un autre fichier :
   - `05-tech-stack.md` : stack et dépendances ;
   - `20-architecture-and-api.md` : architecture, API-first, bus d'événements ;
   - `21-realtime-websocket.md` : temps réel ;
   - `06-frontend-vue3.md` : frontend ;
   - `25-ai-llm-mcp.md` : IA et LLM ;
   - `35-testing-quality-gates.md` : seuils de couverture, patterns de tests ;
   - `50-dev-workflow.md` : cibles Makefile ;
   - `55-project-structure.md` : arborescence.
4. Les autres fichiers de `.roo/rules/` : `00-project-context.md`, `01-Project-management.md`, `03-glossary.md`, `07-python-uv.md`, `30-code-standards.md`, `45-observability.md`, `46-performance-resilience.md`, `60-output-format.md`.
5. Les fichiers `.roo/rules-<mode>/`, qui précisent la conduite d'un mode sans jamais contredire les précédents.
6. Les usages généraux d'un framework, d'un modèle ou d'un tutoriel ; les habitudes héritées du legacy. Jamais opposables à un niveau supérieur.

La spécification dit **quoi** faire, les règles disent **comment**. Si elles divergent, l'agent s'arrête et le signale.

**Exemples windflow concrets :**

- Une story demande d'ajouter `structlog` « pour de meilleurs logs » → conflit avec `45-observability.md` (niveau 4) ET `05-tech-stack.md` (niveau 3, `logging` standard JSON) → refuser sauf décision consignée du propriétaire (niveau 2).
- `30-code-standards.md` tolère une fonction de 40 lignes, mais `40-security.md` exige la validation Pydantic de tous les inputs → la validation s'impose (niveau 1 > niveau 4).
- Le code legacy utilise `requirements.txt` mais `05-tech-stack.md` impose UV + pnpm → la règle prime sur l'habitude (niveau 3 > niveau 6).

## 3. Rappels entre fichiers

Un fichier peut rappeler une règle d'un autre fichier en une phrase suivie du renvoi à sa source (`voir 40-security.md §6`). Il ne la reformule jamais autrement ; en cas d'écart, la source s'applique.

## 4. Ajouter une règle

| Plage | Famille | Règles existantes |
| --- | --- | --- |
| 00–04 | Contexte, gestion de projet, gouvernance, glossaire | `00`, `01`, `02`, `03` |
| 05–09 | Stack, frontend, environnement Python | `05`, `06`, `07` |
| 10–19 | Exigences produit | *(réservé, inutilisé actuellement)* |
| 20–29 | Architecture, API, temps réel, IA | `20`, `21`, `25` |
| 30–39 | Code, erreurs, tests | `30`, `35` |
| 40–49 | Sécurité, observabilité, performance | `40`, `45`, `46` |
| 50–59 | Workflow, structure du dépôt | `50`, `55` |
| 60–69 | Format des réponses des agents | `60` |

Une règle nouvelle va dans le fichier de sa famille. Un nouveau fichier seulement si la famille n'existe pas, avec le premier numéro libre de sa plage. La plage 10–19 reste réservée aux futures exigences produit.

**Le renommage d'une règle existante est interdit** sans accord explicite consigné du propriétaire : les skills (notamment `update-rules`) et la checklist de revue référencent les chemins `.roo/rules/XX-*.md` en dur. Une règle ne change pas de famille par simple édition ; sa relocation est un renommage et suit la même interdiction.

## 5. Faire évoluer une règle

- Proposition : par le propriétaire, ou par un agent qui constate un manque, dans la section « Points d'attention » de sa réponse. Un agent ne modifie jamais les règles de sa propre initiative hors chantier explicitement autorisé d'évolution du harness.
- Toute modification du corpus passe par la skill **`update-rules`** (`.agents/skills/update-rules/SKILL.md`), qui compare la règle au code réel avant d'écrire.
- Forme : changement dédié, commit `docs(regles): …` ou `docs(harness): …` qui en donne le motif. Validation : le propriétaire, seul habilité à fusionner une modification des règles.
- **Ne jamais abaisser la norme pour coller au code** sans décision consignée. Avant toute modification, distinguer trois situations :
  - **Doc périmée** : la règle décrit un état qui n'existe plus → corriger la doc pour refléter la réalité, via `update-rules` ;
  - **Obligation non respectée** : le code viole la règle → le code est en tort, créer une story de mise en conformité, ne pas toucher la règle ;
  - **Cible non implémentée** : la règle décrit un état cible assumé mais pas encore réalisé (ex. OpenTelemetry « prévu mais pas encore implémenté » dans `45`) → conserver la mention explicite de l'écart ; l'implémentation passe par une story du backlog.
- Les gabarits de contrats (`.backlog/_models/`) suivent la même discipline : évolution par gabarit, jamais par édition directe d'un contrat existant.

## 6. Outil de contrôle de chaque règle

Toute règle vérifiable nomme l'outil qui la contrôle. Référence de correspondance :

| Règle contrôlée | Outil / commande |
| --- | --- |
| Formatage & lint (`30`, `05`) | `make lint`, `make format` (black, isort, flake8, mypy, ESLint, Prettier, Stylelint) |
| Types (`30`) | `make typecheck` (mypy + tsc strict) |
| Tests & couverture ≥ 80 % (`35`) | `make test`, `make ci-test-backend` (`--cov-fail-under=80`) |
| Sécurité (`40`) | `make ci-security-backend` (bandit + safety), `make ci-security-frontend` (pnpm audit) |
| Workflows & builds (`50`) | `make ci-full`, `make ci-quick`, `make ci-fast`, `make check` |
| Cohérence backlog (registre, kanban, gabarits — `01`, présente) | `make backlog`, `make backlog-check`, `make check-harness`, `make harness-test` |

Une nouvelle règle sans outil de contrôle doit être explicitement marquée « à revue humaine » (voir §7).

## 7. Zones à revue humaine obligatoire

Aucun changement n'est fusionné dans ces zones sans validation du propriétaire, même si `make lint` et `make test` passent :

- **Migrations Alembic** (`backend/alembic/versions/`) — irréversibles en production, round-trip upgrade/downgrade à vérifier.
- **Sécurité (RBAC / authentification)** — toute modification de `backend/app/auth/`, des dépendances `require_role(...)` / `ensure_role_ws`, des hashes de mots de passe ou des tokens (`40`, `docs/general_specs/07-authentification.md`, `08-rbac-permissions.md`).
- **Déploiement Docker production** — `infrastructure/docker/`, `docker-compose.prod.yml`, `.env.prod.example`.
- **Modifications du harness lui-même** — règles `.roo/rules/` et `.roo/rules-<mode>/`, skills `.agents/skills/`, gabarits `.backlog/_models/` et scripts `scripts/backlog.py` / `scripts/check_harness.py` : ces fichiers pilotent l'exécution de tous les travaux futurs, une régression y est silencieuse et systémique. Un chantier explicitement autorisé d'évolution du harness peut les modifier ; il reste soumis à leur revue et à leurs contrôles.

## 8. Interdits non négociables

| Interdit | Alternative conforme |
| --- | --- |
| Éditer `.backlog/kanban.md` à la main | Modifier les contrats puis `make backlog` ; contrôler avec `make backlog-check` |
| Supprimer un fichier de backlog | Statut `ABANDONED` + marqueur dans le titre + note explicative (`01` §10) |
| Créer une dépendance sans justification | `pyproject.toml` (uv, PEP 621) et `pnpm` uniquement, avec justification (`05` §5) |
| Introduire Redis Streams | Bus canonique `Bus` (`backend/app/core/events.py`), `RedisPubSubEventBus` optionnel — hors périmètre par arbitrage F6 (`20`) |
| Utiliser `structlog` | `logging` standard Python avec format JSON configurable (`45`) |
| Modifier les tables en base manuellement | Migrations Alembic dans `backend/alembic/versions/` (`20`) |
| Renommer/déplacer une règle `.roo/rules/` sans accord | Créer un nouveau numéro dans la bonne famille (§4) et consigner la décision |
| Bypasser la validation Pydantic côté backend | Schémas `*Request`/`*Response` systématiques (`40`, `20`) |
| Éditer un fichier généré (client API, kanban) | Régénération (`make generate-api`, `make backlog`) |
| Test ou valeur attendue modifiés pour passer | Correction du code, ou accord écrit du propriétaire (`35`) |
| Installation par `pip`, `npm`, `yarn`, `poetry` | `uv`, `pnpm` (`00` §5) |
| Secret ou clé d'API en dur, dans les logs ou une URL | Variables d'environnement, SecretManager (`40` §5) |

## 9. Dérive entre règles et code

- À la clôture de chaque epic : contrôler la cohérence entre besoin approuvé, règles et code ; qualifier les écarts et les consigner. La présence du code ne justifie ni une règle ni une fonctionnalité terminée. Corriger l'implémentation ou proposer l'évolution de l'intention à son propriétaire, sans alignement automatique des règles sur le code.
- Un écart découvert en cours de réalisation est signalé dans la réponse, jamais corrigé en silence.

## 10. En cas de doute

Une incertitude de besoin, de droit ou de décision structurante ne se résout pas en devinant : l'agent investigue, expose les faits et options, recommande une solution et demande l'arbitrage utile par le moyen disponible dans son outil. Suspendre seulement les parties dépendantes. Les détails techniques locaux compatibles restent autonomes (`01` §12). En particulier :
- sécurité : retenir l'option la plus restrictive et le signaler ;
- données : aucune suppression, purge ou migration irréversible sans accord écrit ;
- périmètre : rien en dehors des critères d'acceptation du contrat exécutable (epic directe, story ou bug).

## 11. Obsolescence

Une règle obsolète est marquée `**Obsolète depuis AAAA-MM-JJ, remplacée par <renvoi>**` pendant une livraison, puis supprimée. Le propriétaire décide ; l'historique Git conserve la trace.

## 12. Fichiers d'instructions d'autres outils

`AGENTS.md` est le point d'entrée commun et renvoie vers ce corpus et le protocole d'exécution, sans recopier les règles. `CLAUDE.md` importe `@AGENTS.md` pour les sessions Claude qui en ont besoin. Roo Code conserve `.roo/rules/` et ses règles de modes (`.roo/rules-orchestrator/`, `.roo/rules-architect/`, `.roo/rules-code/`, `.roo/rules-debug/`) ; ne pas créer de `.roorules` concurrent. Les skills de `.agents/skills/` sont les workflows de référence ; si un outil exige un adaptateur de découverte, il renvoie à leur source au lieu d'en maintenir une copie divergente.

Vérifier le chargement sur les versions et configurations réellement utilisées ; le contrôle structurel `make check-harness` ne le prouve pas. Les noms d'outils (`ask_followup_question`, `attempt_completion`, sous-agents) sont des capacités propres à un client, jamais des obligations universelles du corpus.
