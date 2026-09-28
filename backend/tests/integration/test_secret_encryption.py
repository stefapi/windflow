"""Tests d'intégration transverses — chiffrement au repos des secrets (STORY-103.4).

Validation finale du plan P0-4 : après exécution des flux d'accès sur une
base avec des données héritées en clair (credentials cible + snapshots de
déploiement), **aucune valeur sensible n'est lisible dans les colonnes
persistées** (credentials cibles et valeurs sensibles des snapshots sont
des tokens Fernet préfixe ``gAAAA``), et l'API ne renvoie jamais de valeur
en clair (masquage ``***`` / champs credentials absents des réponses).

Le test inspecte le **contenu brut des colonnes JSON** (contournant le
modèle et ses propriétés de déchiffrement) pour prouver le chiffrement
effectif au repos — c'est l'oracle « at-rest » du plan.
"""

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.secret_manager import SecretManager
from app.models.deployment import (
    Deployment,
    DeploymentStatus,
    is_sensitive_variable,
)
from app.models.stack import Stack
from app.models.target import Target, TargetStatus, TargetType
from app.schemas.deployment import DeploymentCreate
from app.services.deployment_service import DeploymentService
from tests.conftest import unwrap

# Secrets factices de test — jamais utilisés hors de ces tests.
LEGACY_PASSWORD = "LegacyClearTextPassword123!"
LEGACY_SUDO_PASSWORD = "SudoPass456!"
LEGACY_DB_PASSWORD = "db-p4ssw0rd-legacy"
LEGACY_API_TOKEN = "legacy-api-token-abcdef"
NON_SENSITIVE_VALUE = "not-a-secret-value"

ORCH_PATCH = (
    "app.services.deployment_orchestrator.DeploymentOrchestrator.start_deployment"
)


async def _fetch_raw_columns(db_session: AsyncSession, query: str) -> list[dict]:
    """Exécute une requête SQL brute pour inspecter les colonnes persistées.

    Contourne volontairement le modèle ORM (et ses propriétés de
    déchiffrement/migration) : c'est l'oracle « at-rest » — ce que verrait
    un attaquant ayant accès au fichier de la base. Les colonnes JSON de
    SQLite sont stockées en TEXT : elles sont désérialisées ici pour
    refléter ce qu'un lecteur du fichier verrait après ``json.loads``.
    """
    result = await db_session.execute(text(query))
    rows: list[dict] = []
    for row in result:
        parsed = dict(row._mapping)
        for key, value in parsed.items():
            if isinstance(value, str) and value.startswith(("{", "[")):
                try:
                    parsed[key] = json.loads(value)
                except ValueError:
                    pass  # pas du JSON : garder la valeur brute
        rows.append(parsed)
    return rows


def _assert_no_plaintext_secret(
    raw_value: str, secrets: tuple[str, ...], context: str
) -> None:
    """Vérifie qu'aucun secret en clair n'apparaît dans la valeur brute."""
    for secret in secrets:
        assert secret not in raw_value, (
            f"FUITE ({context}) : le secret en clair est lisible dans la "
            f"colonne persistée (recherche de {secret!r} dans {raw_value!r})"
        )


