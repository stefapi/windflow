"""
Gestion des tokens d'authentification pour WindFlow (STORY-123.2).

- **Access token** : JWT court (15 min par défaut) créé et validé avec
  python-jose — inchangé par la bascule refresh opaque ;
- **Refresh token** : chaîne **opaque** (plus un JWT) générée par
  ``generate_refresh_token()`` — ``secrets.token_urlsafe(64)``, entropie
  512 bits, préfixe ``wf_rt_`` à but diagnostique uniquement. Sa durée de
  vie et sa révocation vivent côté serveur (table ``refresh_tokens``,
  STORY-123.1) : ``create_token_pair()`` retourne la valeur claire et
  **l'appelant doit persister son hash immédiatement** via
  ``RefreshTokenService.create`` (endpoints STORY-123.3).

Sécurité : aucune valeur de token n'est loggée par ce module.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from ..config import settings
from ..schemas.user import TokenData

# Préfixe diagnostique des refresh tokens opaques (aucun format imposé aux
# consommateurs : le contrat API reste ``{refresh_token: string}``).
REFRESH_TOKEN_PREFIX = "wf_rt_"

# Préfixe des clés API (spec 07 — authentification par clé API) : sert de
# discriminateur dans ``Authorization: Bearer ...`` (une valeur préfixée
# ``wf_ak_`` n'est JAMAIS soumise au décodeur JWT — garantie posée par
# STORY-124.3 côté dependencies.py).
API_KEY_PREFIX = "wf_ak_"

# Longueur totale exacte d'une clé API émise (préfixe + 48 caractères).
# Exposée pour la validation de forme AVANT hachage côté service
# (anti-DoS, pattern ``MAX_TOKEN_LENGTH``).
MAX_API_KEY_LENGTH = len(API_KEY_PREFIX) + 48


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Crée un token JWT d'accès.

    Args:
        data: Données à encoder dans le token
        expires_delta: Durée de validité optionnelle

    Returns:
        Token JWT encodé
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )

    to_encode.update({"exp": expire, "type": "access"})

    encoded_jwt = jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def generate_refresh_token() -> str:
    """
    Génère un refresh token opaque (STORY-123.2 — arbitrage spec 07).

    ``secrets.token_urlsafe(64)`` : ~86 caractères base64url dérivés de
    64 octets CSPRNG (entropie 512 bits — recommandation OWASP pour les
    refresh tokens opaques). Le préfixe ``wf_rt_`` facilite le diagnostic
    visuel sans préjuger du format pour les consommateurs.

    Returns:
        Token opaque ``wf_rt_<86 chars>`` (~92 caractères au total)
    """
    return f"{REFRESH_TOKEN_PREFIX}{secrets.token_urlsafe(64)}"


def generate_api_key() -> str:
    """
    Génère une clé API ``wf_ak_`` + 48 caractères aléatoires (STORY-124.2).

    ``secrets.token_urlsafe(36)`` : exactement 48 caractères base64url
    dérivés de 36 octets CSPRNG (entropie ~288 bits, spec 07 § clés
    API). Le préfixe ``wf_ak_`` permet de distinguer une clé API d'un
    JWT dans ``Authorization: Bearer ...`` sans tenter de décoder.

    ⚠️ **Sécurité** : la valeur claire générée n'est **jamais** stockée
    ni loggée — seul son hash déterministe est persisté (table
    ``api_keys``, STORY-124.1). Elle n'apparaît qu'une **seule** fois,
    dans la réponse 201 du ``POST /auth/api-keys`` (STORY-124.3) ; la
    perte de cette valeur est définitive.

    Returns:
        Clé API ``wf_ak_<48 chars>`` (54 caractères au total)
    """
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(36)}"


def create_token_pair(data: dict) -> tuple[str, str]:
    """
    Crée une paire de tokens (access JWT + refresh opaque).

    ⚠️ **Obligation de l'appelant** (endpoints STORY-123.3) : la valeur
    claire du refresh token n'existe qu'ici — persister son hash
    immédiatement via ``RefreshTokenService.create()`` (table
    ``refresh_tokens``) **dans la même requête**, sans quoi le token émis
    sera inutilisable au prochain ``POST /auth/refresh``.

    Args:
        data: Claims à encoder dans l'access token (le refresh opaque ne
            porte aucun claim — métadonnées côté serveur uniquement)

    Returns:
        Tuple (access_token, refresh_token) — refresh en valeur claire
    """
    access_token = create_access_token(data)
    refresh_token = generate_refresh_token()

    return access_token, refresh_token


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Décode et valide un token JWT d'accès.

    Args:
        token: Token JWT à décoder

    Returns:
        TokenData si valide, None sinon
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )

        # Vérifier que c'est bien un token d'accès
        if payload.get("type") != "access":
            return None

        # STORY-121.3 : le claim organization_id n'est plus émis ni lu —
        # les tokens antérieurs qui le portent restent valides (claim
        # simplement ignoré, décodage tolérant)
        user_id = payload.get("sub")
        username = payload.get("username")
        is_superuser = payload.get("is_superuser", False)

        if user_id is None:
            return None

        token_data = TokenData(
            user_id=str(user_id),
            username=str(username) if username is not None else None,
            is_superuser=bool(is_superuser),
        )

        return token_data

    except JWTError:
        return None


def get_token_expiration(token: str) -> Optional[datetime]:
    """
    Récupère la date d'expiration d'un token JWT.

    Args:
        token: Token JWT

    Returns:
        Date d'expiration ou None si invalide
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp, timezone.utc)
        return None
    except JWTError:
        return None
