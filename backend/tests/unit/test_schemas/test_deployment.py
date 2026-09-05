"""Tests unitaires du schéma DeploymentResponse — masquage API (STORY-103.3).

Vérifie :
- ``DeploymentResponse.variables``/``config`` renvoient ``***`` pour toute
  valeur sensible (nom sensible OU ciphertext Fernet), jamais la valeur en
  clair ;
- les valeurs non sensibles restent lisibles (l'UI liste les noms) ;
- le masquage couvre aussi les snapshots legacy non chiffrés ;
- la non-régression des autres champs de la réponse.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.secret_manager import SecretManager, reset_secret_manager
from app.models.deployment import DeploymentStatus, encrypt_variables_for_storage
from app.schemas.deployment import DeploymentResponse


def _response_with(
    variables: dict | None = None, config: dict | None = None
) -> DeploymentResponse:
    """Construit une DeploymentResponse avec snapshots donnés."""
    return DeploymentResponse(
        id="dep-1",
        name="test-deployment",
        stack_id="stack-1",
        target_id="target-1",
        status=DeploymentStatus.RUNNING,
        config=config or {},
        variables=variables or {},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


class TestResponseMasksSensitiveVariables:
    """AC 3 — l'API ne renvoie jamais les valeurs sensibles en clair."""

    def test_response_masks_sensitive_variables(self):
        """``***`` pour les valeurs sensibles, jamais la valeur en clair."""
        response = _response_with(
            variables={
                "db_password": "S3cr3t!Pass",
                "api_token": "tok_abc123",
                "domain": "app.example.com",
            }
        )

        assert response.variables["db_password"] == "***"
        assert response.variables["api_token"] == "***"
        # La valeur en clair ne fuit nulle part dans la réponse.
        assert "S3cr3t!Pass" not in response.model_dump_json()
        assert "tok_abc123" not in response.model_dump_json()

    def test_response_masks_encrypted_tokens(self):
        """Un ciphertext Fernet (snapshot chiffré) est aussi masqué."""
        reset_secret_manager()
        try:
            stored = encrypt_variables_for_storage({"db_password": "valeur-secrète"})
        finally:
            reset_secret_manager()

        response = _response_with(variables=stored)

        assert response.variables["db_password"] == "***"
        assert SecretManager.is_encrypted(stored["db_password"])

    def test_non_sensitive_values_still_returned(self):
        """Les valeurs non sensibles restent lisibles (noms de variables)."""
        response = _response_with(
            variables={"domain": "app.example.com", "port": 8080, "debug": False}
        )

        assert response.variables["domain"] == "app.example.com"
        assert response.variables["port"] == 8080
        assert response.variables["debug"] is False

    def test_config_masked_like_variables(self):
        """Le champ config suit le même masquage que variables."""
        response = _response_with(config={"POSTGRES_PASSWORD": "pg-pass", "retries": 3})

        assert response.config["POSTGRES_PASSWORD"] == "***"
        assert response.config["retries"] == 3

    def test_serialized_payload_contains_no_plain_secret(self):
        """Le JSON sérialisé complet ne contient aucun secret en clair."""
        response = _response_with(
            variables={"jwt_secret": "jwt-plain-value"},
            config={"api_key": "sk-plain"},
        )

        payload = response.model_dump_json()
        assert "jwt-plain-value" not in payload
        assert "sk-plain" not in payload
        assert "***" in payload

    def test_empty_and_none_snapshots_handled(self):
        """Snapshots vides : aucune erreur, valeurs inchangées."""
        response = _response_with(variables={}, config={})

        assert response.variables == {}
        assert response.config == {}

    def test_other_fields_not_impacted(self):
        """Non-régression : les autres champs restent intacts."""
        now = datetime.now(timezone.utc)
        response = DeploymentResponse(
            id="dep-2",
            name="prod",
            stack_id="stack-2",
            target_id="target-2",
            status=DeploymentStatus.PENDING,
            config={},
            variables={"db_password": "x"},
            container_id=None,
            logs="Deploying...",
            deployed_at=None,
            created_at=now,
            updated_at=now,
        )

        assert response.name == "prod"
        assert response.status == DeploymentStatus.PENDING
        assert response.logs == "Deploying..."
        assert response.variables["db_password"] == "***"
