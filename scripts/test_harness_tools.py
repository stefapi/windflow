#!/usr/bin/env python3
"""Tests unitaires des garde-fous du harness (stdlib unittest, corpus temporaires).

Exécution : ``python3 scripts/test_harness_tools.py`` (ou ``make harness-test``).

Couverture :
  - backlog.py    : cas nominal (exit 0, kanban généré), statut invalide, doublon
                    d'identifiant, incohérence registre, statut d'epic incohérent,
                    non-écriture du kanban en cas de violation ;
  - check_harness.py : cas nominal (exit 0), lien cassé détecté, skill manquante,
                    frontmatter invalide (nom ≠ répertoire, description
                    absente/hors bornes), adaptateur .claude/skills (manquant,
                    copie, cible erronée), inventaire du corpus (fichier non
                    listé, référence morte).
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent


def _load_module(name: str, filename: str):
    """Charge un script sibling comme module (sans package)."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


backlog_mod = _load_module("backlog_tool", "backlog.py")
harness_mod = _load_module("check_harness_tool", "check_harness.py")

EPIC_TEMPLATE = """# {eid} : {title}

**Statut :** {status}
**Priorité :** Moyenne

## Vision

Test.

## Liste des Stories liées
{story_lines}
"""

STORY_TEMPLATE = """# {sid} : {title}

**Statut :** {status}
**Epic Parent :** {eid} — Titre epic

## Description

Test.
"""

REGISTRY_HEADER = """# Registre durable des identifiants

## Epics

| Identifiant | Chemin | Date d'attribution | Statut actuel |
|---|---|---|---|
"""

REGISTRY_STORIES_HEADER = """
## Stories

| Identifiant | Chemin | Date d'attribution | Statut actuel |
|---|---|---|---|
"""


def write_minimal_corpus(root: Path, *, epic_status: str = "TODO",
                         story_status: str = "TODO", story_checked: bool = False,
                         registry: bool = True) -> None:
    """Corpus minimal valide : 1 epic EPIC-900 + 1 story STORY-900 + registre."""
    (root / ".backlog" / "epics").mkdir(parents=True)
    (root / ".backlog" / "stories").mkdir(parents=True)
    mark = "x" if story_checked else " "
    epic_status_value = {"TODO": "TODO", "IN_PROGRESS": "IN_PROGRESS", "DONE": "DONE"}[epic_status]
    story_lines = f"- [{mark}] STORY-900 : Titre story" if story_status != "__absent__" else ""
    (root / ".backlog" / "epics" / "EPIC-900-test.md").write_text(
        EPIC_TEMPLATE.format(eid="EPIC-900", title="Epic de test", status=epic_status_value,
                             story_lines=story_lines),
        encoding="utf-8",
    )
    if story_status != "__absent__":
        (root / ".backlog" / "stories" / "STORY-900-test.md").write_text(
            STORY_TEMPLATE.format(sid="STORY-900", title="Titre story",
                                  status=story_status, eid="EPIC-900"),
            encoding="utf-8",
        )
    if registry:
        story_row = (
            "| STORY-900 | .backlog/stories/STORY-900-test.md | 2026-11-01 | %s |\n"
            % ("DONE" if story_status == "DONE" else "TODO")
        )
        (root / ".backlog" / "identifiants.md").write_text(
            REGISTRY_HEADER
            + "| EPIC-900 | .backlog/epics/EPIC-900-test.md | 2026-11-01 | %s |\n"
            % epic_status_value
            + REGISTRY_STORIES_HEADER
            + (story_row if story_status != "__absent__" else ""),
            encoding="utf-8",
        )


