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
   PostgreSQL n'est pas joignable — ex. environnement local sans PG de CI) ;
6. STORY-121.1 : migration additive ``user_organizations`` — structure
   (colonnes, PK composite, FK CASCADE, index, défaut serveur ``viewer``)
   sur base vierge **et** sur base legacy stampée baseline.

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
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine

from app import models  # noqa: F401  # enregistre tous les modèles
from app.config import settings
from app.database import Base, Database, get_alembic_config
from app.models.organization import Organization
from app.models.user import User
from app.services.user_service import UserService

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"

# Tables métier attendues + table technique Alembic (STORY-121.1 :
# + user_organizations ; STORY-123.1 : + refresh_tokens).
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
    "user_organizations",
    "refresh_tokens",
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


def _upgraded_engine(tmp_path: Path, name: str = "uorg.db") -> Engine:
    """Applique ``upgrade head`` sur une base SQLite vierge et retourne
    un engine sync jetable pour inspection structurelle.

    Args:
        tmp_path: Répertoire temporaire unique du test.
        name: Nom du fichier de base SQLite.

    Returns:
        Engine: Engine sync connecté à la base migrée (à disposer).
    """
    db_path = tmp_path / name
    result = _run_alembic("upgrade", "head", db_url=f"sqlite+aiosqlite:///{db_path}")
    assert (
        result.returncode == 0
    ), f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
    return create_engine(f"sqlite:///{db_path}")


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
        assert (
            result.returncode == 0
        ), f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"

        tables = _sqlite_table_names(db_path)
        missing = EXPECTED_TABLES - tables
        assert not missing, f"Tables manquantes après upgrade head : {missing}"
        # Le schéma provient bien des migrations : présence d'alembic_version.
        assert "alembic_version" in tables


