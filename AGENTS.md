# Instructions de WindFlow

Le corpus commun aux agents est dans [.roo/rules/](.roo/rules/).
Lire d'abord [le contexte](.roo/rules/00-project-context.md),
[la gestion du backlog](.roo/rules/01-Project-management.md) et
[la gouvernance](.roo/rules/02-gouvernance-regles.md), puis les règles
de domaine applicables au changement.

Le [protocole d'exécution](docs/dev/protocole-execution.md) relie contrat,
autonomie, réexamen de l'approche, vérification et revue ; la
[matrice de validation](docs/dev/controles-validation.md) inventorie les portes
et leurs limites. La [carte du harness](docs/dev/harness.md) décrit la
compatibilité Claude Code / OpenCode / Roo Code / Codex (points d'entrée,
adaptateur de skills, smoke tests de chargement). Les skills du dépôt sont dans [.agents/skills/](.agents/skills/) ;
ouvrir le `SKILL.md` pertinent lorsqu'une demande appelle ce workflow, sans
charger toutes les skills.

Les règles et décisions consignées font autorité selon leur gouvernance. Les
instructions ne remplacent pas les contrôles exécutables ni les protections
de fusion.

## Trouver rapidement la règle utile

| Tâche | Source dans `.roo/rules/` |
| --- | --- |
| Contrat, suivi et autonomie | [01](.roo/rules/01-Project-management.md) |
| Backend, données, API, bus d'événements | [20](.roo/rules/20-architecture-and-api.md) |
| Temps réel WebSocket | [21](.roo/rules/21-realtime-websocket.md) |
| Frontend, composants, état | [06](.roo/rules/06-frontend-vue3.md) |
| Vocabulaire et noms de code | [03](.roo/rules/03-glossary.md) |
| Tests, acceptation et preuves | [35](.roo/rules/35-testing-quality-gates.md) |
| Authentification, droits et secrets | [40](.roo/rules/40-security.md) |
| IA, LiteLLM et agents | [25](.roo/rules/25-ai-llm-mcp.md) |
| Commandes, dépendances, Git et CI | [50](.roo/rules/50-dev-workflow.md), [07](.roo/rules/07-python-uv.md) |

`make help` liste les commandes. Le kanban est généré : modifier les contrats,
leurs statuts et leurs listes liées, puis `make backlog` et `make backlog-check`.
`make ci-fast` fournit un retour local intermédiaire ; l'acceptation garde ses
contrôles complets (`make check`). Pour les bugs et comportements critiques,
préparer les tests à partir des AC et contrats publics avant l'implémentation ;
voir la skill [write-acceptance-tests](.agents/skills/write-acceptance-tests/SKILL.md).
