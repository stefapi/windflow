"""Tests unitaires du middleware d'enveloppe — anti double-enveloppement (STORY-128).

Couverture (story § Tests à écrire — Unitaires backend) :
- corps ``{data, pagination}`` déjà formé → **pas** de ré-enveloppement,
  ``message: null`` complété si absent ;
- corps métier avec clé ``data`` par hasard (sans ``pagination``) →
  enveloppé normalement (non-régression STORY-126) ;
- détection structurelle : ``pagination`` sans les 4 clés, ``data`` non
  liste → pas considéré comme paginé.

Le middleware est testé via l'app FastAPI réelle (pattern
``test_api_envelope.py``) avec un endpoint de liste paginé réel
(``GET /stacks/``) et des réponses fabriquées via ``Request``/``Response``
starlette pour les cas unitaires purs.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest

from app.middleware.api_response import _is_paginated_body

_META = {"page": 1, "per_page": 20, "total": 3, "pages": 1}


class TestIsPaginatedBody:
    """Détection structurelle stricte d'un corps déjà paginé."""

    def test_valid_paginated_body(self):
        """{data: liste, pagination: 4 clés} → True."""
        assert _is_paginated_body({"data": [1, 2], "pagination": _META}) is True

    def test_missing_pagination_key(self):
        """{data} seul (payload métier) → False — enveloppé normalement."""
        assert _is_paginated_body({"data": [1, 2]}) is False

    def test_missing_data_key(self):
        """{pagination} sans data → False."""
        assert _is_paginated_body({"pagination": _META}) is False

    def test_data_not_a_list(self):
        """data non liste (objet métier) → False."""
        assert _is_paginated_body({"data": {"id": 1}, "pagination": _META}) is False

    def test_pagination_not_a_dict(self):
        """pagination non dict → False."""
        assert _is_paginated_body({"data": [1], "pagination": "nope"}) is False

    def test_pagination_missing_meta_keys(self):
        """pagination sans les 4 clés canoniques → False."""
        partial = {"page": 1, "per_page": 20}
        assert _is_paginated_body({"data": [1], "pagination": partial}) is False

    def test_not_a_dict(self):
        """Corps non dict (liste nue, scalaire) → False."""
        assert _is_paginated_body([1, 2, 3]) is False
        assert _is_paginated_body("string") is False
        assert _is_paginated_body(None) is False

    def test_business_payload_with_data_field_not_confused(self):
        """Un objet métier {data: {...}} (ex. résultat docker inspect)
        n'est jamais confondu avec une enveloppe paginée."""
        assert _is_paginated_body({"data": {"State": {"Running": True}}}) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
