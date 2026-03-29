"""
Tests unitaires pour le TerminalService.

Ces tests vérifient les fonctionnalités du service de terminal interactif
pour les conteneurs Docker, utilisant un pseudo-terminal (PTY).
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.terminal_service import (
    ExecSession,
    ShellInfo,
    TerminalService,
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
        """Test la création d'une session terminal avec succès (PTY)."""
        # Mock container
        mock_container = MagicMock()
        mock_container.state = {"Status": "running"}
        mock_docker_client.get_container.return_value = mock_container

        # Mock PTY et subprocess
        mock_process = MagicMock()
        mock_process.returncode = None

        fake_master_fd = 42
        fake_slave_fd = 43

        with patch(
            "app.services.terminal_service.pty.openpty",
            return_value=(fake_master_fd, fake_slave_fd),
        ), patch("app.services.terminal_service.fcntl.ioctl"), patch(
            "app.services.terminal_service.os.close"
        ) as mock_os_close, patch(
            "app.services.terminal_service.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_process,
        ):

            session = await terminal_service.create_session(
                container_id="test-container",
                shell="/bin/bash",
                user="root",
                cols=80,
                rows=24,
            )

            assert session is not None
            assert session.container_id == "test-container"
            assert session.shell == "/bin/bash"
            assert session.user == "root"
            assert session.cols == 80
            assert session.rows == 24
            assert session.exec_id is not None
            assert len(session.exec_id) == 8
            assert session.master_fd == fake_master_fd
            assert session.process is mock_process

            # Le slave fd doit être fermé côté parent
            mock_os_close.assert_called_once_with(fake_slave_fd)

    @pytest.mark.asyncio
    async def test_create_session_container_not_running(
        self, terminal_service, mock_docker_client
    ):
        """Test la création d'une session quand le container n'est pas en cours d'exécution."""
        mock_container = MagicMock()
        mock_container.state = {"Status": "stopped"}
        mock_docker_client.get_container.return_value = mock_container

        with pytest.raises(ValueError, match="not running"):
            await terminal_service.create_session(
                container_id="test-container", shell="/bin/bash"
            )

    @pytest.mark.asyncio
    async def test_create_session_container_not_found(
        self, terminal_service, mock_docker_client
    ):
        """Test la création d'une session quand le container n'existe pas."""
        mock_docker_client.get_container.side_effect = Exception("Container not found")

        with pytest.raises(ValueError, match="not found"):
            await terminal_service.create_session(
                container_id="nonexistent-container", shell="/bin/bash"
            )

    @pytest.mark.asyncio
    async def test_create_session_with_non_root_user(
        self, terminal_service, mock_docker_client
    ):
        """Test la création d'une session avec un utilisateur non-root."""
        mock_container = MagicMock()
        mock_container.state = {"Status": "running"}
        mock_docker_client.get_container.return_value = mock_container

        mock_process = MagicMock()
        mock_process.returncode = None

        with patch(
            "app.services.terminal_service.pty.openpty", return_value=(10, 11)
        ), patch("app.services.terminal_service.fcntl.ioctl"), patch(
            "app.services.terminal_service.os.close"
        ), patch(
            "app.services.terminal_service.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value=mock_process,
        ) as mock_exec:

            session = await terminal_service.create_session(
                container_id="test-container",
                shell="/bin/bash",
                user="appuser",
            )

            assert session.user == "appuser"

            # Vérifier que la commande contient -u appuser
            call_args = mock_exec.call_args[0]
            cmd_list = list(call_args)
            assert "-u" in cmd_list
            user_idx = cmd_list.index("-u")
            assert cmd_list[user_idx + 1] == "appuser"

    @pytest.mark.asyncio
    async def test_send_input(self, terminal_service):
        """Test l'envoi d'entrée au terminal via master PTY fd."""
        fake_master_fd = 42

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=MagicMock(),
            master_fd=fake_master_fd,
        )

        with patch("app.services.terminal_service.os.write") as mock_os_write:
            await terminal_service.send_input(session, "ls -la\n")

            mock_os_write.assert_called_once_with(fake_master_fd, b"ls -la\n")

    @pytest.mark.asyncio
    async def test_send_input_no_fd_raises(self, terminal_service):
        """Test que send_input lève une erreur si le fd est invalide."""
        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            master_fd=-1,
        )

        with pytest.raises(RuntimeError, match="Session not initialized"):
            await terminal_service.send_input(session, "test")

    @pytest.mark.asyncio
    async def test_resize_tty(self, terminal_service):
        """Test le redimensionnement du TTY via ioctl TIOCSWINSZ."""
        fake_master_fd = 42

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            master_fd=fake_master_fd,
        )

        with patch("app.services.terminal_service.fcntl.ioctl") as mock_ioctl:
            await terminal_service.resize_tty(session, 120, 40)

            assert session.cols == 120
            assert session.rows == 40
            mock_ioctl.assert_called_once()
            # Vérifier que le fd est correct
            assert mock_ioctl.call_args[0][0] == fake_master_fd

    @pytest.mark.asyncio
    async def test_resize_tty_no_fd_raises(self, terminal_service):
        """Test que resize_tty lève une erreur si le fd est invalide."""
        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            master_fd=-1,
        )

        with pytest.raises(RuntimeError, match="Session not initialized"):
            await terminal_service.resize_tty(session, 120, 40)

    @pytest.mark.asyncio
    async def test_cleanup_session(self, terminal_service):
        """Test le nettoyage d'une session (processus + PTY fd)."""
        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()
        mock_process.kill = AsyncMock()

        fake_master_fd = 42

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process,
            master_fd=fake_master_fd,
        )

        # Ajouter la session au service
        terminal_service._sessions["test123"] = session

        with patch("app.services.terminal_service.os.close") as mock_os_close:
            await terminal_service.cleanup_session(session)

            assert "test123" not in terminal_service._sessions
            mock_process.terminate.assert_called_once()
            mock_os_close.assert_called_once_with(fake_master_fd)
            assert session.master_fd == -1

    @pytest.mark.asyncio
    async def test_cleanup_session_process_already_terminated(self, terminal_service):
        """Test le nettoyage quand le processus est déjà terminé."""
        mock_process = MagicMock()
        mock_process.returncode = 0  # Déjà terminé
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock()

        session = ExecSession(
            exec_id="test456",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process,
            master_fd=50,
        )

        terminal_service._sessions["test456"] = session

        with patch("app.services.terminal_service.os.close"):
            await terminal_service.cleanup_session(session)

            # terminate ne doit PAS être appelé si returncode n'est pas None
            mock_process.terminate.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_session_force_kill_on_timeout(self, terminal_service):
        """Test le kill forcé si le processus ne s'arrête pas dans le timeout."""
        import asyncio

        mock_process = MagicMock()
        mock_process.returncode = None
        mock_process.terminate = MagicMock()
        mock_process.wait = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_process.kill = MagicMock()

        session = ExecSession(
            exec_id="test789",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process,
            master_fd=60,
        )

        terminal_service._sessions["test789"] = session

        with patch("app.services.terminal_service.os.close"):
            await terminal_service.cleanup_session(session)

            mock_process.terminate.assert_called_once()
            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_shells(self, terminal_service, mock_docker_client):
        """Test la détection des shells disponibles."""
        # Mock exec_in_container pour retourner différents résultats
        mock_docker_client.exec_in_container = AsyncMock(
            side_effect=[
                MagicMock(exit_code=0),  # /bin/bash existe
                MagicMock(exit_code=1),  # /bin/zsh n'existe pas
                MagicMock(exit_code=0),  # /bin/sh existe
                MagicMock(exit_code=0),  # /bin/ash existe
                MagicMock(exit_code=1),  # /bin/dash n'existe pas
                MagicMock(exit_code=1),  # /bin/ksh n'existe pas
            ]
        )

        shells = await terminal_service.detect_shells("test-container")

        assert len(shells) == 6  # Tous les shells définis
        assert shells[0].path == "/bin/bash"
        assert shells[0].available is True
        assert shells[1].path == "/bin/zsh"
        assert shells[1].available is False
        assert shells[2].path == "/bin/sh"
        assert shells[2].available is True

    @pytest.mark.asyncio
    async def test_detect_shells_exception_marks_unavailable(
        self, terminal_service, mock_docker_client
    ):
        """Test que les exceptions lors de la détection marquent le shell comme indisponible."""
        mock_docker_client.exec_in_container = AsyncMock(
            side_effect=Exception("Connection error")
        )

        shells = await terminal_service.detect_shells("test-container")

        assert len(shells) == 6
        assert all(not s.available for s in shells)

    @pytest.mark.asyncio
    async def test_get_session(self, terminal_service):
        """Test la récupération d'une session par son ID."""
        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
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
            mock_process.returncode = 0  # Déjà terminé
            mock_process.terminate = MagicMock()
            mock_process.wait = AsyncMock()
            mock_process.kill = AsyncMock()

            session = ExecSession(
                exec_id=f"session{i}",
                container_id="test-container",
                shell="/bin/bash",
                user="root",
                cols=80,
                rows=24,
                process=mock_process,
                master_fd=100 + i,
            )
            terminal_service._sessions[f"session{i}"] = session

        with patch("app.services.terminal_service.os.close"):
            await terminal_service.close()

            # Vérifier que toutes les sessions ont été nettoyées
            assert len(terminal_service._sessions) == 0

    @pytest.mark.asyncio
    async def test_stream_output_no_process(self, terminal_service):
        """Test que stream_output ne yield rien si pas de processus."""
        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=None,
            master_fd=-1,
        )

        results = []
        async for data in terminal_service.stream_output(session):
            results.append(data)

        assert results == []

    @pytest.mark.asyncio
    async def test_stream_output_uses_nonblocking_io(self, terminal_service):
        """Test que stream_output lit les données via I/O non-bloquant (add_reader)."""
        import asyncio

        mock_process = MagicMock()
        mock_process.returncode = None

        # Utiliser un vrai pipe pour simuler le fd PTY
        read_fd, write_fd = os.pipe()

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process,
            master_fd=read_fd,
        )

        # Écrire les données de manière asynchrone pour que le stream soit prêt
        async def write_data_async():
            await asyncio.sleep(0.1)
            os.write(write_fd, b"hello world\n")
            await asyncio.sleep(0.1)
            os.close(write_fd)

        write_task = asyncio.create_task(write_data_async())

        try:
            results = []
            async for data in terminal_service.stream_output(session):
                results.append(data)
                # Marquer le processus comme terminé après la première lecture
                mock_process.returncode = 0

            await write_task

            # Vérifier que des données ont été reçues
            assert len(results) >= 1
            assert b"hello world\n" in results[0][0]
            assert results[0][1] is False
        finally:
            try:
                os.close(read_fd)
            except OSError:
                pass
            try:
                os.close(write_fd)
            except OSError:
                pass

    @pytest.mark.asyncio
    async def test_stream_output_drains_on_process_exit(self, terminal_service):
        """Test que stream_output draine les données restantes quand le processus se termine."""
        mock_process = MagicMock()
        mock_process.returncode = 0  # Processus déjà terminé

        # Utiliser un vrai pipe pour simuler le fd PTY
        read_fd, write_fd = os.pipe()

        # Écrire des données restantes puis fermer
        os.write(write_fd, b"remaining data\n")
        os.close(write_fd)

        session = ExecSession(
            exec_id="test123",
            container_id="test-container",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process,
            master_fd=read_fd,
        )

        try:
            results = []
            async for data in terminal_service.stream_output(session):
                results.append(data)

            # Doit avoir drainé les données restantes
            assert len(results) == 1
            assert results[0] == (b"remaining data\n", False)
        finally:
            try:
                os.close(read_fd)
            except OSError:
                pass


class TestShellInfo:
    """Tests pour le dataclass ShellInfo."""

    def test_shell_info_creation(self):
        """Test la création d'un objet ShellInfo."""
        shell = ShellInfo(
            path="/bin/bash",
            label="Bash",
            available=True,
        )

        assert shell.path == "/bin/bash"
        assert shell.label == "Bash"
        assert shell.available is True

    def test_shell_info_unavailable(self):
        """Test ShellInfo avec available=False."""
        shell = ShellInfo(
            path="/bin/sh",
            label="Shell",
            available=False,
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
            rows=24,
        )

        assert session.exec_id == "abc123"
        assert session.container_id == "container-xyz"
        assert session.shell == "/bin/bash"
        assert session.user == "root"
        assert session.cols == 80
        assert session.rows == 24
        assert session.process is None
        assert session.master_fd == -1

    def test_exec_session_with_process_and_fd(self):
        """Test la création d'un ExecSession avec un processus et un fd."""
        mock_process = MagicMock()

        session = ExecSession(
            exec_id="abc123",
            container_id="container-xyz",
            shell="/bin/bash",
            user="root",
            cols=80,
            rows=24,
            process=mock_process,
            master_fd=42,
        )

        assert session.process is mock_process
        assert session.master_fd == 42


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
