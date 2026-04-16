"""
Tests unitaires pour l'endpoint GET /api/v1/stats/stacks/{stack_id}.

Teste les statistiques détaillées par stack :
- Authentification (401 sans token)
- Réponse correcte avec authentification
- Comportement pour une stack inexistante
- Validation du schéma StackStatsResponse
"""

import pytest


# =============================================================================
# Fixture : désactiver le mode dev pour forcer l'auth JWT
# =============================================================================


@pytest.fixture(autouse=True)
def force_real_auth(monkeypatch) -> None:
    """
    Force disable_auth=False pour tous les tests de ce module.

    En mode test, l'env peut avoir DISABLE_AUTH=true, ce qui fait que
    get_current_user cherche un superadmin en base → 500 si inexistant.
    En forçant disable_auth=False, l'auth JWT s'applique normalement.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "disable_auth", False)


# =============================================================================
# Tests /stats/stacks/{stack_id}
# =============================================================================


class TestGetStackStatsEndpoint:
    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client) -> None:
        """Sans token JWT, l'endpoint retourne 401."""
        response = await client.get("/api/v1/stats/stacks/some-stack-id")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_authenticated_returns_200(self, authenticated_client) -> None:
        """Avec un token JWT valide, l'endpoint retourne 200."""
        response = await authenticated_client.get(
            "/api/v1/stats/stacks/some-stack-id"
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_stack_returns_empty_data(
        self, authenticated_client
    ) -> None:
        """Pour une stack inexistante, l'endpoint retourne des zéros."""
        response = await authenticated_client.get(
            "/api/v1/stats/stacks/unknown-stack-id"
        )
        assert response.status_code == 200
        body = response.json()
        # Pas de déploiements pour une stack inconnue
        assert body["deployments_by_status"] == {}
        assert body["deployments_last_30_days"] == 0

    @pytest.mark.asyncio
    async def test_response_matches_schema(self, authenticated_client) -> None:
        """La réponse contient les champs attendus par StackStatsResponse."""
        response = await authenticated_client.get(
            "/api/v1/stats/stacks/some-stack-id"
        )
        assert response.status_code == 200
        body = response.json()

        # Vérifier la présence des deux champs du schéma
        assert "deployments_by_status" in body
        assert "deployments_last_30_days" in body

        # Vérifier les types
        assert isinstance(body["deployments_by_status"], dict)
        assert isinstance(body["deployments_last_30_days"], int)
        assert body["deployments_last_30_days"] >= 0
