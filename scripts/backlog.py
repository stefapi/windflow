#!/usr/bin/env python3
"""Garde-fous du backlog WindFlow (stdlib uniquement).

Deux modes :
  - ``generate`` : vérifie les invariants puis régénère intégralement ``.backlog/kanban.md``
    (aucune écriture en cas de violation, exit 1).
  - ``check``    : mêmes vérifications en lecture seule, sans régénération (exit 1 si anomalie).

Invariants contrôlés (cf. .roo/rules/01-Project-management.md et 02-gouvernance-regles.md) :
  a) identifiants uniques (epics/stories/bugs, sous-stories incluses) ;
  b) statuts valides selon le type + cohérence marqueur ``[ABANDONED]`` du titre ↔ statut ;
  c) registre ``.backlog/identifiants.md`` ↔ disque (présence bidirectionnelle, statuts alignés) ;
  d) référence croisée story ↔ epic (Epic Parent existe, story couverte dans la liste de son epic) ;
  e) statut dérivé des epics conforme au statut déclaré ;
  f) stories DONE/ABANDONED cochées dans la section « Liste des Stories liées » de leur epic.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

EPIC_STATUSES = {"TODO", "IN_PROGRESS", "BLOCKED", "DONE", "ABANDONED"}
STORY_STATUSES = {"TODO", "IN_PROGRESS", "REVIEW", "BLOCKED", "DONE", "ABANDONED"}
BUG_STATUSES = {"NEW", "CONFIRMED", "IN_PROGRESS", "REVIEW", "DONE", "WONT_FIX", "ABANDONED"}

KANBAN_NOTE = (
    "> ⚠️ **Vue générée automatiquement** par `make backlog` (`scripts/backlog.py generate`) — "
    "**ne pas éditer à la main**.\n>\n"
    "> Statut de référence : champ `**Statut :**` des contrats dans "
    "`.backlog/epics/`, `.backlog/stories/` et `.backlog/bugs/`."
)

# Statuts de registre qui exemptent l'entrée de l'exigence « fichier présent sur disque »
_REGISTRY_EXEMPT_HINTS = ("jamais attribué", "trace historique", "réservation sans contrat")

_STORY_ID = r"STORY-\d{3}(?:\.\d+)?"
_FILE_ID_RE = re.compile(r"^(EPIC-\d{3}|%s|BUG-\d{3})" % _STORY_ID)
_TITLE_ID_RE = re.compile(r"(EPIC-\d{3}|%s|BUG-\d{3})" % _STORY_ID)
_STATUS_RE = re.compile(r"^\*\*Statut\s*:\*\*\s*(\S+)", re.M)
_PARENT_RE = re.compile(r"^\*\*Epic Parent\s*:\*\*\s*(EPIC-\d{3})", re.M)
_LIST_ITEM_RE = re.compile(r"^\s*-\s*\[( |x|X)\]\s*(%s)" % _STORY_ID, re.M)
_STORY_REF_RE = re.compile(_STORY_ID)


@dataclass
class Contract:
    """Contrat de backlog (epic, story ou bug) lu sur disque."""

    kind: str  # "epic" | "story" | "bug"
    identifier: str
    path: Path
    title: str
    status: str | None
    abandoned_marker: bool
    parent: str | None = None
    listed: dict[str, bool] = field(default_factory=dict)  # id -> coché ?

    @property
    def parent_story_id(self) -> str | None:
        """STORY-120.1 -> STORY-120 (couverture par la ligne parent dans les epics)."""
        if self.kind == "story" and "." in self.identifier:
            return self.identifier.split(".", 1)[0]
        return None


class BacklogCorpus:
    """Charge et valide le corpus .backlog/ d'une racine donnée."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.backlog_dir = root / ".backlog"
        self.contracts: dict[str, Contract] = {}
        self.registry: dict[str, dict[str, str]] = {}
        self.anomalies: list[str] = []

    # ------------------------------------------------------------------ chargement

    def load(self) -> None:
        self._load_contracts("epic", self.backlog_dir / "epics")
        self._load_contracts("story", self.backlog_dir / "stories")
        self._load_contracts("bug", self.backlog_dir / "bugs")
        self._load_epic_story_lists()
        self._load_registry()

    def _load_contracts(self, kind: str, folder: Path) -> None:
        if not folder.is_dir():
            return
        for path in sorted(folder.glob("*.md")):
            match = _FILE_ID_RE.match(path.name)
            if not match:
                self.anomalies.append(f"[a] nom de fichier sans identifiant : {path.name}")
                continue
            identifier = match.group(1)
            if identifier in self.contracts:
                self.anomalies.append(
                    f"[a] identifiant dupliqué : {identifier} "
                    f"({self.contracts[identifier].path.name} et {path.name})"
                )
                continue
            text = path.read_text(encoding="utf-8")
            title_match = re.search(r"^#\s+(.+)$", text, re.M)
            title = title_match.group(1).strip() if title_match else path.stem
            status_match = _STATUS_RE.search(text)
            status = status_match.group(1) if status_match else None
            parent_match = _PARENT_RE.search(text) if kind == "story" else None
            self.contracts[identifier] = Contract(
                kind=kind,
                identifier=identifier,
                path=path,
                title=title,
                status=status,
                abandoned_marker="[ABANDONED]" in title,
                parent=parent_match.group(1) if parent_match else None,
            )

    def _load_epic_story_lists(self) -> None:
        """Extrait les lignes ``- [x] STORY-XXX`` de la section « Liste des Stories liées »."""
        section_re = re.compile(r"^##\s+Liste des Stories liées\s*$", re.M)
        for contract in self.contracts.values():
            if contract.kind != "epic":
                continue
            text = contract.path.read_text(encoding="utf-8")
            match = section_re.search(text)
            if not match:
                continue
            tail = text[match.end():]
            next_section = re.search(r"^##\s+", tail, re.M)
            section = tail[: next_section.start()] if next_section else tail
            for mark, story_id in _LIST_ITEM_RE.findall(section):
                contract.listed[story_id] = mark.strip().lower() == "x"

    def _load_registry(self) -> None:
        registry_path = self.backlog_dir / "identifiants.md"
        if not registry_path.is_file():
            self.anomalies.append("[c] registre .backlog/identifiants.md introuvable")
            return
        current_section = None
        for line in registry_path.read_text(encoding="utf-8").splitlines():
            header = re.match(r"^##\s+(.+)$", line)
            if header:
                current_section = header.group(1).strip().lower()
                continue
            row = re.match(r"^\|\s*(EPIC-\d{3}|%s|BUG-\d{3})\s*\|" % _STORY_ID, line)
            if not row:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 4:
                continue
            identifier, path, _date, status = cells[0], cells[1], cells[2], cells[3]
            self.registry[identifier] = {
                "path": path,
                "status": status,
                "section": current_section or "",
            }

    # ------------------------------------------------------------------ invariants

    def check(self) -> list[str]:
        if self.anomalies:
            pass  # anomalies de chargement, complétées ci-dessous
        self._check_statuses()
        self._check_registry()
        self._check_cross_references()
        self._check_epic_derived_status()
        self._check_epic_checkboxes()
        return self.anomalies

    def _check_statuses(self) -> None:
        valid = {"epic": EPIC_STATUSES, "story": STORY_STATUSES, "bug": BUG_STATUSES}
        for contract in self.contracts.values():
            if contract.status is None:
                self.anomalies.append(f"[b] champ '**Statut :**' absent : {contract.path}")
                continue
            if contract.status not in valid[contract.kind]:
                self.anomalies.append(
                    f"[b] statut invalide {contract.status!r} ({contract.kind}) : {contract.path.name}"
                )
                continue
            if contract.abandoned_marker and contract.status != "ABANDONED":
                self.anomalies.append(
                    f"[b] marqueur [ABANDONED] dans le titre mais statut {contract.status} : "
                    f"{contract.path.name}"
                )
            if contract.status == "ABANDONED" and not contract.abandoned_marker:
                self.anomalies.append(
                    f"[b] statut ABANDONED sans marqueur [ABANDONED] dans le titre : "
                    f"{contract.path.name}"
                )

    def _check_registry(self) -> None:
        for identifier, entry in self.registry.items():
            raw_path = entry["path"]
            status = entry["status"]
            exempt = (
                not raw_path
                or raw_path.startswith("—")
                or any(hint in status.lower() for hint in _REGISTRY_EXEMPT_HINTS)
            )
            if exempt:
                continue
            if not (self.root / raw_path).exists():
                self.anomalies.append(
                    f"[c] registre → disque : fichier absent pour {identifier} ({raw_path})"
                )
        for identifier, contract in self.contracts.items():
            if identifier not in self.registry:
                self.anomalies.append(
                    f"[c] disque → registre : contrat non inscrit au registre : {contract.path}"
                )
                continue
            registry_status = self.registry[identifier]["status"].split()[0] if self.registry[identifier]["status"] else ""
            if contract.status and registry_status and registry_status != contract.status:
                self.anomalies.append(
                    f"[c] statut registre {registry_status} ≠ statut disque {contract.status} "
                    f"pour {identifier}"
                )

    def _check_cross_references(self) -> None:
        epics = {c.identifier for c in self.contracts.values() if c.kind == "epic"}
        for contract in self.contracts.values():
            if contract.kind != "story":
                continue
            if contract.parent is None:
                self.anomalies.append(
                    f"[d] champ '**Epic Parent :**' absent : {contract.path.name}"
                )
            elif contract.parent not in epics:
                self.anomalies.append(
                    f"[d] Epic Parent inconnu {contract.parent} : {contract.path.name}"
                )
            else:
                epic = self.contracts[contract.parent]
                covered = (
                    contract.identifier in epic.listed
                    or (contract.parent_story_id and contract.parent_story_id in epic.listed)
                    or self._covered_by_substory(contract, epic)
                )
                if not covered:
                    self.anomalies.append(
                        f"[d] story non listée dans la section « Liste des Stories liées » "
                        f"de {epic.identifier} : {contract.identifier}"
                    )

    @staticmethod
    def _covered_by_substory(story: Contract, epic: Contract) -> bool:
        """Parent découpé représenté par sa descendance dans la liste de l'epic.

        Convention du dépôt : après découpe (split-story), le parent ABANDONED est retiré
        de la liste et remplacé par ses sous-stories (lignes « … — STORY-XXX découpée »).
        """
        if story.parent_story_id is not None:
            return False
        prefix = story.identifier + "."
        return any(listed_id.startswith(prefix) for listed_id in epic.listed)

    def _derived_epic_status(self, epic: Contract) -> str | None:
        """Statut dérivé d'une epic à partir de ses stories présentes sur disque.

        None si l'epic n'a aucune story sur disque (roadmap plannifiée ou epic fermée
        avec stories supprimées à la clôture) : pas de dérivation applicable.
        """
        statuses = [
            c.status
            for c in self.contracts.values()
            if c.kind == "story" and c.parent == epic.identifier
        ]
        if not statuses:
            return None
        if all(s in {"DONE", "ABANDONED"} for s in statuses):
            return "DONE"
        if any(s in {"IN_PROGRESS", "REVIEW"} for s in statuses):
            return "IN_PROGRESS"
        if any(s == "DONE" for s in statuses):
            return "IN_PROGRESS"  # travail entamé, il reste des stories ouvertes
        return "TODO"

    def _check_epic_derived_status(self) -> None:
        for contract in self.contracts.values():
            if contract.kind != "epic" or contract.status not in EPIC_STATUSES:
                continue
            derived = self._derived_epic_status(contract)
            if derived is None or contract.status == "ABANDONED":
                continue
            # BLOCKED reste une déclaration manuelle légitime (dépendance externe)
            if contract.status == "BLOCKED":
                continue
            if contract.status != derived:
                self.anomalies.append(
                    f"[e] statut epic {contract.status} incohérent avec ses stories "
                    f"(dérivé attendu : {derived}) : {contract.path.name}"
                )

    def _check_epic_checkboxes(self) -> None:
        for contract in self.contracts.values():
            if contract.kind != "epic":
                continue
            for story_id, checked in contract.listed.items():
                story = self.contracts.get(story_id)
                if story is None or story.status is None:
                    continue  # référence plannifiée ou historique sans contrat sur disque
                closed = story.status in {"DONE", "ABANDONED"}
                if closed and not checked:
                    self.anomalies.append(
                        f"[f] {story_id} est {story.status} mais sa case n'est pas cochée "
                        f"dans {contract.identifier}"
                    )
                elif not closed and checked:
                    self.anomalies.append(
                        f"[f] case cochée pour {story_id} ({story.status}) dans "
                        f"{contract.identifier}"
                    )

    # ------------------------------------------------------------------ kanban

    def _stories_of(self, epic_id: str, statuses: set[str]) -> list[Contract]:
        return sorted(
            (
                c
                for c in self.contracts.values()
                if c.kind == "story" and c.parent == epic_id and c.status in statuses
            ),
            key=lambda c: _sort_key(c.identifier),
        )

    def _epic_progress(self, epic: Contract) -> str:
        stories = [
            c.status
            for c in self.contracts.values()
            if c.kind == "story" and c.parent == epic.identifier
        ]
        if not stories:
            return ""
        done = sum(1 for s in stories if s == "DONE")
        return f" ({done}/{len(stories)} stories DONE)"

    def _clean_title(self, title: str, identifier: str | None = None) -> str:
        cleaned = title.replace("[ABANDONED]", "").strip()
        if identifier:
            # les titres H1 des contrats commencent par leur identifiant : éviter
            # la duplication « EPIC-001 : EPIC-001 : Titre » dans le kanban
            prefix = identifier + " : "
            if cleaned.startswith(identifier):
                cleaned = cleaned[len(identifier):].lstrip(":—- ").strip()
        return cleaned

    def render_kanban(self) -> str:
        epics = sorted(
            (c for c in self.contracts.values() if c.kind == "epic"),
            key=lambda c: c.identifier,
        )
        bugs = sorted(
            (c for c in self.contracts.values() if c.kind == "bug"),
            key=lambda c: c.identifier,
        )
        lines: list[str] = ["# KANBAN BOARD", "", KANBAN_NOTE, ""]

        # --- BACKLOG : epics non terminées, groupées, avec leurs stories TODO
        lines.append("## 📋 BACKLOG")
        lines.append("")
        backlog_epics = [e for e in epics if e.status in {"TODO", "IN_PROGRESS", "BLOCKED"}]
        for epic in backlog_epics:
            lines.append(f"### {epic.identifier} : {self._clean_title(epic.title, epic.identifier)}{self._epic_progress(epic)}")
            todo = self._stories_of(epic.identifier, {"TODO"})
            if todo:
                for story in todo:
                    lines.append(f"- [ ] {story.identifier} : {self._clean_title(story.title, story.identifier)}")
            else:
                lines.append("_(aucun contrat de story créé — voir la liste plannifiée dans l'epic)_")
            lines.append("")
        confirmed = [b for b in bugs if b.status == "CONFIRMED"]
        lines.append("### Bugs")
        if confirmed:
            for bug in confirmed:
                lines.append(f"- [ ] {bug.identifier} : {self._clean_title(bug.title, bug.identifier)}")
        else:
            lines.append("_(aucun)_")
        lines.append("")

        # --- IN PROGRESS : epics actives avec stories IN_PROGRESS / BLOCKED
        lines.append("## 🏗️ IN PROGRESS")
        lines.append("")
        active = [e for e in epics if e.status in {"IN_PROGRESS", "BLOCKED"}]
        if active:
            for epic in active:
                suffix = " # bloquée" if epic.status == "BLOCKED" else ""
                lines.append(
                    f"### {epic.identifier} : {self._clean_title(epic.title, epic.identifier)}"
                    f"{self._epic_progress(epic)}{suffix}"
                )
                ongoing = self._stories_of(epic.identifier, {"IN_PROGRESS"})
                blocked = self._stories_of(epic.identifier, {"BLOCKED"})
                for story in ongoing:
                    lines.append(f"- [~] {story.identifier} : {self._clean_title(story.title, story.identifier)}")
                for story in blocked:
                    lines.append(f"- [!] {story.identifier} : {self._clean_title(story.title, story.identifier)}  # bloqué")
                if not ongoing and not blocked:
                    lines.append("_(aucune story IN_PROGRESS/BLOCKED — stories ouvertes en BACKLOG)_")
                lines.append("")
        else:
            lines.append("_(vide)_")
            lines.append("")

        # --- REVIEW : liste plate stories + bugs
        lines.append("## 🚧 REVIEW")
        lines.append("")
        review = sorted(
            (c for c in self.contracts.values() if c.status == "REVIEW"),
            key=lambda c: _sort_key(c.identifier),
        )
        if review:
            for item in review:
                lines.append(f"- [?] {item.identifier} : {self._clean_title(item.title, item.identifier)}")
        else:
            lines.append("_(vide)_")
        lines.append("")

        # --- DONE : epics terminées (compact) + bugs DONE / WONT_FIX
        lines.append("## ✅ DONE")
        lines.append("")
        done_epics = [e for e in epics if e.status == "DONE"]
        done_bugs = [b for b in bugs if b.status in {"DONE", "WONT_FIX"}]
        if done_epics or done_bugs:
            for epic in done_epics:
                lines.append(f"- [x] {epic.identifier} : {self._clean_title(epic.title, epic.identifier)}{self._epic_progress(epic)}")
            for bug in done_bugs:
                lines.append(f"- [x] {bug.identifier} : {self._clean_title(bug.title, bug.identifier)}")
        else:
            lines.append("_(vide)_")
        lines.append("")

        return "\n".join(lines)

    def stats(self) -> str:
        counters: dict[str, dict[str, int]] = {"epic": {}, "story": {}, "bug": {}}
        for contract in self.contracts.values():
            bucket = counters[contract.kind]
            bucket[contract.status or "?"] = bucket.get(contract.status or "?", 0) + 1
        parts = []
        for kind in ("epic", "story", "bug"):
            detail = ", ".join(f"{k}={v}" for k, v in sorted(counters[kind].items())) or "aucun"
            parts.append(f"{kind}s : {detail}")
        return " | ".join(parts)


