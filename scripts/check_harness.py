#!/usr/bin/env python3
"""Contrôleur du harness windflow (stdlib uniquement).

Vérifie la cohérence du corpus de pilotage (règles, skills, modes, gabarits) :
  1. liens Markdown relatifs de ``.roo/rules/*.md``, ``.roo/rules-*/*.md``,
     ``.agents/skills/**/*.md`` et ``.backlog/_models/*.md`` pointant vers des
     fichiers existants (les blocs de code et liens absolus sont exclus) ;
  2. présence des 16 skills attendues avec un ``SKILL.md`` non vide dans
     ``.agents/skills/`` (et absence de corpus concurrent dans ``.roo/skills/``) ;
  3. frontmatter de chaque ``SKILL.md`` conforme à la spec agentskills
     (``name`` = nom du répertoire, minuscules/chiffres/tirets ≤ 64,
     ``description`` sur une ligne de 1 à 1024 caractères) — Roo Code ignore
     silencieusement une skill non conforme, ce contrôle rend l'échec visible ;
  4. adaptateur Claude Code : ``.claude/skills`` doit être un symlink vers
     ``../.agents/skills`` (lien, jamais copie : source de vérité unique) ;
  5. cohérence d'inventaire du corpus : fichiers numérotés de ``.roo/rules/``
     ↔ table du ``README.md`` ↔ liste de ``02-gouvernance-regles.md`` §1 ;
  6. présence des points d'entrée communs : ``AGENTS.md``, ``CLAUDE.md``
     (import ``@AGENTS.md``), ``docs/dev/protocole-execution.md``,
     ``docs/dev/controles-validation.md``, ``.rooignore`` et les 4 règles de
     modes (orchestrator, architect, code, debug) ;
  7. présence de ``.roomodes`` (JSON ou YAML) et unicité des slugs de modes ;
  8. présence des 4 gabarits ``.backlog/_models/{epic,story,sub-story,bug}.md``.

Exit 0 si tout est conforme, 1 sinon (avec résumé des erreurs fichier:ligne).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EXPECTED_SKILLS = (
    "analyse-story",
    "clean-epic",
    "close-epic",
    "code-review",
    "create-boilerplate",
    "create-epic",
    "create-improvement",
    "create-refactoring",
    "create-stories",
    "finalise-epic",
    "finalise-story",
    "split-story",
    "treat-epic",
    "treat-story",
    "update-rules",
    "write-acceptance-tests",
)

EXPECTED_MODE_RULES = (
    ("rules-orchestrator", "01-orchestration.md"),
    ("rules-architect", "01-analyse-conception.md"),
    ("rules-code", "01-implementation.md"),
    ("rules-debug", "01-debogage.md"),
)

EXPECTED_MODELS = ("epic.md", "story.md", "sub-story.md", "bug.md")

_LINK_RE = re.compile(r"(?<!\!)\[[^\]\n]+\]\(([^)\s]+)\)")
_SLUG_JSON_KEY_RE = re.compile(r"^\s*\"slug\"\s*:\s*\"([^\"]+)\"")
_SLUG_YAML_KEY_RE = re.compile(r"^\s*-?\s*slug\s*:\s*([^\s#]+)\s*$")
_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n", re.S)
_FRONTMATTER_NAME_RE = re.compile(r"^name:[ \t]*(.+?)[ \t]*$", re.M)
_FRONTMATTER_DESC_RE = re.compile(r"^description:[ \t]*(.+?)[ \t]*$", re.M)
_SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CORPUS_REF_RE = re.compile(r"`(\d{2}-[A-Za-z0-9-]+\.md)`")


def strip_code_blocks(text: str) -> str:
    """Retire fenced code blocks et inline code pour éviter les faux positifs."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def check_links(root: Path, errors: list[str]) -> tuple[int, int]:
    """Vérifie les liens relatifs ; retourne (liens vérifiés, liens cassés)."""
    targets: list[Path] = []
    for pattern in (".roo/rules/*.md", ".roo/rules-*/*.md", ".agents/skills/**/*.md", ".backlog/_models/*.md"):
        targets.extend(root.glob(pattern))
    checked = broken = 0
    for path in sorted(set(targets)):
        text = strip_code_blocks(path.read_text(encoding="utf-8"))
        for line_no, line in enumerate(text.splitlines(), start=1):
            for target in _LINK_RE.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#", "tel:")):
                    continue
                rel_path = target.split("#", 1)[0].split("?", 1)[0]
                if not rel_path:
                    continue
                checked += 1
                candidate = (path.parent / rel_path).resolve()
                if not candidate.exists():
                    broken += 1
                    rel_display = path.relative_to(root)
                    errors.append(
                        f"lien cassé : {rel_display}:{line_no} → {target}"
                    )
    return checked, broken


