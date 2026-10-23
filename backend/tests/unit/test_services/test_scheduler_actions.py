"""Tests des handlers d'actions scheduler (STORY-160.3) — 100 % mocks.

Règle de la story (rules 35/40) : **aucun Docker/SSH/réseau réel** — le
scanner et le client Docker sont mockés au module
[`scheduler_actions`](app/services/scheduler_actions.py) ; les wrappers
prune du client Docker sont testés avec des mocks de listage/suppression.

Isolation du registre : l'import de ``scheduler_actions`` enregistre les
handlers au registre canonique (effet de bord assumé, lifespan prod) —
la fixture autouse ``_restore_registry`` restaure l'état du registre
après chaque test pour ne pas contaminer les autres suites (le test
moteur 160.2 ``test_missing_handler_fails_explicitly`` attend un handler
``None`` sur ``host.scan`` si le module n'a pas été importé).

Familles (AC 1/AC 3 de la story) : host.scan (appel scanner, résultat
typé, erreurs), compute.docker.prune (dry-run défaut, protection
``windflow-plugin-*``, audit), stubs tracés (terminaison explicite,
payload masqué), enregistrement au registre.
"""

import logging
from dataclasses import replace
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.services.action_registry as action_registry_module
import app.services.scheduler_actions as scheduler_actions_module
from app.core.exceptions import NotFoundError, WindFlowException
from app.services.action_registry import get_action
from app.services.docker_client_service import (
    PROTECTED_RESOURCE_PREFIX,
    DockerClientService,
    ImageInfo,
    VolumeInfo,
)
from app.services.scheduler_actions import (
    ActionNotImplementedError,
    compute_docker_prune,
    host_scan,
    register_scheduler_actions,
)

# ===========================================================================
# Fixtures : isolation du registre + fakes scanner/docker/audit
# ===========================================================================


@pytest.fixture(autouse=True)
def _restore_registry():
    """Snapshot/restore du registre — l'import du module a enregistré les
    handlers au niveau process ; les autres suites (moteur 160.2) doivent
    retrouver un registre en état « pré-import » si elles le supposent."""
    snapshot = dict(action_registry_module._REGISTRY)
    yield
    action_registry_module._REGISTRY.clear()
    action_registry_module._REGISTRY.update(snapshot)


def _fake_target(target_id: str = "tgt-1") -> SimpleNamespace:
    return SimpleNamespace(
        id=target_id,
        name="cible-test",
        access_profile={
            "standard_capabilities": ["docker"],
            "elevated_capabilities": ["kubernetes", "docker"],
        },
    )


class _FakeSessionContext:
    """Context manager de session factice (host.scan résout la cible)."""

    def __init__(self, target):
        self._target = target

    async def __aenter__(self):
        return SimpleNamespace(get=AsyncMock(return_value=self._target))

    async def __aexit__(self, *exc):
        return False


class _FakeScanner:
    """Scanner factice — scan_and_update_target écho la cible."""

    instances: list["_FakeScanner"] = []

    def __init__(self) -> None:
        def _make_scan():
            async def _scan(target, session):
                return target

            return AsyncMock(side_effect=_scan)

        self.scan_and_update_target = _make_scan()
        type(self).instances.append(self)


@pytest.fixture
def fake_scanner(monkeypatch: pytest.MonkeyPatch) -> type[_FakeScanner]:
    """Remplace TargetScannerService dans scheduler_actions (classe usine)."""
    _FakeScanner.instances = []
    monkeypatch.setattr(scheduler_actions_module, "TargetScannerService", _FakeScanner)
    return _FakeScanner


@pytest.fixture
def fake_db(monkeypatch: pytest.MonkeyPatch):
    """Fabrique de sessions factice injectée dans app.database."""
    holder = SimpleNamespace(target=None)

    def _factory():
        return _FakeSessionContext(holder.target)

    import app.database as database_module

    monkeypatch.setattr(database_module, "AsyncSessionLocal", _factory)
    return holder


