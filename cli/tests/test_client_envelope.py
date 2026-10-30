"""Tests du client CLI contre l'API enveloppée spec 09 (STORY-126.3 + 128).

Couvre :
- unwrap tolérant : ``{"data": ..., "message": ...}`` → charge utile ;
- login : tokens stockés depuis l'enveloppe dépliée ;
- erreurs : ``error.message`` lu et affiché (fallback ``detail`` legacy) ;
- listes paginées : ``items`` lu post-unwrap (STORY-126.3) ;
- STORY-128 : ``get_paginated`` conserve le bloc ``pagination`` ;
- STORY-128 : ``get_all`` assemble les pages (multi-pages > 100) ;
- STORY-128 : commandes liste affichent le total réel de la collection.
"""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest


def _response(status_code: int, payload: dict) -> httpx.Response:
    """Construit une httpx.Response JSON."""
    return httpx.Response(
        status_code,
        content=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "http://testserver/api/v1/x"),
    )


class TestUnwrapSuccess:
    """2xx enveloppé → charge utile dépliée."""

    def test_unwrap_dict_payload(self, isolated_client):
        response = _response(
            200, {"data": {"id": "org-1", "name": "Main"}, "message": None}
        )
        result = isolated_client._handle_response(response)
        assert result == {"id": "org-1", "name": "Main"}

    def test_unwrap_list_payload(self, isolated_client):
        response = _response(
            200, {"data": [{"id": "a"}, {"id": "b"}], "message": "2 items"}
        )
        result = isolated_client._handle_response(response)
        assert result == [{"id": "a"}, {"id": "b"}]

    def test_unwrap_paginated_envelope(self, isolated_client):
        response = _response(
            200,
            {
                "data": [{"id": "u1"}],
                "pagination": {"page": 1, "per_page": 20, "total": 1, "pages": 1},
            },
        )
        result = isolated_client._handle_response(response)
        assert result == [{"id": "u1"}]

    def test_bare_payload_passthrough(self, isolated_client):
        """Corps nu pré-126.2 (pas d'enveloppe) → inchangé."""
        response = _response(200, {"id": "org-1", "name": "Main"})
        result = isolated_client._handle_response(response)
        assert result == {"id": "org-1", "name": "Main"}

    def test_business_payload_with_data_key_not_unwrapped(self, isolated_client):
        """Un payload métier contenant une clé ``data`` n'est pas déplié
        (détection stricte sur les clés d'enveloppe message/pagination)."""
        business = {"data": "2026-01-01", "value": 42}
        response = _response(200, business)
        result = isolated_client._handle_response(response)
        assert result == business


class TestLogin:
    """login() stocke les tokens depuis l'enveloppe dépliée."""

    def test_login_stores_tokens(self, isolated_client):
        tokens = {
            "access_token": "jwt-123",
            "refresh_token": "refresh-456",
            "token_type": "bearer",
            "expires_in": 3600,
        }
        login_response = _response(200, {"data": tokens, "message": None})
        me_payload = {"id": "u1", "username": "admin"}

        mock_http = MagicMock()
        mock_http.post.return_value = login_response
        isolated_client._client = mock_http

        with patch.object(isolated_client, "get", return_value=me_payload):
            result = isolated_client.login("admin", "pass")

        assert result["access_token"] == "jwt-123"
        isolated_client.session.set_tokens.assert_called_once_with(
            access_token="jwt-123",
            refresh_token="refresh-456",
            expires_in=3600,
        )
        # /auth/me interrogé pour les infos utilisateur (payload déplié)
        isolated_client.session.set_user_info.assert_called_once_with(me_payload)


class TestErrors:
    """Erreurs spec 09 → error.message affiché."""

    def test_error_message_extracted(self, isolated_client, capsys):
        response = _response(
            409,
            {
                "error": {"code": "CONFLICT", "message": "Slug déjà utilisé"},
                "correlation_id": "corr-1",
            },
        )
        mock_http = MagicMock()
        mock_http.get.return_value = response
        isolated_client._client = mock_http

        with pytest.raises(httpx.HTTPStatusError):
            isolated_client.get("/organizations")

        output = capsys.readouterr().out
        assert "Slug déjà utilisé" in output

    def test_error_detail_fallback(self, isolated_client, capsys):
        """Fallback legacy ``detail`` (pré-126.2) toujours lu."""
        response = _response(418, {"detail": "legacy message"})
        mock_http = MagicMock()
        mock_http.get.return_value = response
        isolated_client._client = mock_http

        with pytest.raises(httpx.HTTPStatusError):
            isolated_client.get("/organizations")

        output = capsys.readouterr().out
        assert "legacy message" in output

    def test_404_message_included(self, isolated_client, capsys):
        response = _response(
            404,
            {"error": {"code": "NOT_FOUND", "message": "Organization not found"}},
        )
        mock_http = MagicMock()
        mock_http.get.return_value = response
        isolated_client._client = mock_http

        with pytest.raises(httpx.HTTPStatusError):
            isolated_client.get("/organizations/unknown")

        output = capsys.readouterr().out
        assert "Organization not found" in output