def check_skills(root: Path, errors: list[str]) -> int:
    """Vérifie les skills attendues dans .agents/skills/ ; retourne le nombre d'erreurs."""
    count = 0
    for skill in EXPECTED_SKILLS:
        skill_file = root / ".agents" / "skills" / skill / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"skill manquante : {skill_file.relative_to(root)}")
            count += 1
        elif not skill_file.read_text(encoding="utf-8").strip():
            errors.append(f"skill vide : {skill_file.relative_to(root)}")
            count += 1
    legacy = root / ".roo" / "skills"
    if legacy.is_dir() and any(legacy.iterdir()):
        errors.append(
            "skills : .roo/skills/ n'est plus l'emplacement de référence (voir .agents/skills/)"
        )
    return count


def check_skill_frontmatter(root: Path, errors: list[str]) -> int:
    """Valide le frontmatter des SKILL.md (spec agentskills) ; retourne le nombre d'erreurs.

    Claude Code et Roo Code rejettent silencieusement une skill dont le nom ne
    correspond pas au répertoire ou dont la description est absente/hors bornes :
    ce contrôle rend l'échec visible localement et en CI.
    """
    count = 0
    for skill in EXPECTED_SKILLS:
        skill_file = root / ".agents" / "skills" / skill / "SKILL.md"
        if not skill_file.is_file():
            continue  # absence déjà signalée par check_skills
        text = skill_file.read_text(encoding="utf-8")
        rel = skill_file.relative_to(root)
        match = _FRONTMATTER_RE.match(text)
        if match is None:
            errors.append(
                f"skill frontmatter : {rel} doit commencer par un bloc --- (name, description)"
            )
            count += 1
            continue
        frontmatter = match.group(1)
        name_match = _FRONTMATTER_NAME_RE.search(frontmatter)
        desc_match = _FRONTMATTER_DESC_RE.search(frontmatter)
        if name_match is None:
            errors.append(f"skill frontmatter : {rel} sans champ 'name'")
            count += 1
        else:
            name = name_match.group(1).strip()
            if name != skill:
                errors.append(
                    f"skill frontmatter : {rel} name={name!r} ≠ nom du répertoire {skill!r}"
                )
                count += 1
            elif len(name) > 64 or _SKILL_NAME_RE.match(name) is None:
                errors.append(
                    f"skill frontmatter : {rel} name={name!r} non conforme agentskills "
                    "(minuscules/chiffres/tirets, ≤ 64 caractères)"
                )
                count += 1
        if desc_match is None:
            errors.append(
                f"skill frontmatter : {rel} sans champ 'description' (une ligne, 1–1024 caractères)"
            )
            count += 1
        else:
            desc_len = len(desc_match.group(1).strip())
            if not 1 <= desc_len <= 1024:
                errors.append(
                    f"skill frontmatter : {rel} description hors bornes (1–1024, longueur {desc_len})"
                )
                count += 1
    return count


