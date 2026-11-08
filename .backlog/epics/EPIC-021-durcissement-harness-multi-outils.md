# EPIC-021 : Durcissement du harness multi-outils (Claude Code, OpenCode, Roo Code, Codex)

**Statut :** REVIEW
**Priorité :** Haute
**Mode de réalisation :** directe — chantier documentaire et outillage borné (adaptateur, garde-fous, CI, doc), livrable et vérifiable en une fois ; les axes sont indépendants techniquement mais partagent les mêmes fichiers de contrôle ; aucune story nécessaire.

## Vision

Le harness de pilotage reste la source unique (corpus `.roo/rules/`, skills `.agents/skills/`, backlog, protocole) tout en étant **réellement chargé par les quatre outils** (Claude Code, OpenCode, Roo Code, Codex) et **gardé par des contrôles exécutables locaux et distants** : l'écart de découvert constaté à l'audit (skills invisibles de Claude Code, garde-fous absents de la CI, MCP non portable) est résorbé et rendu non régressif.

## Description

Suite de l'audit de compatibilité post-EPIC-020 (constat documenté dans les risques d'EPIC-020 : « sémantique de chargement réelle non prouvée ») :

1. **Adaptateur skills Claude Code** : Claude Code ne lit que `.claude/skills/` (vérifié sur la doc officielle, sept. 2026) ; création de `.claude/skills` comme symlink vers `../.agents/skills` — lien, jamais copie, la référence reste unique.
2. **Garde-fous `check_harness.py` étendus** : validation du frontmatter des `SKILL.md` (spec agentskills : `name` = répertoire, minuscules/tirets ≤ 64, `description` 1–1024 — Roo ignore silencieusement une skill non conforme) ; contrôle de l'adaptateur `.claude/skills` (présent, symlink, cible la référence, pas de copie divergente) ; cohérence d'inventaire du corpus (disque `.roo/rules/*.md` ↔ table du `README.md` ↔ liste `02` §1).
3. **CI Gitea** : job `harness-gates` dans `quality-gates.yml` exécutant `check_harness.py`, `backlog.py check` et `test_harness_tools.py` (stdlib uniquement) — ces contrôles n'existaient que localement.
4. **MCP portable** : suppression du chemin absolu en dur dans `.roo/mcp.json` (chemin relatif au workspace, `cwd` implicite Roo = dossier du workspace) ; politique MCP consignée (Roo Code seul aujourd'hui, secrets via `${env:…}`).
5. **Documentation du harness** : `docs/dev/harness.md` — carte du corpus, matrice de chargement par outil, politique d'adaptateurs, smoke tests de chargement réel (application concrète de `02` §12), zones conservées en l'état ; référencé depuis `AGENTS.md` et le README des règles ; matrice `controles-validation.md` mise à jour.
6. **Statut des zones legacy** : dossiers XML `.roo/rules-{mode-writer,skill-writer,merge-resolver}/` (gabarits marketplace Roo d'avril 2026) conservés en l'état, décision consignée dans la doc harness.

## Liste des Stories liées

Sans objet — réalisation directe.

## Notes de conception

- Décision du propriétaire (8 novembre 2026) : mise en œuvre de tous les axes de l'audit (P0→P3) après présentation du rapport ; choix « adaptateur lien symbolique » plutôt que copie (une seule source de vérité, cohérent avec le garde-fou `.roo/skills/` existant).
- Constats de compatibilité (vérifiés le 2026-11-08) : Claude Code ne découvre les skills **que** via `.claude/skills/` ; Roo Code lit `.roo/skills/` **et** `.agents/skills/` (priorité projet) ; OpenCode lit `.opencode/skills/`, `.claude/skills/` et `.agents/skills/` ; Codex lit `.agents/skills/`. AGENTS.md est lu nativement par OpenCode et Codex ; Claude Code via `CLAUDE.md` → `@AGENTS.md` ; Roo Code via `.roo/rules/`.
- Caveats assumés : les symlinks Git exigent une configuration adaptée sur Windows (`core.symlinks`) — recréation documentée par une commande ; OpenCode scannant aussi `.claude/skills/`, un éventuel doublon d'affichage est à vérifier au smoke test (déduplication par nom attendue) ; le chargement réel reste à constater sur les versions utilisées (`02` §12), la doc fournit la checklist.
- Aucune modification des règles numérotées du corpus (seuls `README.md` des règles, `AGENTS.md`, `docs/dev/` et l'outillage changent) ; la matrice `controles-validation.md` est mise à jour factuellement.

## Critères de succès (Definition of Done)

- [x] `.claude/skills` existe comme symlink vers `../.agents/skills`, sans copie des skills
- [x] `make check-harness` vérifie adaptateur, frontmatter des skills et inventaire du corpus ; vert sur le dépôt
- [x] Job CI `harness-gates` présent dans `quality-gates.yml` (stdlib uniquement) ; matrice `controles-validation.md` à jour
- [x] `.roo/mcp.json` sans chemin absolu ; politique MCP consignée dans `docs/dev/harness.md`
- [x] `docs/dev/harness.md` écrit et référencé depuis `AGENTS.md` et `.roo/rules/README.md`
- [x] `make harness-test` étendu (frontmatter, adaptateur, inventaire) et vert ; `make backlog` / `backlog-check` verts
- [x] Entrée `CHANGELOG.md` (section « Unreleased »)

## Risques

- Sémantique de chargement réelle par client : les contrôles structurels restent des proxys ; les smoke tests de `docs/dev/harness.md` doivent être exécutés sur les versions réellement utilisées et consignés (`02` §12).
- Symlink `.claude/skills` : plateformes sans support symlink (Windows sans `core.symlinks`) → le contrôle échoue avec un message explicite et la commande de recréation est documentée.
- Le job CI `harness-gates` dépend du runner Gitea (actions/checkout préserve les symlinks sous Linux) ; une divergence d'exécution distante reste possible.

## Dépendances

- Aucune bloquante. EPIC-020 est en `REVIEW` : sa clôture formelle reste indépendante et à la décision du propriétaire.

## Source roadmap

Hors roadmap — création directe sur demande du propriétaire (audit de compatibilité du harness du 8 novembre 2026, périmètre « tout (P0→P3) » validé par questionnaire).

## Exécution directe

### Critères d'acceptation (AC)

- [x] AC 1 : `.claude/skills` est un symlink pointant vers `../.agents/skills` ; `check_harness.py` signale son absence, une cible erronée, un lien cassé ou une copie (répertoire réel) à la place du lien.
- [x] AC 2 : `check_harness.py` valide le frontmatter de chaque skill attendue : bloc `---` initial, `name` égal au nom du répertoire et conforme agentskills (minuscules/chiffres/tirets, ≤ 64), `description` non vide de 1 à 1024 caractères ; les 16 skills actuelles passent sans modification.
- [x] AC 3 : `check_harness.py` compare les fichiers numérotés de `.roo/rules/` aux inventaires du `README.md` (table des familles) et de `02` §1 (corpus) ; toute dérive (fichier non listé, liste morte) est une erreur.
- [x] AC 4 : le job `harness-gates` de `quality-gates.yml` exécute les trois contrôles stdlib (`check_harness.py`, `backlog.py check`, `test_harness_tools.py`) sans installation de dépendances.
- [x] AC 5 : `.roo/mcp.json` n'énonce plus de chemin absolu ; `docs/dev/harness.md` consigne la politique MCP (outils couverts, secrets `${env:…}`, extension par adaptateur sur décision du propriétaire).
- [x] AC 6 : `docs/dev/harness.md` contient carte du harness, matrice de chargement par outil, politique d'adaptateurs, checklist de smoke tests et zones conservées ; référencé depuis `AGENTS.md` et `.roo/rules/README.md` ; lignes « Backlog » et « Instructions partagées » de `controles-validation.md` mises à jour.
- [x] AC 7 : `test_harness_tools.py` couvre les nouveaux contrôles (nom de skill divergent, description absente/trop longue, adaptateur manquant/copie, inventaire divergent) et la fixture nominale reste verte.
- [x] AC 8 : le statut « conservé en l'état » des dossiers XML `.roo/rules-{mode-writer,skill-writer,merge-resolver}/` est consigné dans `docs/dev/harness.md`.

### Contexte technique

Références : harness actuel (EPIC-020, état au 2026-11-08) ; `scripts/check_harness.py` (liens, skills, points d'entrée, modes, gabarits) ; `scripts/test_harness_tools.py` (corpus temporaire, unittest stdlib) ; `.gitea/workflows/quality-gates.yml` (jobs Gitea Actions compatibles actions/*, Python 3.11) ; conventions de découverte vérifiées : spec agentskills (frontmatter `name`/`description`), Roo Code SkillsManager (validation `name` = répertoire, description 1–1024, découverte `.agents/skills` + `.roo/skills`), Claude Code (`.claude/skills/` seul), OpenCode (`.opencode/skills/` + `.claude/skills/` + `.agents/skills/`), Codex (`.agents/skills/`). Roo Code lance les serveurs MCP du projet avec `cwd` = dossier du workspace par défaut (chemins relatifs sûrs dans `.roo/mcp.json`).

### Tâches d'implémentation détaillées

- Tâche 1 : symlink `.claude/skills` → `../.agents/skills`.
- Tâche 2 : `scripts/check_harness.py` — nouvelles fonctions `check_skill_frontmatter`, `check_skill_adapters`, `check_rules_inventory` ; docstring et résumé mis à jour.
- Tâche 3 : `scripts/test_harness_tools.py` — fixture nominale étendue (frontmatter valides, adaptateur symlink, corpus minimal inventorié) + tests des nouveaux échecs.
- Tâche 4 : `.gitea/workflows/quality-gates.yml` — job `harness-gates`.
- Tâche 5 : `.roo/mcp.json` — chemin relatif `dev/data/windflow.db`.
- Tâche 6 : `docs/dev/harness.md` + références dans `AGENTS.md`, `.roo/rules/README.md`, `docs/dev/controles-validation.md`.
- Tâche 7 : CHANGELOG, kanban (`make backlog`), contrôles finaux.

### Tests à écrire

- `test_harness_tools.py` : frontmatter invalide (nom ≠ répertoire, description absente, description > 1024), adaptateur (manquant, copie au lieu du lien, cible erronée), inventaire (fichier sur disque absent des listes, liste morte), nominal inchangé.

### État d'avancement technique

- [x] Tâche 1 : adaptateur skills Claude Code
- [x] Tâche 2 : garde-fous check_harness étendus
- [x] Tâche 3 : tests des garde-fous
- [x] Tâche 4 : CI harness-gates
- [x] Tâche 5 : MCP portable
- [x] Tâche 6 : doc harness + références
- [x] Tâche 7 : CHANGELOG, kanban, contrôles

### Notes d'implémentation

- Fichiers : `.claude/skills` (symlink), `scripts/check_harness.py` (+3 contrôles : `check_skill_frontmatter`, `check_skill_adapters`, `check_rules_inventory`), `scripts/test_harness_tools.py` (fixture étendue + 9 tests, 31 au total), `.gitea/workflows/quality-gates.yml` (job `harness-gates`), `.roo/mcp.json` (chemin relatif `dev/data/windflow.db`), `docs/dev/harness.md` (nouveau), `AGENTS.md`, `.roo/rules/README.md`, `docs/dev/controles-validation.md` (2 lignes), `CHANGELOG.md`, présent contrat, `.backlog/identifiants.md`, `.backlog/kanban.md` (régénéré).
- Décisions : l'extraction d'inventaire est cadrée sur les zones réelles (lignes de table du `README.md`, ligne « Corpus actuel : » de `02` §1) car la première version attrapait des références à `docs/general_specs/` (`00-index.md`, `08-rbac-permissions.md`) — les mentions hors de ces zones restent hors périmètre ; le lien cassé Oracle `.claude/skills` produit un message avec la commande de recréation ; aucune règle numérotée du corpus modifiée.
- Contrôles exécutés : `make check-harness` ✅ (24 liens, frontmatter 0 écart, adaptateur + inventaire conformes), `make harness-test` ✅ (31 tests), `make backlog` + `make backlog-check` ✅, syntaxe YAML de `quality-gates.yml` validée. Non exécutés : `make check` complet (tests applicatifs backend/frontend sans rapport avec ce diff documentaire et outillage), exécution distante du nouveau job CI (attestée par la configuration, pas par un run Gitea), smoke tests de chargement réel des quatre clients (checklist `docs/dev/harness.md` §5 — action propriétaire sur les versions utilisées).
- Reprise éventuelle : exécuter la checklist de `docs/dev/harness.md` §5 et consigner les versions ; vérifier l'absence de doublon de skills dans OpenCode (scan `.claude/skills` + `.agents/skills`).

## Historique de clôture

<!-- Renseigné par close-epic : date, décision, contrats conservés, référence évaluée, preuves. -->
