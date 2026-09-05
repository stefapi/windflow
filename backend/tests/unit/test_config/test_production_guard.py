"""
Tests du garde-fou de démarrage — secrets de développement interdits en
production (STORY-101 / P0-2).

Vérifie que :
- en production, les secrets dev (jwt par défaut, changeme123, disable_auth)
  refusent le démarrage avec un message explicite ;
- les secrets forts démarrent normalement (pas de faux positif) ;
- les environnements dev/test ne sont jamais impactés ;
- les alias SUPERADMIN_* / ADMIN_* fonctionnent tous les deux ;
- aucune valeur de secret n'apparaît dans les messages d'erreur.
"""

import pytest

from app.config import (
    DEV_ADMIN_PASSWORD,
    DEV_JWT_SECRET_VALUES,
    Settings,
    enforce_production_secrets,
    validate_production_secrets,
)

# Secrets forts factices pour les cas nominaux (jamais utilisés ailleurs).
STRONG_JWT = "a" * 64
STRONG_PASSWORD = "AVeryStrongProductionPassword42!"


def _prod_settings(**overrides) -> Settings:
    """Construit des Settings production isolés de l'environnement local."""
    values = {
        "environment": "production",
        "jwt_secret_key": STRONG_JWT,
        "admin_password": STRONG_PASSWORD,
        "disable_auth": False,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class TestValidateProductionSecrets:
    """Tests du validateur pur (retour de liste de violations)."""

    def test_startup_fails_in_production_with_default_jwt_secret(self):
        """AC 5 : prod + jwt défaut code → violation JWT_SECRET_KEY."""
        config = _prod_settings(
            jwt_secret_key="dev-secret-key-change-in-production-please-use-a-long-random-string-minimum-32-characters"
        )
        with pytest.raises(RuntimeError) as exc_info:
            enforce_production_secrets(config)
        assert "JWT_SECRET_KEY" in str(exc_info.value)

    def test_startup_fails_in_production_with_env_example_jwt_secret(self):
        """Variante : valeur dev documentée dans env.example → également refusée."""
        config = _prod_settings(
            jwt_secret_key="dev-jwt-secret-key-change-in-production"
        )
        violations = validate_production_secrets(config)
        assert len(violations) == 1
        assert "JWT_SECRET_KEY" in violations[0]

    def test_startup_fails_in_production_with_default_admin_password(self):
        """AC 5 : prod + changeme123 → violation ADMIN_PASSWORD."""
        config = _prod_settings(admin_password="changeme123")
        with pytest.raises(RuntimeError) as exc_info:
            enforce_production_secrets(config)
        assert "ADMIN_PASSWORD" in str(exc_info.value)
        assert "SUPERADMIN_PASSWORD" in str(exc_info.value)

    def test_startup_fails_with_short_admin_password(self):
        """Prod + mot de passe 10 caractères (non défaut) → refus (longueur)."""
        config = _prod_settings(admin_password="short123")
        violations = validate_production_secrets(config)
        assert len(violations) == 1
        assert "16 caractères" in violations[0] or "16 char" in violations[0]

    def test_startup_fails_lists_all_offending_secrets(self):
        """AC 5 : jwt défaut + changeme123 + disable_auth → les 3 listées."""
        config = _prod_settings(
            jwt_secret_key="dev-jwt-secret-key-change-in-production",
            admin_password="changeme123",
            disable_auth=True,
        )
        violations = validate_production_secrets(config)
        assert len(violations) == 3
        joined = " ".join(violations)
        assert "JWT_SECRET_KEY" in joined
        assert "ADMIN_PASSWORD" in joined
        assert "DISABLE_AUTH" in joined

    def test_startup_fails_with_disable_auth_in_production(self):
        """Prod + disable_auth=True (secrets forts par ailleurs) → refus."""
        config = _prod_settings(disable_auth=True)
        violations = validate_production_secrets(config)
        assert len(violations) == 1
        assert "DISABLE_AUTH" in violations[0]

    def test_startup_succeeds_in_production_with_strong_secrets(self):
        """AC 5 / AC 2 : prod + secrets forts → aucune violation, pas d'exception."""
        config = _prod_settings()
        assert validate_production_secrets(config) == []
        enforce_production_secrets(config)  # ne lève pas

    def test_dev_environment_unaffected_by_guard(self):
        """AC 5 / AC 3 : development + tous les défauts dev → aucune violation."""
        config = Settings(_env_file=None, environment="development")
        assert config.jwt_secret_key in DEV_JWT_SECRET_VALUES
        assert config.admin_password == DEV_ADMIN_PASSWORD
        assert validate_production_secrets(config) == []
        enforce_production_secrets(config)  # ne lève pas

    def test_test_environment_unaffected_by_guard(self):
        """AC 3 : environment=test + défauts dev → aucune violation."""
        config = Settings(_env_file=None, environment="test")
        assert validate_production_secrets(config) == []

    def test_no_secret_value_in_error_message(self):
        """Sécurité : le message d'erreur ne contient aucune valeur de secret."""
        dev_secret = "dev-jwt-secret-key-change-in-production"
        config = _prod_settings(jwt_secret_key=dev_secret)
        with pytest.raises(RuntimeError) as exc_info:
            enforce_production_secrets(config)
        assert dev_secret not in str(exc_info.value)

    def test_superadmin_alias_accepted(self, monkeypatch):
        """AC 2 : variable SUPERADMIN_PASSWORD lue via alias pydantic."""
        monkeypatch.setenv("SUPERADMIN_PASSWORD", "AliasedSuperSecurePassword1!")
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("JWT_SECRET_KEY", STRONG_JWT)
        config = Settings(_env_file=None)
        assert config.admin_password == "AliasedSuperSecurePassword1!"
        assert validate_production_secrets(config) == []
        monkeypatch.delenv("SUPERADMIN_PASSWORD")
        monkeypatch.delenv("ENVIRONMENT")
        monkeypatch.delenv("JWT_SECRET_KEY")

    def test_admin_naming_still_works(self, monkeypatch):
        """Non-breaking : ADMIN_PASSWORD continue de fonctionner."""
        monkeypatch.setenv("ADMIN_PASSWORD", "LegacyAdminNamingStillWorks1!")
        config = Settings(_env_file=None)
        assert config.admin_password == "LegacyAdminNamingStillWorks1!"
        monkeypatch.delenv("ADMIN_PASSWORD")

    def test_min_password_boundary_16_chars(self):
        """Limite : exactement 16 caractères → accepté."""
        password = "Exact16CharsPwd!"  # 16 caractères exactement
        assert len(password) == 16
        config = _prod_settings(admin_password=password)
        assert validate_production_secrets(config) == []

    def test_derived_secret_key_rejected_in_production(self):
        """STORY-103.1 : SECRET_ENCRYPTION_KEY = valeur dev → violation.

        Une clé maîtresse de chiffrement prédictible exposerait tous les
        secrets au repos : même garde-fou que JWT_SECRET_KEY.
        """
        config = _prod_settings(
            secret_encryption_key="dev-jwt-secret-key-change-in-production"
        )
        violations = validate_production_secrets(config)
        assert len(violations) == 1
        assert "SECRET_ENCRYPTION_KEY" in violations[0]

    def test_strong_derived_secret_key_accepted_in_production(self):
        """STORY-103.1 : SECRET_ENCRYPTION_KEY forte → pas de faux positif."""
        config = _prod_settings(secret_encryption_key="f" * 64)
        assert validate_production_secrets(config) == []

    def test_no_secret_encryption_key_is_covered_by_jwt_guard(self):
        """STORY-103.1 : fallback JWT → couvert par le garde-fou JWT existant.

        Sans valeur dédiée, la clé maîtresse dérive de jwt_secret_key : si
        celui-ci est une valeur dev, la violation JWT existe déjà (pas de
        doublon de message).
        """
        config = _prod_settings(
            jwt_secret_key="dev-jwt-secret-key-change-in-production"
        )
        violations = validate_production_secrets(config)
        assert len(violations) == 1
        assert "JWT_SECRET_KEY" in violations[0]