@pytest.mark.asyncio
class TestZeroCredentialReadableAfterMigration:
    """AC 5 — 0 credential lisible en base après exécution des flux."""

    async def test_zero_credential_readable_after_migration(
        self,
        db_session: AsyncSession,
        test_organization,
        test_stack: Stack,
    ):
        """Base héritée (credentials + snapshots en clair) → accès → 0 lisible.

        Scénario :
        1. Seed d'une cible avec credentials **hérités en clair** (format
           pré-103.2 : dict JSON lisible) ;
        2. Seed d'un déploiement avec snapshot **hérité en clair** (format
           pré-103.3 : valeurs sensibles lisibles) ;
        3. Exécution des flux d'accès (double lecture métier via
           ``decrypted_credentials`` / ``decrypted_variables``, création
           d'un déploiement via le service) ;
        4. Commit (persiste la migration dirty) puis inspection **brute**
           des colonnes : plus aucune valeur sensible en clair, uniquement
           des tokens Fernet ``gAAAA``.
        """
        # ── 1. Seed : cible avec credentials hérités en clair ──────────
        legacy_target = Target(
            name="Legacy Target",
            host="192.168.1.50",
            port=22,
            type=TargetType.PHYSICAL,
            status=TargetStatus.ONLINE,
            # Format pré-103.2 : dict JSON en clair dans la colonne.
            credentials={
                "auth_method": "password",
                "username": "root",
                "password": LEGACY_PASSWORD,
                "sudo_enabled": True,
                "sudo_user": "root",
                "sudo_password": LEGACY_SUDO_PASSWORD,
            },
            organization_id=test_organization.id,
        )
        db_session.add(legacy_target)
        # Flush : génère l'id de la cible (default Python appliqué au
        # flush) pour l'utiliser comme FK du snapshot hérité.
        await db_session.flush()

        # ── 2. Seed : déploiement avec snapshot hérité en clair ────────
        legacy_deployment = Deployment(
            name="legacy-deployment",
            stack_id=test_stack.id,
            target_id=legacy_target.id,
            organization_id=test_organization.id,
            status=DeploymentStatus.STOPPED,
            # Format pré-103.3 : valeurs sensibles lisibles.
            config={"DB_PASSWORD": LEGACY_DB_PASSWORD, "port": 5432},
            variables={"API_TOKEN": LEGACY_API_TOKEN, "debug": "false"},
        )
        db_session.add(legacy_deployment)
        await db_session.commit()

        # ── 3. Flux d'accès (double lecture + ré-encryptage dirty) ─────
        # Accès métier à la cible (déclenche la migration double lecture).
        assert legacy_target.decrypted_credentials["password"] == LEGACY_PASSWORD

        # Accès métier au snapshot (déclenche la migration double lecture).
        assert legacy_deployment.decrypted_variables["API_TOKEN"] == LEGACY_API_TOKEN
        assert legacy_deployment.decrypted_config["DB_PASSWORD"] == LEGACY_DB_PASSWORD

        # Nouveau déploiement via le service (chiffre à la création).
        # L'orchestrateur (DB globale, tâche de fond) est patché — hors
        # périmètre : on teste le chiffrement au repos du snapshot.
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            new_deployment = await DeploymentService.create(
                db_session,
                DeploymentCreate(
                    stack_id=test_stack.id,
                    target_id=legacy_target.id,
                    name="post-migration-deployment",
                    config={"DB_PASSWORD": "new-db-pass", "port": 5433},
                    variables={"API_TOKEN": "new-api-token", "debug": "true"},
                ),
                organization_id=test_organization.id,
                user_id=str(uuid.uuid4()),
            )

        # Persiste les migrations dirty (commit implicite du service pour
        # new_deployment ; commit explicite pour les lignes legacy).
        await db_session.commit()

        # ── 4. Inspection brute des colonnes (oracle at-rest) ──────────
        raw_targets = await _fetch_raw_columns(
            db_session, "SELECT credentials FROM targets"
        )
        assert len(raw_targets) >= 1
        for row in raw_targets:
            stored_credentials = row["credentials"]
            # dict {} (fixture sans secret) ou dict opaque chiffré — jamais
            # de secrets en clair dans un cas comme dans l'autre.
            assert isinstance(stored_credentials, dict)
            raw_credentials = json.dumps(stored_credentials, sort_keys=True)
            _assert_no_plaintext_secret(
                raw_credentials,
                (LEGACY_PASSWORD, LEGACY_SUDO_PASSWORD),
                "targets.credentials",
            )
            if not stored_credentials:
                continue  # cible sans credentials : rien à chiffrer
            token = stored_credentials.get("_encrypted")
            assert isinstance(token, str) and SecretManager.is_encrypted(token), (
                f"targets.credentials n'est pas au format chiffré : {raw_credentials!r}"
            )

        raw_deployments = await _fetch_raw_columns(
            db_session, "SELECT config, variables FROM deployments"
        )
        assert len(raw_deployments) >= 2
        for row in raw_deployments:
            for column in ("config", "variables"):
                raw_snapshot = str(row[column])
                _assert_no_plaintext_secret(
                    raw_snapshot,
                    (
                        LEGACY_DB_PASSWORD,
                        LEGACY_API_TOKEN,
                        "new-db-pass",
                        "new-api-token",
                    ),
                    f"deployments.{column}",
                )
                # Les valeurs sensibles sont des tokens Fernet (jamais du clair).
                for key, value in row[column].items():
                    if isinstance(value, str) and SecretManager.is_encrypted(value):
                        continue  # token Fernet : attendu
                    # Valeur non chiffrée : elle ne doit PAS être sensible.
                    assert not any(
                        secret in str(value)
                        for secret in (LEGACY_DB_PASSWORD, LEGACY_API_TOKEN)
                    ), f"deployments.{column}[{key!r}] contient un secret en clair"

        # ── Relecture métier : les flux existants fonctionnent ──────────
        await db_session.refresh(legacy_target)
        await db_session.refresh(legacy_deployment)
        await db_session.refresh(new_deployment)
        assert legacy_target.decrypted_credentials["password"] == LEGACY_PASSWORD
        assert legacy_deployment.decrypted_variables["API_TOKEN"] == LEGACY_API_TOKEN
        assert new_deployment.decrypted_config["port"] == 5433
        # Idempotence : la réassignation ne re-chiffre pas un ciphertext.
        token_before = legacy_target.credentials["_encrypted"]
        _ = legacy_target.decrypted_credentials
        assert legacy_target.credentials["_encrypted"] == token_before

    async def test_legacy_deployment_with_missing_target_id_integrity(
        self,
        db_session: AsyncSession,
        test_organization,
        test_stack: Stack,
        test_target: Target,
    ):
        """Variante : snapshot legacy attaché à une cible fixture ``{}``.

        Vérifie que les fixtures existantes avec ``credentials={}`` ne sont
        pas migrées (aucun secret à protéger) et que le snapshot legacy est
        bien ré-encrypté au premier accès — sans modification des fixtures.
        """
        legacy_deployment = Deployment(
            name="legacy-on-fixture-target",
            stack_id=test_stack.id,
            target_id=test_target.id,
            organization_id=test_organization.id,
            status=DeploymentStatus.STOPPED,
            config={"ADMIN_TOKEN": "admin-token-legacy-xyz"},
            variables={},
        )
        db_session.add(legacy_deployment)
        await db_session.commit()

        # Accès métier → migration.
        assert (
            legacy_deployment.decrypted_config["ADMIN_TOKEN"]
            == "admin-token-legacy-xyz"
        )
        await db_session.commit()

        raw = await _fetch_raw_columns(
            db_session,
            "SELECT config FROM deployments WHERE name = 'legacy-on-fixture-target'",
        )
        assert len(raw) == 1
        stored_token = raw[0]["config"].get("ADMIN_TOKEN")
        assert isinstance(stored_token, str)
        assert SecretManager.is_encrypted(stored_token)
        assert "admin-token-legacy-xyz" not in str(raw[0]["config"])

        # La cible fixture credentials={} reste non migrée (aucun secret).
        raw_target = await _fetch_raw_columns(
            db_session,
            f"SELECT credentials FROM targets WHERE id = '{test_target.id}'",
        )
        assert raw_target[0]["credentials"] == {}


