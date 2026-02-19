"""
Tests d'intégration pour le middleware Correlation ID.

Vérifie que les IDs de corrélation sont générés, préservés
et transmis correctement dans les en-têtes HTTP.
"""

import pytest
import uuid
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_correlation_id_generated(client: AsyncClient):
    """Test qu'un correlation ID est généré si non fourni."""
    response = await client.get("/health")

    assert "X-Correlation-ID" in response.headers
    correlation_id = response.headers["X-Correlation-ID"]
    # Doit être un UUID valide
    uuid.UUID(correlation_id)


@pytest.mark.asyncio
async def test_correlation_id_preserved(client: AsyncClient):
    """Test qu'un correlation ID fourni est préservé."""
    test_id = "test-correlation-123"

    response = await client.get(
        "/health",
        headers={"X-Correlation-ID": test_id}
    )

    assert response.headers["X-Correlation-ID"] == test_id


@pytest.mark.asyncio
async def test_correlation_id_unique_per_request(client: AsyncClient):
    """Test que chaque requête reçoit un correlation ID unique."""
    response1 = await client.get("/health")
    response2 = await client.get("/health")

    id1 = response1.headers["X-Correlation-ID"]
    id2 = response2.headers["X-Correlation-ID"]

    assert id1 != id2


@pytest.mark.asyncio
async def test_correlation_id_on_different_endpoints(client: AsyncClient):
    """Test que le correlation ID est présent sur différents endpoints."""
    endpoints = ["/health", "/"]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert "X-Correlation-ID" in response.headers, \
            f"Missing X-Correlation-ID on {endpoint}"


@pytest.mark.asyncio
async def test_correlation_id_on_error_responses(client: AsyncClient):
    """Test que le correlation ID est présent même sur les réponses d'erreur."""
    response = await client.get("/api/v1/nonexistent-endpoint")

    assert "X-Correlation-ID" in response.headers
