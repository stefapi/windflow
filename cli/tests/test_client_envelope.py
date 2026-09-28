"""Tests du client CLI contre l'API enveloppée spec 09 (STORY-126.3).

Couvre :
- unwrap tolérant : ``{"data": ..., "message": ...}`` → charge utile ;
- login : tokens stockés depuis l'enveloppe dépliée ;
- erreurs : ``error.message`` lu et affiché (fallback ``detail`` legacy) ;
- listes paginées : ``items`` lu post-unwrap.
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


class TestListCommands:
    """Les commandes list lisent `items` post-unwrap (pas `data`)."""

    def test_handle_list_reads_items(self, capsys):
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
            mock_client.get.return_value = paginated
            exit_code = handle_list(output_format="table")

        assert exit_code == 0
        output = capsys.readouterr().out
        assert "Main" in output
        assert "Total: 1 organisation(s)" in output
