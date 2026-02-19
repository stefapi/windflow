"""
Tests d'intégration pour les security headers middleware.

Vérifie que tous les en-têtes de sécurité sont présents
et correctement configurés dans les réponses HTTP.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_csp_header_present(client: AsyncClient):
    """Test que l'en-tête CSP est présent."""
    response = await client.get("/health")

    assert "Content-Security-Policy" in response.headers
    assert "'self'" in response.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_csp_header_contains_required_directives(client: AsyncClient):
    """Test que le CSP contient toutes les directives requises."""
    response = await client.get("/health")
    csp = response.headers.get("Content-Security-Policy", "")

    required_directives = [
        "default-src",
        "script-src",
        "style-src",
        "img-src",
        "connect-src",
        "frame-ancestors",
        "base-uri",
        "form-action",
    ]

    for directive in required_directives:
        assert directive in csp, f"Missing CSP directive: {directive}"


@pytest.mark.asyncio
async def test_security_headers_complete(client: AsyncClient):
    """Test que tous les en-têtes de sécurité sont présents."""
    response = await client.get("/health")

    required_headers = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "X-XSS-Protection",
        "Referrer-Policy",
        "Permissions-Policy",
    ]

    for header in required_headers:
        assert header in response.headers, f"Missing security header: {header}"


@pytest.mark.asyncio
async def test_x_content_type_options_value(client: AsyncClient):
    """Test la valeur de X-Content-Type-Options."""
    response = await client.get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.asyncio
async def test_x_frame_options_value(client: AsyncClient):
    """Test la valeur de X-Frame-Options."""
    response = await client.get("/health")

    assert response.headers["X-Frame-Options"] in ("DENY", "SAMEORIGIN")


@pytest.mark.asyncio
async def test_x_xss_protection_value(client: AsyncClient):
    """Test la valeur de X-XSS-Protection."""
    response = await client.get("/health")

    assert response.headers["X-XSS-Protection"] == "1; mode=block"


@pytest.mark.asyncio
async def test_referrer_policy_value(client: AsyncClient):
    """Test la valeur de Referrer-Policy."""
    response = await client.get("/health")

    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.mark.asyncio
async def test_permissions_policy_value(client: AsyncClient):
    """Test la valeur de Permissions-Policy."""
    response = await client.get("/health")

    permissions = response.headers["Permissions-Policy"]
    assert "geolocation=()" in permissions
    assert "microphone=()" in permissions
    assert "camera=()" in permissions


@pytest.mark.asyncio
async def test_security_headers_on_api_endpoints(client: AsyncClient):
    """Test que les security headers sont présents sur les endpoints API."""
    response = await client.get("/")

    assert "X-Content-Type-Options" in response.headers
    assert "X-Frame-Options" in response.headers
    assert "Referrer-Policy" in response.headers
