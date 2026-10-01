"""Tests unitaires du helper pagination canonique spec 09 (STORY-128).

Couverture (story § Tests à écrire — Unitaires backend) :
- :func:`build_meta` : ``total=0`` → ``pages=0`` ; ``total=21, per_page=20``
  → ``pages=2`` ; arrondi ceil exact ;
- :func:`paginate_sequence` : page 1, dernière page, page au-delà →
  ``data: []`` + méta exactes, slicing sans chevauchement ;
- :class:`PaginationQuery` : bornes OpenAPI (``per_page`` max 100,
  ``page`` min 1, défauts 1/20) — validées sur les métadonnées des
  objets ``Query`` (la validation 422 runtime est couverte en
  intégration).

Fonctions pures — cible ~100 % de couverture (rules 35).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from app.helper.pagination import (
    DEFAULT_PAGE,
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    PaginationQuery,
    build_meta,
    paginate_sequence,
)


class TestBuildMeta:
    """build_meta : pages = ceil(total/per_page), 0 si total=0."""

    def test_total_zero_pages_zero(self):
        """total=0 → pages=0 (convention spec 09)."""
        meta = build_meta(page=1, per_page=20, total=0)
        assert meta.pages == 0
        assert meta.total == 0
        assert meta.page == 1
        assert meta.per_page == 20

    def test_total_21_per_page_20_pages_2(self):
        """total=21, per_page=20 → pages=2 (ceil)."""
        meta = build_meta(page=1, per_page=20, total=21)
        assert meta.pages == 2

    def test_exact_multiple_no_extra_page(self):
        """total=40, per_page=20 → pages=2 (pas de page vide finale)."""
        meta = build_meta(page=2, per_page=20, total=40)
        assert meta.pages == 2

    def test_single_item_single_page(self):
        """total=1, per_page=20 → pages=1."""
        assert build_meta(page=1, per_page=20, total=1).pages == 1

    def test_per_page_1_pages_equals_total(self):
        """per_page=1 → pages == total."""
        assert build_meta(page=3, per_page=1, total=7).pages == 7

    def test_meta_fields_roundtrip(self):
        """Les 4 champs page/per_page/total/pages sont transportés."""
        meta = build_meta(page=2, per_page=10, total=35)
        assert meta.model_dump() == {
            "page": 2,
            "per_page": 10,
            "total": 35,
            "pages": 4,
        }


class TestPaginateSequence:
    """paginate_sequence : slicing mémoire pour sources non-SQL."""

    def test_first_page(self):
        """Page 1 → premiers per_page éléments, total=len complet."""
        items = list(range(50))
        result = paginate_sequence(items, page=1, per_page=20)
        assert result.data == list(range(20))
        assert result.pagination.total == 50
        assert result.pagination.pages == 3
        assert result.pagination.page == 1

    def test_last_partial_page(self):
        """50 items, per_page=20 → page 3 contient les 10 restants."""
        result = paginate_sequence(list(range(50)), page=3, per_page=20)
        assert result.data == list(range(40, 50))
        assert result.pagination.total == 50
        assert result.pagination.pages == 3

    def test_beyond_last_page_returns_empty_with_exact_meta(self):
        """Page au-delà de la dernière → 200 sémantique : data=[] + méta exactes."""
        result = paginate_sequence(list(range(5)), page=4, per_page=20)
        assert result.data == []
        assert result.pagination.total == 5
        assert result.pagination.pages == 1
        assert result.pagination.page == 4

    def test_no_overlap_between_pages(self):
        """Slicing sans chevauchement ni trou sur l'ensemble des pages."""
        items = list(range(45))
        collected: list[int] = []
        for page in (1, 2, 3):
            collected.extend(paginate_sequence(items, page=page, per_page=20).data)
        assert collected == items

    def test_empty_sequence(self):
        """Séquence vide → data=[], total=0, pages=0."""
        result = paginate_sequence([], page=1, per_page=20)
        assert result.data == []
        assert result.pagination.total == 0
        assert result.pagination.pages == 0

    def test_filtered_sequence_total_reflects_input(self):
        """Le total reflète la séquence FILTRÉE passée en entrée (filtres
        category/query appliqués en amont — décision d'analyse)."""
        filtered = ["a", "b"]
        result = paginate_sequence(filtered, page=1, per_page=20)
        assert result.pagination.total == 2

    def test_exact_page_boundary(self):
        """40 items, per_page=20 → page 2 pleine (pas de page 3 de données)."""
        result = paginate_sequence(list(range(40)), page=2, per_page=20)
        assert result.data == list(range(20, 40))


def _numeric_constraints(field) -> dict:
    """Extrait les contraintes ge/le des métadonnées pydantic d'un Query."""
    constraints = {}
    for meta in field.metadata:
        name = type(meta).__name__.lower()
        if name in ("ge", "le", "gt", "lt"):
            constraints[name] = getattr(meta, name)
    return constraints


class TestPaginationQuery:
    """PaginationQuery : bornes et défauts exposés à OpenAPI (AC 2).

    Les contraintes ``ge``/``le`` sont transportées dans ``metadata``
    (objets ``Ge``/``Le`` pydantic — FastAPI n'expose pas d'attribut
    direct). La validation runtime 422 est couverte en intégration.
    """

    def test_defaults(self):
        """Défauts canoniques : page=1, per_page=20 (spec 09)."""
        assert DEFAULT_PAGE == 1
        assert DEFAULT_PER_PAGE == 20
        assert PaginationQuery.page.default == 1
        assert PaginationQuery.per_page.default == 20

    def test_page_lower_bound(self):
        """page >= 1 (pagination 1-indexée — page=0 → 422)."""
        constraints = _numeric_constraints(PaginationQuery.page)
        assert constraints.get("ge") == 1

    def test_per_page_bounds(self):
        """per_page : ge=1, le=100 (dépassement → 422, pas de clamp)."""
        constraints = _numeric_constraints(PaginationQuery.per_page)
        assert constraints.get("ge") == 1
        assert constraints.get("le") == MAX_PER_PAGE == 100

    def test_descriptions_documented(self):
        """Descriptions OpenAPI présentes (defaults visibles — AC 2)."""
        assert PaginationQuery.page.description
        assert PaginationQuery.per_page.description
        assert "422" in PaginationQuery.per_page.description


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