class TestGetPaginated:
    """STORY-128 : get_paginated conserve le bloc ``pagination``."""

    def test_get_paginated_exposes_items_and_meta(self, isolated_client):
        """La nouvelle API livre la liste ET les métadonnées pagination."""
        response = _response(
            200,
            {
                "data": [{"id": "s-01"}, {"id": "s-02"}],
                "pagination": {"page": 2, "per_page": 20, "total": 25, "pages": 2},
                "message": None,
            },
        )
        mock_http = MagicMock()
        mock_http.get.return_value = response
        isolated_client._client = mock_http

        result = isolated_client.get_paginated("/stacks", page=2)

        assert result.items == [{"id": "s-01"}, {"id": "s-02"}]
        assert result.pagination == {
            "page": 2,
            "per_page": 20,
            "total": 25,
            "pages": 2,
        }
        assert result.total == 25

    def test_get_paginated_sends_page_params(self, isolated_client):
        """page/per_page sont envoyés au serveur (pas de skip/limit legacy)."""
        response = _response(
            200,
            {
                "data": [],
                "pagination": {"page": 1, "per_page": 50, "total": 0, "pages": 0},
            },
        )
        mock_http = MagicMock()
        mock_http.get.return_value = response
        isolated_client._client = mock_http

        isolated_client.get_paginated("/hosts", params={"status": "up"}, per_page=50)

        call = mock_http.get.call_args
        sent_params = call.kwargs.get("params") or call[1]["params"]
        assert sent_params["page"] == 1
        assert sent_params["per_page"] == 50
        assert sent_params["status"] == "up"

    def test_get_paginated_bare_list_transition(self, isolated_client):
        """Liste nue pré-128 → métadonnées déduites localement (total=len)."""
        response = _response(200, [{"id": "a"}, {"id": "b"}])
        mock_http = MagicMock()
        mock_http.get.return_value = response
        isolated_client._client = mock_http

        result = isolated_client.get_paginated("/organizations")

        assert result.items == [{"id": "a"}, {"id": "b"}]
        assert result.total == 2
        assert result.pagination["pages"] == 1


class TestGetAll:
    """STORY-128 : get_all assemble les pages d'une liste complète."""

    @staticmethod
    def _page(
        items: list, page: int, pages: int, total: int, per_page: int = 100
    ) -> dict:
        return {
            "data": items,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
            },
        }

    def test_get_all_fetches_every_page(self, isolated_client):
        """N > per_page → 2 requêtes, affichage fusionné sans doublon."""
        page1 = self._page([{"id": f"t-{i:03d}"} for i in range(100)], 1, 2, 102)
        page2 = self._page([{"id": "t-100"}, {"id": "t-101"}], 2, 2, 102)
        responses = [
            _response(200, page1),
            _response(200, page2),
        ]

        mock_http = MagicMock()
        mock_http.get.side_effect = responses
        isolated_client._client = mock_http

        result = isolated_client.get_all("/hosts")

        assert mock_http.get.call_count == 2
        assert len(result.items) == 102
        assert [item["id"] for item in result.items][:2] == ["t-000", "t-001"]
        assert result.items[-1]["id"] == "t-101"
        # total = total réel de la collection, pas len(items) de la dernière page
        assert result.total == 102

    def test_get_all_single_page_short_list(self, isolated_client):
        """Liste tenant sur une page → 1 seule requête."""
        body = self._page([{"id": "only"}], 1, 1, 1)
        mock_http = MagicMock()
        mock_http.get.return_value = _response(200, body)
        isolated_client._client = mock_http

        result = isolated_client.get_all("/organizations")

        assert mock_http.get.call_count == 1
        assert result.items == [{"id": "only"}]
        assert result.total == 1


class TestListCommands:
    """Commandes liste : lecture post-unwrap + total réel (STORY-128)."""

    def test_handle_list_reads_items_legacy_shape(self, capsys):
        """Transition : fallback {items, ...} legacy pré-128 toléré."""
        from cli.commands.org import handle_list

        paginated = {
            "items": [
                {
                    "id": "org-1",
                    "name": "Main",
                    "slug": "main",
                    "is_active": True,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ],
            "total": 1,
            "skip": 0,
            "limit": 20,
        }
        with patch("cli.commands.org.api_client") as mock_client:
            mock_client.get_all.return_value = MagicMock(
                items=paginated["items"], total=1
            )
            exit_code = handle_list(output_format="table")

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Main" in output
        assert "Total: 1 organisation(s)" in output

    def test_handle_list_shows_real_total_multi_page(self, capsys):
        """STORY-128 : « N résultats affichés sur T » — total réel exposé."""
        from cli.commands.org import handle_list

        items = [
            {
                "id": f"org-{i}",
                "name": f"Org {i}",
                "slug": f"org-{i}",
                "is_active": True,
                "created_at": "2026-01-01T00:00:00Z",
            }
            for i in range(3)
        ]
        with patch("cli.commands.org.api_client") as mock_client:
            mock_client.get_all.return_value = MagicMock(items=items, total=150)
            exit_code = handle_list(output_format="table")

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Total: 150 organisation(s)" in output

    def test_deploy_list_uses_get_all(self, capsys):
        """STORY-128 : deploy list passe par get_all (multi-pages)."""
        from cli.commands.deploy import handle_list as deploy_list

        deployments = [
            {
                "id": f"dep-{i}",
                "name": f"Dep {i}",
                "stack_name": "web",
                "status": "completed",
                "created_at": "2026-01-01T00:00:00Z",
            }
            for i in range(2)
        ]
        with patch("cli.commands.deploy.api_client") as mock_client:
            mock_client.get_all.return_value = MagicMock(items=deployments, total=120)
            exit_code = deploy_list(output_format="table")

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Total: 120 déploiement(s)" in output
        mock_client.get_all.assert_called_once()
