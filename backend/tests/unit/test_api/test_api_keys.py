"""Tests des endpoints `/auth/api-keys` et de l'auth par clé (STORY-124.3).

Couvre les trois endpoints posés par la Tâche 1 (création avec affichage
unique, liste sans secrets, révocation scoped) et la voie clé API dans
``get_current_user`` (Tâche 2) :

- **201 + affichage unique** : la clé ``wf_ak_…`` (48 car. après préfixe)
  apparaît uniquement dans la réponse du POST — jamais ensuite ;
- **liste sans secrets** : ``APIKeyResponse`` sans ``key_hash`` ni ``key`` ;
- **révocation immédiate** : vérification en base à chaque requête → la
  clé révoquée reçoit 401 aussitôt ;
- **isolation** : liste/révocation scoped ``user_id == current_user.id``,
  clé étrangère → 404 (pas d'oracle d'existence) ;
- **coexistence clé/JWT** : ``X-API-Key``, ``Authorization: Bearer wf_ak_…``
  et JWT fonctionnent côte à côte — clé préfixée jamais soumise au
  décodeur JWT ;
- **401 générique** sur clé inconnue/invalide/révoquée/expirée ou
  propriétaire désactivé (anti-énumération).

Les tests transverses de sécurité systématiques (STORY-124.4) sont
consolidés ci-dessous : RBAC du propriétaire par clé, contraste rôle
suffisant, absence de secrets dans réponses/logs/base, throttling
``last_used_at`` de bout en bout.

Sécurité (rules 40) : fixture ``_jwt_mode`` (pattern 123.4) — le ``.env``
racine porte ``DISABLE_AUTH=true`` qui court-circuiterait ``get_current_user``
et ferait échouer les 401 attendus.
"""

import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import API_KEY_PREFIX, MAX_API_KEY_LENGTH
from app.core.cache import reset_role_cache
from app.models.api_key import APIKey
from app.models.user import User
from tests.conftest import unwrap

API_KEYS_URL = "/api/v1/auth/api-keys"
ME_URL = "/api/v1/auth/me"

USER_PASSWORD = "testpassword123"
SUPERUSER_PASSWORD = "adminpassword123"


@pytest.fixture(autouse=True)
def _jwt_mode(monkeypatch):
    """Force le mode JWT normal (disable_auth=False) — pattern 123.4.

    Le ``.env`` racine du dépôt porte ``DISABLE_AUTH=true`` : sans cette
    garde, ``get_current_user`` auto-login le premier superadmin et ignore
    tout header — les 401 attendus seraient des 200/500 incohérents.
    """
    from app.auth import dependencies as auth_deps

    monkeypatch.setattr(auth_deps.settings, "disable_auth", False)


