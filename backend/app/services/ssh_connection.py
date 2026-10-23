"""Helper unique de connexion SSH avec vérification TOFU anti-MITM (STORY-131.3).

Remplace **tous** les kwargs ``asyncssh.connect`` inline dupliqués du
dépôt (scanner, connectivity, scanning) — les 5 sites historiques
passaient ``known_hosts=None`` (acceptation silencieuse de la clé
serveur = faille MITM, ``backend_status.md`` §7). Ce helper est
désormais **le seul** point du dépôt autorisé à construire des kwargs
``asyncssh.connect`` (garde-fou grep R4 : zéro ``known_hosts`` hors de
ce module).

Deux politiques de vérification de la clé d'hôte (spec 15 § Hosts
distants) :

- **STRICT** (scan, discovery, sessions opérationnelles —
  :class:`HostKeyPolicy.STRICT`) :

  * pas de ligne d'empreinte → **capture en PENDING** (``accepted=
    False`` — jamais d'ajout silencieux) + event ``PENDING`` +
    :class:`~app.core.exceptions.SSHHostKeyNotAcceptedError` ;
  * ligne non acceptée → idem (l'autorité est la colonne ``accepted`` +
    ``accepted_at``, pas l'existence d'une ligne) ;
  * empreinte divergente vs ligne acceptée → event ``DIVERGENCE`` +
    audit ``target.fingerprint_divergence`` +
    :class:`~app.core.exceptions.SSHHostKeyMismatchError` — l'empreinte
    acceptée n'est **jamais écrasée** (ré-acceptation délibérée via
    reset + accept, STORY-131.2) ;
  * acceptée + matching → session établie (``last_used_at`` de la clé
    d'authentification mise à jour le cas échéant — throttlé, via
    ``SSHKeyService``).

- **COLLECT** (test-connection uniquement —
  :class:`HostKeyPolicy.COLLECT`) : capture l'empreinte présentée
  **sans rien persister** et la retourne au caller pour affichage /
  acceptation explicite (AC « le test de connexion n'ajoute jamais
  silencieusement — il capte sans persister »). Une divergence
  détectée en COLLECT bloque tout de même la session (jamais de
  connexion vers un hôte dont la clé a changé sans ré-acceptation).

Contexte sans cible persistée (``target=None`` — scan ad hoc /
discovery pré-création / test-connection) : les empreintes TOFU sont
liées à ``targets.id`` (arbitrage F3 STORY-131, FK), aucune ligne ne
peut être lue ni écrite — STRICT bloque donc systématiquement au
premier contact (event ``PENDING`` avec ``target_id=None`` : jamais de
session non vérifiée), COLLECT retourne ``status="unknown"``. La voie
d'acceptation passe par la cible persistée : création manuelle → scan
(capture PENDING) → acceptation API (STORY-131.2) → re-scan.

Résolution de l'authentification (transition STORY-131) :

- ``ssh_key_id`` explicite ou ``target.ssh_key_id`` → clé réutilisable
  (voie canonique) : ``SSHKey.decrypted_private_key`` en
  ``client_keys`` + ``touch_last_used()`` throttlé — via
  ``SSHKeyService.resolve_for_target()`` ;
- sinon fallback credentials legacy : ``password`` ou
  ``ssh_private_key`` résiduel des credentials chiffrées (double
  lecture STORY-103.2) — compatibilité totale pendant la transition.

Sécurité (rules 40) : aucun matériau de clé (privée, passphrase) n'est
loggé ni transporté dans les events ; l'empreinte d'hôte est publique
par nature (identifiant de présentation, pas un secret).

Contrat P2 (STORY-174) : le workload adapter distant consommera ce
même helper — le contrat TOFU posé ici s'appliquera aux déploiements
runtime dès P2 (il n'existe pas de déploiement SSH runtime en P1,
cf. analyse STORY-131).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import asyncssh
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.events import EventType, event_bus
from ..core.exceptions import (
    SSHHostKeyMismatchError,
    SSHHostKeyNotAcceptedError,
)
from ..models.host_ssh_fingerprint import HostSSHFingerprint
from ..models.target import Target
from ..services.audit_service import AuditService
from ..services.ssh_key_service import SSHKeyService

logger = logging.getLogger(__name__)


class HostKeyPolicy(str, Enum):
    """Politique de vérification de la clé d'hôte SSH.

    - ``STRICT`` : bloque toute session si empreinte inconnue,
      non acceptée ou divergente (scan, discovery, sessions
      opérationnelles) — c'est la politique anti-MITM par défaut ;
    - ``COLLECT`` : capte l'empreinte sans persister (test-connection
      uniquement — l'acceptation est laissée à l'utilisateur).
    """

    STRICT = "strict"
    COLLECT = "collect"


@dataclass
class HostKeyCapture:
    """Empreinte d'hôte capturée pendant la négociation (mode COLLECT).

    Résultat non-persistant de la vérification — retourné au caller
    (``test-connection``) pour affichage et acceptation explicite via
    l'API STORY-131.2. Ne vit qu'en mémoire.

    Attributes:
        fingerprint: Empreinte présentée ``SHA256:<base64nopad>``.
        key_type: Algorithme de la clé d'hôte (``ssh-ed25519``…).
        status: Statut TOFU au moment de la capture — ``unknown``
            (aucune ligne acceptée), ``accepted`` (matching une ligne
            acceptée) ou ``mismatch`` (diverge d'une ligne acceptée).
        hostname: Hôte vérifié (contexte).
        port: Port vérifié (contexte).
        details: Contexte additionnel (ex.
            ``expected_fingerprint`` en cas de mismatch).
    """

    fingerprint: str
    key_type: str
    status: str
    hostname: str = ""
    port: int = 22
    details: dict[str, Any] = field(default_factory=dict)


def _presented_fingerprint(key: asyncssh.SSHKey) -> tuple[str, str]:
    """Extrait (empreinte, key_type) d'une clé d'hôte présentée.

    Divergence asyncssh documentée (131.1) : la lib expose
    ``get_fingerprint()`` (méthode, pas d'attribut ``fingerprint``) au
    format normalisé ``SHA256:<base64nopad>``.

    Args:
        key: Clé d'hôte présentée par le serveur (callback asyncssh).

    Returns:
        Tuple ``(fingerprint, key_type)`` — ``key_type`` via
        ``get_algorithm()`` (ex. ``ssh-ed25519``).
    """
    return key.get_fingerprint(), key.get_algorithm()


async def _lookup_fingerprint(
    db: AsyncSession,
    host_id: str,
    hostname: str,
    port: int,
    key_type: str,
) -> Optional[HostSSHFingerprint]:
    """Recherche la ligne d'empreinte ``(host_id, hostname, port, key_type)``.

    Args:
        db: Session de base de données async.
        host_id: Cible vérifiée (``targets.id``).
        hostname: Adresse de connexion.
        port: Port SSH.
        key_type: Algorithme de la clé d'hôte présentée.

    Returns:
        La ligne existante ou ``None`` (contrainte UNIQUE — au plus
        une par identité).
    """
    return (
        await db.execute(
            select(HostSSHFingerprint).where(
                HostSSHFingerprint.host_id == host_id,
                HostSSHFingerprint.hostname == hostname,
                HostSSHFingerprint.port == port,
                HostSSHFingerprint.key_type == key_type,
            )
        )
    ).scalar_one_or_none()


async def _emit_pending(
    target_id: Optional[str],
    hostname: str,
    port: int,
    key_type: str,
    fingerprint: str,
) -> None:
    """Émet l'événement ``HOST_SSH_FINGERPRINT_PENDING`` (sans secret)."""
    await event_bus.emit(
        EventType.HOST_SSH_FINGERPRINT_PENDING,
        {
            "target_id": target_id,
            "hostname": hostname,
            "port": port,
            "key_type": key_type,
            "fingerprint": fingerprint,
        },
    )


async def _emit_divergence(
    target_id: Optional[str],
    hostname: str,
    port: int,
    key_type: str,
    fingerprint: str,
    expected_fingerprint: str,
) -> None:
    """Émet l'événement ``HOST_SSH_FINGERPRINT_DIVERGENCE`` + audit.

    La divergence est une **alerte sécurité** (MITM potentiel) :
    l'événement est émis sur le bus (STORY-164 consommera) **et** une
    ligne d'audit ``target.fingerprint_divergence`` est persistée
    (acteur système — le blocage survient à l'établissement de la
    session, hors contexte utilisateur). Les empreintes d'hôte sont
    publiques par nature (identification, pas des secrets).
    """
    payload = {
        "target_id": target_id,
        "hostname": hostname,
        "port": port,
        "key_type": key_type,
        "fingerprint": fingerprint,
        "expected_fingerprint": expected_fingerprint,
    }
    await event_bus.emit(
        EventType.HOST_SSH_FINGERPRINT_DIVERGENCE,
        payload,
    )
    try:
        await AuditService.log(
            "target.fingerprint_divergence",
            user_id=None,
            organization_id=None,
            resource_type="host_ssh_fingerprint",
            resource_id=target_id,
            details=payload,
        )
    except Exception:  # pragma: no cover - AuditService.log n'est déjà
        # censé jamais lever (best-effort AC 4 STORY-125.1) ; garde
        # défensive : l'audit ne doit pas masquer le blocage SSH.
        logger.warning("ssh.fingerprint_divergence.audit_failed")


async def _verify_strict(
    db: AsyncSession,
    host_id: Optional[str],
    hostname: str,
    port: int,
    key: asyncssh.SSHKey,
) -> HostKeyCapture:
    """Vérification STRICT : seules les empreintes acceptées font autorité.

    Args:
        db: Session de base de données async.
        host_id: Cible vérifiée (``targets.id``) — ``None`` hors
            contexte cible persistée (scan ad hoc, discovery
            pré-création) : aucune lecture/écriture d'empreinte
            possible, blocage systématique au premier contact.
        hostname: Adresse de connexion.
        port: Port SSH.
        key: Clé d'hôte présentée.

    Returns:
        Capture ``status="accepted"`` si la session peut être établie.

    Raises:
        SSHHostKeyNotAcceptedError: Empreinte inconnue (ligne PENDING
            créée + event PENDING) ou enregistrée mais non acceptée ;
            systématique quand ``host_id`` est ``None``.
        SSHHostKeyMismatchError: Divergence avec une ligne acceptée
            (event DIVERGENCE + audit — jamais d'écrasement).
    """
    fingerprint, key_type = _presented_fingerprint(key)

    if host_id is None:
        # Pas de cible persistée : le TOFU vit sur ``targets.id``
        # (arbitrage F3) — aucune ligne n'existe ni ne peut être
        # créée. Blocage systématique : jamais de session non
        # vérifiée (event PENDING sans target pour l'observabilité).
        await _emit_pending(None, hostname, port, key_type, fingerprint)
        logger.warning(
            "ssh.host_key_pending_no_target hostname=%s port=%d "
            "key_type=%s — acceptation explicite requise (cible requise)",
            hostname,
            port,
            key_type,
        )
        raise SSHHostKeyNotAcceptedError(
            details={
                "hostname": hostname,
                "port": port,
                "key_type": key_type,
                "fingerprint": fingerprint,
                "target_id": None,
            },
            fingerprint=fingerprint,
            target_id=None,
        )

    row = await _lookup_fingerprint(db, host_id, hostname, port, key_type)

    if row is None:
        # Première connexion : capture PENDING (accepted=False —
        # jamais d'ajout silencieux) + event + blocage.
        db.add(
            HostSSHFingerprint(
                host_id=host_id,
                hostname=hostname,
                port=port,
                key_type=key_type,
                fingerprint=fingerprint,
                accepted=False,
            )
        )
        await db.commit()
        await _emit_pending(host_id, hostname, port, key_type, fingerprint)
        logger.warning(
            "ssh.host_key_pending target_id=%s hostname=%s port=%d "
            "key_type=%s — acceptation explicite requise",
            host_id,
            hostname,
            port,
            key_type,
        )
        raise SSHHostKeyNotAcceptedError(
            details={
                "hostname": hostname,
                "port": port,
                "key_type": key_type,
                "fingerprint": fingerprint,
                "target_id": host_id,
            },
            fingerprint=fingerprint,
            target_id=host_id,
        )

    if not row.accepted:
        # Ligne PENDING existante : pas d'autorité (ni re-création, ni
        # écrasement) — l'acceptation reste attendue côté API (131.2).
        await _emit_pending(host_id, hostname, port, key_type, fingerprint)
        raise SSHHostKeyNotAcceptedError(
            details={
                "hostname": hostname,
                "port": port,
                "key_type": key_type,
                "fingerprint": fingerprint,
                "target_id": host_id,
            },
            fingerprint=fingerprint,
            target_id=host_id,
        )

    if row.fingerprint != fingerprint:
        # Divergence vs ligne acceptée : blocage systématique, jamais
        # d'écrasement de l'empreinte faisant autorité.
        await _emit_divergence(
            host_id, hostname, port, key_type, fingerprint, row.fingerprint
        )
        logger.error(
            "ssh.host_key_mismatch target_id=%s hostname=%s port=%d "
            "key_type=%s — hôte reconfiguré ou usurpation (MITM ?)",
            host_id,
            hostname,
            port,
            key_type,
        )
        raise SSHHostKeyMismatchError(
            details={
                "hostname": hostname,
                "port": port,
                "key_type": key_type,
                "fingerprint": fingerprint,
                "target_id": host_id,
            },
            fingerprint=fingerprint,
            expected_fingerprint=row.fingerprint,
            target_id=host_id,
        )

    return HostKeyCapture(
        fingerprint=fingerprint,
        key_type=key_type,
        status="accepted",
        hostname=hostname,
        port=port,
    )


async def _verify_collect(
    db: AsyncSession,
    host_id: Optional[str],
    hostname: str,
    port: int,
    key: asyncssh.SSHKey,
) -> HostKeyCapture:
    """Vérification COLLECT : capte sans jamais persister.

    Compare à la ligne éventuelle pour renseigner le statut
    (``unknown`` / ``accepted`` / ``mismatch``) mais **aucune écriture**
    en base (AC « jamais d'ajout silencieux » — le test de connexion
    ne crée même pas de ligne PENDING ; c'est STRICT qui capture).
    Hors cible persistée (``host_id=None``) : statut ``unknown`` (le
    TOFU vit sur ``targets.id``).

    Args:
        db: Session de base de données async.
        host_id: Cible vérifiée (``targets.id``) ou ``None``.
        hostname: Adresse de connexion.
        port: Port SSH.
        key: Clé d'hôte présentée.

    Returns:
        Capture avec statut TOFU — en cas de mismatch,
        ``details["expected_fingerprint"]`` porte l'empreinte faisant
        autorité (publique, pour corrélation avec l'audit).
    """
    fingerprint, key_type = _presented_fingerprint(key)

    details: dict[str, Any] = {}
    if host_id is None:
        status = "unknown"
    else:
        row = await _lookup_fingerprint(db, host_id, hostname, port, key_type)
        if row is None or not row.accepted:
            status = "unknown"
        elif row.fingerprint == fingerprint:
            status = "accepted"
        else:
            status = "mismatch"
            details["expected_fingerprint"] = row.fingerprint

    return HostKeyCapture(
        fingerprint=fingerprint,
        key_type=key_type,
        status=status,
        hostname=hostname,
        port=port,
        details=details,
    )


async def _resolve_authentication_kwargs(
    db: AsyncSession,
    *,
    target: Target | None,
    ssh_key_id: str | None,
    password: str | None,
    ssh_private_key: str | None,
    passphrase: str | None,
    credentials: dict[str, Any] | None,
) -> dict[str, Any]:
    """Résout les kwargs d'authentification asyncssh.

    Priorité : ``ssh_key_id`` explicite → ``target.ssh_key_id``
    (service canonique, fallback legacy inclus) → matériau explicite
    de la requête → credentials legacy. Retourne ``{}`` si aucun
    matériau (asyncssh tentera alors l'agent par défaut).

    Args:
        db: Session de base de données async.
        target: Cible persistée éventuelle.
        ssh_key_id: Clé réutilisable explicite.
        password: Mot de passe explicite.
        ssh_private_key: Clé privée PEM explicite.
        passphrase: Passphrase explicite.
        credentials: Credentials déchiffrées de fallback.

    Returns:
        Kwargs d'authentification (``client_keys`` / ``password``).
    """
    if ssh_key_id is not None:
        row = await SSHKeyService.get(db, ssh_key_id)
        client_key = asyncssh.import_private_key(row.decrypted_private_key)
        await SSHKeyService.touch_last_used(db, ssh_key_id)
        return {"client_keys": [client_key]}

    if target is not None and target.ssh_key_id is not None:
        # Voie canonique — resolve_for_target gère clé référencée +
        # fallback legacy interne + touch_last_used throttlé.
        resolved = await SSHKeyService.resolve_for_target(db, target)
        if resolved:
            return resolved

    if ssh_private_key:
        return {"client_keys": [ssh_private_key], "passphrase": passphrase}

    # Fallback credentials legacy : dict explicite, sinon credentials
    # déchiffrées de la cible (double lecture STORY-103.2).
    creds = credentials or (
        target.decrypted_credentials if target is not None else {}
    )
    legacy_key = creds.get("ssh_private_key")
    if isinstance(legacy_key, str) and legacy_key.strip():
        return {
            "client_keys": [legacy_key],
            "passphrase": creds.get("ssh_private_key_passphrase"),
        }

    resolved_password = password or creds.get("password")
    if resolved_password:
        return {"password": resolved_password}
    return {}


async def build_ssh_kwargs(
    db: AsyncSession,
    *,
    host: str,
    port: int,
    username: str | None,
    mode: HostKeyPolicy,
    target: Target | None = None,
    ssh_key_id: str | None = None,
    password: str | None = None,
    ssh_private_key: str | None = None,
    passphrase: str | None = None,
    credentials: dict[str, Any] | None = None,
    capture_out: list[HostKeyCapture] | None = None,
) -> dict[str, Any]:
    """Construit les kwargs ``asyncssh.connect`` avec vérification TOFU.

    Point d'entrée unique (DRY) : résolution de l'authentification
    (clé référencée → fallback credentials) + callback
    ``server_host_key_verify`` appliquant la politique demandée. Ne
    passe **jamais** ``known_hosts`` (R4).

    Résolution de l'authentification, par ordre de priorité :

    1. ``ssh_key_id`` explicite (via :meth:`SSHKeyService.get` +
       ``decrypted_private_key`` + ``touch_last_used``) ;
    2. ``target.ssh_key_id`` (voie canonique —
       :meth:`SSHKeyService.resolve_for_target`, qui gère aussi le
       fallback legacy interne et le throttling) ;
    3. ``ssh_private_key`` / ``passphrase`` explicites (test-connection,
       discovery — matériau fourni dans la requête) ;
    4. ``password`` explicite, sinon ``credentials["password"]``.

    Args:
        db: Session de base de données async.
        host: Adresse de l'hôte distant.
        port: Port SSH.
        username: Utilisateur SSH (requis par asyncssh).
        mode: Politique de vérification (STRICT sessions
            opérationnelles, COLLECT test-connection).
        target: Cible persistée éventuelle — fournit ``ssh_key_id``,
            les credentials de fallback et l'identité ``id`` du TOFU.
            Si ``None`` (scan ad hoc, discovery pré-création,
            test-connection), STRICT bloque au premier contact sans
            persister (cf. docstring module) et COLLECT retourne
            ``unknown``.
        ssh_key_id: Clé SSH réutilisable explicite (prime sur
            ``target.ssh_key_id``).
        password: Mot de passe SSH explicite (fallback).
        ssh_private_key: Clé privée PEM explicite (fallback).
        passphrase: Passphrase de la clé privée explicite.
        credentials: Credentials déchiffrées éventuelles (fallback
            ``password`` / ``ssh_private_key``).
        capture_out: Liste recevant la capture (COLLECT — le caller
            la consomme pour ``ConnectionTestResponse`` ; STRICT la
            reçoit aussi en cas de succès).

    Returns:
        Kwargs prêts pour ``asyncssh.connect(**kwargs)``.

    Raises:
        SSHHostKeyNotAcceptedError: STRICT — empreinte inconnue ou
            non acceptée (session bloquée, ligne PENDING créée le cas
            échéant).
        SSHHostKeyMismatchError: STRICT — divergence (session bloquée,
            jamais d'écrasement).
    """
    # Identité TOFU : la cible persistée si disponible (arbitrage F3
    # STORY-131 — host_ssh_fingerprints.host_id → targets.id), sinon
    # None (aucune lecture/écriture d'empreinte possible).
    host_id = target.id if target is not None else None

    async def _verify_host_key(
        _host: str,
        _addr: str,
        _port: int,
        key: asyncssh.SSHKey,
        _algorithm: str,  # noqa: ARG001 — signature asyncssh
    ) -> bool:
        """Callback ``server_host_key_verify`` — délègue à la politique."""
        if mode is HostKeyPolicy.COLLECT:
            capture = await _verify_collect(db, host_id, host, port, key)
            if capture_out is not None:
                capture_out.append(capture)
            # COLLECT n'établit jamais l'autorité (l'acceptation est
            # explicite, via API), mais une divergence détectée bloque
            # tout de même la connexion : jamais de session vers un
            # hôte dont la clé acceptée a changé sans ré-acceptation.
            if capture.status == "mismatch":
                await _emit_divergence(
                    host_id,
                    host,
                    port,
                    capture.key_type,
                    capture.fingerprint,
                    str(capture.details.get("expected_fingerprint", "")),
                )
                return False
            return True

        capture = await _verify_strict(db, host_id, host, port, key)
        if capture_out is not None:
            capture_out.append(capture)
        return True

    kwargs: dict[str, Any] = {
        "host": host,
        "port": port,
        "username": username,
        "server_host_key_verify": _verify_host_key,
    }

    # ── Authentification ──────────────────────────────────────────
    resolved = await _resolve_authentication_kwargs(
        db,
        target=target,
        ssh_key_id=ssh_key_id,
        password=password,
        ssh_private_key=ssh_private_key,
        passphrase=passphrase,
        credentials=credentials,
    )
    kwargs.update(resolved)
    return kwargs
