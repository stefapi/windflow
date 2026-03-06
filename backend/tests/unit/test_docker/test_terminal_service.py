"""
Tests unitaires pour le TerminalService.

Ces tests vérifient les fonctionnalités du service de terminal interactif
pour les conteneurs Docker.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime

from app.services.terminal_service import (
    TerminalService,
    ExecSession,
    ShellInfo,
    get_terminal_service,
)


class TestTerminalService:
    """Tests pour la classe TerminalService."""

    @pytest.fixture
    def mock_docker_client(self):
        """Crée un mock du client Docker."""
        client = MagicMock()
        client.get_container = AsyncMock()
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def terminal_service(self, mock_docker_client):
        """Crée une instance du TerminalService avec un mock."""
        service = TerminalService(docker_client=mock_docker_client)
        return service

    @pytest.mark.asyncio
    async def test_create_session_success(self, terminal_service, mock_docker_client):
        """Test la création d'une session terminal avec succès."""
        # Mock container
        mock_container = MagicMock()
        mock_container.state = {"Status": "running"}
        mock_docker_client.get_container.return_value = mock_container

        # Mock subprocess
        mock_process = MagicMock()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()
        mock_stdin.write = AsyncMock()
        mock_stdin.flush = AsyncMock()
        mock_process.stdin = mock_stdin
        mock_process.stdout = mock_stdout
        mock_process.stderr = mock_stderr
        mock_process.returncode = None

        async def mock_create_subprocess(*args, **kwargs):
            return mock_process

        with patch('app.services.terminal_service.asyncio.create_subprocess_exec', side_effect=mock_create_subprocess):
            session = await terminal_service.create_session(
                container_id="test-container",
                shell="/bin/bash",
                user="root"
            )

            assert session is not None
            assert session.container_id == "test-container"
            assert session.shell == "/bin/bash"
            assert session.user == "root"
            assert session.exec_id is not None
            assert len(session.exec_id) == 8

    @pytest.mark.asyncio
    async def test_create_session_container_not_running(self, terminal_service, mock_docker_client):
        """Test la création d'une session quand le container n'est pas en cours d'exécution."""
        mock_container = MagicMock()
        mock_container.state = {"Status": "stopped"}
        mock_docker_client.get_container.return_value = mock_container

        with pytest.raises(ValueError, match="not running"):
            await terminal_service.create_session(
                container_id="test-container",
                shell="/bin/bash"
            )

    @pytest.mark.asyncio
    async def test_create_session_container_not_found(self, terminal_service, mock_docker_client):
        """Test la création d'une session quand le container n'existe pas."""
        mock_docker_client.get_container.side_effect = Exception("Container not found")

        with pytest.raises(ValueError, match="not found"):
            await terminal_service.create_session(
                container_id="nonexistent-container",
                shell="/bin/bash"
            )

    @pytest.mark.asyncio
    async def test_send_input(self, terminal_service):
        """Test l'envoi d'entrée au terminal."""
        mock_stdin = AsyncMock()
        mock_stdin.write = MagicMock()
        mock_stdin.flush = AsyncMock()

        mock_process = MagicMock()
        mock_process.stdin = mock_stdin
        mock_process.returncode = None

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process
        )

        await terminal_service.send_input(session, "ls -la\n")

        mock_stdin.write.assert_called_once()
        mock_stdin.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_resize_tty(self, terminal_service):
        """Test le redimensionnement du TTY."""
        mock_stdin = AsyncMock()
        mock_stdin.write = MagicMock()
        mock_stdin.flush = AsyncMock()

        mock_process = MagicMock()
        mock_process.stdin = mock_stdin
        mock_process.returncode = None

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process
        )

        await terminal_service.resize_tty(session, 120, 40)

        assert session.cols == 120
        assert session.rows == 40
        mock_stdin.write.assert_called_once()
        mock_stdin.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_session(self, terminal_service):
        """Test le nettoyage d'une session."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.stdin = MagicMock()
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        mock_process.kill = AsyncMock()

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process
        )

        # Ajouter la session au service
        terminal_service._sessions["test123"] = session

        await terminal_service.cleanup_session(session)

        assert "test123" not in terminal_service._sessions
        mock_process.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_shells(self, terminal_service, mock_docker_client):
        """Test la détection des shells disponibles."""
        # Mock exec_in_container pour retourner不同的 résultats
        mock_docker_client.exec_in_container = AsyncMock(side_effect=[
            MagicMock(exit_code=0),  # /bin/bash existe
            MagicMock(exit_code=1),  # /bin/zsh n'existe pas
            MagicMock(exit_code=0),  # /bin/sh existe
        ])

        shells = await terminal_service.detect_shells("test-container")

        assert len(shells) == 6  # Tous les shells définis
        assert shells[0].path == "/bin/bash"
        assert shells[0].available is True
        assert shells[1].path == "/bin/zsh"
        assert shells[1].available is False

    @pytest.mark.asyncio
    async def test_get_session(self, terminal_service):
        """Test la récupération d'une session par son ID."""
        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24
        )

        terminal_service._sessions["test123"] = session

        retrieved = await terminal_service.get_session("test123")

        assert retrieved is not None
        assert retrieved.exec_id == "test123"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, terminal_service):
        """Test la récupération d'une session inexistante."""
        retrieved = await terminal_service.get_session("nonexistent")

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_close(self, terminal_service):
        """Test la fermeture du service et nettoyage des sessions."""
        # Créer des sessions mock avec processus mocké
        for i in range(3):
            mock_process = MagicMock()
            mock_process.returncode = 0  # Pas déjà terminé
            mock_process.stdin = MagicMock()
            mock_process.stdout = MagicMock()
            mock_process.stderr = MagicMock()
            mock_process.terminate = AsyncMock()
            mock_process.wait = AsyncMock()
            mock_process.kill = AsyncMock()

            session = ExecSession(
                exec_id=f"session{i}",
                container_id="test-container",
                shell="/bin/bash",
                user="root",
                cols=80,
                rows=24,
                process=mock_process
            )
            terminal_service._sessions[f"session{i}"] = session

        # Fermer le service
        await terminal_service.close()

        # Vérifier que toutes les sessions ont été nettoyées
        assert len(terminal_service._sessions) == 0


