"""Tests du runner de migrations au démarrage (STORY-120.2).

Vérifie :
- ``Database.run_migrations()`` sur base vierge → schéma complet créé par les
  migrations uniquement ;
- base existante non versionnée (héritée de ``create_all``) → stamp
  automatique de la baseline puis upgrade no-op, données préservées ;
- échec de migration → ``WindFlowException`` bloquante (aucun fallback
  ``create_all``), sans fuite de l'URL DB dans le message ;
- le seed de démarrage reste fonctionnel après migrations (ordre startup
  inchangé : connect → run_migrations → seed_tables) ;
- inspection statique : plus aucun ``create_all`` nu dans ``backend/app/``
  (critère de done de l'epic EPIC-012) ;
- la fixture ``test_db_engine`` produit un schéma issu des migrations
  (présence de ``alembic_version``) et isolé entre tests.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text

from app import models  # noqa: F401  # enregistre tous les modèles
from app.config import settings
from app.core.exceptions import WindFlowException
from app.database import Base, Database, get_alembic_config
from app.models.organization import Organization
from app.models.user import User

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_DIR = REPO_ROOT / "backend" / "app"


def _sync_table_names(db_path: Path) -> set[str]:
    """Inspecte les tables d'une base SQLite via un engine sync jetable."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def _drop_targets_ssh_key_id(db_path: Path) -> None:
    """STORY-131.1 : retire ``targets.ssh_key_id`` d'une base create_all.

    SQLite refuse ``ALTER TABLE ... DROP COLUMN`` sur une colonne
    référencée par un FK inline : le rebuild batch d'Alembic est utilisé
    (même mécanique que le downgrade de la migration 1311).
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            operations = Operations(ctx)
            with operations.batch_alter_table("targets") as batch_op:
                batch_op.drop_column("ssh_key_id")
            conn.commit()
    finally:
        engine.dispose()


def _restore_legacy_scheduled_tasks(db_path: Path) -> None:
    """STORY-160.1 : ramène ``scheduled_tasks`` à son état pré-1321 sur
    une base create_all (modèles courants — colonnes spec 17 déjà
    posées, plus d'enum ``task_type``).

    Retire les 5 colonnes v2 (rebuild batch) puis recrée ``task_type``
    VARCHAR(20) NOT NULL DEFAULT 'CUSTOM' (fidèle à la baseline ; le
    CHECK enum est omis — la migration 1321 lit la valeur brute).
    """
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn)
            operations = Operations(ctx)
            with operations.batch_alter_table("scheduled_tasks") as batch_op:
                for column in (
                    "action",
                    "trigger_type",
                    "event_name",
                    "timezone",
                    "error_policy",
                ):
                    batch_op.drop_column(column)
            conn.execute(
                text(
                    "ALTER TABLE scheduled_tasks ADD COLUMN task_type "
                    "VARCHAR(20) NOT NULL DEFAULT 'CUSTOM'"
                )
            )
            conn.commit()
    finally:
        engine.dispose()


def _alembic_version(db_path: Path) -> str | None:
    """Lit la révision courante dans la table ``alembic_version``."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as conn:
            return conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
    finally:
        engine.dispose()


async def _run_migrations_on(db_path: Path) -> Database:
    """Exécute ``connect()`` + ``run_migrations()`` sur une base fichier isolée.

    L'URL des settings est ponctuellement redirigée vers ``db_path`` (le
    runner Alembic ``env.py`` lit ``settings.database_url``), puis restaurée.
    """
    original_url = settings.database_url
    settings.database_url = f"sqlite+aiosqlite:///{db_path}"
    database = Database()
    try:
        await database.connect()
        await database.run_migrations()
    finally:
        await database.disconnect()
        settings.database_url = original_url
    return database


class TestRunMigrationsFreshDb:
    """test_run_migrations_on_fresh_db_applies_upgrade_head."""

    async def test_run_migrations_on_fresh_db_applies_upgrade_head(
        self, tmp_path: Path
    ) -> None:
        """Base vierge → upgrade head : schéma complet par migrations uniquement."""
        db_path = tmp_path / "fresh.db"

        await _run_migrations_on(db_path)

        tables = _sync_table_names(db_path)
        # Toutes les tables des modèles, créées par les migrations.
        assert (
            set(Base.metadata.tables) <= tables
        ), f"Tables manquantes : {set(Base.metadata.tables) - tables}"
        # Preuve que le schéma vient des migrations (create_all ne crée pas
        # cette table) et que la base est versionnée à la tête courante
        # (robuste aux migrations suivantes — STORY-121.3).
        assert "alembic_version" in tables
        assert (
            _alembic_version(db_path)
            == ScriptDirectory.from_config(get_alembic_config()).get_current_head()
        )


class TestRunMigrationsExistingUnversionedDb:
    """test_run_migrations_stamps_existing_unversioned_db."""

    async def test_run_migrations_stamps_existing_unversioned_db(
        self, tmp_path: Path
    ) -> None:
        """Base pré-remplie sans ``alembic_version`` → stamp auto, aucune
        recréation/altération, données métier préservées."""
        db_path = tmp_path / "legacy.db"

        # Simule une installation historique : schéma create_all (usage de
        # simulation dans le test uniquement — interdit dans backend/app/)
        # + DROP des tables additives pour simuler fidèlement une base
        # antérieure à STORY-121.1 (create_all des métadonnées courantes
        # les créerait aussi — DROP refresh_tokens ajouté par
        # STORY-123.1, DROP api_keys par STORY-124.1, ssh_keys/
        # host_ssh_fingerprints par STORY-131.1) + données métier
        # à préserver.
        legacy_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(legacy_engine)
        # STORY-131.1 : retirer targets.ssh_key_id AVANT de dropper
        # ssh_keys — SQLite refuse DROP COLUMN sur une colonne FK inline,
        # le rebuild batch d'Alembic est utilisé (FK résolvable tant que
        # ssh_keys existe).
        legacy_engine.dispose()
        _drop_targets_ssh_key_id(db_path)
        # STORY-160.1 : scheduled_tasks à l'état pré-1321 (sinon
        # duplicate column lors de l'upgrade 1321).
        _restore_legacy_scheduled_tasks(db_path)
        legacy_engine = create_engine(f"sqlite:///{db_path}")
        with legacy_engine.begin() as conn:
            conn.execute(text("DROP TABLE user_organizations"))
            conn.execute(text("DROP TABLE refresh_tokens"))
            conn.execute(text("DROP TABLE api_keys"))
            conn.execute(text("DROP TABLE audit_logs"))
            conn.execute(text("DROP TABLE ssh_keys"))
            conn.execute(text("DROP TABLE host_ssh_fingerprints"))
            # STORY-161 : table additive scheduled_task_executions.
            conn.execute(text("DROP TABLE scheduled_task_executions"))
        # STORY-121.3 : simuler la colonne héritée users.organization_id
        # (+ index) — absente du schéma courant mais attendue par la
        # migration 1213 sur une base pré-121.3
        with legacy_engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN organization_id VARCHAR(36)")
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_users_organization_id "
                    "ON users (organization_id)"
                )
            )
        with legacy_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO organizations "
                    "(id, name, slug, settings, created_at, updated_at) "
                    "VALUES ('org-legacy', 'Legacy Org', 'legacy-org', '{}', "
                    "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                )
            )
        legacy_engine.dispose()
        assert "alembic_version" not in _sync_table_names(db_path)

        # 1er démarrage migré : stamp automatique puis upgrade (no-op).
        await _run_migrations_on(db_path)

        assert (
            _alembic_version(db_path)
            == ScriptDirectory.from_config(get_alembic_config()).get_current_head()
        )
        check_engine = create_engine(f"sqlite:///{db_path}")
        try:
            with check_engine.connect() as conn:
                slug = conn.execute(
                    text("SELECT slug FROM organizations WHERE id = 'org-legacy'")
                ).scalar_one_or_none()
        finally:
            check_engine.dispose()
        assert slug == "legacy-org", "Les données existantes ont été altérées/perdues"

        # 2e démarrage (base versionnée) : upgrade no-op, données intactes.
        await _run_migrations_on(db_path)
        check_engine = create_engine(f"sqlite:///{db_path}")
        try:
            with check_engine.connect() as conn:
                slug_again = conn.execute(
                    text("SELECT slug FROM organizations WHERE id = 'org-legacy'")
                ).scalar_one_or_none()
        finally:
            check_engine.dispose()
        assert slug_again == "legacy-org"

    async def test_detect_schema_state_classifies_correctly(
        self, tmp_path: Path
    ) -> None:
        """``_detect_schema_state`` distingue fresh / unversioned / versioned."""
        db_path = tmp_path / "states.db"
        database = Database()
        assert database.engine is None

        # Sans engine → RuntimeError (garde-fou contractuel).
        with pytest.raises(RuntimeError, match="engine not initialized"):
            await database.run_migrations()
        with pytest.raises(RuntimeError, match="engine not initialized"):
            await database._detect_schema_state()

        original_url = settings.database_url
        settings.database_url = f"sqlite+aiosqlite:///{db_path}"
        try:
            await database.connect()

            # Base vierge (fichier créé mais sans table).
            assert await database._detect_schema_state() == "fresh"

            # Tables métier sans alembic_version → unversioned.
            from sqlalchemy import text as _text

            async with database.engine.begin() as conn:
                await conn.execute(
                    _text("CREATE TABLE organizations (id TEXT PRIMARY KEY)")
                )
            assert await database._detect_schema_state() == "unversioned"

            # alembic_version présente → versioned.
            async with database.engine.begin() as conn:
                await conn.execute(
                    _text(
                        "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
                    )
                )
            assert await database._detect_schema_state() == "versioned"
        finally:
            await database.disconnect()
            settings.database_url = original_url