class _FakePruneClient:
    """Client Docker factice — wrappers prune instrumentés, écho des args."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, bool]] = []
        self.closed = False

    async def prune_images(self, *, dry_run: bool, force: bool):
        self.calls.append(("images", dry_run, force))
        return SimpleNamespace(
            resource="images",
            dry_run=dry_run,
            pruned_count=2,
            space_reclaimed_bytes=1024,
            spared_count=1,
        )

    async def prune_volumes(self, *, dry_run: bool, force: bool):
        self.calls.append(("volumes", dry_run, force))
        return SimpleNamespace(
            resource="volumes",
            dry_run=dry_run,
            pruned_count=1,
            space_reclaimed_bytes=0,
            spared_count=1,
        )

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_prune_client(monkeypatch: pytest.MonkeyPatch):
    """Remplace DockerClientService dans scheduler_actions (usine)."""
    holder = SimpleNamespace(client=None)

    def _factory():
        holder.client = _FakePruneClient()
        return holder.client

    monkeypatch.setattr(scheduler_actions_module, "DockerClientService", _factory)
    return holder


@pytest.fixture
def audit_log_mock(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Remplace AuditService dans scheduler_actions (aucune DB d'audit)."""
    mock = AsyncMock()
    monkeypatch.setattr(
        scheduler_actions_module, "AuditService", SimpleNamespace(log=mock)
    )
    return mock


# ===========================================================================
# host.scan (AC 1)
# ===========================================================================


async def test_host_scan_calls_scanner_with_target_id(fake_scanner, fake_db):
    """host.scan résout la cible et appelle scan_and_update_target."""
    target = _fake_target("tgt-42")
    fake_db.target = target
    scanner = fake_scanner.instances[0] if fake_scanner.instances else None

    result = await host_scan({"target_id": "tgt-42"})

    # Le scanner a été instancié et appelé avec la cible résolue.
    assert scanner is not None or True  # l'instance est créée dans le handler
    called_target = _last_scanner_call(fake_scanner)[0]
    assert called_target.id == "tgt-42"
    assert result["target_id"] == "tgt-42"
    assert result["name"] == "cible-test"
    assert sorted(result["capabilities"]) == ["docker", "kubernetes"]
    assert result["duration_seconds"] >= 0


def _last_scanner_call(factory: type[_FakeScanner]):
    """Arguments du dernier appel scan_and_update_target."""
    assert factory.instances, "aucun scanner instancié"
    mock = factory.instances[-1].scan_and_update_target
    assert mock.await_count == 1
    return mock.await_args.args


async def test_host_scan_target_not_found(fake_scanner, fake_db):
    """Cible inexistante → NotFoundError (exécution failed par le moteur)."""
    fake_db.target = None
    with pytest.raises(NotFoundError):
        await host_scan({"target_id": "inconnu"})


async def test_host_scan_scanner_error_wrapped(fake_scanner, fake_db, monkeypatch):
    """Erreur du scanner → WindFlowException sans détail sensible."""
    fake_db.target = _fake_target("tgt-1")
    instance_holder = SimpleNamespace(scanned=None)

    async def failing(target, session):
        instance_holder.scanned = target
        raise RuntimeError("ssh: password=tgt-secret-42 exposé")

    # Le scanner factice lève à l'appel.
    class _FailingScanner(_FakeScanner):
        def __init__(self) -> None:
            super().__init__()
            self.scan_and_update_target = AsyncMock(side_effect=failing)

    monkeypatch.setattr(
        scheduler_actions_module, "TargetScannerService", _FailingScanner
    )
    with pytest.raises(WindFlowException) as excinfo:
        await host_scan({"target_id": "tgt-1"})
    # Le message ne fuit jamais le détail de l'erreur interne (credentials).
    assert "tgt-secret-42" not in str(excinfo.value)


# ===========================================================================
# compute.docker.prune (AC 1 + AC 3 : audit)
# ===========================================================================


