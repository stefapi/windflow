"""Tests d'intégration des migrations Alembic (STORY-120.3).

Scénarios couverts (AC 3/AC 4 de STORY-120) :
1. base vierge SQLite → ``upgrade head`` → schéma complet créé par les
   migrations uniquement (inspection) ;
2. base existante non versionnée (héritage ``create_all``) → stamp baseline
   → démarrage → **aucun diff** (``alembic check``) : aucune recréation ni
   altération des tables existantes ;
3. ``alembic check`` sans diff après upgrade (baseline synchronisée avec
   les modèles) ;
4. non-régression du seed sur base migrée : organisation par défaut
   présente + login admin fonctionnel (vérification du mot de passe) ;
5. variante PostgreSQL des scénarios 1 et 3 (skippée si le service
   PostgreSQL n'est pas joignable — ex. environnement local sans PG de CI).

La génération ``make migrate`` (autogenerate) est validée manuellement sur
un changement de modèle factice reverté ensuite (AC 3) — hors pytest car
elle modifie les sources et le dossier ``versions/``.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app import models  # noqa: F401  # enregistre tous les modèles
from app.config import settings
from app.database import Base, Database
from app.models.organization import Organization
from app.models.user import User
from app.services.user_service import UserService

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

# Tables métier attendues + table technique Alembic.
EXPECTED_TABLES = {
    "users",
    "organizations",
    "targets",
    "stacks",
    "stack_versions",
    "deployments",
    "plugins",
    "plugin_hook_logs",
    "scheduled_tasks",
    "target_capabilities",
    "alembic_version",
}

# URL PostgreSQL de test : paramétrable via l'environnement (CI : service
# postgres du job), aucun secret en dur côté application — les credentials
# de CI vivent dans la définition du workflow.
PG_TEST_URL = os.environ.get(
    "WINDFLOW_TEST_PG_URL",
    "postgresql+asyncpg://windflow:windflow123@localhost:5432/windflow_migrations",
)


def _run_alembic(*args: str, db_url: str) -> subprocess.CompletedProcess[str]:
    """Exécute la CLI alembic dans un sous-process isolé (env DATABASE_URL)."""
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _sqlite_table_names(db_path: Path) -> set[str]:
    """Inspecte les tables d'une base SQLite via un engine sync jetable."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


async def _startup_migrated(db_path: Path) -> Database:
    """Simule le démarrage applicatif (connect → run_migrations) sur une
    base fichier isolée ; l'URL des settings est restaurée en fin."""
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


class TestFreshSqliteDbUpgradeHead:
    """test_fresh_sqlite_db_upgrade_head_creates_full_schema."""

    async def test_fresh_sqlite_db_upgrade_head_creates_full_schema(
        self, tmp_path: Path
    ) -> None:
        """Scénario 1 : base vierge → ``upgrade head`` (CLI alembic) →
        le schéma complet des modèles est créé par les migrations uniquement."""
        db_path = tmp_path / "fresh.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        result = _run_alembic("upgrade", "head", db_url=db_url)
        assert result.returncode == 0, (
            f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        )

        tables = _sqlite_table_names(db_path)
        missing = EXPECTED_TABLES - tables
        assert not missing, f"Tables manquantes après upgrade head : {missing}"
        # Le schéma provient bien des migrations : présence d'alembic_version.
        assert "alembic_version" in tables


class TestExistingDbStampedThenStartupNoDiff:
    """test_existing_db_stamped_then_startup_has_no_diff."""

    async def test_existing_db_stamped_then_startup_has_no_diff(
        self, tmp_path: Path
    ) -> None:
        """Scénario 2 : base existante non versionnée (créée historiquement
        par ``create_all`` — simulé ici, usage interdit dans ``backend/app/``)
        → stamp baseline → démarrage migré → ``alembic check`` sans diff :
        aucune table recréée ni altérée, données préservées."""
        db_path = tmp_path / "legacy.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # Installation legacy : schéma create_all + données métier.
        legacy_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(legacy_engine)
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
        tables_before = _sqlite_table_names(db_path)
        assert "alembic_version" not in tables_before

        # Stamp explicite (équivalent du make migrate-stamp pour ops) puis
        # démarrage applicatif migré (détection versioned → upgrade no-op).
        stamp = _run_alembic("stamp", "baseline", db_url=db_url)
        assert stamp.returncode == 0, (
            f"stamp baseline a échoué :\nstdout={stamp.stdout}\nstderr={stamp.stderr}"
        )
        await _startup_migrated(db_path)

        # Aucune recréation/altération : mêmes tables, données intactes.
        tables_after = _sqlite_table_names(db_path)
        assert tables_after == tables_before | {"alembic_version"}
        check_engine = create_engine(f"sqlite:///{db_path}")
        try:
            with check_engine.connect() as conn:
                slug = conn.execute(
                    text("SELECT slug FROM organizations WHERE id = 'org-legacy'")
                ).scalar_one_or_none()
        finally:
            check_engine.dispose()
        assert slug == "legacy-org", "Données existantes altérées par le démarrage"

        # Preuve « aucun diff » : alembic check ne détecte rien.
        check = _run_alembic("check", db_url=db_url)
        assert check.returncode == 0, (
            f"alembic check rapporte un diff inattendu :\n"
            f"stdout={check.stdout}\nstderr={check.stderr}"
        )


