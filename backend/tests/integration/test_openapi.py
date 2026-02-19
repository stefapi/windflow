"""
Tests d'intégration pour la documentation OpenAPI.

Vérifie que le schéma OpenAPI est valide, que tous les endpoints
critiques sont documentés, et que Scalar est accessible.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_openapi_schema_valid(client: AsyncClient):
    """Test que le schéma OpenAPI est un JSON valide."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()

    assert "openapi" in schema
    assert "info" in schema
    assert "paths" in schema


@pytest.mark.asyncio
async def test_openapi_info_complete(client: AsyncClient):
    """Test que les informations de l'API sont complètes."""
    response = await client.get("/openapi.json")
    schema = response.json()
    info = schema["info"]

    assert "title" in info
    assert "version" in info
    assert "description" in info
    assert len(info["description"]) > 50  # Description substantielle


@pytest.mark.asyncio
async def test_openapi_has_servers(client: AsyncClient):
    """Test que les serveurs sont configurés."""
    response = await client.get("/openapi.json")
    schema = response.json()

    assert "servers" in schema
    assert len(schema["servers"]) >= 1
    assert "url" in schema["servers"][0]


@pytest.mark.asyncio
async def test_all_critical_endpoints_documented(client: AsyncClient):
    """Test que les endpoints critiques sont documentés."""
    response = await client.get("/openapi.json")
    schema = response.json()

    critical_paths = [
        "/api/v1/auth/login",
        "/health",
    ]

    for path in critical_paths:
        assert path in schema["paths"], f"Missing documentation for {path}"


@pytest.mark.asyncio
async def test_openapi_tags_present(client: AsyncClient):
    """Test que les tags OpenAPI sont définis."""
    response = await client.get("/openapi.json")
    schema = response.json()

    assert "tags" in schema
    tag_names = [tag["name"] for tag in schema["tags"]]

    expected_tags = ["auth", "deployments", "stacks", "health"]
    for tag in expected_tags:
        assert tag in tag_names, f"Missing OpenAPI tag: {tag}"


@pytest.mark.asyncio
async def test_openapi_components_schemas(client: AsyncClient):
    """Test que les schémas de composants sont présents."""
    response = await client.get("/openapi.json")
    schema = response.json()

    assert "components" in schema
    assert "schemas" in schema["components"]
    schemas = schema["components"]["schemas"]

    # Vérifier que les schémas principaux sont documentés
    expected_schemas = ["DeploymentCreate", "DeploymentResponse"]
    for expected in expected_schemas:
        assert expected in schemas, f"Missing schema: {expected}"


@pytest.mark.asyncio
async def test_scalar_docs_accessible(client: AsyncClient):
    """Test que la page Scalar est accessible."""
    response = await client.get("/docs")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_swagger_docs_accessible(client: AsyncClient):
    """Test que Swagger UI est toujours accessible."""
    response = await client.get("/swagger")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_redoc_accessible(client: AsyncClient):
    """Test que ReDoc est toujours accessible."""
    response = await client.get("/redoc")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_contact_info(client: AsyncClient):
    """Test que les informations de contact sont présentes."""
    response = await client.get("/openapi.json")
    schema = response.json()
    info = schema["info"]

    assert "contact" in info
    assert "name" in info["contact"]


@pytest.mark.asyncio
async def test_openapi_license_info(client: AsyncClient):
    """Test que les informations de licence sont présentes."""
    response = await client.get("/openapi.json")
    schema = response.json()
    info = schema["info"]

    assert "license" in info
    assert "name" in info["license"]
