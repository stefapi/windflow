"""Helper de pagination canonique spec 09 (STORY-128).

Fournit le socle commun partagé par **tous** les endpoints de liste :

- :class:`PaginationQuery` : query params ``?page=&per_page=`` validés
  (``Query(1, ge=1)`` / ``Query(20, ge=1, le=100)``) avec descriptions
  et examples OpenAPI — bornes tranchées par l'analyse (dépassement →
  ``422``, pas de clamp silencieux) ;
- :func:`build_meta` : construction de :class:`PaginationMeta`
  (``pages = ceil(total/per_page)``, ``0`` si ``total=0``) ;
- :func:`paginate_sequence` : slicing mémoire pour les sources non-SQL
  (Docker daemon, registry YAML filesystem…) — ``total = len(liste)``.

Fonctions pures, type hints complets (rules 30) — pattern fichier :
``helper/permissions.py``.

Décisions d'analyse (STORY-128, « Décisions tranchées ») :

=====================  ====================================================
Question               Décision
=====================  ====================================================
``per_page`` > 100     ``422`` via ``Query(ge=1, le=100)``
``page`` au-delà        ``200`` + ``data: []`` + métadonnées exactes
``page=0``/négatif      ``422`` via ``Query(ge=1)`` (pagination 1-indexée)
Défauts                ``page=1``, ``per_page=20``
Sources non SQL        ``total = len(liste)`` + slicing mémoire
``total`` SQL           ``COUNT`` avec les mêmes filtres que la liste
=====================  ====================================================
"""

from __future__ import annotations

import math
from typing import Any, List, Sequence

from fastapi import Query

from ..schemas.common import PaginatedResponse, PaginationMeta

# Bornes canoniques spec 09 (STORY-128 AC 2) — utilisées par les
# déclarations Query() et testées unitairement.
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


class PaginationQuery:
    """Déclarations ``Query`` canoniques pour les paramètres de pagination.

    À utiliser dans les signatures d'endpoints de liste (STORY-128) :

    .. code-block:: python

        async def list_things(
            page: int = PaginationQuery.page,
            per_page: int = PaginationQuery.per_page,
        ):
            ...

    Les valeurs par défaut (``page=1``, ``per_page=20``) et les bornes
    (``page >= 1``, ``1 <= per_page <= 100``) sont visibles dans OpenAPI
    (descriptions + examples) — AC 2 « defaults visibles ».
    """

    page: int = Query(
        DEFAULT_PAGE,
        ge=1,
        description=(
            "Numéro de la page demandée (1-indexé). Au-delà de la "
            "dernière page : 200 avec `data: []` et métadonnées exactes."
        ),
        json_schema_extra={"example": 1},
    )

    per_page: int = Query(
        DEFAULT_PER_PAGE,
        ge=1,
        le=MAX_PER_PAGE,
        description=(
            "Nombre d'éléments par page (1-100). Valeur au-delà de 100 "
            "→ 422 VALIDATION_ERROR (pas de clamp silencieux)."
        ),
        json_schema_extra={"example": 20},
    )


def build_meta(page: int, per_page: int, total: int) -> PaginationMeta:
    """Construit les métadonnées de pagination spec 09.

    Args:
        page: Page courante (1-indexée).
        per_page: Taille de page.
        total: Nombre total d'éléments disponibles (filtrés/scopés).

    Returns:
        :class:`PaginationMeta` avec ``pages = ceil(total / per_page)``
        (``0`` si ``total == 0``).

    Examples:
        >>> build_meta(1, 20, 0).pages
        0
        >>> build_meta(1, 20, 21).pages
        2
        >>> build_meta(2, 20, 21).page
        2
    """
    pages = math.ceil(total / per_page) if per_page > 0 else 0
    return PaginationMeta(page=page, per_page=per_page, total=total, pages=pages)


def paginate_sequence(
    items: Sequence[Any], page: int, per_page: int
) -> PaginatedResponse:
    """Pagine une séquence en mémoire (sources non-SQL — STORY-128).

    ``total = len(items)`` (aucun ``COUNT`` possible sur Docker daemon
    ou filesystem YAML) ; le slicing ``(page - 1) * per_page`` reproduit
    la sémantique offset/limit existante. Une page au-delà de la
    dernière retourne ``data: []`` avec des métadonnées exactes.

    Args:
        items: Séquence complète **déjà filtrée** (les filtres
            ``category``/``query`` éventuels doivent être appliqués
            AVANT l'appel — ``total`` reflète la liste filtrée).
        page: Page courante (1-indexée, validée en amont par ``Query``).
        per_page: Taille de page (bornée par ``Query(le=100)``).

    Returns:
        :class:`PaginatedResponse` prête à être retournée par le handler.
    """
    total = len(items)
    offset = (page - 1) * per_page
    page_items: List[Any] = list(items[offset : offset + per_page])
    return PaginatedResponse(
        data=page_items,
        pagination=build_meta(page=page, per_page=per_page, total=total),
    )