class TempRootMixin:
    """Fournit self.root (corpus temporaire) détruit après chaque test."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="windflow-harness-")
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)


class TestBacklogTool(TempRootMixin, unittest.TestCase):
    """Tests de scripts/backlog.py (invariants + génération)."""

    def run_main(self, mode: str) -> int:
        return backlog_mod.main([mode, "--root", str(self.root)])

    # ------------------------------------------------------------------ nominal

    def test_nominal_check_exit_0(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="TODO")
        self.assertEqual(self.run_main("check"), 0)

    def test_nominal_generate_writes_kanban(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="TODO")
        self.assertEqual(self.run_main("generate"), 0)
        kanban = (self.root / ".backlog" / "kanban.md").read_text(encoding="utf-8")
        self.assertIn("# KANBAN BOARD", kanban)
        self.assertIn("ne pas éditer à la main", kanban)
        self.assertIn("### EPIC-900", kanban)
        self.assertIn("- [ ] STORY-900", kanban)

    def test_generate_refuses_write_on_violation(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="WONT_FIX")
        code = self.run_main("generate")
        self.assertEqual(code, 1)
        self.assertFalse((self.root / ".backlog" / "kanban.md").exists())

    # ------------------------------------------------------------------ invariants

    def test_invalid_status_detected(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="WONT_FIX")
        code = self.run_main("check")
        self.assertEqual(code, 1)
        # le statut WONT_FIX est réservé aux bugs : la story doit être signalée
        self.assertEqual(code, 1)

    def test_duplicate_identifier_detected(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="TODO")
        duplicate = (
            self.root / ".backlog" / "stories" / "STORY-900-doublon.md"
        )
        duplicate.write_text(
            STORY_TEMPLATE.format(sid="STORY-900", title="Doublon",
                                  status="TODO", eid="EPIC-900"),
            encoding="utf-8",
        )
        code = self.run_main("check")
        self.assertEqual(code, 1)

    def test_registry_mismatch_detected(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="TODO")
        registry = self.root / ".backlog" / "identifiants.md"
        # simule un statut registre divergent (disque TODO, registre DONE)
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                ".backlog/stories/STORY-900-test.md | 2026-11-01 | TODO",
                ".backlog/stories/STORY-900-test.md | 2026-11-01 | DONE",
            ),
            encoding="utf-8",
        )
        code = self.run_main("check")
        self.assertEqual(code, 1)

    def test_epic_status_inconsistency_detected(self) -> None:
        # epic déclarée TODO alors que sa seule story est DONE → dérivé DONE ≠ TODO
        write_minimal_corpus(self.root, epic_status="TODO", story_status="DONE",
                             story_checked=True)
        code = self.run_main("check")
        self.assertEqual(code, 1)

    def test_epic_done_with_done_story_passes(self) -> None:
        write_minimal_corpus(self.root, epic_status="DONE", story_status="DONE",
                             story_checked=True)
        self.assertEqual(self.run_main("check"), 0)

    def test_epic_review_is_manual_declaration(self) -> None:
        # epic REVIEW avec story DONE : déclaration manuelle légitime (revue globale),
        # la dérivation ne s'applique pas (cf. règle 01 §6)
        write_minimal_corpus(self.root, epic_status="DONE", story_status="DONE",
                             story_checked=True)
        epic = self.root / ".backlog" / "epics" / "EPIC-900-test.md"
        epic.write_text(
            EPIC_TEMPLATE.format(eid="EPIC-900", title="Epic de test", status="REVIEW",
                                 story_lines="- [x] STORY-900 : Titre story"),
            encoding="utf-8",
        )
        registry = self.root / ".backlog" / "identifiants.md"
        registry.write_text(
            registry.read_text(encoding="utf-8").replace(
                ".backlog/epics/EPIC-900-test.md | 2026-11-01 | DONE",
                ".backlog/epics/EPIC-900-test.md | 2026-11-01 | REVIEW",
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.run_main("check"), 0)

    def test_abandoned_title_marker_mismatch_detected(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="TODO")
        story = self.root / ".backlog" / "stories" / "STORY-900-test.md"
        story.write_text(
            STORY_TEMPLATE.format(sid="STORY-900", title="[ABANDONED] Titre story",
                                  status="TODO", eid="EPIC-900"),
            encoding="utf-8",
        )
        self.assertEqual(self.run_main("check"), 1)

    def test_unregistered_contract_detected(self) -> None:
        write_minimal_corpus(self.root, epic_status="TODO", story_status="TODO")
        # retire la story du registre → contrat non inscrit
        registry = self.root / ".backlog" / "identifiants.md"
        registry.write_text(
            "".join(
                line for line in registry.read_text(encoding="utf-8").splitlines(keepends=True)
                if "STORY-900" not in line
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.run_main("check"), 1)

    def test_done_story_checkbox_consistency(self) -> None:
        # story DONE mais case non cochée dans l'epic → invariant [f]
        write_minimal_corpus(self.root, epic_status="DONE", story_status="DONE",
                             story_checked=False)
        self.assertEqual(self.run_main("check"), 1)


class TestCheckHarnessTool(TempRootMixin, unittest.TestCase):
    """Tests de scripts/check_harness.py."""

    def build_valid_harness(self) -> None:
        rules = self.root / ".roo" / "rules"
        rules.mkdir(parents=True)
        (rules / "README.md").write_text(
            "# Rules\n\n"
            "| Famille | Fichiers |\n| --- | --- |\n"
            "| 00–02 | `00-project-context.md`, `02-gouvernance-regles.md` |\n\n"
            "Voir [les gabarits](../../.backlog/_models/README.md).\n",
            encoding="utf-8",
        )
        (rules / "00-project-context.md").write_text("# Contexte\n", encoding="utf-8")
        (rules / "02-gouvernance-regles.md").write_text(
            "# 02 — Gouvernance\n\nCorpus actuel : `00-project-context.md`, "
            "`02-gouvernance-regles.md`.\n",
            encoding="utf-8",
        )
        for folder, filename in harness_mod.EXPECTED_MODE_RULES:
            mode_dir = self.root / ".roo" / folder
            mode_dir.mkdir(parents=True, exist_ok=True)
            (mode_dir / filename).write_text(f"# Mode {folder}\n\nRègle de mode.\n", encoding="utf-8")
        for skill in harness_mod.EXPECTED_SKILLS:
            skill_file = self.root / ".agents" / "skills" / skill / "SKILL.md"
            skill_file.parent.mkdir(parents=True, exist_ok=True)
            skill_file.write_text(
                f"---\nname: {skill}\ndescription: Skill de test {skill}.\n---\n\n"
                f"# {skill}\n\nContenu non vide.\n",
                encoding="utf-8",
            )
        claude_dir = self.root / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        adapter = claude_dir / "skills"
        if adapter.is_symlink() or adapter.exists():
            adapter.unlink()
        os.symlink("../.agents/skills", adapter)
        models = self.root / ".backlog" / "_models"
        models.mkdir(parents=True)
        for model in harness_mod.EXPECTED_MODELS:
            (models / model).write_text(f"# Gabarit {model}\n", encoding="utf-8")
        (models / "README.md").write_text("# Gabarits\n", encoding="utf-8")
        (self.root / ".roomodes").write_text(
            "customModes:\n  - slug: code\n    name: Code\n  - slug: architect\n    name: Architect\n",
            encoding="utf-8",
        )
        (self.root / "AGENTS.md").write_text("# Instructions\n\nVoir [.roo/rules](.roo/rules).\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (self.root / ".rooignore").write_text(".env\n", encoding="utf-8")
        dev_docs = self.root / "docs" / "dev"
        dev_docs.mkdir(parents=True)
        (dev_docs / "protocole-execution.md").write_text("# Protocole\n", encoding="utf-8")
        (dev_docs / "controles-validation.md").write_text("# Contrôles\n", encoding="utf-8")

    def run_main(self) -> int:
        return harness_mod.main(["--root", str(self.root)])

    def test_nominal_exit_0(self) -> None:
        self.build_valid_harness()
        self.assertEqual(self.run_main(), 0)

    def test_broken_link_detected(self) -> None:
        self.build_valid_harness()
        readme = self.root / ".roo" / "rules" / "README.md"
        readme.write_text(
            "# Rules\n\n| Famille | Fichiers |\n| --- | --- |\n"
            "| 00–02 | `00-project-context.md`, `02-gouvernance-regles.md` |\n\n"
            "Voir [cible inexistante](./absent.md).\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_main(), 1)

    def test_missing_skill_detected(self) -> None:
        self.build_valid_harness()
        (self.root / ".agents" / "skills" / "analyse-story" / "SKILL.md").unlink()
        self.assertEqual(self.run_main(), 1)

    def test_empty_skill_detected(self) -> None:
        self.build_valid_harness()
        (self.root / ".agents" / "skills" / "treat-story" / "SKILL.md").write_text(
            "   \n", encoding="utf-8"
        )
        self.assertEqual(self.run_main(), 1)

    def test_legacy_roo_skills_detected(self) -> None:
        self.build_valid_harness()
        legacy = self.root / ".roo" / "skills" / "analyse-story" / "SKILL.md"
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text("# Ancien emplacement\n", encoding="utf-8")
        self.assertEqual(self.run_main(), 1)

    # ------------------------------------------------------- frontmatter skills

    def test_frontmatter_name_mismatch_detected(self) -> None:
        self.build_valid_harness()
        skill = self.root / ".agents" / "skills" / "treat-story" / "SKILL.md"
        skill.write_text(
            "---\nname: wrong-name\ndescription: Skill de test.\n---\n\nContenu.\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_main(), 1)

    def test_frontmatter_missing_description_detected(self) -> None:
        self.build_valid_harness()
        skill = self.root / ".agents" / "skills" / "treat-story" / "SKILL.md"
        skill.write_text("---\nname: treat-story\n---\n\nContenu.\n", encoding="utf-8")
        self.assertEqual(self.run_main(), 1)

    def test_frontmatter_description_too_long_detected(self) -> None:
        self.build_valid_harness()
        skill = self.root / ".agents" / "skills" / "treat-story" / "SKILL.md"
        skill.write_text(
            f"---\nname: treat-story\ndescription: {'x' * 1025}\n---\n\nContenu.\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_main(), 1)

    def test_frontmatter_block_missing_detected(self) -> None:
        self.build_valid_harness()
        skill = self.root / ".agents" / "skills" / "treat-story" / "SKILL.md"
        skill.write_text("# treat-story\n\nPas de frontmatter.\n", encoding="utf-8")
        self.assertEqual(self.run_main(), 1)

    # -------------------------------------------------------- adaptateur Claude

    def test_claude_adapter_missing_detected(self) -> None:
        self.build_valid_harness()
        (self.root / ".claude" / "skills").unlink()
        self.assertEqual(self.run_main(), 1)

    def test_claude_adapter_copy_detected(self) -> None:
        self.build_valid_harness()
        adapter = self.root / ".claude" / "skills"
        adapter.unlink()
        adapter.mkdir()
        (adapter / "treat-story").mkdir()
        (adapter / "treat-story" / "SKILL.md").write_text("# Copie\n", encoding="utf-8")
        self.assertEqual(self.run_main(), 1)

    def test_claude_adapter_wrong_target_detected(self) -> None:
        self.build_valid_harness()
        adapter = self.root / ".claude" / "skills"
        adapter.unlink()
        os.symlink("../.backlog", adapter)
        self.assertEqual(self.run_main(), 1)

    # ------------------------------------------------------------ inventaire corpus

    def test_inventory_unlisted_file_detected(self) -> None:
        self.build_valid_harness()
        (self.root / ".roo" / "rules" / "99-experiment.md").write_text(
            "# 99 — Hors inventaire\n", encoding="utf-8"
        )
        self.assertEqual(self.run_main(), 1)

    def test_inventory_dead_reference_detected(self) -> None:
        self.build_valid_harness()
        readme = self.root / ".roo" / "rules" / "README.md"
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(
                "`02-gouvernance-regles.md` |", "`02-gouvernance-regles.md`, `77-fantome.md` |"
            ),
            encoding="utf-8",
        )
        self.assertEqual(self.run_main(), 1)

    def test_missing_entry_points_detected(self) -> None:
        self.build_valid_harness()
        (self.root / "AGENTS.md").unlink()
        self.assertEqual(self.run_main(), 1)
        (self.root / "AGENTS.md").write_text("# Instructions\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Pas d'import\n", encoding="utf-8")
        self.assertEqual(self.run_main(), 1)
        (self.root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (self.root / ".roo" / "rules-debug" / "01-debogage.md").unlink()
        self.assertEqual(self.run_main(), 1)

    def test_code_block_links_ignored(self) -> None:
        self.build_valid_harness()
        readme = self.root / ".roo" / "rules" / "README.md"
        readme.write_text(
            "# Rules\n\n| Famille | Fichiers |\n| --- | --- |\n"
            "| 00–02 | `00-project-context.md`, `02-gouvernance-regles.md` |\n\n"
            "Exemple :\n\n```markdown\n[placeholder](./dans-un-bloc.md)\n```\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_main(), 0)

    def test_duplicate_mode_slug_detected(self) -> None:
        self.build_valid_harness()
        (self.root / ".roomodes").write_text(
            "customModes:\n  - slug: code\n    name: Code\n  - slug: code\n    name: Autre\n",
            encoding="utf-8",
        )
        self.assertEqual(self.run_main(), 1)

    def test_json_roomodes_supported(self) -> None:
        self.build_valid_harness()
        (self.root / ".roomodes").write_text(
            '[{"slug": "code"}, {"slug": "debug"}]', encoding="utf-8"
        )
        self.assertEqual(self.run_main(), 0)

    def test_missing_model_detected(self) -> None:
        self.build_valid_harness()
        (self.root / ".backlog" / "_models" / "bug.md").unlink()
        self.assertEqual(self.run_main(), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
