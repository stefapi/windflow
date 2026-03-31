"""
Détection du profil d'accès d'un utilisateur sur une cible de déploiement.

Détermine le niveau d'accès (root, sudo, sudo_passwordless, limited)
via une série de tests commandes (whoami, which sudo, sudo -n, sudo -S).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ..enums.target import AccessLevel
from ..schemas.target import TargetAccessProfile
from .commands import CommandExecutor, CommandResult, LocalCommandExecutor

logger = logging.getLogger(__name__)


class TargetAccessProfileDetector:
    """Détecte le profil d'accès d'un utilisateur sur une cible.

    Étapes de détection :
    1. ``whoami`` → l'utilisateur est-il root ?
    2. ``which sudo`` → binaire sudo présent ?
    3. Test de sudo (avec mot de passe, sans mot de passe, ou vers root)
    4. Construction du :class:`TargetAccessProfile`
    """

    async def detect(
        self,
        executor: CommandExecutor,
        ssh_user: str | None = None,
        sudo_user: str | None = None,
        sudo_password: str | None = None,
        sudo_enabled: bool = False,
        detection_method: str = "scan",
    ) -> TargetAccessProfile:
        """Détecte le niveau d'accès de l'exécuteur courant sur la cible.

        Args:
            executor: Exécuteur de commande (local ou SSH).
            ssh_user: Nom d'utilisateur SSH (métadonnée).
            sudo_user: Utilisateur sudo configuré.
            sudo_password: Mot de passe sudo configuré.
            sudo_enabled: Sudo explicitement activé par l'utilisateur.
            detection_method: Origine de la détection (``"scan"`` ou ``"discovery"``).

        Returns:
            Le profil d'accès détecté.
        """
        connected_user = await self._detect_connected_user(executor, ssh_user)
        sudo_available = await self._check_sudo_available(executor)

        access_level, sudo_verified, sudo_passwordless, effective_sudo_user = (
            await self._determine_access_level(
                executor, connected_user, sudo_available,
                sudo_enabled, sudo_user, sudo_password,
            )
        )

        return self._build_profile(
            connected_user=connected_user, sudo_available=sudo_available,
            sudo_verified=sudo_verified, sudo_passwordless=sudo_passwordless,
            effective_sudo_user=effective_sudo_user, access_level=access_level,
            detection_method=detection_method,
        )

    # ─── Construction du profil ───────────────────────────────

    @staticmethod
    def _build_profile(
        *,
        connected_user: str,
        sudo_available: bool,
        sudo_verified: bool,
        sudo_passwordless: bool,
        effective_sudo_user: str | None,
        access_level: AccessLevel,
        detection_method: str,
    ) -> TargetAccessProfile:
        """Construit le :class:`TargetAccessProfile` à partir des données détectées."""
        is_root = connected_user == "root"
        return TargetAccessProfile(
            ssh_user=connected_user,
            is_root_user=is_root,
            sudo_available=sudo_available,
            sudo_verified=sudo_verified,
            sudo_passwordless=sudo_passwordless,
            sudo_user=effective_sudo_user,
            access_level=access_level,
            can_install_packages=TargetAccessProfileDetector._can_install_packages(
                is_root, sudo_verified, effective_sudo_user,
            ),
            standard_capabilities=[],
            elevated_capabilities=[],
            detected_at=datetime.now(timezone.utc),
            detection_method=detection_method,
        )

    # ─── Détection interne ────────────────────────────────────

    @staticmethod
    async def _detect_connected_user(
        executor: CommandExecutor, ssh_user: str | None,
    ) -> str:
        """Détermine l'utilisateur connecté via ``whoami``."""
        result = await executor.run("whoami", timeout=10)
        if result.success:
            return result.stripped_stdout()
        return ssh_user or "unknown"

    @staticmethod
    async def _check_sudo_available(executor: CommandExecutor) -> bool:
        """Vérifie si le binaire sudo est présent."""
        result = await executor.run("which sudo 2>/dev/null", timeout=10)
        return result.success and bool(result.stripped_stdout())

    async def _determine_access_level(
        self,
        executor: CommandExecutor,
        connected_user: str,
        sudo_available: bool,
        sudo_enabled: bool,
        sudo_user: str | None,
        sudo_password: str | None,
    ) -> tuple[AccessLevel, bool, bool, str | None]:
        """Détermine le niveau d'accès effectif en testant sudo."""
        if connected_user == "root":
            return AccessLevel.ROOT, False, False, "root"

        if not sudo_enabled or not sudo_available:
            return AccessLevel.LIMITED, False, False, None

        if sudo_user and sudo_password:
            return await self._test_sudo_password(executor, sudo_user, sudo_password)
        if sudo_user and not sudo_password:
            return await self._test_sudo_passwordless(executor, sudo_user)
        return await self._test_sudo_passwordless_root(executor)

    async def _test_sudo_password(
        self, executor: CommandExecutor, sudo_user: str, sudo_password: str,
    ) -> tuple[AccessLevel, bool, bool, str | None]:
        """Teste sudo avec mot de passe."""
        sudo_test = await self._run_sudo_test(executor, sudo_user, sudo_password)
        if sudo_test.success and sudo_test.stripped_stdout():
            return AccessLevel.SUDO, True, False, sudo_test.stripped_stdout()
        return AccessLevel.LIMITED, False, False, None

    async def _test_sudo_passwordless(
        self, executor: CommandExecutor, sudo_user: str,
    ) -> tuple[AccessLevel, bool, bool, str | None]:
        """Teste sudo sans mot de passe vers un utilisateur spécifique."""
        result = await executor.run(
            f"sudo -n -u {sudo_user} whoami 2>/dev/null", timeout=15,
        )
        if result.success and result.stripped_stdout():
            return AccessLevel.SUDO_PASSWORDLESS, True, True, result.stripped_stdout()
        return AccessLevel.LIMITED, False, False, None

    async def _test_sudo_passwordless_root(
        self, executor: CommandExecutor,
    ) -> tuple[AccessLevel, bool, bool, str | None]:
        """Teste sudo sans mot de passe vers root."""
        result = await executor.run("sudo -n whoami 2>/dev/null", timeout=15)
        if result.success and result.stripped_stdout():
            return AccessLevel.SUDO_PASSWORDLESS, True, True, result.stripped_stdout()
        return AccessLevel.LIMITED, False, False, None

    async def _run_sudo_test(
        self, executor: CommandExecutor, sudo_user: str, sudo_password: str,
    ) -> CommandResult:
        """Exécute un test sudo avec mot de passe, de manière sécurisée.

        Pour l'exécution locale, utilise stdin pour éviter l'injection shell.
        Pour SSH, utilise l'executor directement.
        """
        if isinstance(executor, LocalCommandExecutor):
            return await self._test_sudo_local_stdin(sudo_user, sudo_password)
        return await executor.run(
            f"sudo -S -p '' -u {sudo_user} whoami 2>/dev/null",
            timeout=15,
        )

    @staticmethod
    async def _test_sudo_local_stdin(
        sudo_user: str, sudo_password: str,
    ) -> CommandResult:
        """Teste sudo localement en pipant le mot de passe via stdin."""
        command = f"sudo -S -p '' -u {sudo_user} whoami"
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )
            password_bytes = f"{sudo_password}\n".encode("utf-8")
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(input=password_bytes), timeout=15,
            )
            stdout = stdout_bytes.decode("utf-8", errors="ignore")
            stderr = stderr_bytes.decode("utf-8", errors="ignore")
            return CommandResult(process.returncode, stdout, stderr)
        except asyncio.TimeoutError:
            process.kill()
            return CommandResult(124, "", "Commande expirée")

    @staticmethod
    def _can_install_packages(
        is_root: bool, sudo_verified: bool, effective_sudo_user: str | None,
    ) -> bool:
        """Détermine si l'utilisateur peut installer des paquets.

        Seul root (ou sudo vers root) permet l'installation de paquets.
        """
        return is_root or (sudo_verified and effective_sudo_user == "root")