def check_skill_adapters(root: Path, errors: list[str]) -> None:
    """Vérifie l'adaptateur Claude Code : .claude/skills = symlink vers ../.agents/skills.

    Claude Code ne découvre les skills que via .claude/skills/ ; l'adaptateur
    doit rester un lien (source unique), jamais une copie divergente.
    """
    adapter = root / ".claude" / "skills"
    reference = (root / ".agents" / "skills").resolve()
    if not adapter.is_symlink():
        if adapter.exists():
            errors.append(
                "adaptateur skills : .claude/skills doit être un symlink vers ../.agents/skills "
                "(pas une copie) — recréer : rm -rf .claude/skills && ln -sfn ../.agents/skills .claude/skills"
            )
        else:
            errors.append(
                "adaptateur skills : .claude/skills manquant (Claude Code ne lit que .claude/skills/) — "
                "créer : ln -sfn ../.agents/skills .claude/skills"
            )
        return
    if not adapter.exists():
        errors.append("adaptateur skills : .claude/skills est un lien cassé (cible inexistante)")
        return
    if adapter.resolve() != reference:
        errors.append(
            f"adaptateur skills : .claude/skills pointe vers {adapter.resolve()} au lieu de {reference}"
        )


def _corpus_refs_readme(text: str) -> set[str] | None:
    """Référence du corpus dans la table « Organisation du corpus » du README (lignes de table)."""
    table_lines = [line for line in text.splitlines() if line.lstrip().startswith("|")]
    if not table_lines:
        return None
    return set(_CORPUS_REF_RE.findall("\n".join(table_lines)))


def _corpus_refs_rule02(text: str) -> set[str] | None:
    """Référence du corpus dans la ligne « Corpus actuel : » de 02-gouvernance-regles.md §1."""
    for line in text.splitlines():
        if line.strip().startswith("Corpus actuel :"):
            return set(_CORPUS_REF_RE.findall(line))
    return None


def check_rules_inventory(root: Path, errors: list[str]) -> None:
    """Cohérence d'inventaire : fichiers numérotés de .roo/rules/ ↔ README ↔ 02 §1.

    Détecte automatiquement la dérive entre le disque, la table du README.md et
    la liste « Corpus actuel : » de 02-gouvernance-regles.md (§1). Les mentions
    de documents externes (ex. `docs/general_specs/`) sont hors périmètre.
    Sans corpus sur disque (dépôts de test), le contrôle est sans objet.
    """
    rules_dir = root / ".roo" / "rules"
    if not rules_dir.is_dir():
        return
    disk = {p.name for p in rules_dir.glob("[0-9][0-9]-*.md")}
    if not disk:
        return
    readme = rules_dir / "README.md"
    rule02 = rules_dir / "02-gouvernance-regles.md"
    sources = (
        (readme, "README.md", _corpus_refs_readme),
        (rule02, "02-gouvernance-regles.md §1", _corpus_refs_rule02),
    )
    for path, label, extractor in sources:
        if not path.is_file():
            errors.append(
                f"inventaire corpus : {label} requis pour contrôler la cohérence de .roo/rules/"
            )
            continue
        refs = extractor(path.read_text(encoding="utf-8"))
        if refs is None:
            errors.append(f"inventaire corpus : inventaire introuvable dans {label}")
            continue
        unlisted = sorted(disk - refs)
        dead = sorted(refs - disk)
        if unlisted:
            errors.append(
                f"inventaire corpus : fichier(s) non listé(s) dans {label} : {', '.join(unlisted)}"
            )
        if dead:
            errors.append(
                f"inventaire corpus : référence(s) morte(s) dans {label} : {', '.join(dead)}"
            )


def check_entry_points(root: Path, errors: list[str]) -> None:
    """Vérifie les points d'entrée communs : AGENTS.md, CLAUDE.md, protocole, règles de modes."""
    agents = root / "AGENTS.md"
    if not agents.is_file():
        errors.append("point d'entrée : AGENTS.md introuvable à la racine")
    claude = root / "CLAUDE.md"
    if not claude.is_file():
        errors.append("point d'entrée : CLAUDE.md introuvable à la racine")
    elif "@AGENTS.md" not in claude.read_text(encoding="utf-8"):
        errors.append("point d'entrée : CLAUDE.md doit importer @AGENTS.md")
    protocol = root / "docs" / "dev" / "protocole-execution.md"
    if not protocol.is_file():
        errors.append("point d'entrée : docs/dev/protocole-execution.md introuvable")
    validation = root / "docs" / "dev" / "controles-validation.md"
    if not validation.is_file():
        errors.append("point d'entrée : docs/dev/controles-validation.md introuvable")
    rooignore = root / ".rooignore"
    if not rooignore.is_file():
        errors.append("point d'entrée : .rooignore introuvable à la racine")
    for folder, filename in EXPECTED_MODE_RULES:
        path = root / ".roo" / folder / filename
        if not path.is_file():
            errors.append(f"règle de mode manquante : {path.relative_to(root)}")


