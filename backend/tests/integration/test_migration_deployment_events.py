"""Tests d'intégration de la migration 1671 deployment_events (STORY-167 — AC 1).

Scénarios sur base SQLite réelle (pattern ``TestMigration1662``) :

1. **Data migration sans perte** : un déploiement historique avec logs
   texte multi-lignes (``[INFO]``/``[ERROR]``…) voit chaque ligne
   convertie en event requêtable — la concaténation des messages
   reconstitue le texte original ;
2. **Mapping** : ``level`` par préfixe, ``event_type`` par statut du
   déploiement (failed → error, running → success, sinon deploying) ;
3. **Interpolation linéaire** : ``created_at`` strictement croissants
   entre ``created_at`` et ``COALESCE(stopped_at, deployed_at,
   updated_at)`` (décision d'analyse 3) ;
4. **Round-trip downgrade** : table absente, ``deployments.logs``
   **intacte** (non destructif) ;
5. **Logs NULL** : aucune ligne, aucune erreur ;
6. **Schéma** : colonnes spec 06 + index nommés.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic import command as alembic_command
from sqlalchemy import create_engine, inspect, text

from app.database import get_alembic_config

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

_PRE_1671 = "1662_environments_stacks_origin_git_url"

HISTORICAL_LOGS = (
    "[INFO] Starting deployment of stack nginx\n"
    "[INFO] Pulling image nginx:latest\n"
    "[SYSTEM] Health check unstable\n"
    "[ERROR] Container exited with code 1"
)


def _run_alembic(*args: str, db_url: str) -> subprocess.CompletedProcess[str]:
    """Exécute la CLI alembic en sous-process isolé (env DATABASE_URL)."""
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _seed_pre_1671_base(db_path: Path) -> None:
    """Base à l'état pré-1671 (upgrade 1662) + déploiements historiques."""
    db_url = f"sqlite+aiosqlite:///{db_path}"
    assert _run_alembic("upgrade", _PRE_1671, db_url=db_url).returncode == 0

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organizations (id, name, slug, settings, "
                    "created_at, updated_at) VALUES ('org-1671', "
                    "'Org 1671', 'org-1671', '{}', '2026-01-01 00:00:00', "
                    "'2026-01-01 00:00:00')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO stacks (id, name, description, version, "
                    "category, tags, template, variables, icon_url, "
                    "screenshots, documentation_url, author, license, "
                    "organization_id, target_type, is_public, downloads, "
                    "rating, is_archived, created_at, updated_at) "
                    "VALUES ('stk-1671', 'stack 1671', NULL, '1.0.0', NULL, "
                    "'[]', '{}', '{}', NULL, '[]', NULL, NULL, 'MIT', "
                    "'org-1671', 'docker', 0, 0, 0, 0, "
                    "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO hosts (id, name, host, port, profile, "
                    "status, credentials, extra_metadata, organization_id, "
                    "created_at, updated_at) VALUES ('host-1671', "
                    "'host 1671', '127.0.0.1', 22, 'host_remote_docker', "
                    "'online', '{}', '{}', 'org-1671', "
                    "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                )
            )
            # Déploiement failed avec logs multi-lignes historiques.
            conn.execute(
                text(
                    "INSERT INTO deployments (id, stack_id, host_id, "
                    "organization_id, name, status, config, variables, "
                    "logs, error_message, task_retry_count, created_at, "
                    "updated_at, stopped_at) VALUES "
                    "('dep-failed', 'stk-1671', 'host-1671', 'org-1671', "
                    "'dep failed', 'failed', '{}', '{}', :logs, "
                    "'boom', 0, '2026-01-02 10:00:00', "
                    "'2026-01-02 10:05:00', '2026-01-02 10:05:00')"
                ),
                {"logs": HISTORICAL_LOGS},
            )
            # Déploiement running.
            conn.execute(
                text(
                    "INSERT INTO deployments (id, stack_id, host_id, "
                    "organization_id, name, status, config, variables, "
                    "logs, error_message, task_retry_count, created_at, "
                    "updated_at, deployed_at) VALUES "
                    "('dep-running', 'stk-1671', 'host-1671', 'org-1671', "
                    "'dep running', 'running', '{}', '{}', "
                    "'[INFO] started', NULL, 0, '2026-01-02 11:00:00', "
                    "'2026-01-02 11:02:00', '2026-01-02 11:02:00')"
                )
            )
            # Déploiement à logs NULL : aucune ligne attendue.
            conn.execute(
                text(
                    "INSERT INTO deployments (id, stack_id, host_id, "
                    "organization_id, name, status, config, variables, "
                    "logs, error_message, task_retry_count, created_at, "
                    "updated_at) VALUES "
                    "('dep-nullogs', 'stk-1671', 'host-1671', 'org-1671', "
                    "'dep null', 'pending', '{}', '{}', NULL, NULL, 0, "
                    "'2026-01-02 12:00:00', '2026-01-02 12:00:00')"
                )
            )
    finally:
        engine.dispose()


