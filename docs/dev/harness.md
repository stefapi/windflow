# Harness de pilotage — carte, compatibilité outils et smoke tests

Le harness est l'ensemble des fichiers qui pilotent le travail des agents et
des humains sur ce dépôt : corpus de règles, skills, modes, backlog, protocole
d'exécution et garde-fous exécutables. Son évolution suit la gouvernance
(`02` §5, §7) : zone à revue humaine, modifications par chantier autorisé via
la skill `update-rules`.

## 1. Carte du harness

| Composant | Emplacement | Rôle | Contrôlé par |
| --- | --- | --- | --- |
| Instructions communes | `AGENTS.md` (racine) | Point d'entrée unique, renvoie au corpus sans recopier | `make check-harness` |
| Import Claude | `CLAUDE.md` (racine) | `@AGENTS.md` pour les sessions Claude Code | `make check-harness` |
| Corpus de règles | `.roo/rules/` (18 fichiers + `README.md`) | Obligations « comment », sources normatives par domaine | `make check-harness` (liens, inventaire) |
| Règles de modes | `.roo/rules-{orchestrator,architect,code,debug}/` | Conduite des modes Roo Code, sans contredire le corpus | `make check-harness` |
| Skills | `.agents/skills/` (16) | Workflows de référence pilotés par contrat (spec agentskills) | `make check-harness`, `make harness-test` |
| Adaptateur Claude | `.claude/skills` (symlink → `../.agents/skills`) | Découverte des skills par Claude Code | `make check-harness` |
| Modes personnalisés | `.roomodes` (racine) | Modes Roo Code du projet (slugs uniques) | `make check-harness` |
| Backlog | `.backlog/` (contrats, registre, kanban généré) | Contrats exécutables et suivi (règle `01`) | `make backlog`, `make backlog-check` |
| Protocole / matrice | `docs/dev/protocole-execution.md`, `controles-validation.md` | Exécution commune, preuves et portes | `make check-harness` (présence) |
| MCP | `.roo/mcp.json` | Serveurs MCP du projet (Roo Code) | relecture (voir §4) |
| Exclusions | `.rooignore` | Ce que Roo Code ne lit ni n'écrit | `make check-harness` (présence) |

## 2. Chargement réel par outil

Conventions vérifiées le 2026-11-08 (docs officielles des outils) ; à revérifier
sur les versions réellement utilisées (`02` §12) — checklist au §5.

| Composant | Claude Code | OpenCode | Roo Code | Codex |
| --- | --- | --- | --- | --- |
| Instructions d'entrée | `CLAUDE.md` → `@AGENTS.md` | `AGENTS.md` natif | `.roo/rules/` (chargé intégralement) | `AGENTS.md` natif |
| Skills | `.claude/skills/` **uniquement** (d'où l'adaptateur symlink) | `.opencode/skills/`, `.claude/skills/`, `.agents/skills/` | `.roo/skills/` et `.agents/skills/` | `.agents/skills/` |
| Modes personnalisés | sans objet | sans objet | `.roomodes` | sans objet |
| MCP | `.mcp.json` (non configuré ici) | `opencode.json` (non configuré ici) | `.roo/mcp.json` | configuration propre (non configuré ici) |

Points d'attention :

- Claude Code ne lit **pas** `.agents/skills/` : sans l'adaptateur
  `.claude/skills`, les 16 skills du dépôt lui sont invisibles.
- Roo Code et Claude Code **ignorent silencieusement** une skill dont le
  frontmatter est invalide (`name` ≠ répertoire, `description` absente ou
  > 1024) : le contrôle de frontmatter de `check_harness.py` rend l'échec
  visible.
- OpenCode scanne à la fois `.claude/skills/` et `.agents/skills/` : vérifier
  au smoke test qu'aucun doublon n'apparaît (déduplication par nom attendue).

## 3. Politique d'adaptateurs

