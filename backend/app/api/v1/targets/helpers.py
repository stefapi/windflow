"""Fonctions utilitaires partagées entre les sous-modules targets."""

from __future__ import annotations

from typing import Any

from ....services.commands import LocalCommandExecutor, SSHCommandExecutor


async def test_sudo_access(
    executor: LocalCommandExecutor | SSHCommandExecutor,
    sudo_user: str,
    sudo_password: str | None,
) -> dict[str, Any]:
    """Test sudo access with optional password.

    Returns dict with 'success' (bool) and 'message' (str).
    """
    try:
        if isinstance(executor, SSHCommandExecutor):
            # For SSH: use echo pipe approach
            if sudo_password:
                cmd = f"echo '{sudo_password}' | sudo -S -p '' -u {sudo_user} whoami 2>/dev/null"
            else:
                cmd = f"sudo -n -u {sudo_user} whoami 2>/dev/null"
            result = await executor.run(cmd, timeout=15)
        else:
            # For local: create a sudo-enabled executor to test
            sudo_exec = LocalCommandExecutor(
                sudo_user=sudo_user,
                sudo_password=sudo_password,
            )
            result = await sudo_exec.run("whoami", timeout=15)

        if result.success and result.stdout.strip():
            return {
                "success": True,
                "message": f"sudo OK → {result.stdout.strip()}",
            }
        return {
            "success": False,
            "message": result.stderr.strip() or "exit code non-zero",
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}