class TestRunMigrationsFailure:
    """test_run_migrations_failure_raises_windflow_exception."""

    async def test_run_migrations_failure_raises_windflow_exception(
        self, tmp_path: Path
    ) -> None:
        """Erreur de migration → ``WindFlowException`` bloquante, sans
        fallback ``create_all`` ni fuite de l'URL DB (sanitisation)."""
        db_path = tmp_path / "failing.db"
        original_url = settings.database_url
        settings.database_url = f"sqlite+aiosqlite:///{db_path}"
        database = Database()
        await database.connect()
        try:
            secret_url = settings.database_url
            with patch(
                "app.database.alembic_command.upgrade",
                side_effect=RuntimeError(f"migration boom {secret_url}"),
            ):
                with pytest.raises(WindFlowException) as exc_info:
                    await database.run_migrations()

            message = str(exc_info.value)
            assert "migration boom" in message
            # Sécurité : l'URL DB (potentiellement avec credentials) est masquée.
            assert secret_url not in message
            assert isinstance(exc_info.value.__cause__, RuntimeError)
        finally:
            await database.disconnect()
            settings.database_url = original_url


class TestStartupSeedPreserved:
    """Seed préservé : ordre startup inchangé (connect → migrations → seed)."""

    async def test_seed_runs_after_migrations_on_fresh_db(self, tmp_path: Path) -> None:
        """Après migrations sur base vierge, ``seed_tables()`` crée bien
        l'organisation par défaut et l'admin superuser (comportement
        historique inchangé)."""
        db_path = tmp_path / "startup.db"
        original_url = settings.database_url
        original_admin_email = settings.admin_email
        settings.database_url = f"sqlite+aiosqlite:///{db_path}"
        # Robustesse inter-versions d'email-validator : le défaut
        # ``admin@windflow.local`` (TLD réservé) est rejeté par les versions
        # récentes — sans lien avec le schéma ni le seed lui-même.
        settings.admin_email = "admin-seed-test@example.com"
        database = Database()
        try:
            await database.connect()
            await database.run_migrations()

            # Le scan réseau localhost (subprocess docker/libvirt) est
            # indépendant du schéma et non déterministe en CI → stubbé.
            with patch(
                "app.database_seed._create_localhost_target",
                new=AsyncMock(return_value=(False, ["scan stubbed in test"])),
            ):
                await database.seed_tables()

            async with database.session() as session:
                orgs = (await session.execute(select(Organization))).scalars().all()
                assert any(
                    o.slug == settings.default_org_slug for o in orgs
                ), "Organisation par défaut absente après seed"

                admin = (
                    await session.execute(
                        select(User).where(User.username == settings.admin_username)
                    )
                ).scalar_one_or_none()
                assert admin is not None, "Admin par défaut absent après seed"
                assert admin.is_superuser
        finally:
            await database.disconnect()
            settings.database_url = original_url
            settings.admin_email = original_admin_email