- **Source de vérité unique** : `.agents/skills/`. Aucune copie de skill n'est
  maintenue ailleurs.
- `.claude/skills` est un **symlink** vers `../.agents/skills` — jamais un
  répertoire copié. Recréation :
  `ln -sfn ../.agents/skills .claude/skills` (dans le dépôt, `.claude/` présent).
- `.roo/skills/` est interdit (garde-fou `check_harness.py`) : Roo Code lit
  déjà `.agents/skills/`.
- `check_harness.py` vérifie : présence du lien, cible correcte, lien non
  cassé, absence de copie divergente.
- Caveat plateformes : les symlinks Git exigent `core.symlinks` actif (Linux
  et macOS par défaut ; Windows : mode développeur ou `git config -c
  core.symlinks=true` lors du clone). Sans symlink, le contrôle échoue avec la
  commande de recréation.

## 4. MCP

- Configuration actuelle : `.roo/mcp.json` (Roo Code uniquement) — sqlite
  (base de dev, chemin **relatif** au workspace : Roo Code lance les serveurs
  du projet avec `cwd` = dossier du workspace), context7, playwright (version
  épinglée pour la reproductibilité).
- Secrets : jamais en dur — variable d'environnement via `${env:NOM}` dans
  `.roo/mcp.json`.
- Étendre MCP à un autre outil (Claude Code `.mcp.json`, OpenCode
  `opencode.json`) est une décision du propriétaire : créer un adaptateur
  minimal dérivé de la même liste de serveurs, sans duplication de secrets, et
  documenter l'ajout ici.

## 5. Smoke tests de chargement réel (`02` §12)

À exécuter après toute évolution du harness ou montée de version d'un client ;
consigner les versions testées dans le contrat ou l'entrée `CHANGELOG.md`.

- **Claude Code** : ouvrir une session dans le dépôt → vérifier que les
  instructions se chargent (contenu d'`AGENTS.md` actif) et que les 16 skills
  du projet sont proposées (menu `/` ou `/doctor prompt-audit` ≥ 2.1.283).
- **OpenCode** : session dans le dépôt → instructions `AGENTS.md` actives,
  skills du projet présentes **sans doublon** (cf. §2).
- **Roo Code** : les règles du corpus apparaissent dans le contexte du mode ;
  les skills de `.agents/skills/` sont découvertes ; les modes de `.roomodes`
  sont sélectionnables.
- **Codex** : session dans le dépôt → `AGENTS.md` actif, skills de
  `.agents/skills/` découvertes.

Les contrôles structurels (`make check-harness`) ne prouvent aucun de ces
comportements : ils vérifient la forme, pas le chargement.

## 6. Zones conservées en l'état

- `.roo/rules-{mode-writer,skill-writer,merge-resolver}/*.xml` : gabarits
  marketplace Roo d'avril 2026 (anglais, XML), antérieurs à l'alignement
  EPIC-020. Décision EPIC-021 : conservés en l'état, hors corpus numéroté ;
  toute harmonisation (traduction, condensation, migration `.md`) est une
  évolution du harness à décider par le propriétaire via `update-rules`.
- Modes `.roomodes` `documentation-writer` et `merge-resolver` : sans règle de
  mode dédiée, ce qui est autorisé (seules les 4 règles des modes cœur sont
  exigées par `check_harness.py`).

## 7. Contrôles et CI

| Contrôle | Local | CI Gitea |
| --- | --- | --- |
| Cohérence du harness (liens, skills, frontmatter, adaptateur, inventaire, points d'entrée, modes, gabarits) | `make check-harness` | job `harness-gates` (`quality-gates.yml`) |
| Invariants du backlog | `make backlog-check` / `make backlog` | job `harness-gates` |
| Tests des garde-fous | `make harness-test` | job `harness-gates` |

Les trois scripts sont stdlib uniquement : aucun environnement virtuel requis,
exécution rapide locale et distante. La matrice complète des portes vit dans
[controles-validation.md](controles-validation.md).
