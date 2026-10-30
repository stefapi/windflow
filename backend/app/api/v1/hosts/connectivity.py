"""Tests de connectivité des cibles (reachability + SSH)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import asyncssh
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ....auth.rbac import require_operator
from ....core.exceptions import SSHHostKeyMismatchError, SSHHostKeyNotAcceptedError
from ....core.rate_limit import conditional_rate_limiter
from ....database import get_db
from ....models.user import User
from ....schemas.host import (
    ConnectionTestRequest,
    ConnectionTestResponse,
    HostReachabilityRequest,
    HostReachabilityResponse,
    HostReachabilityStepResult,
    SSHAuthMethod,
)
from ....services.commands import LocalCommandExecutor, SSHCommandExecutor
from ....services.ssh_connection import (
    HostKeyCapture,
    HostKeyPolicy,
    build_ssh_kwargs,
)
from .helpers import test_sudo_access

router = APIRouter()
logger = logging.getLogger(__name__)


def target_ip_display(host: str, resolved_ip: str | None) -> str:
    """Helper pour afficher l'IP résolue si différente du host."""
    if resolved_ip and resolved_ip != host:
        return f"{resolved_ip}"
    return host


@router.post(
    "/test-reachability",
    response_model=HostReachabilityResponse,
    status_code=status.HTTP_200_OK,
    summary="Test host reachability (DNS + Ping + SSH port)",
    description="""
Test la joignabilité d'un hôte sans authentification.

## Étapes séquentielles
1. **DNS** — Résolution du nom d'hôte (si ce n'est pas une IP)
2. **Ping** — Test ICMP (peut échouer si ping désactivé sur le serveur)
3. **SSH** — Tentative de connexion TCP au port SSH sans login

## Utilisation
- Vérifier qu'un hôte est accessible avant de saisir les credentials
- Diagnostic rapide de connectivité
- Valider la résolution DNS et l'ouverture du port SSH

## Notes
- L'étape Ping peut échouer si l'hôte cible bloque l'ICMP (pare-feu).
  Ce n'est pas forcément bloquant — le test SSH sera quand même exécuté.

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    tags=["hosts"],
)
async def test_reachability(
    request: Request,
    reachability_request: HostReachabilityRequest,
    current_user: User = Depends(require_operator),
) -> HostReachabilityResponse:
    """Test host reachability: DNS resolution + SSH port check (no auth).

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``operator`` minimum — diagnostic réseau
    lecture-only sans credentials (spec 08 § familles : opération
    Operator+). Divergence inventaire (admin) signalée : libellé réel =
    test de joignabilité, pas un scan d'ajout de cible.
    """
    import socket
    import time

    correlation_id = getattr(request.state, "correlation_id", None)
    host = reachability_request.host
    port = reachability_request.port
    logger.info(
        f"Testing reachability for {host}:{port}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host": host,
            "port": port,
        },
    )

    steps: list[HostReachabilityStepResult] = []
    resolved_ip: str | None = None

    # ── Step 1: DNS Resolution ──────────────────────────────────
    # Skip DNS check for plain IP addresses
    is_ip = False
    try:
        socket.inet_pton(socket.AF_INET, host)
        is_ip = True
    except OSError:
        try:
            socket.inet_pton(socket.AF_INET6, host)
            is_ip = True
        except OSError:
            pass

    if is_ip:
        steps.append(
            HostReachabilityStepResult(
                step="dns",
                success=True,
                message=f"{host} est une adresse IP (pas de résolution DNS nécessaire)",
                duration_ms=0,
            )
        )
        resolved_ip = host
    else:
        t0 = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
            addr_infos = await asyncio.wait_for(
                loop.getaddrinfo(host, None),
                timeout=5.0,
            )
            elapsed = (time.monotonic() - t0) * 1000
            if addr_infos:
                resolved_ip = addr_infos[0][4][0]
                steps.append(
                    HostReachabilityStepResult(
                        step="dns",
                        success=True,
                        message=f"Résolution DNS réussie : {host} → {resolved_ip}",
                        duration_ms=round(elapsed, 1),
                    )
                )
            else:
                steps.append(
                    HostReachabilityStepResult(
                        step="dns",
                        success=False,
                        message=f"Aucun enregistrement DNS pour {host}",
                        duration_ms=round(elapsed, 1),
                    )
                )
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - t0) * 1000
            steps.append(
                HostReachabilityStepResult(
                    step="dns",
                    success=False,
                    message=f"Timeout de résolution DNS pour {host} (>{elapsed:.0f}ms)",
                    duration_ms=round(elapsed, 1),
                )
            )
        except OSError as exc:
            elapsed = (time.monotonic() - t0) * 1000
            steps.append(
                HostReachabilityStepResult(
                    step="dns",
                    success=False,
                    message=f"Échec de résolution DNS pour {host} : {exc}",
                    duration_ms=round(elapsed, 1),
                )
            )

    # ── Step 2: SSH Port Check ──────────────────────────────────
    dns_ok = steps[0].success
    if dns_ok:
        target_host = resolved_ip or host
        t0 = time.monotonic()
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(target_host, port),
                timeout=5.0,
            )
            elapsed = (time.monotonic() - t0) * 1000
            writer.close()
            await writer.wait_closed()
            steps.append(
                HostReachabilityStepResult(
                    step="ssh",
                    success=True,
                    message=f"Port SSH {port} ouvert sur {host} ({target_ip_display(host, resolved_ip)})",
                    duration_ms=round(elapsed, 1),
                )
            )
        except asyncio.TimeoutError:
            elapsed = (time.monotonic() - t0) * 1000
            steps.append(
                HostReachabilityStepResult(
                    step="ssh",
                    success=False,
                    message=f"Timeout de connexion au port {port} sur {host} (>{elapsed:.0f}ms)",
                    duration_ms=round(elapsed, 1),
                )
            )
        except OSError as exc:
            elapsed = (time.monotonic() - t0) * 1000
            steps.append(
                HostReachabilityStepResult(
                    step="ssh",
                    success=False,
                    message=f"Impossible de se connecter au port {port} sur {host} : {exc}",
                    duration_ms=round(elapsed, 1),
                )
            )
    else:
        steps.append(
            HostReachabilityStepResult(
                step="ssh",
                success=False,
                message="Étape ignorée : la résolution DNS a échoué",
                duration_ms=None,
            )
        )

    reachable = all(s.success for s in steps)
    return HostReachabilityResponse(
        host=host,
        port=port,
        steps=steps,
        reachable=reachable,
    )


@router.post(
    "/test-connection",
    response_model=ConnectionTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test SSH connection to a host",
    description="""
Test SSH connection to a host with provided credentials.

## Process
1. Attempts to establish an SSH connection using provided credentials
2. Captures the SSH **host key fingerprint** (TOFU — STORY-131.3):
   nothing is persisted, the fingerprint is returned for
   **explicit acceptance** via `POST /hosts/{id}/ssh-fingerprints/accept`
3. If successful, retrieves basic OS information
4. Returns connection status, OS details and fingerprint status

## Fingerprint statuses (STORY-131.3)
- `unknown` — no accepted fingerprint for this host yet (first use);
- `accepted` — matches a previously accepted fingerprint;
- `mismatch` — differs from an accepted fingerprint: the connection
  is **refused** (potential host reconfiguration or MITM — spec 15).

## Supported Authentication Methods
- **Password**: Username + password authentication
- **SSH Key**: Username + private key (with optional passphrase)

## Use Cases
- Validate credentials before creating a host
- Capture the host fingerprint for first-use acceptance
- Test connection after updating credentials
- Troubleshoot connectivity issues

**Authentication Required**
""",
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    responses={
        200: {
            "description": "Connection test result (with captured fingerprint)",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": (
                            "Connexion réussie à prod-vm01:22 en tant que "
                            "'deploy' — empreinte hôte : "
                            "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc "
                            "(unknown)"
                        ),
                        "os_info": {"uname": "Linux prod-vm01 5.15.0 …"},
                        "host_fingerprint": (
                            "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
                        ),
                        "fingerprint_status": "unknown",
                    }
                }
            },
        },
    },
    tags=["hosts"],
)
async def test_connection(
    request: Request,
    test_request: ConnectionTestRequest,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
) -> ConnectionTestResponse:
    """Test SSH connection to a host.

    ## Access Control (STORY-122.5)

    Nécessite le rôle global ``operator`` minimum — test de connexion
    SSH lecture-only (spec 08 § familles : SSH lecture = Operator+).
    Divergence inventaire (admin) signalée : libellé réel = test de
    connexion, cas prévu par la story.

    ## TOFU (STORY-131.3)

    Mode COLLECT : l'empreinte présentée est capturée **sans être
    persistée** (jamais d'ajout silencieux) et retournée dans
    ``host_fingerprint``/``fingerprint_status`` pour acceptation
    explicite ; une divergence avec une empreinte acceptée refuse la
    connexion (``mismatch``).
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Testing SSH connection to {test_request.host}:{test_request.port}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "host": test_request.host,
        },
    )
    creds = test_request.credentials

    # ── Mode local (sans SSH) ────────────────────────────────────
    if creds.auth_method == SSHAuthMethod.LOCAL:
        return await _test_local_connection(creds, correlation_id)

    # ── Mode SSH (password ou clé) ──────────────────────────────
    return await _test_ssh_connection(
        test_request, creds, correlation_id, session=session
    )


