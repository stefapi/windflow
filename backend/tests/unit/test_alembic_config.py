"""Tests de l'infrastructure Alembic (STORY-120.1).

Vérifie :
- le ``alembic.ini`` racine est parsable et pointe vers ``backend/alembic/`` ;
- ``env.py`` ne loggue jamais l'URL DB (qui peut contenir le mot de
  passe PostgreSQL) ;
- la migration baseline crée exactement les tables de ``Base.metadata`` ;
- le scénario AC 1 : base existante (create_all) → ``stamp baseline`` →
  ``upgrade head`` no-op → ``alembic check`` sans diff.
"""

import os
import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from app import models  # noqa: F401  # enregistre tous les modèles
from app.database import Base

REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
SCRIPT_LOCATION = REPO_ROOT / "backend" / "alembic"

# Tables attendues : exactement celles des modèles ORM (STORY-121.1 :
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
}


def _run_alembic(*args: str, db_url: str) -> subprocess.CompletedProcess[str]:
    """Exécute la CLI alembic dans un sous-process isolé (env DATABASE_URL)."""
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class TestAlembicIni:
    """test_alembic_ini_resolves_script_location."""

    def test_alembic_ini_resolves_script_location(self) -> None:
        """L'alembic.ini racine est parsable et script_location existe."""
        assert ALEMBIC_INI.is_file(), "alembic.ini manquant à la racine du repo"

        parser = ConfigParser()
        read = parser.read(ALEMBIC_INI)
        assert read, "alembic.ini illisible"

        script_location = parser.get("alembic", "script_location")
        assert script_location, "script_location vide"

        resolved = (REPO_ROOT / script_location).resolve()
        assert resolved == SCRIPT_LOCATION.resolve()
        assert resolved.is_dir(), f"backend/alembic/ introuvable : {resolved}"
        assert (resolved / "env.py").is_file(), "env.py manquant"
        assert (SCRIPT_LOCATION / "versions").is_dir(), "versions/ manquant"

    def test_alembic_ini_contains_no_secret(self) -> None:
        """Sécurité : sqlalchemy.url reste vide dans alembic.ini."""
        parser = ConfigParser()
        parser.read(ALEMBIC_INI)
        url = parser.get("alembic", "sqlalchemy.url", fallback="")
        assert url.strip() == "", "sqlalchemy.url doit rester vide (aucun secret)"


class TestEnvDoesNotLogDatabaseUrl:
    """test_env_does_not_log_database_url."""

    def test_env_does_not_log_database_url(self, tmp_path: Path) -> None:
        """L'URL DB (avec credentials en variante PostgreSQL) n'apparaît
        dans aucun log après exécution d'env.py.

        Le mode offline (``--sql``) exécute réellement ``env.py`` (branche
        ``run_migrations_offline``) avec le dialecte PostgreSQL **sans
        connexion réseau** : tout le pipeline est exercé et l'on vérifie
        que le mot de passe n'apparaît ni dans stdout (DDL généré) ni dans
        stderr (logs alembic).
        """
        db_path = tmp_path / "nolog.db"

        # Variante SQLite : URL avec query-param secret — exécution online
        # complète, le secret ne doit fuir dans aucune sortie.
        sqlite_url = f"sqlite+aiosqlite:///{db_path}?secret=S3cret-P4ssw0rd"
        result = _run_alembic("upgrade", "head", db_url=sqlite_url)
        assert (
            result.returncode == 0
        ), f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        combined = result.stdout + result.stderr
        assert (
            "S3cret-P4ssw0rd" not in combined
        ), "L'URL DB (avec secret) fuit dans les sorties de la CLI alembic"

        # Variante PostgreSQL : mode offline (--sql) exécute env.py avec le
        # dialecte asyncpg/PostgreSQL et un mot de passe dans l'URL, sans
        # nécessiter de serveur réel.
        pg_url = "postgresql+asyncpg://windflow:S3cret-P4ssw0rd@localhost:5432/windflow"
        result = _run_alembic("upgrade", "base:head", "--sql", db_url=pg_url)
        assert result.returncode == 0, (
            f"upgrade --sql (offline PostgreSQL) a échoué :\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert (
            "S3cret-P4ssw0rd" not in combined
        ), "Le mot de passe PostgreSQL est apparu dans les logs/DDL générés"
        # Le DDL offline PostgreSQL contient bien les CREATE TABLE attendus :
        # preuve que env.py a traité la variante PostgreSQL de bout en bout.
        assert "CREATE TABLE organizations" in result.stdout


