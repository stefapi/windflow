"""Tests unitaires du registre d'actions scheduler (STORY-160.1, AC 1).

Couverture :
- registre : les 5 actions core exposées, chacune avec ``params_schema``
  Pydantic strict ;
- stubs explicites : ``stack.backup``/``admin.backup``/``notification.send``
  marquées ``implemented=False`` (renvois F8/P2-15) ;
- action inconnue → erreur **explicite** (``InvalidInputError``, pas de
  ``KeyError`` brut) ;
- ``is_valid()`` cohérent avec ``get_action()`` ;
- ``validate_params`` : nominaux + rejets (schéma par action).
"""

import pytest
from pydantic import BaseModel, ValidationError

from app.core.exceptions import InvalidInputError
from app.services.action_registry import (
    get_action,
    is_valid,
    list_actions,
    validate_params,
)

# Les 5 actions core du registre canonique (arbitrage STORY-160.1).
EXPECTED_ACTIONS = {
    "host.scan",
    "compute.docker.prune",
    "stack.backup",
    "admin.backup",
    "notification.send",
}

# Stubs explicites — jamais de succès silencieux (renvois F8/P2-15).
STUB_ACTIONS = {"stack.backup", "admin.backup", "notification.send"}


class TestRegistryContent:
    """Contenu canonique du registre."""

    def test_registry_exposes_five_core_actions(self):
        """AC 1 : les 5 actions core sont enregistrées — ni plus ni moins."""
        names = {definition.name for definition in list_actions()}
        assert names == EXPECTED_ACTIONS

    def test_every_action_has_pydantic_params_schema(self):
        """AC 1 : chaque action porte un ``params_schema`` Pydantic."""
        for definition in list_actions():
            assert issubclass(
                definition.params_schema, BaseModel
            ), f"{definition.name}: params_schema doit être un BaseModel"

    def test_params_schemas_forbid_extra_fields(self):
        """Sécurité (rules 40) : ``extra='forbid'`` sur tous les schémas
        d'action — pas de paramètre libre persistable."""
        for definition in list_actions():
            schema = definition.params_schema
            with pytest.raises(ValidationError):
                schema.model_validate({"definitely_not_a_field": "x"})

    def test_list_actions_sorted_alphabetically(self):
        """Ordre stable (alphabétique) pour l'affichage/OpenAPI."""
        names = [definition.name for definition in list_actions()]
        assert names == sorted(names)


class TestStubActions:
    """Stubs explicites documentés (AC 1)."""

    @pytest.mark.parametrize("name", sorted(STUB_ACTIONS))
    def test_stub_actions_marked_not_implemented(self, name):
        """``stack.backup``/``admin.backup``/``notification.send`` sont des
        stubs explicites (``implemented=False``)."""
        definition = get_action(name)
        assert definition.implemented is False

    def test_stub_status_visible_in_description(self):
        """Le statut stub est documenté dans la description."""
        definition = get_action("stack.backup")
        assert "STUB" in definition.description

    def test_consumable_actions_marked_implemented(self):
        """``host.scan`` et ``compute.docker.prune`` sont consommables
        (implémentation réelle portée par STORY-160.3)."""
        assert get_action("host.scan").implemented is True
        assert get_action("compute.docker.prune").implemented is True


class TestUnknownAction:
    """Action inconnue → erreur explicite (pas de KeyError brut)."""

    def test_get_action_unknown_raises_explicit_error(self):
        with pytest.raises(InvalidInputError) as exc_info:
            get_action("definitely.not.registered")
        # Le message porte l'action et les clés connues (aide au 422).
        assert "definitely.not.registered" in str(exc_info.value)

    def test_get_action_unknown_not_keyerror(self):
        """Jamais de KeyError brut remontant en 500."""
        try:
            get_action("nope")
        except KeyError as exc:
            pytest.fail(f"KeyError brut levé : {exc}")
        except InvalidInputError:
            pass  # attendu

    def test_is_valid_false_for_unknown(self):
        assert is_valid("nope.action") is False

    def test_is_valid_true_for_known(self):
        for name in EXPECTED_ACTIONS:
            assert is_valid(name) is True

    def test_is_valid_consistent_with_get_action(self):
        """Cohérence : is_valid(name) ⟺ get_action(name) ne lève pas."""
        for candidate in [*EXPECTED_ACTIONS, "unknown.action"]:
            if is_valid(candidate):
                get_action(candidate)  # ne doit pas lever
            else:
                with pytest.raises(InvalidInputError):
                    get_action(candidate)


class TestValidateParams:
    """Validation des paramètres par le schéma de l'action."""

    def test_host_scan_params_valid(self):
        result = validate_params("host.scan", {"target_id": "tgt-123"})
        assert result == {"target_id": "tgt-123"}

    def test_host_scan_missing_target_id_rejected(self):
        from app.core.exceptions import UnprocessableEntityError

        with pytest.raises((UnprocessableEntityError, ValidationError)):
            validate_params("host.scan", {})

    def test_docker_prune_defaults_dry_run_true(self):
        """STORY-173 : dry_run vaut True par défaut (prune protégé)."""
        result = validate_params("compute.docker.prune", {"resource": "images"})
        assert result["dry_run"] is True

    def test_docker_prune_invalid_resource_rejected(self):
        """Ressource bornée images|volumes — 'networks' rejeté."""
        from app.core.exceptions import UnprocessableEntityError

        with pytest.raises((UnprocessableEntityError, ValidationError)):
            validate_params("compute.docker.prune", {"resource": "networks"})

    def test_notification_send_params_valid(self):
        result = validate_params(
            "notification.send",
            {"channel": "webhook", "message": "Deployment failed"},
        )
        assert result["severity"] == "info"  # défaut

    def test_unknown_action_rejected_in_validate_params(self):
        with pytest.raises(InvalidInputError):
            validate_params("unknown.action", {})