async def _test_local_connection(
    creds: Any,
    correlation_id: str | None,
) -> ConnectionTestResponse:
    """Test connexion locale (mode LOCAL)."""
    try:
        executor = LocalCommandExecutor()
        os_info: dict[str, Any] = {}

        uname_result = await executor.run("uname -a", timeout=10)
        if uname_result.success:
            os_info["uname"] = uname_result.stdout.strip()

        os_release_result = await executor.run("cat /etc/os-release", timeout=10)
        if os_release_result.success:
            for line in os_release_result.stdout.splitlines():
                if line.startswith("PRETTY_NAME="):
                    os_info["distribution"] = line.split("=", 1)[1].strip('"')
                elif line.startswith("VERSION="):
                    os_info["version"] = line.split("=", 1)[1].strip('"')

        import getpass

        local_user = getpass.getuser()

        # ── Test sudo access if enabled ──────────────────────
        sudo_test_msg = ""
        if creds.sudo_enabled:
            sudo_user = creds.sudo_user or "root"
            sudo_test = await test_sudo_access(
                executor=executor,
                sudo_user=sudo_user,
                sudo_password=creds.sudo_password,
            )
            if sudo_test["success"]:
                sudo_test_msg = f" — sudo vers {sudo_user} vérifié"
            else:
                sudo_test_msg = (
                    f" — ⚠ sudo vers {sudo_user} échoué : {sudo_test['message']}"
                )

        return ConnectionTestResponse(
            success=True,
            message=f"Connexion locale réussie en tant que '{local_user}'{sudo_test_msg}",
            os_info=os_info or None,
        )
    except Exception as exc:
        return ConnectionTestResponse(
            success=False,
            message=f"Échec d'accès local : {exc}",
        )


