# WindFlow — Règles de développement

Le répertoire `.roo/rules/` contient le corpus de règles du projet. L'ordre de lecture n'est pas un ordre de priorité : voir `02-gouvernance-regles.md` §2.

## Organisation du corpus

| Plage | Famille | Fichiers |
| --- | --- | --- |
| 00–04 | Contexte, gestion de projet, gouvernance, glossaire | `00-project-context.md`, `01-Project-management.md`, `02-gouvernance-regles.md`, `03-glossary.md` |
| 05–09 | Stack, frontend, environnement Python | `05-tech-stack.md`, `06-frontend-vue3.md`, `07-python-uv.md` |
| 20–29 | Architecture, API, temps réel, IA | `20-architecture-and-api.md`, `21-realtime-websocket.md`, `25-ai-llm-mcp.md` |
| 30–39 | Code, tests | `30-code-standards.md`, `35-testing-quality-gates.md` |
| 40–49 | Sécurité, observabilité, performance | `40-security.md`, `45-observability.md`, `46-performance-resilience.md` |
| 50–59 | Workflow, structure | `50-dev-workflow.md`, `55-project-structure.md` |
| 60–69 | Format de sortie | `60-output-format.md` |

Les règles de modes (conduite des modes Roo Code `orchestrator`, `architect`, `code`, `debug`) sont dans `.roo/rules-<mode>/` et précisent le corpus sans jamais le contredire.

## Contexte projet et suivi

- Spécifications : `docs/general_specs/` (index `00-index.md`) et `docs/technical_specs/`
- Feuille de route : `docs/Roadmap.md`
- Backlog et contrats : `.backlog/` (gabarits dans `.backlog/_models/`)
- Protocole commun d'exécution : `docs/dev/protocole-execution.md` ; matrice de validation : `docs/dev/controles-validation.md`
- Carte du harness, compatibilité outils et smoke tests : [docs/dev/harness.md](../../docs/dev/harness.md)
- Skills (workflows de référence) : `.agents/skills/` ; point d'entrée commun : `AGENTS.md` (racine)

## Application et évolution des règles

1. **Lecture** des règles pertinentes avant tout développement ; les règles font foi en cas de conflit avec une habitude générale.
2. **Validation automatique** via le `Makefile` (`make lint`, `make typecheck`, `make test`, `make check`).
3. Toute modification du corpus passe par la skill `update-rules` (`.agents/skills/update-rules/SKILL.md`) ; l'ordre de priorité, le plan de numérotation et les interdits sont définis dans `02-gouvernance-regles.md` ; la fusion d'un changement de règles appartient au propriétaire.
4. Cohérence contrôlée par `make check-harness` (liens, skills, points d'entrée, modes, gabarits) et `make backlog-check` (contrats du backlog).
