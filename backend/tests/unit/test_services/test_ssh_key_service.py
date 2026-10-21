"""Tests unitaires du service ``SSHKeyService`` (STORY-131.2, famille 4).

Couvre le cycle de vie métier des clés SSH (modèles STORY-131.1) :
génération serveur, import (avec/sans passphrase, re-stockage
dé-passphrasé), dédup par empreinte (invariant de service), liste
paginée avec compteurs de cibles, renommage, suppression contrôlée
(``force``), ``touch_last_used`` throttlé et résolution pour cible.

Sécurité (rules 40 / story) :

- la clé privée chiffrée n'est **jamais** égale au PEM clair
  (token Fernet ``gAAAA…``) et le PEM clair ne fuit ni dans les
  réponses de consultation ni dans les logs (caplog) ;
- l'import illisible/mauvaise passphrase → ``InvalidInputError``
  (message générique, jamais le matériau).

Aucun réseau réel : asyncssh n'est **pas** mocké pour la génération
(génération locale sans I/O — déterministe côté clés) ; les tests
d'API mockent le service (famille 7) et non l'inverse.
"""

import logging

import asyncssh
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from app.models.ssh_key import SSHKey
from app.models.target import Target
from app.schemas.ssh_key import (
    SSHKeyGenerateRequest,
    SSHKeyImportRequest,
)
from app.services.ssh_key_service import SSHKeyService

# Empreinte SHA256 valide en forme (43 car. base64 sans padding) pour
# les payloads d'acceptation — le contenu importe peu (jamais en DB ici).
FP = "SHA256:" + "A" * 43


def _pem(passphrase: str | None = None) -> str:
    """Génère un PEM ed25519 (chiffré si passphrase fournie)."""
    key = asyncssh.generate_private_key("ssh-ed25519")
    if passphrase is None:
        return key.export_private_key().decode()
    return key.export_private_key(passphrase=passphrase).decode()


class TestGenerate:
    """Génération serveur ed25519/RSA."""

    async def test_generate_ed25519_full_material(self, db_session: AsyncSession):
        """Nominal : clé publique consultable, fingerprint SHA256:,
        PEM clair retourné (affichage unique) + chiffré en base."""
        row, private_pem = await SSHKeyService.generate(
            db_session,
            SSHKeyGenerateRequest(name="k1", key_type="ssh-ed25519"),
        )
        assert row.key_type == "ssh-ed25519"
        assert row.public_key.startswith("ssh-ed25519 ")
        assert row.fingerprint.startswith("SHA256:")
        # Affichage unique : le PEM clair n'est retourné qu'ici…
        assert private_pem.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
        # …et la base ne contient qu'un token Fernet (jamais le clair).
        assert row.private_key_encrypted.startswith("gAAAA")
        assert private_pem not in row.private_key_encrypted
        # Le déchiffrement in-memory redonne exactement le PEM.
        assert row.decrypted_private_key == private_pem

    async def test_generate_duplicate_name_conflict(self, db_session: AsyncSession):
        """Doublon de name → 409 ConflictError."""
        await SSHKeyService.generate(db_session, SSHKeyGenerateRequest(name="dup"))
        with pytest.raises(ConflictError):
            await SSHKeyService.generate(db_session, SSHKeyGenerateRequest(name="dup"))

    async def test_generate_duplicate_fingerprint_conflict(
        self, db_session: AsyncSession
    ):
        """Invariant de dédup : ré-importer LE MÊME matériau (même
        empreinte) sous un autre nom → 409."""
        pem = _pem()
        await SSHKeyService.import_key(
            db_session, SSHKeyImportRequest(name="first", private_key=pem)
        )
        with pytest.raises(ConflictError):
            await SSHKeyService.import_key(
                db_session, SSHKeyImportRequest(name="second", private_key=pem)
            )


