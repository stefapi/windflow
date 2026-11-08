# EPIC-020 : Alignement du harness de pilotage sur PreviImmo

**Statut :** REVIEW
**Priorité :** Haute
**Mode de réalisation :** directe — chantier documentaire et outillage borné (corpus, skills, modes, protocole, garde-fous), livrable et vérifiable en une fois ; aucune story nécessaire.

## Vision

Le harness de pilotage de WindFlow (règles, skills, modes d'agents, protocole d'exécution, garde-fous) atteint le niveau de maturité du harness PreviImmo : corpus concis piloté par contrat, autonomie locale encadrée avec réexamen d'approche, epic directes possibles, revue distincte, preuves reliées aux contrôles, et points d'entrée communs aux outils (AGENTS.md/CLAUDE.md).

## Description

Refonte du corpus `.roo/rules/` au style PreviImmo (fond WindFlow préservé) : 12 règles réécrites, 6 nouvelles (`03-glossary`, `06-frontend-vue3`, `07-python-uv`, `21-realtime-websocket`, `25-ai-llm-mcp`, `46-performance-resilience`). Ajout des règles de modes (orchestrator, architect, code, debug). Migration des skills de `.roo/skills/` vers `.agents/skills/` avec les versions retravaillées (+ `write-acceptance-tests`, + `treat-epic/references/unite-execution.md`). Ajout d'`AGENTS.md`/`CLAUDE.md`, `.rooignore`, `docs/dev/protocole-execution.md`, `docs/dev/controles-validation.md`. Outillage : cibles `make ci-fast`/`make check`, statut `REVIEW` des epics dans `scripts/backlog.py`, `scripts/check_harness.py` étendu (skills 16, points d'entrée, règles de modes, `.agents/skills/`), gabarit epic étendu (Mode de réalisation + Exécution directe).

## Liste des Stories liées

Sans objet — réalisation directe.

## Notes de conception

- Décision du propriétaire (8 novembre 2026) : alignement complet — migration `.agents/skills/`, 6 nouvelles règles, refonte complète du corpus, ajout de `ci-fast` + `check`.
- Pas d'ADR dans ce dépôt : les décisions sont consignées dans les contrats (`02` §2).
- Le fond des règles WindFlow (versions de bibliothèques, mécanismes auth/bus/WebSocket/métriques, seuils) a été préservé et restructuré ; seules les références internes et le style changent.
- Les gabarits `.backlog/_models/` évoluent par gabarit ; aucun contrat existant n'est modifié (les epics EPIC-001…019 restent en l'état, la métadonnée « Mode de réalisation » n'est rétroactive que si une reprise l'exige).

## Critères de succès (Definition of Done)

- [x] Corpus `.roo/rules/` : 18 règles + README cohérents, liens relatifs valides
- [x] 4 règles de modes présentes et référencées
- [x] 16 skills dans `.agents/skills/` (dont `write-acceptance-tests`), plus de copie dans `.roo/skills/`
- [x] `AGENTS.md` + `CLAUDE.md` (`@AGENTS.md`) + `.rooignore` à la racine
- [x] `docs/dev/protocole-execution.md` + `docs/dev/controles-validation.md`
- [x] `make check-harness` et `make harness-test` verts ; `make backlog`/`backlog-check` verts
- [x] Cibles `make ci-fast` et `make check` opérationnelles
- [x] Entrée `CHANGELOG.md` (section « Unreleased »)

## Risques

- Sémantique de chargement réelle des règles par chaque client (Roo, Claude Code, Codex) non prouvée par les contrôles structurels — vérifier sur les versions réellement utilisées (`02` §12).
- Les skills conservent des références aux commandes `make` ; toute évolution ultérieure du Makefile doit maintenir `backlog`, `check-harness`, `harness-test`, `ci-fast`, `check` (`update-rules`).

## Dépendances

- Aucune (chantier autonome).

## Source roadmap

Hors roadmap — création directe sur demande du propriétaire (demande explicite « inspire-toi du harness de previimmo », arbitrages validés par questionnaire : migration `.agents/skills/`, 6 règles nouvelles, refonte complète, `ci-fast` + `check`).

## Exécution directe

### Critères d'acceptation (AC)