async def _auth_headers(user: User) -> dict:
    """Headers Authorization Bearer JWT pour un utilisateur.

    Mint direct du access token (mêmes claims que ``/auth/login``) — évite
    de consommer le quota de rate limiting du login dans les tests
    multi-utilisateurs ; la voie login elle-même est couverte par
    ``test_auth_refresh_security.py``.
    """
    from app.auth.jwt import create_access_token

    token = create_access_token(
        {"sub": user.id, "username": user.username, "is_superuser": user.is_superuser}
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_key(
    client: AsyncClient, headers: dict, name: str = "test-key"
) -> dict:
    """POST /auth/api-keys → 201 ; retourne le body (clé brute incluse)."""
    response = await client.post(API_KEYS_URL, json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return unwrap(response)


class TestCreateApiKey:
    """POST /auth/api-keys — 201 + affichage unique."""

    async def test_create_api_key_returns_201_with_key_once(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """201 + ``APIKeyCreated`` ; la clé ``wf_ak_`` (48 car.) apparaît
        uniquement dans cette réponse — un GET ultérieur ne la montre plus."""
        headers = await _auth_headers(test_user)

        body = await _create_key(client, headers, name="CLI laptop")

        # Clé complète : préfixe + 48 caractères, une seule fois (201)
        raw_key = body["key"]
        assert raw_key.startswith(API_KEY_PREFIX)
        assert len(raw_key) == MAX_API_KEY_LENGTH
        assert body["name"] == "CLI laptop"
        assert body["revoked"] is False
        assert "expires_at" in body and "created_at" in body

        # Affichage unique : le GET suivant ne retourne que les métadonnées
        listing = await client.get(API_KEYS_URL, headers=headers)
        assert listing.status_code == 200, listing.text
        assert len(unwrap(listing)) == 1
        assert "key" not in unwrap(listing)[0]
        assert "key_hash" not in unwrap(listing)[0]
        assert raw_key not in listing.text

        # Le hash en base ne contient jamais la valeur claire (rules 40)
        rows = list((await db_session.execute(select(APIKey))).scalars())
        assert rows, "la clé doit être persistée"
        for row in rows:
            assert row.key_hash != raw_key
            assert raw_key not in row.key_hash

    async def test_create_api_key_invalid_body_422(
        self, client: AsyncClient, test_user: User
    ):
        """``name`` vide / > 100 chars, ``expires_at`` invalide → 422."""
        headers = await _auth_headers(test_user)

        for payload in (
            {"name": ""},  # vide
            {"name": "x" * 101},  # > 100 chars
            {"name": "ok", "expires_at": "not-a-date"},  # date invalide
        ):
            response = await client.post(API_KEYS_URL, json=payload, headers=headers)
            assert response.status_code == 422, (payload, response.text)

    async def test_create_api_key_requires_auth_401(self, client: AsyncClient):
        """Sans token ni clé → 401."""
        response = await client.post(API_KEYS_URL, json={"name": "x"})
        assert response.status_code == 401, response.text


class TestListApiKeys:
    """GET /auth/api-keys — liste scopée, sans secrets."""

    async def test_list_api_keys_no_secrets(self, client: AsyncClient, test_user: User):
        """200 ; liste ``APIKeyResponse`` sans ``key_hash`` ni ``key`` ;
        champs nom/dates/statut présents."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers, name="visible-key")

        response = await client.get(API_KEYS_URL, headers=headers)
        assert response.status_code == 200, response.text

        keys = unwrap(response)
        assert len(keys) == 1
        entry = keys[0]
        assert set(entry.keys()) == {
            "id",
            "name",
            "expires_at",
            "last_used_at",
            "revoked",
            "created_at",
        }
        assert entry["id"] == created["id"]
        assert entry["name"] == "visible-key"
        assert entry["revoked"] is False

    async def test_list_api_keys_keeps_expired(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Clé expirée toujours listée avec ``expires_at`` visible et
        ``revoked=false`` (arbitrage : expiration ≠ révocation)."""
        headers = await _auth_headers(test_user)
        body = await _create_key(client, headers, name="expired-key")
        assert body["expires_at"] is None  # création sans expiration

        # Passe expires_at dans le passé directement en base (l'API ne
        # permet pas de créer une clé déjà expirée — seule la lecture nous
        # intéresse ici)
        await db_session.execute(
            update(APIKey)
            .where(APIKey.id == body["id"])
            .values(
                expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                - timedelta(days=1)
            )
        )
        await db_session.commit()

        response = await client.get(API_KEYS_URL, headers=headers)
        assert response.status_code == 200, response.text
        entries = {e["id"]: e for e in unwrap(response)}
        assert body["id"] in entries
        assert entries[body["id"]]["expires_at"] is not None
        assert entries[body["id"]]["revoked"] is False

    async def test_list_api_keys_scoped_404_isolation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
    ):
        """Un user ne liste que ses clés ; DELETE de la clé d'un autre
        user → 404 (pas d'oracle d'existence)."""
        headers_a = await _auth_headers(test_user)
        headers_b = await _auth_headers(test_superuser)

        key_a = await _create_key(client, headers_a, name="key-of-A")
        key_b = await _create_key(client, headers_b, name="key-of-B")

        # Chacun ne voit que ses clés
        list_a = await client.get(API_KEYS_URL, headers=headers_a)
        list_b = await client.get(API_KEYS_URL, headers=headers_b)
        assert [k["id"] for k in unwrap(list_a)] == [key_a["id"]]
        assert [k["id"] for k in unwrap(list_b)] == [key_b["id"]]

        # A tente de révoquer la clé de B → 404 (traitée comme inexistante)
        delete = await client.delete(f"{API_KEYS_URL}/{key_b['id']}", headers=headers_a)
        assert delete.status_code == 404, delete.text


class TestRevokeApiKey:
    """DELETE /auth/api-keys/{id} — révocation immédiate, idempotente."""

    async def test_revoke_then_key_unauthorized_401(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """DELETE → 200 (état révoqué) ; requête suivante avec cette clé
        → 401 (révocation immédiate, vérification en base par requête)."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers, name="doomed-key")
        raw_key = created["key"]

        # La clé authentifie avant révocation
        before = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert before.status_code == 200, before.text

        # Révocation par le propriétaire
        delete = await client.delete(f"{API_KEYS_URL}/{created['id']}", headers=headers)
        assert delete.status_code == 200, delete.text
        assert unwrap(delete)["revoked"] is True

        # Révocation immédiate : la même clé → 401
        after = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert after.status_code == 401, after.text

    async def test_revoke_idempotent(self, client: AsyncClient, test_user: User):
        """Révoquer une clé déjà révoquée → 200 avec l'état courant."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers, name="double-revoke")

        first = await client.delete(f"{API_KEYS_URL}/{created['id']}", headers=headers)
        assert first.status_code == 200
        second = await client.delete(f"{API_KEYS_URL}/{created['id']}", headers=headers)
        assert second.status_code == 200, second.text
        assert unwrap(second)["revoked"] is True

    async def test_revoke_unknown_key_404(self, client: AsyncClient, test_user: User):
        """key_id inexistant → 404."""
        headers = await _auth_headers(test_user)
        response = await client.delete(
            f"{API_KEYS_URL}/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert response.status_code == 404, response.text


class TestAuthViaApiKey:
    """Voie clé API dans get_current_user (Tâche 2)."""

    async def test_auth_via_x_api_key_header(
        self, client: AsyncClient, test_user: User
    ):
        """``X-API-Key: wf_ak_…`` authentifie sur une route protégée (200)."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers)

        response = await client.get(ME_URL, headers={"X-API-Key": created["key"]})
        assert response.status_code == 200, response.text
        assert unwrap(response)["username"] == test_user.username

    async def test_auth_via_bearer_wf_ak(self, client: AsyncClient, test_user: User):
        """``Authorization: Bearer wf_ak_…`` authentifie (200) — la valeur
        préfixée n'est jamais soumise au décodeur JWT."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers)

        response = await client.get(
            ME_URL, headers={"Authorization": f"Bearer {created['key']}"}
        )
        assert response.status_code == 200, response.text
        assert unwrap(response)["username"] == test_user.username

    async def test_invalid_or_expired_key_401(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        test_superuser: User,
    ):
        """Clé inconnue / malformée / révoquée / expirée → 401 (paramétré)."""

        async def _prepare(case: str) -> str:
            if case == "unknown":
                return API_KEY_PREFIX + "A" * 48
            if case == "malformed":
                return "not-an-api-key-at-all"

            headers = await _auth_headers(test_user)
            created = await _create_key(client, headers)
            raw = created["key"]

            if case == "revoked":
                revoke = await client.delete(
                    f"{API_KEYS_URL}/{created['id']}", headers=headers
                )
                assert revoke.status_code == 200
            elif case == "expired":
                await db_session.execute(
                    update(APIKey)
                    .where(APIKey.id == created["id"])
                    .values(
                        expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
                        - timedelta(minutes=5)
                    )
                )
                await db_session.commit()
            return raw

        for case in ("unknown", "malformed", "revoked", "expired"):
            key = await _prepare(case)
            response = await client.get(ME_URL, headers={"X-API-Key": key})
            assert response.status_code == 401, (case, response.text)

    async def test_jwt_still_works_alongside_api_key(
        self, client: AsyncClient, test_user: User
    ):
        """Auth JWT existante non régressée (200 sans aucune clé)."""
        headers = await _auth_headers(test_user)
        response = await client.get(ME_URL, headers=headers)
        assert response.status_code == 200, response.text
        assert unwrap(response)["username"] == test_user.username

    async def test_disabled_user_key_401(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Clé d'un utilisateur ``is_active=False`` → 401 (refus posé par
        ``ApiKeyService.verify`` — STORY-124.2)."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers)

        # La clé fonctionne avant désactivation
        ok = await client.get(ME_URL, headers={"X-API-Key": created["key"]})
        assert ok.status_code == 200, ok.text

        await db_session.execute(
            update(User).where(User.id == test_user.id).values(is_active=False)
        )
        await db_session.commit()

        response = await client.get(ME_URL, headers={"X-API-Key": created["key"]})
        assert response.status_code == 401, response.text

    async def test_last_used_at_updated_on_request(
        self, client: AsyncClient, test_user: User
    ):
        """Requête authentifiée par clé → ``last_used_at`` alimenté (visible
        via GET ; throttlé 60 s — première utilisation donc forcément NULL → set)."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers)

        # last_used_at NULL à la création
        listing = await client.get(API_KEYS_URL, headers=headers)
        entry = next(k for k in unwrap(listing) if k["id"] == created["id"])
        assert entry["last_used_at"] is None

        # Utilisation de la clé sur une route protégée
        used = await client.get(ME_URL, headers={"X-API-Key": created["key"]})
        assert used.status_code == 200, used.text

        # Le GET suivant montre last_used_at alimenté
        listing = await client.get(API_KEYS_URL, headers=headers)
        entry = next(k for k in unwrap(listing) if k["id"] == created["id"])
        assert entry["last_used_at"] is not None


# --- STORY-124.4 : tests transverses et sécurité ------------------------------


class TestRbacViaApiKey:
    """AC 4 — le RBAC du **propriétaire** s'applique à l'identique par clé.

    Une clé API n'est jamais un contournement du RBAC : la chaîne
    ``get_current_user`` (voie clé) → ``require_role`` est identique à la
    voie JWT — le rôle résolu est celui du propriétaire de la clé (spec
    08, matrice rôle × endpoint inchangée après auth par clé).
    """

    @pytest.fixture(autouse=True)
    def _clean_role_cache(self):
        """Cache de rôles vierge autour de chaque test (TTL 300 s — sinon
        fuite entre tests de rôles différents, pattern test_docker_rbac)."""
        reset_role_cache()
        yield
        reset_role_cache()

    async def test_viewer_key_forbidden_on_modifying_endpoint_403(
        self, client: AsyncClient, viewer_user: User
    ):
        """Clé d'un viewer sur un endpoint modifiant (DELETE conteneur
        Docker, ``require_admin``) → 403 — le RBAC du propriétaire
        s'applique par clé ; court-circuit avant toute E/S Docker."""
        headers = await _auth_headers(viewer_user)
        created = await _create_key(client, headers, name="viewer-key")

        response = await client.delete(
            "/api/v1/docker/containers/any-container-id",
            headers={"X-API-Key": created["key"]},
        )
        assert response.status_code == 403, response.text

    async def test_admin_key_allowed_on_same_endpoint(
        self, client: AsyncClient, org_admin_user: User
    ):
        """Contraste : clé d'un rôle **suffisant** sur le même DELETE →
        204 — la clé n'est ni un rabaissement ni une élévation.

        Divergence vs analyse 124.4 : le contraste y était spécifié avec
        ``operator_user``, mais la matrice spec 08 (STORY-122.2) réserve
        le DELETE conteneur aux admins (operator → 403, cf.
        ``test_docker_rbac.TestOperatorMatrix``) — le rôle réellement
        suffisant sur cet endpoint est admin.
        """
        headers = await _auth_headers(org_admin_user)
        created = await _create_key(client, headers, name="admin-key")

        docker = AsyncMock()
        docker.close = AsyncMock()

        with patch("app.api.v1.docker.get_docker_client", return_value=docker):
            response = await client.delete(
                "/api/v1/docker/containers/any-container-id",
                headers={"X-API-Key": created["key"]},
            )

        assert response.status_code == 204, response.text
        docker.remove_container.assert_awaited_once_with(
            "any-container-id", force=False
        )


class TestSecretsHygiene:
    """AC 4 — aucune clé ni hash dans les réponses, les logs, ni la base."""

    async def test_no_key_no_hash_in_any_response(
        self, client: AsyncClient, test_user: User
    ):
        """Parcours complet : la clé brute n'apparaît que dans le 201 du
        POST (affichage unique) — toutes les réponses suivantes (liste,
        ``/auth/me``, révocation, liste finale) n'exposent ni la clé ni
        son hash."""
        headers = await _auth_headers(test_user)

        created = await _create_key(client, headers, name="hygiene-key")
        raw_key = created["key"]

        listing = await client.get(API_KEYS_URL, headers=headers)
        assert listing.status_code == 200, listing.text
        me = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert me.status_code == 200, me.text
        revoke = await client.delete(f"{API_KEYS_URL}/{created['id']}", headers=headers)
        assert revoke.status_code == 200, revoke.text
        listing_after = await client.get(API_KEYS_URL, headers=headers)
        assert listing_after.status_code == 200, listing_after.text

        for response in (listing, me, revoke, listing_after):
            assert raw_key not in response.text
            assert "key_hash" not in response.text

    async def test_no_key_no_hash_in_logs(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        test_user: User,
        caplog: pytest.LogCaptureFixture,
    ):
        """Parcours complet (création → usage → échec volontaire sur clé
        révoquée → ``api_key.auth_failed``) sous capture DEBUG : ni la
        clé brute ni son hash ne fuient dans les logs — les events
        ``api_key.*`` ne portent que ``user_id``/``key_id``.

        Défense du piège environnement documenté dans la story : le
        logger ``sqlalchemy.engine`` est bridé à WARNING (ses logs INFO
        échappent les paramètres bindés, dont ``key_hash``) — au
        lancement manuel, exiger ``LOG_LEVEL=WARNING`` en tête de
        commande.
        """
        caplog.set_level(logging.DEBUG)
        caplog.set_level(logging.WARNING, logger="sqlalchemy.engine")

        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers, name="logged-key")
        raw_key = created["key"]

        # Usage valide puis échec volontaire (révocation → auth_failed)
        ok = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert ok.status_code == 200, ok.text
        revoke = await client.delete(f"{API_KEYS_URL}/{created['id']}", headers=headers)
        assert revoke.status_code == 200, revoke.text
        failed = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert failed.status_code == 401, failed.text

        # Hash réellement stocké — pour prouver son absence des logs
        row = (
            await db_session.execute(select(APIKey).where(APIKey.id == created["id"]))
        ).scalar_one()
        key_hash = row.key_hash
        assert key_hash and key_hash != raw_key

        assert raw_key not in caplog.text
        assert key_hash not in caplog.text

    async def test_hash_not_plaintext_in_db(
        self, client: AsyncClient, db_session: AsyncSession, test_user: User
    ):
        """Consolidation : en base, ``key_hash`` est un hash Argon2 fort
        (déterministe — arbitrage n°3) et jamais la clé en clair."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers, name="hashed-key")
        raw_key = created["key"]

        row = (
            await db_session.execute(select(APIKey).where(APIKey.id == created["id"]))
        ).scalar_one()
        assert row.key_hash != raw_key
        assert raw_key not in row.key_hash
        assert row.key_hash.startswith("$argon2")


class TestTransversalInvariants:
    """Invariants transverses non couverts par STORY-124.3 (Tâche 2).

    Les invariants « révocation immédiate » et « expirée listée mais
    non authentifiante » sont déjà couverts par 124.3
    (``test_revoke_then_key_unauthorized_401``,
    ``test_list_api_keys_keeps_expired`` +
    ``test_invalid_or_expired_key_401[expired]``) — référencés en Notes
    d'implémentation, non dupliqués ici.
    """

    async def test_last_used_at_throttled_end_to_end(
        self, client: AsyncClient, test_user: User
    ):
        """Deux authentifications par clé dans la même minute →
        ``last_used_at`` alimenté **une seule fois** : la valeur après
        le 2e usage est identique à celle après le 1er (throttle 60 s,
        arbitrage n°2 — la mécanique service est couverte par 124.2, ce
        test prouve le comportement via HTTP)."""
        headers = await _auth_headers(test_user)
        created = await _create_key(client, headers, name="throttled-key")
        raw_key = created["key"]

        async def _last_used() -> str | None:
            listing = await client.get(API_KEYS_URL, headers=headers)
            entry = next(k for k in unwrap(listing) if k["id"] == created["id"])
            return entry["last_used_at"]

        assert await _last_used() is None  # jamais utilisée à la création

        first = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert first.status_code == 200, first.text
        used_once = await _last_used()
        assert used_once is not None

        second = await client.get(ME_URL, headers={"X-API-Key": raw_key})
        assert second.status_code == 200, second.text
        used_twice = await _last_used()

        assert used_twice == used_once  # throttling : pas de ré-écriture