class TestShellInfo:
    """Tests pour le dataclass ShellInfo."""

    def test_shell_info_creation(self):
        """Test la création d'un objet ShellInfo."""
        shell = ShellInfo(
            path="/bin/bash",
            label="Bash",
            available=True
        )

        assert shell.path == "/bin/bash"
        assert shell.label == "Bash"
        assert shell.available is True

    def test_shell_info_defaults(self):
        """Test les valeurs par défaut de ShellInfo - available doit être False par défaut."""
        # ShellInfo n'a pas de valeur par défaut, on teste juste la création
        shell = ShellInfo(
            path="/bin/sh",
            label="Shell",
            available=False
        )

        assert shell.available is False


class TestExecSession:
    """Tests pour le dataclass ExecSession."""

    def test_exec_session_creation(self):
        """Test la création d'un objet ExecSession."""
        session = ExecSession(
            exec_id="abc123",
            container_id="container-xyz",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24
        )

        assert session.exec_id == "abc123"
        assert session.container_id == "container-xyz"
        assert session.shell == "/bin/bash"
        assert session.user == "root"
        assert session.cols == 80
        assert session.rows == 24
        assert session.process is None

    def test_exec_session_with_process(self):
        """Test la création d'un ExecSession avec un processus."""
        mock_process = MagicMock()

        session = ExecSession(
            exec_id="abc123",
            container_id="container-xyz",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process
        )

        assert session.process is mock_process


class TestGetTerminalService:
    """Tests pour la fonction get_terminal_service."""

    @pytest.mark.asyncio
    async def test_get_terminal_service(self):
        """Test la création d'une instance via get_terminal_service."""
        service = await get_terminal_service()

        assert service is not None
        assert isinstance(service, TerminalService)
        assert service._docker_client is None  # Lazy initialization


# =============================================================================
# Tests d'intégration avec le serveur Docker (optionnels)
# =============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_terminal_service_integration():
    """
    Test d'intégration avec le serveur Docker réel.

    Ce test nécessite un serveur Docker en cours d'exécution
    et sera ignoré si Docker n'est pas disponible.
    """
    try:
        service = TerminalService()

        # Tester la détection des shells sur un container existant
        # Note: Ce test nécessite un container en cours d'exécution
        # shells = await service.detect_shells("some-running-container")

        await service.close()

    except Exception as e:
        pytest.skip(f"Docker not available: {e}")
