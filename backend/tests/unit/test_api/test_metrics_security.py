"""Tests de sécurité de l'exposition Prometheus (STORY-172 — rules 40).

Évaluation de la checklist sécurité (story) : l'endpoint ``/metrics`` est
**volontairement sans auth** (exemption sondes spec 09 — scrape interne
Docker uniquement, jamais routé Internet). Les garanties testées ici :

1. l'exemption d'auth est le comportement **attendu** (documenté) ;
2. **aucune donnée sensible** dans les labels (tokens, mots de passe, query
   strings, noms d'utilisateur) après un run réel avec login ;
3. la cardinalité des labels HTTP est **bornée** (anti-DoS mémoire) ;
4. aucun router Traefik n'expose ``/api/v1/metrics`` vers l'extérieur
   (test de configuration — lecture des fichiers infra).
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings

# Racine du repo (backend/tests/unit/test_api/x.py → parents[4]).
REPO_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def prometheus_enabled():
    original = settings.prometheus_enabled
    settings.prometheus_enabled = True
    yield
    settings.prometheus_enabled = original


async def test_metrics_endpoint_no_auth_required_by_design(
    client: AsyncClient, prometheus_enabled
):
    """Exemption documentée : 200 **sans** header Authorization.

    C'est le comportement attendu (spec 09 — sondes/scrape), pas une faille :
    l'endpoint est consommé par Prometheus sur le réseau interne Docker
    uniquement (cf. test Traefik ci-dessous ; Prometheus behind basic-auth
    en prod).
    """
    client.headers.pop("Authorization", None)
    response = await client.get("/api/v1/metrics")
    assert response.status_code == 200
    assert "windflow_" in response.text


async def test_metrics_labels_contain_no_sensitive_data(
    client: AsyncClient, prometheus_enabled
):
    """Après trafic réel (login + lecture + 404), le body ne fuit rien.

    Sont vérifiés absents : le mot de passe de login, un éventuel token de
    query string, les valeurs de variables de déploiement, les noms
    d'utilisateurs.
    """
    from tests.conftest import _ROLE_USER_PASSWORD  # type: ignore[attr-defined]

    # Trafic réel : login (le mot de passe transite en form-data) + GET.
    await client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": _ROLE_USER_PASSWORD},
    )
    await client.get(f"/api/v1/stacks/{uuid.uuid4()}?token=LEAKED-TOKEN-XYZ")

    body = await client.get("/api/v1/metrics")
    text = body.text

    assert _ROLE_USER_PASSWORD not in text
    assert "LEAKED-TOKEN-XYZ" not in text
    assert "token" not in text.lower() or "LEAKED" not in text
    # Aucun username seedé ne doit apparaître dans les labels.
    assert "admin@example" not in text
    assert "windflow_http_requests_total" in text  # le scrape est bien peuplé


async def test_http_labels_cardinality_bounded(client: AsyncClient, prometheus_enabled):
    """N requêtes sur des IDs différents → UNE seule série ``{id}``.

    Sans normalisation, chaque UUID créerait une série — explosion mémoire
    (DoS) ; la cardinalité est bornée par construction (décision D4).
    """
    ids = [str(uuid.uuid4()) for _ in range(10)]
    for resource_id in ids:
        await client.get(f"/api/v1/stacks/{resource_id}")

    response = await client.get("/api/v1/metrics")
    text = response.text

    # Aucun UUID brut ne fuite dans les labels.
    for resource_id in ids:
        assert resource_id not in text
    # La série normalisée existe bien (une seule entrée par statut).
    assert 'path="/api/v1/stacks/{id}"' in text


async def test_circuit_breaker_series_exposed_via_metrics(
    client: AsyncClient, prometheus_enabled
):
    """STORY-251 AC 3 : après transitions réelles, les séries breaker sont exposées.

    Un circuit de test est ouvert (échecs réels via le breaker), puis le
    scrape doit contenir la gauge d'état (valeur 2 = open) et le compteur
    d'échecs cumulés.
    """
    from app.core.resilience import CircuitBreaker, get_circuit_breaker_registry

    get_circuit_breaker_registry().reset_all()
    breaker = CircuitBreaker("metrics-exposure-test", failure_threshold=1)

    async def boom() -> None:
        raise ConnectionError("transport down")

    with pytest.raises(ConnectionError):
        await breaker.call(boom)
    # failure_threshold=1 → circuit OPEN (transition loggée + gauge=2)

    response = await client.get("/api/v1/metrics")
    text = response.text
    assert "windflow_circuit_breaker_state" in text
    assert 'name="metrics-exposure-test"' in text
    assert "windflow_circuit_breaker_failures_total" in text

    get_circuit_breaker_registry().reset_all()


async def test_circuit_labels_contain_no_sensitive_data(
    client: AsyncClient, prometheus_enabled
):
    """STORY-251 : labels breaker restreints à des noms statiques/UUID.

    Les circuits légitimes sont ``docker_engine``, ``plugin_registry`` et
    ``ssh:{uuid}`` — jamais de hostname libre, de query string ni de
    secret. Après avoir forcé des échecs sur plusieurs circuits, le
    scrape ne doit exposer que des labels ``name`` conformes.
    """
    import re

    from app.core.resilience import CircuitBreaker

    valid_names = re.compile(
        r"^(docker_engine|plugin_registry|ssh:[0-9a-fA-F-]{36}|" r"[A-Za-z0-9._-]+)$"
    )

    async def boom() -> None:
        raise ConnectionError("secret-free transport error")

    for name in (
        "docker_engine",
        "plugin_registry",
        "ssh:550e8400-e29b-41d4-a716-446655440000",
    ):
        breaker = CircuitBreaker(name, failure_threshold=1)
        with pytest.raises(ConnectionError):
            await breaker.call(boom)

    response = await client.get("/api/v1/metrics")
    text = response.text

    # Chaque label name exposé est un nom de circuit légitime…
    for match in re.finditer(r'name="([^"]+)"', text):
        if match.group(1).startswith(("windflow", "docker", "plugin", "ssh:")):
            assert valid_names.match(match.group(1)), f"label illégal: {match.group(1)}"
    # …aucune donnée sensible ne transite dans les labels breaker
    assert "transport error" not in text  # jamais le message d'exception
    assert "token" not in text.lower() or "LEAKED" not in text
    assert 'name="ssh:my-server.example.com"' not in text  # pas de hostname libre


def test_metrics_not_exposed_by_traefik_routers():
    """Garde-fou d'exposition : aucun router Traefik ne matche /api/v1/metrics.

    Lecture des fichiers de configuration infra (traefik/, compose prod) :
    l'endpoint doit rester interne au réseau Docker (spec 15 — jamais routé
    vers Internet).
    """
    candidates = [
        REPO_ROOT / "infrastructure" / "docker" / "traefik",
        REPO_ROOT / "docker-compose.prod.yml",
        REPO_ROOT / "docker-compose.dev.yml",
        REPO_ROOT / "docker-compose.extensions.yml",
    ]

    scanned = 0
    for candidate in candidates:
        if candidate.is_dir():
            files = list(candidate.rglob("*"))
            paths = [f for f in files if f.is_file()]
        elif candidate.is_file():
            paths = [candidate]
        else:
            continue
        for path in paths:
            scanned += 1
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert "/api/v1/metrics" not in content, (
                f"route /api/v1/metrics exposée dans {path} — doit rester "
                "interne au réseau Docker"
            )

    # Le garde-fou doit avoir réellement scanné de la configuration.
    assert scanned >= 3, "aucune configuration Traefik/compose trouvée à scanner"