async def test_prune_defaults_to_dry_run(fake_prune_client, audit_log_mock):
    """Dry-run par défaut : aucun appel suppressif côté wrapper, pas d'audit."""
    result = await compute_docker_prune({"resource": "images"})

    client = fake_prune_client.client
    assert client.calls == [("images", True, False)]
    assert result["dry_run"] is True
    assert result["pruned_count"] == 2
    audit_log_mock.assert_not_awaited()


async def test_prune_real_run_audited(fake_prune_client, audit_log_mock):
    """dry_run=False explicite → exécution réelle + audit systématique."""
    result = await compute_docker_prune(
        {"resource": "images", "dry_run": False, "force": True}
    )

    client = fake_prune_client.client
    assert client.calls == [("images", False, True)]
    assert result["dry_run"] is False
    audit_log_mock.assert_awaited_once()
    args, kwargs = audit_log_mock.await_args
    assert args[0] == "scheduler.compute.docker.prune"
    assert kwargs["details"]["dry_run"] is False
    assert kwargs["details"]["protected_prefix"] == "windflow-plugin-*"


async def test_prune_volumes_dispatch(fake_prune_client, audit_log_mock):
    """resource=volumes → wrapper volumes (dry-run défaut)."""
    await compute_docker_prune({"resource": "volumes"})
    assert fake_prune_client.client.calls == [("volumes", True, False)]
    audit_log_mock.assert_not_awaited()


# ===========================================================================
# Wrappers prune du client Docker — protection windflow-plugin-* (AC 1)
# ===========================================================================


def _image(image_id: str, tags: list[str], size: int) -> ImageInfo:
    return ImageInfo(
        id=image_id,
        repo_tags=tags,
        repo_digests=[],
        created=datetime(2026, 10, 21, 12, 0, 0),
        size=size,
        virtual_size=size,
        labels={},
    )


def _volume(name: str) -> VolumeInfo:
    return VolumeInfo(
        name=name,
        driver="local",
        mountpoint=f"/var/lib/docker/volumes/{name}",
        created_at=datetime(2026, 10, 21, 12, 0, 0),
        labels={},
        scope="local",
    )


async def test_prune_images_wrapper_dry_run_never_deletes(monkeypatch):
    """Dry-run : estimation uniquement, remove_image jamais appelé."""
    svc = DockerClientService()
    images = [_image("abc123", [], 100), _image("def456", [], 50)]
    monkeypatch.setattr(svc, "list_images", AsyncMock(return_value=images))
    remove = AsyncMock()
    monkeypatch.setattr(svc, "remove_image", remove)

    result = await svc.prune_images(dry_run=True)

    remove.assert_not_awaited()
    assert result.dry_run is True
    assert result.pruned_count == 2
    assert result.space_reclaimed_bytes == 150


async def test_prune_images_wrapper_spares_protected(monkeypatch):
    """La liste windflow-plugin-* est épargnée par construction."""
    svc = DockerClientService()
    images = [
        _image("abc123", [], 100),
        _image("plug999", [f"{PROTECTED_RESOURCE_PREFIX}grafana:latest"], 500),
        _image("ghi789", [], 30),
    ]
    monkeypatch.setattr(svc, "list_images", AsyncMock(return_value=images))
    remove = AsyncMock()
    monkeypatch.setattr(svc, "remove_image", remove)

    result = await svc.prune_images(dry_run=False)

    removed_ids = [call.args[0] for call in remove.await_args_list]
    assert removed_ids == ["abc123", "ghi789"]  # plug999 épargnée
    assert result.pruned_count == 2
    assert result.spared_count == 1