- [x] AC 1 : le corpus de règles est complet (18 fichiers + README), au style contrat/protocole, avec priorités, interdits et outil de contrôle par règle vérifiable.
- [x] AC 2 : les 4 règles de modes existent et ne contredisent pas le corpus.
- [x] AC 3 : les 16 skills vivent dans `.agents/skills/`, versions concises pilotées par contrat, `write-acceptance-tests` incluse ; `.roo/skills/` supprimé.
- [x] AC 4 : `AGENTS.md` renvoie au corpus et au protocole sans recopier les règles ; `CLAUDE.md` importe `@AGENTS.md` ; `.rooignore` exclut secrets, données et artefacts.
- [x] AC 5 : le protocole d'exécution et la matrice de validation existent et sont référencés par les règles, modes et skills.
- [x] AC 6 : `scripts/check_harness.py` vérifie skills, points d'entrée, règles de modes et liens ; `scripts/backlog.py` accepte le statut `REVIEW` pour les epics (déclaration manuelle) ; les tests de garde-fous couvrent ces évolutions (22 tests verts).
- [x] AC 7 : `make ci-fast` et `make check` existent dans le Makefile et n'appellent que des cibles existantes.
- [x] AC 8 : le gabarit epic supporte le mode de réalisation et l'exécution directe.

### Contexte technique

Référence : harness PreviImmo observé le 2026-11-08 (`.roo/rules/` 22 fichiers, `.roo/rules-{orchestrator,architect,code,debug}/`, `.agents/skills/` 16 skills, `AGENTS.md`, `.rooignore`, `docs/dev/protocole-execution.md` + `controles-validation.md`). Outillage WindFlow préexistant réutilisé : `scripts/backlog.py` (invariants + kanban), `scripts/check_harness.py`, `scripts/test_harness_tools.py`, cibles `backlog`/`backlog-check`/`check-harness`/`harness-test`.

### Tâches d'implémentation détaillées

- Tâche 1 : refonte du corpus `.roo/rules/` (12 réécritures, 6 créations, README) — faite.
- Tâche 2 : création des 4 règles de modes — faite.
- Tâche 3 : migration skills vers `.agents/skills/` + adaptations windflow (roadmap `docs/Roadmap.md`, specs `docs/general_specs/`, protocole, commandes make) — faite.
- Tâche 4 : `AGENTS.md`, `CLAUDE.md`, `.rooignore` — faits.
- Tâche 5 : `docs/dev/protocole-execution.md` + `controles-validation.md` — faits.
- Tâche 6 : Makefile (`ci-fast`, `check`), `backlog.py` (REVIEW epics), `check_harness.py` (16 skills, `.agents/skills/`, points d'entrée, règles de modes), `test_harness_tools.py` (nouveaux tests) — faits.
- Tâche 7 : gabarit `.backlog/_models/epic.md` étendu, contrat EPIC-020, registre, kanban, CHANGELOG — faits.

### Tests à écrire

- `scripts/test_harness_tools.py` : étendu (points d'entrée, emplacement `.agents/skills/`, epic REVIEW) — 22 tests verts.

### État d'avancement technique

- [x] Tâche 1 : corpus de règles
- [x] Tâche 2 : règles de modes
- [x] Tâche 3 : skills `.agents/skills/`
- [x] Tâche 4 : points d'entrée racine
- [x] Tâche 5 : protocole + matrice
- [x] Tâche 6 : outillage (Makefile, scripts, tests)
- [x] Tâche 7 : gabarit, contrat, registre, CHANGELOG

### Notes d'implémentation

- Fichiers : 18 règles + README, 4 règles de modes, 16 skills (+2 annexes code-review, +1 référence treat-epic), AGENTS.md, CLAUDE.md, .rooignore, 2 docs/dev, Makefile, scripts/{backlog,check_harness,test_harness_tools}.py, `.backlog/_models/epic.md`, `.backlog/identifiants.md`, `.backlog/kanban.md`, CHANGELOG.md.
- Décisions : nommage des fichiers de règles conservé (renommage interdit sans accord, `02` §4) ; nouveaux fichiers en convention anglais du dépôt ; bug lifecycle WindFlow conservé (NEW/CONFIRMED/…) ; statut `REVIEW` ajouté aux epics comme déclaration manuelle (pas de rétro-effect sur les epics existantes) ; `check` appelle `cli-lint`+`cli-test` (pas `cli-format`, mutatif) ; la skill `code-review` windflow était déjà adaptée — migrée avec corrections (uv au lieu de Poetry, chemins, numéros de sections).
- Contrôles exécutés : `make check-harness` ✅, `make harness-test` ✅ (22 tests), `make backlog-check` ✅ (après inscription). Non exécutés : `make check` complet (tests applicatifs hors périmètre de ce chantier documentaire — la CI Gitea et les tests backend/frontend ne sont pas impactés par ce diff), vérification du chargement réel des règles par chaque client d'agent.