class TestBaselineCreatesAllModelTables:
    """test_baseline_creates_all_model_tables."""

    def test_baseline_creates_all_model_tables(self, tmp_path: Path) -> None:
        """``alembic upgrade head`` sur base SQLite temporaire → l'inspection
        révèle exactement les tables de Base.metadata (ni plus, ni moins).

        Depuis STORY-121.1, le schéma complet est créé par ``upgrade head``
        (baseline + migration additive ``user_organizations``) et non par
        la seule baseline."""
        db_path = tmp_path / "baseline.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        result = _run_alembic("upgrade", "head", db_url=db_url)
        assert (
            result.returncode == 0
        ), f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            inspector = inspect(engine)
            db_tables = set(inspector.get_table_names())
        finally:
            engine.dispose()

        # alembic_version est créée par Alembic lui-même : attendue en plus.
        assert db_tables == EXPECTED_TABLES | {
            "alembic_version"
        }, f"Tables observées : {sorted(db_tables)}"
        assert db_tables == set(Base.metadata.tables) | {"alembic_version"}, (
            "La baseline diverge de Base.metadata : "
            f"{db_tables ^ (set(Base.metadata.tables) | {'alembic_version'})}"
        )


class TestExistingDatabaseStampScenario:
    """Scénario AC 1 : base existante (create_all) → stamp → upgrade
    additif → check (chemin « base existante + migration additive »
    depuis STORY-121.1)."""

    def test_stamp_then_upgrade_is_noop_and_check_clean(self, tmp_path: Path) -> None:
        """Sur une base créée par create_all (simulée **antérieure à
        STORY-121.1**) : stamp baseline → upgrade head applique les
        migrations additives (``user_organizations`` puis
        ``refresh_tokens``) → tables d'origine intactes + nouvelles
        tables → alembic check sans diff."""
        db_path = tmp_path / "existing.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        # 1. Simule la base existante : create_all via un engine sync
        #    (équivalent SQLite du create_all async de database.py),
        #    puis DROP des tables additives pour simuler fidèlement une
        #    base antérieure à STORY-121.1 (sinon create_all les crée
        #    aussi et l'upgrade entrerait en collision — pattern
        #    STORY-121.1, étendu à refresh_tokens par STORY-123.1).
        sync_engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(sync_engine)
        with sync_engine.begin() as conn:
            conn.execute(text("DROP TABLE user_organizations"))
            conn.execute(text("DROP TABLE refresh_tokens"))
        # STORY-121.3 : recréer la colonne héritée users.organization_id
        # (+ index) — le schéma courant (modèles) ne la crée plus mais la
        # migration 1213 s'attend à la trouver sur une base pré-121.3
        with sync_engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE users ADD COLUMN organization_id VARCHAR(36)")
            )
            conn.execute(
                text(
                    "CREATE INDEX ix_users_organization_id "
                    "ON users (organization_id)"
                )
            )
        before = set(inspect(sync_engine).get_table_names())
        sync_engine.dispose()
        assert (
            EXPECTED_TABLES - {"user_organizations", "refresh_tokens"} <= before
        ), "create_all n'a pas créé les tables modèles"
        assert "user_organizations" not in before
        assert "refresh_tokens" not in before

        # 2. stamp baseline — marque la base comme étant au niveau baseline
        result = _run_alembic("stamp", "baseline", db_url=db_url)
        assert (
            result.returncode == 0
        ), f"stamp a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"

        # 3. upgrade head → applique uniquement la migration additive
        #    (baseline déjà stampée)
        result = _run_alembic("upgrade", "head", db_url=db_url)
        assert (
            result.returncode == 0
        ), f"upgrade head a échoué :\nstdout={result.stdout}\nstderr={result.stderr}"
        assert "Running upgrade baseline -> 1211_user_organizations" in (
            result.stdout + result.stderr
        ), "upgrade head n'a pas appliqué la migration additive attendue"

        # Tables d'origine intactes + nouvelle table créée.
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            after = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        assert (
            before | {"alembic_version", "user_organizations", "refresh_tokens"}
            == after
        ), "Le schéma d'origine a été altéré ou une table additive manque"

        # 4. alembic check → aucun diff (commande échoue (rc=255) si diff
        #    détecté, rc=0 si propre).
        result = _run_alembic("check", db_url=db_url)
        assert (
            result.returncode == 0
        ), f"alembic check a détecté un diff :\n{result.stdout}\n{result.stderr}"
        assert "No new upgrade operations detected" in result.stdout


class TestDowngrade:
    """Complément baseline : downgrade complet fonctionnel."""

    def test_downgrade_base_drops_all_tables(self, tmp_path: Path) -> None:
        """upgrade head puis downgrade base → toutes les tables modèles
        sont supprimées (downgrade complet implémenté)."""
        db_path = tmp_path / "downgrade.db"
        db_url = f"sqlite+aiosqlite:///{db_path}"

        up = _run_alembic("upgrade", "head", db_url=db_url)
        assert up.returncode == 0, up.stderr

        down = _run_alembic("downgrade", "base", db_url=db_url)
        assert down.returncode == 0, down.stderr

        engine = create_engine(f"sqlite:///{db_path}")
        try:
            remaining = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()
        assert remaining == {
            "alembic_version"
        }, f"Tables résiduelles après downgrade base : {sorted(remaining)}"


@pytest.mark.unit
class TestSanityMarker:
    """Marquage unit standard du projet (cohérence conventions)."""

    def test_expected_tables_match_metadata(self) -> None:
        """La liste attendue correspond exactement à Base.metadata."""
        assert EXPECTED_TABLES == set(Base.metadata.tables)
