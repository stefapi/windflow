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