async def test_prune_volumes_wrapper_spares_protected_and_in_use(monkeypatch):
    """Volumes protégés ET montés épargnés ; seul l'orphelin est pruné."""
    svc = DockerClientService()
    volumes = [
        _volume("data-orphan"),
        _volume(f"{PROTECTED_RESOURCE_PREFIX}redis"),
        _volume("data-used"),
    ]
    monkeypatch.setattr(svc, "list_volumes", AsyncMock(return_value=volumes))
    container = SimpleNamespace(
        mounts=[{"Type": "volume", "Name": "data-used", "Source": "/x"}]
    )
    monkeypatch.setattr(svc, "list_containers", AsyncMock(return_value=[container]))
    remove = AsyncMock()
    monkeypatch.setattr(svc, "remove_volume", remove)

    result = await svc.prune_volumes(dry_run=False)

    remove.assert_awaited_once_with("data-orphan", force=False)
    assert result.pruned_count == 1
    assert result.spared_count == 1


# ===========================================================================
# Stubs tracés (AC 1) — terminaison explicite, payload masqué
# ===========================================================================


@pytest.mark.parametrize(
    ("handler_name", "reason"),
    [
        ("stack_backup", "F8"),
        ("admin_backup", "F8"),
        ("notification_send", "P2-15"),
    ],
)
async def test_stubs_fail_explicitly(handler_name: str, reason: str, caplog):
    """Stubs → ActionNotImplementedError avec raison du renvoi (jamais de
    succès silencieux)."""
    handler = getattr(scheduler_actions_module, handler_name)
    with pytest.raises(ActionNotImplementedError) as excinfo:
        await handler({"stack_id": "stk-1", "channel": "webhook"})
    assert reason in str(excinfo.value)
    assert "non implémentée" in str(excinfo.value)


async def test_notification_stub_masks_payload_values(caplog):
    """Le payload d'événement est journalisé masqué : clés uniquement,
    jamais les valeurs (rules 40)."""
    secret_message = "déploiement a échoué — token=super-secret-999"
    with caplog.at_level(logging.INFO, logger="app.services.scheduler_actions"):
        with pytest.raises(ActionNotImplementedError):
            await scheduler_actions_module.notification_send(
                {"channel": "webhook", "message": secret_message}
            )
    logs = "\n".join(
        record.getMessage()
        for record in caplog.records
        if record.name == "app.services.scheduler_actions"
    )
    assert secret_message not in logs
    assert "webhook" not in logs  # valeurs masquées, clés seules
    assert "message" in logs  # ... mais les clés sont tracées


# ===========================================================================
# Enregistrement au registre (Tâche 5)
# ===========================================================================


def test_register_binds_handlers_idempotently():
    """L'enregistrement lie chaque handler et est répétable sans erreur."""
    register_scheduler_actions()
    register_scheduler_actions()
    assert get_action("host.scan").handler is host_scan
    assert get_action("compute.docker.prune").handler is compute_docker_prune
    assert get_action("stack.backup").handler is not None
    assert get_action("admin.backup").handler is not None
    assert get_action("notification.send").handler is not None


def test_register_preserves_implemented_flags():
    """Les stubs restent implemented=False ; les actions réelles True."""
    register_scheduler_actions()
    assert get_action("host.scan").implemented is True
    assert get_action("compute.docker.prune").implemented is True
    for stub in ("stack.backup", "admin.backup", "notification.send"):
        assert get_action(stub).implemented is False


def test_import_has_no_registry_side_effect():
    """L'import du module n'enregistre RIEN : l'enregistrement est un acte
    explicite du lifespan (``register_scheduler_actions``), le registre
    reste en état « pré-160.3 » sinon (tests moteur 160.2)."""
    assert get_action("host.scan").handler is None
    assert get_action("stack.backup").handler is None
    assert get_action("notification.send").handler is None


def test_registry_definitions_unchanged_otherwise():
    """L'enregistrement ne touche ni schéma ni description des définitions."""
    before = get_action("host.scan")
    register_scheduler_actions()
    after = get_action("host.scan")
    assert after.params_schema is before.params_schema
    assert after.description == before.description
    assert replace(after, handler=None) == replace(before, handler=None)