@pytest.mark.asyncio
class TestMaskingAcrossApiEndpoints:
    """AC 5 — masquage API : jamais de valeur en clair dans les réponses."""

    async def test_masking_across_api_endpoints(
        self,
        admin_client: AsyncClient,
        db_session: AsyncSession,
        test_organization,
        test_stack: Stack,
        test_target: Target,
    ):
        """Endpoints deployments/targets : masquage ``***`` et zéro clair.

        - POST /deployments avec variables sensibles → 201 ; la réponse ne
          contient jamais les valeurs en clair (masquées ``***``) ;
        - GET /deployments et GET /deployments/{id} → idem ;
        - GET /targets et GET /targets/{id} → champ credentials absent,
          username exposé mais jamais password/clé privée.
        """
        secrets = ("api-secret-value-xyz", "db-password-abc")

        # ── POST /deployments : création avec variables sensibles ──────
        with patch(ORCH_PATCH, new_callable=AsyncMock, return_value=None):
            create_response = await admin_client.post(
                "/api/v1/deployments",
                json={
                    "name": "masking-e2e-deployment",
                    "stack_id": test_stack.id,
                    "target_id": test_target.id,
                    "config": {"DB_PASSWORD": secrets[1], "port": 5555},
                    "variables": {"API_SECRET": secrets[0], "debug": "true"},
                },
            )
        assert create_response.status_code == 201, create_response.text
        created = unwrap(create_response)
        deployment_id = created["id"]

        # La réponse de création est déjà masquée.
        payload_text = str(created)
        for secret in secrets:
            assert secret not in payload_text
        assert created["config"]["DB_PASSWORD"] == "***"
        assert created["variables"]["API_SECRET"] == "***"
        # Les valeurs non sensibles restent lisibles.
        assert created["config"]["port"] == 5555

        # ── GET /deployments/{id} : détail masqué ──────────────────────
        detail_response = await admin_client.get(f"/api/v1/deployments/{deployment_id}")
        assert detail_response.status_code == 200
        detail = unwrap(detail_response)
        assert detail["config"]["DB_PASSWORD"] == "***"
        assert detail["variables"]["API_SECRET"] == "***"
        for secret in secrets:
            assert secret not in str(detail)

        # ── GET /deployments : liste masquée ───────────────────────────
        list_response = await admin_client.get("/api/v1/deployments")
        assert list_response.status_code == 200
        for item in list_response.json().get("items", []):
            item_text = str(item)
            for secret in secrets:
                assert secret not in item_text
            config = item.get("config") or {}
            variables = item.get("variables") or {}
            assert config.get("DB_PASSWORD") in (None, "***")
            assert variables.get("API_SECRET") in (None, "***")

        # ── GET /targets : credentials jamais exposés ──────────────────
        targets_response = await admin_client.get(
            "/api/v1/targets", follow_redirects=True
        )
        assert targets_response.status_code == 200
        targets_text = str(unwrap(targets_response))
        for secret in secrets:
            assert secret not in targets_text
        assert "credentials" not in targets_text
        assert "password" not in targets_text.lower()

        # ── GET /targets/{id} : détail sans credentials ────────────────
        target_response = await admin_client.get(
            f"/api/v1/targets/{test_target.id}", follow_redirects=True
        )
        assert target_response.status_code == 200
        target_detail = str(unwrap(target_response))
        assert "credentials" not in target_detail
        assert "password" not in target_detail.lower()

        # ── Oracle at-rest : la base contient des tokens, pas du clair ─
        await db_session.commit()
        raw = await _fetch_raw_columns(
            db_session,
            "SELECT config, variables FROM deployments "
            "WHERE name = 'masking-e2e-deployment'",
        )
        assert len(raw) == 1
        for column in ("config", "variables"):
            snapshot: dict = raw[0][column]
            for secret in secrets:
                assert secret not in str(snapshot)
            # Seules les valeurs SENSIBLES sont chiffrées (clé conservée,
            # valeur chiffrée) ; les valeurs normales restent lisibles.
            for key, value in snapshot.items():
                if isinstance(value, str) and is_sensitive_variable(key):
                    assert SecretManager.is_encrypted(value), (
                        f"deployments.{column}[{key!r}] = valeur sensible "
                        f"stockée en clair : {value!r}"
                    )
            # Au moins une valeur sensible chiffrée par snapshot utilisé.
            assert any(
                isinstance(v, str) and SecretManager.is_encrypted(v)
                for v in snapshot.values()
            )