async def _test_ssh_connection(
    test_request: ConnectionTestRequest,
    creds: Any,
    correlation_id: str | None,
    session: AsyncSession | None = None,
) -> ConnectionTestResponse:
    """Test connexion SSH (password ou clé) — mode COLLECT (STORY-131.3).

    TOFU : l'empreinte de la clé d'hôte est **capturée sans être
    persistée** (jamais d'ajout silencieux) et retournée dans la
    réponse (``host_fingerprint`` + ``fingerprint_status``) pour
    acceptation explicite via l'API STORY-131.2. Une divergence avec
    une empreinte acceptée bloque la connexion (``mismatch``).
    """
    captures: list[HostKeyCapture] = []
    ssh_kwargs = await build_ssh_kwargs(
        session,
        host=test_request.host,
        port=test_request.port,
        username=creds.username,
        mode=HostKeyPolicy.COLLECT,
        password=creds.password if creds.auth_method != SSHAuthMethod.SSH_KEY else None,
        ssh_private_key=(
            creds.ssh_private_key
            if creds.auth_method == SSHAuthMethod.SSH_KEY
            else None
        ),
        passphrase=(
            creds.ssh_private_key_passphrase
            if creds.auth_method == SSHAuthMethod.SSH_KEY
            else None
        ),
        capture_out=captures,
    )

    def _response(
        success: bool, message: str, os_info: dict[str, Any] | None = None
    ) -> ConnectionTestResponse:
        """Construit la réponse en attachant la capture éventuelle."""
        capture = captures[0] if captures else None
        return ConnectionTestResponse(
            success=success,
            message=message,
            os_info=os_info or None,
            host_fingerprint=capture.fingerprint if capture else None,
            fingerprint_status=capture.status if capture else None,
        )

    try:
        async with asyncssh.connect(**ssh_kwargs) as conn:
            # Connection successful — try to get OS info
            os_info = await _fetch_os_info(conn)

            # ── Test sudo access if enabled ──────────────────────
            sudo_test_msg = ""
            if creds.sudo_enabled:
                sudo_user = creds.sudo_user or "root"
                ssh_plain_executor = SSHCommandExecutor(conn)
                sudo_test = await test_sudo_access(
                    executor=ssh_plain_executor,
                    sudo_user=sudo_user,
                    sudo_password=creds.sudo_password,
                )
                if sudo_test["success"]:
                    sudo_test_msg = f" — sudo vers {sudo_user} vérifié"
                else:
                    sudo_test_msg = (
                        f" — ⚠ sudo vers {sudo_user} échoué : {sudo_test['message']}"
                    )

            status = captures[0].status if captures else "unknown"
            fp_msg = (
                f" — empreinte hôte : {captures[0].fingerprint} ({status})"
                if captures
                else ""
            )
            return _response(
                True,
                f"Connexion réussie à {test_request.host}:{test_request.port} "
                f"en tant que '{creds.username}'{sudo_test_msg}{fp_msg}",
                os_info,
            )
    except (SSHHostKeyNotAcceptedError, SSHHostKeyMismatchError) as exc:
        # Blocage TOFU (STORY-131.3 — mismatch COLLECT) : message
        # générique côté client, détail interne déjà loggé par le
        # helper (rules 40).
        return _response(
            False,
            f"Connexion refusée : {exc.message}",
        )
    except asyncssh.PermissionDenied:
        return _response(
            False,
            "Authentification échouée : identifiants incorrects",
        )
    except asyncssh.ConnectionLost:
        return _response(
            False,
            "Connexion perdue pendant la négociation SSH",
        )
    except OSError as exc:
        return _response(
            False,
            f"Impossible de se connecter à {test_request.host}:{test_request.port} — {exc}",
        )
    except Exception as exc:  # noqa: B902
        logger.warning(
            f"Unexpected SSH test error: {exc}",
            extra={"correlation_id": correlation_id},
        )
        return _response(
            False,
            f"Erreur inattendue : {exc}",
        )


async def _fetch_os_info(conn: asyncssh.SSHClientConnection) -> dict[str, str]:
    """Récupère les infos OS via la connexion SSH."""
    os_info: dict[str, str] = {}
    try:
        result = await asyncio.wait_for(
            conn.run("uname -a", check=False, encoding="utf-8"),
            timeout=10,
        )
        if result.exit_status == 0:
            os_info["uname"] = str(result.stdout).strip()  # type: ignore[union-attr]

        result = await asyncio.wait_for(
            conn.run("cat /etc/os-release", check=False, encoding="utf-8"),
            timeout=10,
        )
        if result.exit_status == 0:
            for line in str(result.stdout).splitlines():  # type: ignore[union-attr]
                if line.startswith("PRETTY_NAME="):
                    os_info["distribution"] = line.split("=", 1)[1].strip('"')  # type: ignore[arg-type]
                elif line.startswith("VERSION="):
                    os_info["version"] = line.split("=", 1)[1].strip('"')  # type: ignore[arg-type]
    except (asyncio.TimeoutError, asyncssh.Error):
        pass  # Non-critical: OS info is optional
    return os_info
