"""Tests des claims JWT après la bascule STORY-121.3.

Arbitrage appliqué : le claim ``organization_id`` n'est plus émis ni lu
(incompatible multi-appartenance, zéro consommateur runtime) — le
décodage reste tolérant aux tokens antérieurs qui le portent.
"""

from datetime import timedelta

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)
from app.schemas.user import TokenData


class TestAccessTokenClaims:
    """Claims émis sans ``organization_id``."""

    def test_access_token_has_no_organization_id_claim(self):
        """Token émis avec le payload login réduit → décodé : claim
        ``organization_id`` absent, ``sub``/``username``/``is_superuser``
        présents."""
        token = create_access_token(
            {"sub": "user-1", "username": "jdoe", "is_superuser": False}
        )
        payload_decoded = decode_access_token(token)
        assert payload_decoded is not None
        assert payload_decoded.user_id == "user-1"
        assert payload_decoded.username == "jdoe"
        assert payload_decoded.is_superuser is False
        # Champ retiré du schéma → jamais peuplé
        assert not hasattr(payload_decoded, "organization_id") or getattr(
            payload_decoded, "organization_id", None
        ) is None and "organization_id" not in TokenData.model_fields

    def test_decode_accepts_legacy_token_with_organization_id_claim(self):
        """Rétro-compatibilité : token forgé avec l'ancien claim (tokens en
        circulation avant déploiement) → ``decode_access_token`` retourne
        un ``TokenData`` valide (claim ignoré)."""
        token = create_access_token(
            {
                "sub": "user-1",
                "username": "jdoe",
                "organization_id": "org-legacy",
                "is_superuser": True,
            }
        )
        decoded = decode_access_token(token)
        assert decoded is not None
        assert decoded.user_id == "user-1"
        assert decoded.is_superuser is True

    def test_refresh_token_decoding_ignores_legacy_claim(self):
        """Rétro-compatibilité côté refresh : ancien claim ignoré."""
        token = create_refresh_token(
            {
                "sub": "user-1",
                "username": "jdoe",
                "organization_id": "org-legacy",
                "is_superuser": False,
            }
        )
        decoded = decode_refresh_token(token)
        assert decoded is not None
        assert decoded.user_id == "user-1"


class TestTokenDataSchema:
    """Schéma ``TokenData`` sans champ organisation."""

    def test_token_data_schema_has_no_organization_id(self):
        """``TokenData`` n'expose plus le champ (l'organisation est résolue
        en base à chaque requête)."""
        assert "organization_id" not in TokenData.model_fields
        fields = set(TokenData.model_fields)
        assert fields == {"user_id", "username", "is_superuser"}


class TestRefreshRotation:
    """Anti-dérive refresh sur ``username`` + ``is_superuser`` uniquement."""

    def test_refresh_rotation_comparison_ignores_organization(self):
        """L'anti-dérive du refresh (auth.py) compare uniquement
        ``username`` + ``is_superuser`` : un token legacy (avec claim org)
        reste utilisable pour un refresh même si l'appartenance a changé
        depuis — simulation de la comparaison effectuée par l'endpoint."""
        legacy_token = create_refresh_token(
            {
                "sub": "user-1",
                "username": "jdoe",
                "organization_id": "org-old",
                "is_superuser": False,
            }
        )
        token_data = decode_refresh_token(legacy_token)
        assert token_data is not None

        # État courant de l'utilisateur (en base) : username et flag
        # inchangés, appartenance différente → comparaison OK (pas de
        # mismatch) car organization_id n'est plus comparé
        current_username = "jdoe"
        current_is_superuser = False
        assert current_username == token_data.username
        assert current_is_superuser == token_data.is_superuser
        # Le nouveau token émis ne porte plus le claim
        new_token = create_refresh_token(
            {
                "sub": "user-1",
                "username": current_username,
                "is_superuser": current_is_superuser,
            }
        )
        new_decoded = decode_refresh_token(new_token)
        assert new_decoded is not None
        assert new_decoded.user_id == "user-1"

    def test_expired_legacy_token_still_rejected(self):
        """Sécurité : un token expiré (claim legacy ou non) est rejeté."""
        token = create_access_token(
            {"sub": "user-1", "organization_id": "org-legacy"},
            expires_delta=timedelta(seconds=-3600),
        )
        assert decode_access_token(token) is None