class TestImport:
    """Import de clés existantes."""

    async def test_import_plain_pem(self, db_session: AsyncSession):
        """Nominal sans passphrase : matériau équivalent, chiffré au repos.

        NB : le format OpenSSH embarque un ``checkint`` aléatoire — deux
        exports d'une même clé ne sont pas identiques octet par octet ;
        l'invariant vérifié est l'empreinte (même clé matérielle) et la
        ré-importabilité du PEM retourné.
        """
        pem = _pem()
        row, returned_pem = await SSHKeyService.import_key(
            db_session, SSHKeyImportRequest(name="imported", private_key=pem)
        )
        assert row.name == "imported"
        reimported = asyncssh.import_private_key(returned_pem)
        assert reimported.get_fingerprint() == row.fingerprint
        assert returned_pem.startswith("-----BEGIN OPENSSH PRIVATE KEY-----")
        assert row.private_key_encrypted.startswith("gAAAA")

    async def test_import_with_passphrase_re_stored_decrypted(
        self, db_session: AsyncSession
    ):
        """Arbitrage d'analyse : la passphrase sert à lire la clé, qui
        est ensuite re-stockée **dé-passphrasée mais chiffrée** — le
        déchiffrement in-memory redonne un PEM importable sans secret."""
        passphrase = "secret123"
        encrypted_pem = _pem(passphrase=passphrase)

        row, returned_pem = await SSHKeyService.import_key(
            db_session,
            SSHKeyImportRequest(
                name="vaulted", private_key=encrypted_pem, passphrase=passphrase
            ),
        )
        # Le PEM retourné (affichage unique) est dé-passphrasé :
        # ré-importable sans passphrase.
        reimported = asyncssh.import_private_key(returned_pem)
        assert reimported.get_fingerprint() == row.fingerprint
        # Jamais de trace de la passphrase en base.
        assert passphrase not in row.private_key_encrypted
        assert passphrase not in row.public_key

    async def test_import_wrong_passphrase_invalid_input(
        self, db_session: AsyncSession
    ):
        """Mauvaise passphrase → UnprocessableEntityError (422
        VALIDATION_ERROR — sémantique spec 09), message générique."""
        encrypted_pem = _pem(passphrase="right")
        with pytest.raises(UnprocessableEntityError):
            await SSHKeyService.import_key(
                db_session,
                SSHKeyImportRequest(
                    name="bad", private_key=encrypted_pem, passphrase="wrong"
                ),
            )

    async def test_import_invalid_pem_invalid_input(self, db_session: AsyncSession):
        """PEM illisible → UnprocessableEntityError (422 côté endpoint)."""
        with pytest.raises(UnprocessableEntityError):
            await SSHKeyService.import_key(
                db_session,
                SSHKeyImportRequest(name="junk", private_key="not a pem at all"),
            )


class TestListAndGet:
    """Consultation paginée + compteurs de cibles."""

    async def test_get_not_found(self, db_session: AsyncSession):
        """404 : clé inconnue."""
        with pytest.raises(NotFoundError):
            await SSHKeyService.get(db_session, "missing-id")

    async def test_list_with_targets_count(
        self, db_session: AsyncSession, test_organization
    ):
        """AC 1 (réutilisabilité) : une même clé référençable par N
        cibles — ``targets_count`` reflète les N références."""
        row, _ = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="shared")
        )
        for i in range(3):
            db_session.add(
                Target(
                    name=f"t{i}",
                    host=f"host{i}",
                    credentials={},
                    organization_id=test_organization.id,
                    ssh_key_id=row.id,
                )
            )
        await db_session.commit()

        rows = await SSHKeyService.list_keys(db_session, page=1, per_page=20)
        assert len(rows) == 1
        key, count = rows[0]
        assert key.id == row.id
        assert count == 3
        assert await SSHKeyService.count(db_session) == 1

    async def test_list_pagination(self, db_session: AsyncSession):
        """Pagination : 2 clés, per_page=1 → page 1 et 2 d'un élément."""
        await SSHKeyService.generate(db_session, SSHKeyGenerateRequest(name="a"))
        await SSHKeyService.generate(db_session, SSHKeyGenerateRequest(name="b"))
        page1 = await SSHKeyService.list_keys(db_session, page=1, per_page=1)
        page2 = await SSHKeyService.list_keys(db_session, page=2, per_page=1)
        assert len(page1) == 1 and len(page2) == 1
        assert page1[0][0].id != page2[0][0].id


class TestRename:
    """Renommage (rotation = nouvelle clé)."""

    async def test_rename_nominal(self, db_session: AsyncSession):
        row, _ = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="old-name")
        )
        renamed = await SSHKeyService.rename(db_session, row.id, "new-name")
        assert renamed.name == "new-name"

    async def test_rename_conflict_on_existing_name(self, db_session: AsyncSession):
        await SSHKeyService.generate(db_session, SSHKeyGenerateRequest(name="a"))
        row_b, _ = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="b")
        )
        with pytest.raises(ConflictError):
            await SSHKeyService.rename(db_session, row_b.id, "a")

    async def test_rename_not_found(self, db_session: AsyncSession):
        with pytest.raises(NotFoundError):
            await SSHKeyService.rename(db_session, "missing", "x")