class TestNoNakedCreateAll:
    """test_no_naked_create_all_in_app_code — critère de done de l'epic."""

    def test_no_naked_create_all_in_app_code(self) -> None:
        """Inspection statique : aucun ``metadata.create_all`` actif dans
        ``backend/app/`` (les commentaires sont ignorés)."""
        offenders: list[str] = []
        for py_file in sorted(APP_DIR.rglob("*.py")):
            for lineno, line in enumerate(
                py_file.read_text(encoding="utf-8").splitlines(), 1
            ):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "metadata.create_all" in line or ".create_all(" in line:
                    offenders.append(f"{py_file.relative_to(REPO_ROOT)}:{lineno}")

        assert not offenders, (
            "create_all nu détecté dans backend/app/ : "
            f"{offenders} (le schéma doit passer exclusivement par Alembic)"
        )


class TestConftestSchemaFromMigrations:
    """Fixture ``test_db_engine`` : schéma par migrations, isolation par test."""

    async def test_engine_schema_comes_from_migrations(self, test_db_engine) -> None:
        """La base de test contient les tables métier ET ``alembic_version``
        — seule preuve possible d'un schéma appliqué par migrations."""
        async with test_db_engine.connect() as conn:
            tables = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))

        assert set(Base.metadata.tables) <= tables
        assert "alembic_version" in tables

    async def test_engine_data_isolated_per_test(self, test_session_factory) -> None:
        """Chaque test repart d'une copie vierge du template migré (aucune
        donnée résiduelle des tests précédents)."""
        async with test_session_factory() as session:
            user = (await session.execute(select(User))).scalars().first()
        assert user is None, "La base de test devait être vide de données"
