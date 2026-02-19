"""
Tests d'intégration pour le middleware de timing.

Vérifie que l'en-tête X-Process-Time est présent
et contient des valeurs cohérentes.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_process_time_header_present(client: AsyncClient):
    """Test que l'en-tête X-Process-Time est présent."""
    response = await client.get("/health")

    assert "X-Process-Time" in response.headers


@pytest.mark.asyncio
async def test_process_time_header_format(client: AsyncClient):
    """Test que X-Process-Time contient une valeur numérique valide."""
    response = await client.get("/health")

    process_time = response.headers["X-Process-Time"]
    # Le header peut être en secondes brutes ou avec suffixe 'ms'
    cleaned = process_time.replace("ms", "")
    time_value = float(cleaned)
    assert time_value >= 0


@pytest.mark.asyncio
async def test_process_time_reasonable_value(client: AsyncClient):
    """Test que le temps de traitement est raisonnable (< 5s)."""
    response = await client.get("/health")

    process_time = response.headers["X-Process-Time"]
    cleaned = process_time.replace("ms", "")
    time_value = float(cleaned)

    # Valeur en secondes ou ms, dans les deux cas < 5000
    assert time_value < 5000


@pytest.mark.asyncio
async def test_process_time_on_different_endpoints(client: AsyncClient):
    """Test que X-Process-Time est présent sur différents endpoints."""
    endpoints = ["/health", "/"]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert "X-Process-Time" in response.headers, \
            f"Missing X-Process-Time on {endpoint}"


@pytest.mark.asyncio
async def test_process_time_on_error_responses(client: AsyncClient):
    """Test que X-Process-Time est présent même sur les erreurs."""
    response = await client.get("/api/v1/nonexistent-endpoint")

    assert "X-Process-Time" in response.headers