class TestDelete:
    """Suppression contrôlée — jamais silencieuse (AC 1)."""

    async def _seed_key_with_target(
        self, db_session, organization_id
    ) -> tuple[SSHKey, Target]:
        row, _ = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="referenced")
        )
        target = Target(
            name="holder",
            host="h",
            credentials={},
            organization_id=organization_id,
            ssh_key_id=row.id,
        )
        db_session.add(target)
        await db_session.commit()
        await db_session.refresh(target)
        return row, target

    async def test_delete_refused_when_referenced(
        self, db_session: AsyncSession, test_organization
    ):
        """409 si des cibles référencent la clé sans force."""
        row, _ = await self._seed_key_with_target(db_session, test_organization.id)
        with pytest.raises(ConflictError):
            await SSHKeyService.delete(db_session, row.id)

    async def test_delete_force_dereferences_then_deletes(
        self, db_session: AsyncSession, test_organization
    ):
        """force=True → targets.ssh_key_id = NULL puis suppression."""
        row, target = await self._seed_key_with_target(db_session, test_organization.id)
        dereferenced = await SSHKeyService.delete(db_session, row.id, force=True)
        assert dereferenced == 1
        await db_session.refresh(target)
        assert target.ssh_key_id is None
        remaining = (await db_session.execute(select(SSHKey.id))).scalars().all()
        assert row.id not in remaining

    async def test_delete_unreferenced_nominal(self, db_session: AsyncSession):
        """Aucune référence → suppression directe (retour 0)."""
        row, _ = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="free")
        )
        assert await SSHKeyService.delete(db_session, row.id) == 0

    async def test_delete_not_found(self, db_session: AsyncSession):
        with pytest.raises(NotFoundError):
            await SSHKeyService.delete(db_session, "missing")


class TestTouchLastUsed:
    """Alimentation throttlée de ``last_used_at`` (pattern 124.2)."""

    async def test_touch_sets_then_throttles(self, db_session: AsyncSession):
        row, _ = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="used")
        )
        await db_session.refresh(row)
        assert row.last_used_at is None

        await SSHKeyService.touch_last_used(db_session, row.id)
        await db_session.refresh(row)
        first = row.last_used_at
        assert first is not None

        # Fenêtre < 60 s : la deuxième écriture est throttlée (skippée).
        await SSHKeyService.touch_last_used(db_session, row.id)
        await db_session.refresh(row)
        assert row.last_used_at == first


class TestResolveForTarget:
    """Résolution des kwargs asyncssh pour une cible."""

    async def test_resolve_via_ssh_key_entity(
        self, db_session: AsyncSession, test_organization
    ):
        """Cible avec ssh_key_id → client_keys re-importé depuis le PEM
        déchiffré (jamais loggé) + touch_last_used."""
        row, pem = await SSHKeyService.generate(
            db_session, SSHKeyGenerateRequest(name="resolved")
        )
        target = Target(
            name="t",
            host="h",
            credentials={},
            organization_id=test_organization.id,
            ssh_key_id=row.id,
        )
        db_session.add(target)
        await db_session.commit()

        kwargs = await SSHKeyService.resolve_for_target(db_session, target)
        assert "client_keys" in kwargs
        assert len(kwargs["client_keys"]) == 1
        assert kwargs["client_keys"][0].get_fingerprint() == row.fingerprint
        # last_used_at alimenté par la résolution.
        await db_session.refresh(row)
        assert row.last_used_at is not None

    async def test_resolve_without_any_key_returns_empty(
        self, db_session: AsyncSession, test_organization
    ):
        """Ni entité ni matériau legacy → {} (auth password ou autre)."""
        target = Target(
            name="t2",
            host="h2",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.commit()
        assert await SSHKeyService.resolve_for_target(db_session, target) == {}


class TestLogsSanitization:
    """Rules 40 : aucun secret dans les logs du service (caplog)."""

    async def test_no_private_key_in_logs(self, db_session: AsyncSession, caplog):
        """Le PEM clair et la passphrase n'apparaissent jamais dans les
        logs émis par le service (création, import, suppression)."""
        passphrase = "log-secret-123"
        encrypted_pem = _pem(passphrase=passphrase)

        with caplog.at_level(logging.DEBUG, logger="app.services.ssh_key_service"):
            await SSHKeyService.generate(
                db_session, SSHKeyGenerateRequest(name="logged-gen")
            )
            row, returned_pem = await SSHKeyService.import_key(
                db_session,
                SSHKeyImportRequest(
                    name="logged-imp",
                    private_key=encrypted_pem,
                    passphrase=passphrase,
                ),
            )
            await SSHKeyService.rename(db_session, row.id, "logged-renamed")
            await SSHKeyService.delete(db_session, row.id)

        logged = caplog.text
        assert "BEGIN OPENSSH PRIVATE KEY" not in logged
        assert passphrase not in logged
        assert returned_pem not in logged