def _add_legacy_users_org_column(db_path: Path) -> None:
    """STORY-121.3 : recrée la colonne héritée ``users.organization_id``
    (+ index) sur une base legacy stampée — le schéma courant (modèles)
    ne la crée plus, mais la migration 1213 s'attend à la trouver."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN organization_id VARCHAR(36)")
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_users_organization_id "
                    "ON users (organization_id)"
                )
            )
    finally:
        engine.dispose()


class TestExistingDbStampedThenStartupNoDiff:
    """test_existing_db_stamped_then_startup_has_no_diff."""

    async def test_existing_db_stamped_then_startup_has_no_diff(
        self, tmp_path: Path
    ) -> None:
        """Scénario 2 : base existante non versionnée (créée historiquement
        par ``create_all`` — simulé ici, usage interdit dans ``backend/app/``,
        et **antérieure à STORY-121.1**) → stamp baseline → démarrage migré
        (applique la migration additive ``user_organizations``) →
        ``alembic check`` sans diff : aucune table existante recréée ni
        altérée, données préservées."""
        db_path = tmp_path / "legacy.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # Installation legacy : schéma create_all + DROP des tables
        # additives (les métadonnées courantes les créeraient aussi — il
        # faut simuler une base strictement antérieure à STORY-121.1 ;
        # pattern étendu à refresh_tokens par STORY-123.1)
        # + données métier.
        legacy_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(legacy_engine)
        with legacy_engine.begin() as conn:
            conn.execute(text("DROP TABLE user_organizations"))
            conn.execute(text("DROP TABLE refresh_tokens"))
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
        # STORY-121.3 : la colonne héritée doit être simulée avant
        # l'upgrade (1213 la copie puis la retire)
        _add_legacy_users_org_column(db_path)
        stamp = _run_alembic("stamp", "baseline", db_url=db_url)
        assert (
            stamp.returncode == 0
        ), f"stamp baseline a échoué :\nstdout={stamp.stdout}\nstderr={stamp.stderr}"
        await _startup_migrated(db_path)

        # Aucune recréation/altération : mêmes tables + les tables
        # additives, données intactes.
        tables_after = _sqlite_table_names(db_path)
        assert tables_after == tables_before | {
            "alembic_version",
            "user_organizations",
            "refresh_tokens",
        }
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


class TestUserOrganizationsTableMigration:
    """STORY-121.1 — migration additive ``user_organizations`` : structure
    de la table (spec 06/08) sur base vierge **et** sur base legacy
    stampée baseline."""

    def test_fresh_db_upgrade_creates_user_organizations_table(
        self, tmp_path: Path
    ) -> None:
        """Base vierge → ``upgrade head`` → table ``user_organizations``
        présente dans le schéma."""
        engine = _upgraded_engine(tmp_path, "fresh-uorg.db")
        try:
            assert "user_organizations" in inspect(engine).get_table_names()
        finally:
            engine.dispose()

    def test_table_structure_matches_spec_06(self, tmp_path: Path) -> None:
        """Colonnes conformes à la spec 06 : ``user_id``/``organization_id``
        ``String(36)`` NOT NULL, ``role`` ``String(20)`` NOT NULL avec
        défaut serveur ``'viewer'``, ``joined_at``/``created_at``/
        ``updated_at`` ``DateTime`` NOT NULL."""
        engine = _upgraded_engine(tmp_path, "structure-uorg.db")
        try:
            columns = {
                col["name"]: col
                for col in inspect(engine).get_columns("user_organizations")
            }
        finally:
            engine.dispose()

        assert set(columns) == {
            "user_id",
            "organization_id",
            "role",
            "joined_at",
            "created_at",
            "updated_at",
        }
        for name, length in (
            ("user_id", 36),
            ("organization_id", 36),
            ("role", 20),
        ):
            assert (
                columns[name]["type"].length == length
            ), f"{name} doit être String({length})"
            assert not columns[name]["nullable"], f"{name} doit être NOT NULL"

        # Défaut serveur 'viewer' (SQLite le rend avec quotes).
        role_default = columns["role"]["default"]
        assert (
            role_default is not None and role_default.strip("'\"") == "viewer"
        ), f"role doit avoir un server_default 'viewer', obtenu : {role_default!r}"
        for name in ("joined_at", "created_at", "updated_at"):
            assert not columns[name]["nullable"], f"{name} doit être NOT NULL"

    def test_composite_primary_key(self, tmp_path: Path) -> None:
        """PK composite == (user_id, organization_id) — une seule
        association par couple utilisateur × organisation."""
        engine = _upgraded_engine(tmp_path, "pk-uorg.db")
        try:
            pk = inspect(engine).get_pk_constraint("user_organizations")
        finally:
            engine.dispose()
        assert pk["constrained_columns"] == ["user_id", "organization_id"]

    def test_foreign_keys_cascade(self, tmp_path: Path) -> None:
        """FK ``user_id → users.id`` et ``organization_id →
        organizations.id`` avec ``ondelete CASCADE`` (réflexion SQLite)."""
        engine = _upgraded_engine(tmp_path, "fk-uorg.db")
        try:
            with engine.connect() as conn:
                rows = conn.exec_driver_sql(
                    "PRAGMA foreign_key_list(user_organizations)"
                ).fetchall()
        finally:
            engine.dispose()

        fks = {
            row[3]: {"table": row[2], "to": row[4], "on_delete": row[6]} for row in rows
        }
        assert fks["user_id"]["table"] == "users"
        assert fks["user_id"]["to"] == "id"
        assert fks["user_id"]["on_delete"] == "CASCADE"
        assert fks["organization_id"]["table"] == "organizations"
        assert fks["organization_id"]["to"] == "id"
        assert fks["organization_id"]["on_delete"] == "CASCADE"

    def test_index_on_organization_id(self, tmp_path: Path) -> None:
        """Index ``ix_user_organizations_organization_id`` présent, non
        unique (spec 06 — la PK composite couvre déjà ``user_id``)."""
        engine = _upgraded_engine(tmp_path, "idx-uorg.db")
        try:
            indexes = inspect(engine).get_indexes("user_organizations")
        finally:
            engine.dispose()

        by_name = {idx["name"]: idx for idx in indexes}
        assert (
            "ix_user_organizations_organization_id" in by_name
        ), f"Index manquant : présentes = {sorted(by_name)}"
        index = by_name["ix_user_organizations_organization_id"]
        # SQLite renvoie un entier (0/1) pour « unique ».
        assert not index["unique"]
        assert index["column_names"] == ["organization_id"]

    def test_stamped_baseline_db_upgrade_creates_table_and_preserves_data(
        self, tmp_path: Path
    ) -> None:
        """Base legacy simulée (create_all + ``DROP TABLE
        user_organizations`` + donnée org insérée) → stamp baseline →
        ``upgrade head`` → table ``user_organizations`` créée **vide**,
        données existantes intactes, version = head courant."""
        db_path = tmp_path / "stamped-uorg.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        legacy_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(legacy_engine)
        with legacy_engine.begin() as conn:
            conn.execute(text("DROP TABLE user_organizations"))
            conn.execute(text("DROP TABLE refresh_tokens"))
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

        # STORY-121.3 : simuler la colonne héritée (base pré-121.3)
        _add_legacy_users_org_column(db_path)

        stamp = _run_alembic("stamp", "baseline", db_url=db_url)
        assert (
            stamp.returncode == 0
        ), f"stamp baseline a échoué :\nstdout={stamp.stdout}\nstderr={stamp.stderr}"

        upgrade = _run_alembic("upgrade", "head", db_url=db_url)
        assert (
            upgrade.returncode == 0
        ), f"upgrade head a échoué :\nstdout={upgrade.stdout}\nstderr={upgrade.stderr}"
        assert (
            "Running upgrade baseline -> 1211_user_organizations"
            in upgrade.stdout + upgrade.stderr
        ), "La migration additive n'a pas été appliquée après stamp baseline"

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            assert "user_organizations" in inspector.get_table_names()

            # Migration strictement additive : table créée vide.
            with engine.connect() as conn:
                count = conn.execute(
                    text("SELECT COUNT(*) FROM user_organizations")
                ).scalar_one()
                slug = conn.execute(
                    text("SELECT slug FROM organizations WHERE id = 'org-legacy'")
                ).scalar_one_or_none()
                version = conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
        finally:
            engine.dispose()

        assert count == 0, "La table additive doit être créée vide (pas de copie)"
        assert slug == "legacy-org", "Les données existantes ont été altérées"
        assert (
            version
            == ScriptDirectory.from_config(get_alembic_config()).get_current_head()
        )


class TestUsersOrgMigrationData:
    """STORY-121.3 — migration de données ``users.organization_id`` →
    ``user_organizations`` (mapping non cassant) + retrait de la colonne.

    Simulation base legacy pré-121.3 : ``create_all`` (qui, depuis le
    retrait de la colonne du modèle, ne crée plus ``users.organization_id``)
    **puis** recréation manuelle de la colonne legacy + index + fixtures
    réalistes — fidèle à une base antérieure à STORY-121.3.
    """

    @staticmethod
    def _seed_legacy_base(db_path: Path) -> None:
        """Base legacy pré-121.3 : schéma create_all (drop de
        ``user_organizations`) + colonne ``users.organization_id`` recréée
        à la main + données réalistes (2 orgs, 4 users)."""
        legacy_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(legacy_engine)
        with legacy_engine.begin() as conn:
            conn.execute(text("DROP TABLE user_organizations"))
            conn.execute(text("DROP TABLE refresh_tokens"))
            # Recréer la colonne legacy (create_all ne la crée plus)
            conn.execute(
                text("ALTER TABLE users ADD COLUMN organization_id VARCHAR(36)")
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_users_organization_id "
                    "ON users (organization_id)"
                )
            )
            for org_id, name in (("org-a", "Org A"), ("org-b", "Org B")):
                conn.execute(
                    text(
                        "INSERT INTO organizations "
                        "(id, name, slug, settings, created_at, updated_at) "
                        "VALUES (:id, :name, :slug, '{}', "
                        "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                    ),
                    {"id": org_id, "name": name, "slug": org_id},
                )
            users = [
                ("u-super", "s@x.io", "super", 1, "org-a"),
                ("u-op", "o@x.io", "oper", 0, "org-a"),
                ("u-op2", "o2@x.io", "oper2", 0, "org-b"),
                ("u-null", "n@x.io", "nullorg", 0, None),
            ]
            for uid, email, username, su, org in users:
                conn.execute(
                    text(
                        "INSERT INTO users (id, email, username, full_name, "
                        "hashed_password, is_active, is_superuser, keycloak_id, "
                        "organization_id, created_at, updated_at) "
                        "VALUES (:id, :email, :username, :full_name, 'h', 1, "
                        ":su, NULL, :org, "
                        "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                    ),
                    {
                        "id": uid,
                        "email": email,
                        "username": username,
                        "full_name": username.title(),
                        "su": su,
                        "org": org,
                    },
                )
        legacy_engine.dispose()

    @staticmethod
    def _associations(db_path: Path) -> list[tuple[str, str, str]]:
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                return conn.exec_driver_sql(
                    "SELECT user_id, organization_id, role FROM user_organizations"
                ).fetchall()
        finally:
            engine.dispose()

    @staticmethod
    def _users_columns(db_path: Path) -> set[str]:
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            return {col["name"] for col in inspect(engine).get_columns("users")}
        finally:
            engine.dispose()

    def _legacy_then_upgrade(self, tmp_path: Path, name: str) -> Path:
        db_path = tmp_path / name
        db_url = f"sqlite+aiosqlite:///{db_path}"
        self._seed_legacy_base(db_path)
        stamp = _run_alembic("stamp", "baseline", db_url=db_url)
        assert stamp.returncode == 0, stamp.stderr
        upgrade = _run_alembic("upgrade", "head", db_url=db_url)
        assert (
            upgrade.returncode == 0
        ), f"upgrade head a échoué :\nstdout={upgrade.stdout}\nstderr={upgrade.stderr}"
        return db_path

    def test_migration_creates_association_for_every_user_with_org(
        self, tmp_path: Path
    ) -> None:
        """Sans perte : chaque user avec organization_id a exactement 1
        ligne user_organizations avec le bon (user_id, organization_id)."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-1.db")
        rows = self._associations(db_path)
        by_user = {row[0]: row for row in rows}
        assert by_user["u-super"][1] == "org-a"
        assert by_user["u-op"][1] == "org-a"
        assert by_user["u-op2"][1] == "org-b"

    def test_migration_mapping_superuser_gets_admin_role(self, tmp_path: Path) -> None:
        """Mapping non cassant : superuser → ``admin`` **et** flag
        ``is_superuser`` inchangé (le rôle système reste porté par le flag)."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-2.db")
        rows = dict((row[0], row[2]) for row in self._associations(db_path))
        assert rows["u-super"] == "admin"

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                su = conn.execute(
                    text("SELECT is_superuser FROM users WHERE id='u-super'")
                ).scalar_one()
        finally:
            engine.dispose()
        assert su == 1

    def test_migration_mapping_regular_user_gets_operator_role(
        self, tmp_path: Path
    ) -> None:
        """User actif non-superuser → ``operator``."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-3.db")
        rows = dict((row[0], row[2]) for row in self._associations(db_path))
        assert rows["u-op"] == "operator"
        assert rows["u-op2"] == "operator"

    def test_migration_no_row_for_user_without_org(self, tmp_path: Path) -> None:
        """User avec organization_id NULL → aucune ligne (pas de
        rattachement inventé)."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-4.db")
        rows = self._associations(db_path)
        assert not any(row[0] == "u-null" for row in rows)

    def test_migration_drops_users_organization_id_column_and_index(
        self, tmp_path: Path
    ) -> None:
        """Colonne ``organization_id`` absente de ``users`` après upgrade."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-5.db")
        cols = self._users_columns(db_path)
        assert "organization_id" not in cols

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            indexes = inspect(engine).get_indexes("users")
        finally:
            engine.dispose()
        assert all(idx["name"] != "ix_users_organization_id" for idx in indexes)

    def test_migration_idempotent_via_composite_pk(self, tmp_path: Path) -> None:
        """La migration rejouée sur données migrées ne duplique pas (garde
        NOT EXISTS + PK composite) — scénario downgrade (associations
        conservées) puis re-upgrade."""
        db_path = tmp_path / "mig-data-6.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"
        self._seed_legacy_base(db_path)
        stamp = _run_alembic("stamp", "baseline", db_url=db_url)
        assert stamp.returncode == 0
        assert _run_alembic("upgrade", "head", db_url=db_url).returncode == 0
        rows_after_first = sorted(self._associations(db_path))
        assert len(rows_after_first) == 3

        # Downgrade (conserve les associations) puis re-upgrade
        down = _run_alembic("downgrade", "1211_user_organizations", db_url=db_url)
        assert down.returncode == 0, down.stderr
        up = _run_alembic("upgrade", "head", db_url=db_url)
        assert up.returncode == 0, up.stderr

        rows_after_replay = sorted(self._associations(db_path))
        assert (
            rows_after_replay == rows_after_first
        ), "la migration rejouée ne doit pas dupliquer les associations"

    def test_downgrade_restores_column_nullable_and_backfills_first_membership(
        self, tmp_path: Path
    ) -> None:
        """Downgrade : colonne recréée **nullable**, backfill première
        appartenance par joined_at, lignes user_organizations conservées
        (limite documentée)."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-7.db")
        db_url = f"sqlite+aiosqlite:///{db_path}"
        down = _run_alembic("downgrade", "1211_user_organizations", db_url=db_url)
        assert down.returncode == 0, down.stderr

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            columns = {col["name"]: col for col in inspect(engine).get_columns("users")}
            assert "organization_id" in columns
            assert columns["organization_id"]["nullable"] is True
            with engine.connect() as conn:
                org = conn.execute(
                    text("SELECT organization_id FROM users WHERE id='u-super'")
                ).scalar_one()
                count = conn.execute(
                    text("SELECT COUNT(*) FROM user_organizations")
                ).scalar_one()
        finally:
            engine.dispose()
        assert org == "org-a", "backfill première appartenance"
        assert count == 3, "les associations sont conservées au downgrade"

    def test_full_upgrade_path_preserves_existing_data(self, tmp_path: Path) -> None:
        """Données préexistantes (stacks d'une org) intactes après le
        chemin complet baseline → 1211 → 1213."""
        db_path = self._legacy_then_upgrade(tmp_path, "mig-data-8.db")
        # Ajouter une stack puis rejouer via downgrade/upgrade complets
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO stacks (id, name, description, version, "
                        "category, tags, template, variables, icon_url, "
                        "screenshots, documentation_url, author, license, "
                        "organization_id, target_type, is_public, downloads, "
                        "rating, is_archived, created_at, updated_at) "
                        "VALUES ('stk-1', 'legacy-stack', NULL, '1.0.0', NULL, "
                        "'[]', '{}', '{}', NULL, '[]', NULL, NULL, 'MIT', "
                        "'org-a', 'docker', 0, 0, 0, 0, "
                        "'2026-01-01 00:00:00', '2026-01-01 00:00:00')"
                    )
                )
        finally:
            engine.dispose()

        db_url = f"sqlite+aiosqlite:///{db_path}"
        # Rejouer 1213 (downgrade → upgrade) : les stacks doivent survivre
        assert (
            _run_alembic(
                "downgrade", "1211_user_organizations", db_url=db_url
            ).returncode
            == 0
        )
        assert _run_alembic("upgrade", "head", db_url=db_url).returncode == 0

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as conn:
                name = conn.execute(
                    text("SELECT name FROM stacks WHERE id='stk-1'")
                ).scalar_one_or_none()
        finally:
            engine.dispose()
        assert name == "legacy-stack", "données préexistantes altérées"


class TestAlembicCheckNoPendingChanges:
    """test_alembic_check_reports_no_pending_changes."""

    def test_alembic_check_reports_no_pending_changes(self, tmp_path: Path) -> None:
        """Scénario 3 : après ``upgrade head``, ``alembic check`` ne détecte
        aucun changement en attente — la baseline est synchronisée avec les
        modèles (garde-fou anti-dérivation modèles/migrations)."""
        db_path = tmp_path / "check.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        upgrade = _run_alembic("upgrade", "head", db_url=db_url)
        assert (
            upgrade.returncode == 0
        ), f"upgrade head a échoué :\nstdout={upgrade.stdout}\nstderr={upgrade.stderr}"

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
                assert any(
                    o.slug == settings.default_org_slug for o in orgs
                ), "Organisation par défaut absente après seed sur base migrée"

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