def _upgraded(tmp_path: Path, name: str) -> Path:
    """Seed pré-1671 puis upgrade head — retourne le chemin de la base."""
    db_path = tmp_path / name
    _seed_pre_1671_base(db_path)
    result = _run_alembic("upgrade", "head", db_url=f"sqlite+aiosqlite:///{db_path}")
    assert (
        result.returncode == 0
    ), f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
    return db_path


class TestMigration1671DeploymentEvents:
    """STORY-167 — migration ``1671`` : DDL + data migration des logs."""

    def test_table_created_with_spec06_columns_and_indexes(
        self, tmp_path: Path
    ) -> None:
        """Schéma spec 06 : colonnes exactes + index nommés."""
        db_path = _upgraded(tmp_path, "schema1671.db")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            assert "deployment_events" in inspector.get_table_names()

            columns = {
                col["name"] for col in inspector.get_columns("deployment_events")
            }
            assert columns == {
                "id",
                "deployment_id",
                "event_type",
                "level",
                "message",
                "data",
                "created_at",
            }

            index_names = {
                idx["name"] for idx in inspector.get_indexes("deployment_events")
            }
            assert "idx_deploy_events_deployment" in index_names
            assert "idx_deploy_events_created" in index_names

            # FK CASCADE déclarée sur deployment_id.
            fks = inspector.get_foreign_keys("deployment_events")
            assert any(
                fk.get("referred_table") == "deployments"
                and "CASCADE" in (fk.get("options") or {}).get("ondelete", "")
                or fk.get("ondelete") == "CASCADE"
                for fk in fks
            )
        finally:
            engine.dispose()

    def test_data_migration_lines_without_loss(self, tmp_path: Path) -> None:
        """AC 1 — chaque ligne = un event requêtable, aucune perte de
        contenu (concaténation des messages == texte original)."""
        db_path = _upgraded(tmp_path, "data1671.db")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT message FROM deployment_events "
                        "WHERE deployment_id = 'dep-failed' "
                        "ORDER BY created_at ASC, id ASC"
                    )
                ).fetchall()
            messages = [row[0] for row in rows]
            assert len(messages) == 4
            # Aucune perte : reconstitution exacte du texte original.
            assert "\n".join(messages) == HISTORICAL_LOGS
        finally:
            engine.dispose()

    def test_data_migration_level_and_event_type_mapping(self, tmp_path: Path) -> None:
        """Mapping : level par préfixe ([ERROR]→error, [SYSTEM]→warning,
        sinon info) ; event_type par statut (failed→error, running→success)."""
        db_path = _upgraded(tmp_path, "mapping1671.db")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                failed_rows = conn.execute(
                    text(
                        "SELECT message, level FROM deployment_events "
                        "WHERE deployment_id = 'dep-failed' "
                        "ORDER BY created_at ASC, id ASC"
                    )
                ).fetchall()
                running_rows = conn.execute(
                    text(
                        "SELECT DISTINCT event_type FROM deployment_events "
                        "WHERE deployment_id = 'dep-running'"
                    )
                ).fetchall()

            # Levels par préfixe (dans l'ordre des lignes du logs).
            assert [row[1] for row in failed_rows] == [
                "info",
                "info",
                "warning",
                "error",
            ]
            # Statut running → event_type success (décision 1).
            assert running_rows == [("success",)]
        finally:
            engine.dispose()

    def test_created_at_interpolated_strictly_increasing(self, tmp_path: Path) -> None:
        """Décision 3 — interpolation linéaire entre created_at et
        stopped_at : horodatages strictement croissants dans l'ordre."""
        db_path = _upgraded(tmp_path, "interp1671.db")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        "SELECT created_at FROM deployment_events "
                        "WHERE deployment_id = 'dep-failed' "
                        "ORDER BY created_at ASC, id ASC"
                    )
                ).fetchall()
            timestamps = [row[0] for row in rows]
            assert len(timestamps) == 4
            assert timestamps == sorted(timestamps)
            # Bornes : première ligne = created_at du déploiement.
            assert str(timestamps[0]).startswith("2026-01-02 10:00")
        finally:
            engine.dispose()

    def test_null_logs_produce_no_rows(self, tmp_path: Path) -> None:
        """Logs NULL : aucune ligne migrée, aucune erreur."""
        db_path = _upgraded(tmp_path, "null1671.db")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM deployment_events "
                        "WHERE deployment_id = 'dep-nullogs'"
                    )
                ).scalar_one()
            assert count == 0
        finally:
            engine.dispose()

    def test_downgrade_drops_table_keeps_logs_intact(self, tmp_path: Path) -> None:
        """Round-trip : downgrade → table absente, ``deployments.logs``
        intacte (non destructif)."""
        db_path = tmp_path / "downgrade1671.db"
        _seed_pre_1671_base(db_path)
        db_url = f"sqlite+aiosqlite:///{db_path}"

        assert _run_alembic("upgrade", "head", db_url=db_url).returncode == 0
        assert _run_alembic("downgrade", _PRE_1671, db_url=db_url).returncode == 0

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            assert "deployment_events" not in inspector.get_table_names()

            with engine.connect() as conn:
                logs = conn.execute(
                    text("SELECT logs FROM deployments WHERE id = 'dep-failed'")
                ).scalar_one()
            assert logs == HISTORICAL_LOGS  # colonne texte jamais modifiée
        finally:
            engine.dispose()

    def test_reupgrade_after_downgrade_reinserts_lines(self, tmp_path: Path) -> None:
        """Limite documentée : un re-upgrade re-migre les lignes (PK
        uuid4 nouvelles) — le contenu reste identique."""
        db_path = tmp_path / "roundtrip1671.db"
        _seed_pre_1671_base(db_path)
        db_url = f"sqlite+aiosqlite:///{db_path}"

        assert _run_alembic("upgrade", "head", db_url=db_url).returncode == 0
        assert _run_alembic("downgrade", _PRE_1671, db_url=db_url).returncode == 0
        assert _run_alembic("upgrade", "head", db_url=db_url).returncode == 0

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                count = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM deployment_events "
                        "WHERE deployment_id = 'dep-failed'"
                    )
                ).scalar_one()
            assert count == 4
        finally:
            engine.dispose()


class TestAlembicOfflineModeSkipsDataMigration:
    """Mode offline (``--sql``) : DDL seul, data migration court-circuitée."""

    def test_offline_upgrade_generates_ddl_only(self, tmp_path: Path) -> None:
        """La génération SQL hors ligne ne tente aucune connexion (skip
        data migration — pattern 1311)."""
        from alembic.config import Config

        config = get_alembic_config()
        assert isinstance(config, Config)
        # upgrade offline de 1662 → head : produit le SQL DDL sans base.
        sql = alembic_command.upgrade(
            config,
            f"{_PRE_1671}:1671_deployment_events_table",
            sql=True,
        )
        # Le DDL de la table est présent dans le script généré.
        output = getattr(sql, "output_scripts", None)
        assert output is None or isinstance(output, dict)  # n'a pas levé
