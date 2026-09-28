"""Fixtures partagées des tests CLI (STORY-126.3)."""

import sys
from pathlib import Path

# Rendre le package `cli` importable quel que soit le rootdir pytest
# (la cible Makefile `cli-test` lance pytest sur cli/tests/ sans installer
# le package — pas de PYTHONPATH garanti).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from unittest.mock import MagicMock, patch

import pytest

from cli.client import APIClient


@pytest.fixture
def isolated_client(tmp_path, monkeypatch):
    """APIClient avec session/config isolées du HOME réel.

    Évite toute écriture dans ~/.windflow pendant les tests — la session
    pointe vers un tmp_path jetable.
    """
    with patch("cli.config.config_manager") as mock_config, patch(
        "cli.client.session"
    ) as mock_session:
        mock_config.load.return_value = MagicMock(
            api_url="http://testserver",
            api_timeout=5,
            api_prefix="/api/v1",
        )
        client = APIClient()
        # session mockée : set_tokens/set_user_info espionnés, pas d'écriture
        client.session = mock_session
        yield client