def _slugs_from_json(data: object) -> list[str] | None:
    """Extrait les slugs d'un .roomodes au format JSON (liste ou {customModes:...})."""
    modes = data if isinstance(data, list) else None
    if modes is None and isinstance(data, dict):
        modes = data.get("customModes")
    if not isinstance(modes, list):
        return None
    return [m.get("slug") for m in modes if isinstance(m, dict) and "slug" in m]


def _slugs_from_yaml(text: str) -> list[str]:
    """Extrait les slugs d'un .roomodes YAML (clé ``slug:`` des items de modes)."""
    return [
        match.group(1)
        for line in text.splitlines()
        if (match := _SLUG_YAML_KEY_RE.match(line)) is not None
    ]


def check_roomodes(root: Path, errors: list[str]) -> None:
    """Vérifie .roomodes : présent, parsable (JSON ou YAML), slugs uniques."""
    roomodes = root / ".roomodes"
    if not roomodes.is_file():
        errors.append("modes : fichier .roomodes introuvable à la racine")
        return
    text = roomodes.read_text(encoding="utf-8")
    slugs: list[str] | None = None
    if text.lstrip().startswith(("[", "{")):
        try:
            slugs = _slugs_from_json(json.loads(text))
        except json.JSONDecodeError as exc:
            errors.append(f"modes : .roomodes JSON invalide ({exc})")
            return
        if slugs is None:
            errors.append("modes : .roomodes JSON sans liste de modes (customModes)")
            return
    else:
        slugs = _slugs_from_yaml(text)
        if not slugs:
            errors.append("modes : .roomodes YAML sans aucun slug de mode")
            return
    duplicates = sorted({s for s in slugs if slugs.count(s) > 1})
    if duplicates:
        errors.append(f"modes : slug(s) dupliqué(s) dans .roomodes : {', '.join(duplicates)}")


def check_models(root: Path, errors: list[str]) -> None:
    """Vérifie la présence des 4 gabarits .backlog/_models/."""
    for model in EXPECTED_MODELS:
        path = root / ".backlog" / "_models" / model
        if not path.is_file():
            errors.append(f"gabarit manquant : {path.relative_to(root)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_harness.py",
        description="Vérifie la cohérence du harness windflow (liens, skills, modes, gabarits).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Racine du dépôt (défaut : parent du dossier scripts/)",
    )
    args = parser.parse_args(argv)

    errors: list[str] = []
    checked, broken = check_links(args.root, errors)
    skill_errors = check_skills(args.root, errors)
    frontmatter_errors = check_skill_frontmatter(args.root, errors)
    check_skill_adapters(args.root, errors)
    check_rules_inventory(args.root, errors)
    check_entry_points(args.root, errors)
    check_roomodes(args.root, errors)
    check_models(args.root, errors)

    print(f"Harness : {len(EXPECTED_SKILLS)} skills attendues (.agents/skills/), "
          f"{checked} liens relatifs vérifiés, 4 gabarits attendus, "
          f"{len(EXPECTED_MODE_RULES)} règles de modes attendues ; "
          f"frontmatter ({frontmatter_errors} écart(s)), adaptateur .claude/skills "
          f"et inventaire du corpus contrôlés.")
    if errors:
        print(f"❌ {len(errors)} problème(s) détecté(s) :")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("✅ Harness conforme (liens, skills, points d'entrée, modes, gabarits).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
