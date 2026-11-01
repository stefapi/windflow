#!/usr/bin/env python3
"""Contrôleur du harness windflow (stdlib uniquement).

Vérifie la cohérence du corpus de pilotage (règles, skills, modes, gabarits) :
  1. liens Markdown relatifs de ``.roo/rules/*.md``, ``.roo/skills/**/*.md`` et
     ``.backlog/_models/*.md`` pointant vers des fichiers existants
     (les blocs de code et liens absolus sont exclus) ;
  2. présence des 15 skills attendues avec un ``SKILL.md`` non vide ;
  3. présence de ``.roomodes`` (JSON ou YAML) et unicité des slugs de modes ;
  4. présence des 4 gabarits ``.backlog/_models/{epic,story,sub-story,bug}.md``.

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
)

EXPECTED_MODELS = ("epic.md", "story.md", "sub-story.md", "bug.md")

_LINK_RE = re.compile(r"(?<!\!)\[[^\]\n]+\]\(([^)\s]+)\)")
_SLUG_JSON_KEY_RE = re.compile(r"^\s*\"slug\"\s*:\s*\"([^\"]+)\"")
_SLUG_YAML_KEY_RE = re.compile(r"^\s*-?\s*slug\s*:\s*([^\s#]+)\s*$")


def strip_code_blocks(text: str) -> str:
    """Retire fenced code blocks et inline code pour éviter les faux positifs."""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"~~~.*?~~~", "", text, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", text)


def check_links(root: Path, errors: list[str]) -> tuple[int, int]:
    """Vérifie les liens relatifs ; retourne (liens vérifiés, liens cassés)."""
    targets: list[Path] = []
    for pattern in (".roo/rules/*.md", ".roo/skills/**/*.md", ".backlog/_models/*.md"):
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
    """Vérifie les skills attendues ; retourne le nombre d'erreurs."""
    count = 0
    for skill in EXPECTED_SKILLS:
        skill_file = root / ".roo" / "skills" / skill / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"skill manquante : {skill_file.relative_to(root)}")
            count += 1
        elif not skill_file.read_text(encoding="utf-8").strip():
            errors.append(f"skill vide : {skill_file.relative_to(root)}")
            count += 1
    return count


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
    check_roomodes(args.root, errors)
    check_models(args.root, errors)

    print(f"Harness : {len(EXPECTED_SKILLS)} skills attendues, "
          f"{checked} liens relatifs vérifiés, 4 gabarits attendus.")
    if errors:
        print(f"❌ {len(errors)} problème(s) détecté(s) :")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("✅ Harness conforme (liens, skills, modes, gabarits).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