class TestAlembicCheckNoPendingChanges:
    """test_alembic_check_reports_no_pending_changes."""

    def test_alembic_check_reports_no_pending_changes(self, tmp_path: Path) -> None:
        """Scénario 3 : après ``upgrade head``, ``alembic check`` ne détecte
        aucun changement en attente — la baseline est synchronisée avec les
        modèles (garde-fou anti-dérivation modèles/migrations)."""
        db_path = tmp_path / "check.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        upgrade = _run_alembic("upgrade", "head", db_url=db_url)
        assert upgrade.returncode == 0, (
            f"upgrade head a échoué :\nstdout={upgrade.stdout}\nstderr={upgrade.stderr}"
        )

        check = _run_alembic("check", db_url=db_url)
        assert check.returncode == 0, (
            f"alembic check rapporte des changements en attente :\n"
            f"stdout={check.stdout}\nstderr={check.stderr}"
        )


class TestMigratedDbSeedAndAdminLogin:
    """test_migrated_existing_db_seed_and_admin_login_not_regressed."""

    async def test_migrated_existing_db_seed_and_admin_login_not_regressed(
        self, tmp_path: Path
    ) -> None:
        """Scénario 4 : démarrage complet sur base vierge migrée
        (migrations puis seed) → organisation par défaut présente, admin
        créé, **login admin fonctionnel** (mot de passe vérifié positivement
        et rejeté s'il est erroné)."""
        db_path = tmp_path / "seeded.db"

        original_url = settings.database_url
        original_admin_email = settings.admin_email
        settings.database_url = f"sqlite+aiosqlite:///{db_path}"
        # Robustesse inter-versions d'email-validator (cf. STORY-120.2) :
        # le défaut admin@windflow.local (TLD réservé) est rejeté par les
        # versions récentes — sans lien avec le schéma ni le seed.
        settings.admin_email = "admin-migration-test@example.com"
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
                # Organisation par défaut présente.
                orgs = (await session.execute(select(Organization))).scalars().all()
                assert any(o.slug == settings.default_org_slug for o in orgs), (
                    "Organisation par défaut absente après seed sur base migrée"
                )

                # Admin présent et superuser.
                admin = (
                    await session.execute(
                        select(User).where(User.username == settings.admin_username)
                    )
                ).scalar_one_or_none()
                assert admin is not None, "Admin par défaut absent après seed"
                assert admin.is_superuser

                # Login admin fonctionnel : mot de passe accepté,
                # mot de passe erroné rejeté.
                assert await UserService.verify_and_update_user(
                    session, admin, settings.admin_password
                ), "Login admin en échec sur base migrée (mot de passe rejeté)"
                assert not await UserService.verify_and_update_user(
                    session, admin, "definitely-wrong-password"
                ), "Un mot de passe erroné ne doit jamais être accepté"
        finally:
            await database.disconnect()
            settings.database_url = original_url
            settings.admin_email = original_admin_email


class TestMigrationsCompatiblePostgresql:
    """test_migrations_compatible_postgresql (skippé si PG indisponible)."""

    def _pg_available(self) -> bool:
        """Vérifie la joignabilité du service PostgreSQL (timeout court)."""

        async def _probe() -> bool:
            import asyncpg

            plain_url = PG_TEST_URL.replace("+asyncpg", "")
            try:
                conn = await asyncio.wait_for(asyncpg.connect(plain_url), timeout=3)
            except Exception:
                return False
            await conn.close()
            return True

        return asyncio.run(_probe())

    def test_migrations_compatible_postgresql(self) -> None:
        """Scénario 5 : mêmes opérations sur PostgreSQL — ``upgrade head``
        sur base vierge (schéma complet) puis ``alembic check`` sans diff.

        Skippé si le service PostgreSQL n'est pas joignable (développement
        local sans conteneur CI ; les credentials de test viennent de
        ``WINDFLOW_TEST_PG_URL`` ou du défaut aligné sur le service CI).
        """
        if not self._pg_available():
            pytest.skip("Service PostgreSQL de test indisponible (hors CI)")

        async def _fresh_schema() -> None:
            """Drop toutes les tables pour démarrer sur une base vierge."""
            import asyncpg

            plain_url = PG_TEST_URL.replace("+asyncpg", "")
            conn = await asyncpg.connect(plain_url)
            try:
                rows = await conn.fetch(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                for row in rows:
                    await conn.execute(
                        f'DROP TABLE IF EXISTS "{row["tablename"]}" CASCADE'
                    )
            finally:
                await conn.close()

        asyncio.run(_fresh_schema())

        upgrade = _run_alembic("upgrade", "head", db_url=PG_TEST_URL)
        assert upgrade.returncode == 0, (
            f"upgrade head (PostgreSQL) a échoué :\n"
            f"stdout={upgrade.stdout}\nstderr={upgrade.stderr}"
        )

        check = _run_alembic("check", db_url=PG_TEST_URL)
        assert check.returncode == 0, (
            f"alembic check (PostgreSQL) rapporte un diff :\n"
            f"stdout={check.stdout}\nstderr={check.stderr}"
        )

        async def _inspect_tables() -> set[str]:
            import asyncpg

            plain_url = PG_TEST_URL.replace("+asyncpg", "")
            conn = await asyncpg.connect(plain_url)
            try:
                rows = await conn.fetch(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            finally:
                await conn.close()
            return {row["tablename"] for row in rows}

        tables = asyncio.run(_inspect_tables())
        missing = EXPECTED_TABLES - tables
        assert not missing, f"Tables manquantes sur PostgreSQL : {missing}"
