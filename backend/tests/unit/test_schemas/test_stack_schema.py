"""Tests de validation des schémas Stack (STORY-166.4 — origin/git_url/environment_id).

Couvre (cf. story § Tests à écrire) :
- ``git_url`` : ``"not-a-url"`` → ``ValidationError`` (422) ;
  ``https://git.example.com/org/repo.git`` → valide ; ``None`` → valide
  (optionnel) ; chemin relatif/ftp rejetés (pas de surface SSRF — aucun
  fetch à ce stade) ;
- ``origin`` : hors ``{managed, adopted, external}`` → rejeté ;
- ``environment_id`` : non-UUID → rejeté, UUID canonique → ``str``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.enums.host import WorkloadOrigin
from app.schemas.stack import StackCreate, StackUpdate

_VALID_URL = "https://git.example.com/org/repo.git"


def _base_payload(**overrides) -> dict:
    payload: dict = {
        "name": "Test Stack",
        "template": {"version": "3.8", "services": {"web": {"image": "nginx"}}},
        "organization_id": "org-001",
    }
    payload.update(overrides)
    return payload


class TestGitUrlValidation:
    """git_url — URL http/https stricte (D2, règle 40)."""

    def test_valid_https_url_is_accepted(self) -> None:
        stack = StackCreate(**_base_payload(git_url=_VALID_URL))
        assert stack.git_url == _VALID_URL

    def test_none_is_accepted(self) -> None:
        """Optionnel — None valide."""
        stack = StackCreate(**_base_payload(git_url=None))
        assert stack.git_url is None

    def test_not_a_url_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StackCreate(**_base_payload(git_url="not-a-url"))

    def test_relative_path_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StackCreate(**_base_payload(git_url="./local/repo"))

    def test_ftp_scheme_is_rejected(self) -> None:
        """Seuls http/https sont acceptés (pas de schéma exotique)."""
        with pytest.raises(ValidationError):
            StackCreate(**_base_payload(git_url="ftp://git.example.com/repo.git"))

    def test_update_rejects_invalid_url(self) -> None:
        with pytest.raises(ValidationError):
            StackUpdate(git_url="not-a-url")

    def test_update_accepts_valid_url(self) -> None:
        update = StackUpdate(git_url=_VALID_URL)
        assert update.git_url == _VALID_URL


class TestOriginValidation:
    """origin — valeurs de l'enum WorkloadOrigin uniquement."""

    def test_default_origin_is_managed(self) -> None:
        """Création manuelle → ``managed`` par défaut (AC 1)."""
        stack = StackCreate(**_base_payload())
        assert stack.origin is WorkloadOrigin.MANAGED

    @pytest.mark.parametrize(
        "value",
        ["managed", "adopted", "external"],
    )
    def test_valid_origins_are_accepted(self, value: str) -> None:
        stack = StackCreate(**_base_payload(origin=value))
        assert stack.origin == value

    @pytest.mark.parametrize("value", ["unknown", "MANAGED", "", "imported"])
    def test_invalid_origins_are_rejected(self, value: str) -> None:
        with pytest.raises(ValidationError):
            StackCreate(**_base_payload(origin=value))


class TestEnvironmentIdValidation:
    """environment_id — UUID stricte."""

    def test_valid_uuid_is_canonicalized_to_str(self) -> None:
        raw = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        stack = StackCreate(**_base_payload(environment_id=raw))
        assert stack.environment_id == raw
        assert isinstance(stack.environment_id, str)

    def test_non_uuid_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StackCreate(**_base_payload(environment_id="org-001"))

    def test_none_is_accepted(self) -> None:
        stack = StackCreate(**_base_payload(environment_id=None))
        assert stack.environment_id is None
