"""Tests des claims JWT et du refresh opaque (STORY-121.3 puis 123.2).

Arbitrage 121.3 : le claim ``organization_id`` n'est plus émis ni lu
(incompatible multi-appartenance) — décodage tolérant aux tokens
antérieurs qui le portent.

Arbitrage 123.2 (spec 07) : le **refresh token émis est une chaîne
opaque** (``wf_rt_`` + ``secrets.token_urlsafe(64)``), plus un JWT —
seul l'access token reste un JWT 15 min. Les tests ci-dessous
vérifient l'opacité structurelle (pas de segments décodables, entropie)
et la préservation des claims access.
"""

from datetime import timedelta

from app.auth.jwt import (
    REFRESH_TOKEN_PREFIX,
    create_access_token,
    create_token_pair,
    decode_access_token,
    generate_refresh_token,
)
from app.schemas.user import TokenData

# Payload login réduit (STORY-121.3)
LOGIN_PAYLOAD = {"sub": "user-1", "username": "jdoe", "is_superuser": False}


class TestAccessTokenClaims:
    """Claims access émis sans ``organization_id`` — inchangés par 123.2."""

    def test_access_token_has_no_organization_id_claim(self):
        """Token émis avec le payload login réduit → décodé : claim
        ``organization_id`` absent, ``sub``/``username``/``is_superuser``
        présents."""
        token = create_access_token(LOGIN_PAYLOAD)
        payload_decoded = decode_access_token(token)
        assert payload_decoded is not None
        assert payload_decoded.user_id == "user-1"
        assert payload_decoded.username == "jdoe"
        assert payload_decoded.is_superuser is False
        # Champ retiré du schéma → jamais peuplé
        assert (
            not hasattr(payload_decoded, "organization_id")
            or getattr(payload_decoded, "organization_id", None) is None
            and "organization_id" not in TokenData.model_fields
        )

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

    def test_access_token_duration_is_15_minutes(self):
        """Arbitrage F5 : l'access JWT reste à 15 min par défaut (durée du
        code, plus sûre que la spec — 123.2 n'y touche pas)."""
        from datetime import datetime, timezone

        from app.auth.jwt import get_token_expiration
        from app.config import settings

        token = create_access_token(LOGIN_PAYLOAD)
        expiration = get_token_expiration(token)
        assert expiration is not None

        delta = expiration - datetime.now(timezone.utc)
        expected = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        # Le token expire dans ~15 min : ni déjà expiré, ni au-delà
        assert timedelta(0) < delta <= expected

    def test_expired_legacy_token_still_rejected(self):
        """Sécurité : un token expiré (claim legacy ou non) est rejeté."""
        token = create_access_token(
            {"sub": "user-1", "organization_id": "org-legacy"},
            expires_delta=timedelta(seconds=-3600),
        )
        assert decode_access_token(token) is None


class TestTokenDataSchema:
    """Schéma ``TokenData`` sans champ organisation."""

    def test_token_data_schema_has_no_organization_id(self):
        """``TokenData`` n'expose plus le champ (l'organisation est résolue
        en base à chaque requête)."""
        assert "organization_id" not in TokenData.model_fields
        fields = set(TokenData.model_fields)
        assert fields == {"user_id", "username", "is_superuser"}


class TestRefreshTokenOpaque:
    """STORY-123.2 : le refresh émis est opaque, pas un JWT."""

    def test_generate_refresh_token_is_not_a_jwt(self):
        """Le refresh n'a pas la structure JWT à 3 segments séparées par
        des points — il n'est pas décodable."""
        token = generate_refresh_token()
        segments = token.split(".")
        assert len(segments) != 3, "un refresh opaque ne doit pas être un JWT"

    def test_generate_refresh_token_has_diagnostic_prefix(self):
        """Préfixe ``wf_rt_`` à but diagnostique (aucun format imposé aux
        consommateurs — contrat ``{refresh_token: string}``)."""
        token = generate_refresh_token()
        assert token.startswith(REFRESH_TOKEN_PREFIX)

    def test_generate_refresh_token_has_512_bits_entropy(self):
        """``token_urlsafe(64)`` : ~86 caractères base64url après le
        préfixe (entropie 512 bits — recommandation OWASP)."""
        token = generate_refresh_token()
        body = token[len(REFRESH_TOKEN_PREFIX) :]
        assert len(body) >= 86

    def test_generate_refresh_token_is_unique_per_emission(self):
        """Deux émissions produisent des valeurs distinctes (CSPRNG)."""
        assert generate_refresh_token() != generate_refresh_token()

    def test_create_token_pair_returns_jwt_access_and_opaque_refresh(self):
        """``create_token_pair`` : l'access se décode avec ses claims, le
        refresh est opaque et sans claim transporté."""
        access_token, refresh_token = create_token_pair(LOGIN_PAYLOAD)

        # Access : JWT décodable, claims préservés
        decoded = decode_access_token(access_token)
        assert decoded is not None
        assert decoded.user_id == "user-1"
        assert decoded.username == "jdoe"

        # Refresh : opaque, préfixé, non décodable
        assert refresh_token.startswith(REFRESH_TOKEN_PREFIX)
        assert len(refresh_token.split(".")) != 3

    def test_decode_access_token_rejects_refresh_type_token(self):
        """Un JWT de type ``refresh`` n'est pas un access : rejeté."""
        from datetime import datetime, timezone

        from jose import jwt as jose_jwt

        from app.config import settings

        refresh_jwt = jose_jwt.encode(
            {
                "sub": "user-1",
                "type": "refresh",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert decode_access_token(refresh_jwt) is None

    def test_decode_access_token_rejects_token_without_sub(self):
        """Un JWT sans claim ``sub`` est rejeté."""
        from datetime import datetime, timezone

        from jose import jwt as jose_jwt

        from app.config import settings

        no_sub = jose_jwt.encode(
            {
                "type": "access",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )
        assert decode_access_token(no_sub) is None