def _sort_key(identifier: str) -> tuple:
    """Clé de tri naturel : STORY-120.10 après STORY-120.2."""
    parts = re.split(r"[-.]", identifier)
    return tuple(int(p) if p.isdigit() else p for p in parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="backlog.py",
        description="Contrôle et régénère le backlog WindFlow (kanban généré, invariants).",
    )
    parser.add_argument(
        "mode",
        choices=("generate", "check"),
        help="generate : vérifie puis régénère .backlog/kanban.md ; check : lecture seule",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Racine du dépôt (défaut : parent du dossier scripts/)",
    )
    args = parser.parse_args(argv)

    corpus = BacklogCorpus(args.root)
    corpus.load()
    anomalies = corpus.check()

    if anomalies:
        print(f"❌ {len(anomalies)} anomalie(s) détectée(s) dans le backlog :")
        for anomaly in anomalies:
            print(f"  - {anomaly}")
        if args.mode == "generate":
            print("Aucune écriture effectuée (kanban non régénéré).")
        return 1

    print(f"✅ Backlog cohérent — {corpus.stats()}")

    if args.mode == "generate":
        kanban_path = args.root / ".backlog" / "kanban.md"
        kanban_path.write_text(corpus.render_kanban(), encoding="utf-8")
        print(f"📝 Kanban régénéré : {kanban_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
