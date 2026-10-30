"""
Tests unitaires du service PluginDependencyService.

Couvre : check_install_dependencies, check_uninstall_dependents,
resolve_transitive_dependencies, detect_circular_dependencies,
validate_version_constraint.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import WindFlowException
from app.models.organization import Organization
from app.models.plugin import Plugin, PluginStatus
from app.models.user import User
from app.schemas.plugin_manifest import PluginManifest
from app.services.plugin_dependency_service import PluginDependencyService

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def service() -> PluginDependencyService:
    """Instance du service PluginDependency."""
    return PluginDependencyService()


def _make_manifest(
    name: str = "test-plugin",
    version: str = "1.0.0",
    requires: list[str] | None = None,
    optional: list[str] | None = None,
    conflicts: list[str] | None = None,
) -> PluginManifest:
    """Crée un manifest de test avec dépendances."""
    deps: dict = {}
    if requires is not None:
        deps["requires"] = requires
    if optional is not None:
        deps["optional"] = optional
    if conflicts is not None:
        deps["conflicts"] = conflicts

    return PluginManifest(
        name=name,
        version=version,
        display_name=f"Test {name}",
        description=f"Test plugin {name}",
        category="other",
        author="Test",
        license="MIT",
        type="extension",
        architectures=["linux/amd64"],
        extensions={"api_module": "api.py"},
        dependencies=deps if deps else None,
    )


async def _create_installed_plugin(
    db: AsyncSession,
    name: str,
    version: str,
    organization_id: str,
    user_id: str,
    requires: list[str] | None = None,
) -> Plugin:
    """Crée un plugin installé en base pour les tests."""
    manifest_data: dict = {
        "name": name,
        "version": version,
        "display_name": name,
        "description": f"Plugin {name}",
        "category": "other",
        "type": "extension",
        "config": [],
    }
    if requires:
        manifest_data["dependencies"] = {"requires": requires}

    plugin = Plugin(
        name=name,
        version=version,
        display_name=name,
        description=f"Plugin {name}",
        category="other",
        type="extension",
        status=PluginStatus.INSTALLED.value,
        manifest_data=manifest_data,
        config_values={},
        organization_id=organization_id,
        installed_by=user_id,
    )
    db.add(plugin)
    await db.commit()
    await db.refresh(plugin)
    return plugin


# ── TestCheckInstallDependencies ────────────────────────────────────────────


class TestCheckInstallDependencies:
    """Tests de la méthode check_install_dependencies."""

    @pytest.mark.asyncio
    async def test_all_dependencies_satisfied(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas nominal : toutes les dépendances sont installées avec version compatible."""
        # Installer la dépendance docker
        await _create_installed_plugin(
            db_session, "docker", "1.2.0", test_organization.id, test_superuser.id
        )

        manifest = _make_manifest(requires=["docker>=1.0.0"])
        result = await service.check_install_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result.can_proceed is True
        assert len(result.satisfied) == 1
        assert result.satisfied[0].name == "docker"
        assert len(result.missing) == 0
        assert len(result.version_mismatches) == 0
        assert len(result.conflicts) == 0

    @pytest.mark.asyncio
    async def test_missing_required_dependency(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        service: PluginDependencyService,
    ) -> None:
        """Cas d'erreur : dépendance requise non installée."""
        manifest = _make_manifest(requires=["docker"])
        result = await service.check_install_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result.can_proceed is False
        assert len(result.missing) == 1
        assert result.missing[0].name == "docker"

    @pytest.mark.asyncio
    async def test_version_mismatch(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas d'erreur : dépendance installée mais version incompatible."""
        await _create_installed_plugin(
            db_session, "docker", "0.9.0", test_organization.id, test_superuser.id
        )

        manifest = _make_manifest(requires=["docker>=1.0.0"])
        result = await service.check_install_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result.can_proceed is False
        assert len(result.version_mismatches) == 1
        assert result.version_mismatches[0].dependency_name == "docker"
        assert result.version_mismatches[0].required_constraint == ">=1.0.0"
        assert result.version_mismatches[0].installed_version == "0.9.0"

    @pytest.mark.asyncio
    async def test_conflict_detected(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas d'erreur : plugin en conflit déjà installé."""
        await _create_installed_plugin(
            db_session,
            "nginx-proxy-manager",
            "1.0.0",
            test_organization.id,
            test_superuser.id,
        )

        manifest = _make_manifest(conflicts=["nginx-proxy-manager"])
        result = await service.check_install_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result.can_proceed is False
        assert "nginx-proxy-manager" in result.conflicts

    @pytest.mark.asyncio
    async def test_no_dependencies(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        service: PluginDependencyService,
    ) -> None:
        """Cas nominal : manifest sans dépendances."""
        manifest = _make_manifest()
        result = await service.check_install_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result.can_proceed is True
        assert len(result.satisfied) == 0

    @pytest.mark.asyncio
    async def test_optional_dependency_missing(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        service: PluginDependencyService,
    ) -> None:
        """Cas nominal : dépendance optionnelle absente → can_proceed=True."""
        manifest = _make_manifest(optional=["cloudflare-dns"])
        result = await service.check_install_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result.can_proceed is True


# ── TestCheckUninstallDependents ────────────────────────────────────────────


class TestCheckUninstallDependents:
    """Tests de la méthode check_uninstall_dependents."""

    @pytest.mark.asyncio
    async def test_no_dependents(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas nominal : aucun plugin ne dépend du plugin ciblé."""
        await _create_installed_plugin(
            db_session, "docker", "1.0.0", test_organization.id, test_superuser.id
        )

        dependents = await service.check_uninstall_dependents(
            db_session, "docker", test_organization.id
        )

        assert dependents == []

    @pytest.mark.asyncio
    async def test_has_dependents(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas d'erreur : des plugins dépendent du plugin ciblé."""
        # Installer docker (la dépendance)
        await _create_installed_plugin(
            db_session, "docker", "1.0.0", test_organization.id, test_superuser.id
        )
        # Installer traefik qui dépend de docker
        await _create_installed_plugin(
            db_session,
            "traefik",
            "1.0.0",
            test_organization.id,
            test_superuser.id,
            requires=["docker"],
        )

        dependents = await service.check_uninstall_dependents(
            db_session, "docker", test_organization.id
        )

        assert "traefik" in dependents

    @pytest.mark.asyncio
    async def test_transitive_dependents(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas d'erreur : dépendance transitive A→B→C, tentative uninstall B."""
        # C est installé
        await _create_installed_plugin(
            db_session, "plugin-c", "1.0.0", test_organization.id, test_superuser.id
        )
        # B dépend de C
        await _create_installed_plugin(
            db_session,
            "plugin-b",
            "1.0.0",
            test_organization.id,
            test_superuser.id,
            requires=["plugin-c"],
        )
        # A dépend de B
        await _create_installed_plugin(
            db_session,
            "plugin-a",
            "1.0.0",
            test_organization.id,
            test_superuser.id,
            requires=["plugin-b"],
        )

        dependents = await service.check_uninstall_dependents(
            db_session, "plugin-b", test_organization.id
        )

        assert "plugin-a" in dependents


# ── TestResolveTransitiveDependencies ───────────────────────────────────────


class TestResolveTransitiveDependencies:
    """Tests de la méthode resolve_transitive_dependencies."""

    @pytest.mark.asyncio
    async def test_resolve_missing_not_found(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        service: PluginDependencyService,
    ) -> None:
        """Cas d'erreur : dépendance introuvable → WindFlowException."""
        manifest = _make_manifest(requires=["nonexistent-plugin"])

        with pytest.raises(WindFlowException, match="introuvables"):
            await service.resolve_transitive_dependencies(
                db_session, manifest, test_organization.id
            )

    @pytest.mark.asyncio
    async def test_resolve_no_missing(
        self,
        db_session: AsyncSession,
        test_organization: Organization,
        test_superuser: User,
        service: PluginDependencyService,
    ) -> None:
        """Cas nominal : pas de dépendances manquantes."""
        await _create_installed_plugin(
            db_session, "docker", "1.0.0", test_organization.id, test_superuser.id
        )

        manifest = _make_manifest(requires=["docker"])
        result = await service.resolve_transitive_dependencies(
            db_session, manifest, test_organization.id
        )

        assert result == []


# ── TestDetectCircularDependencies ──────────────────────────────────────────


class TestDetectCircularDependencies:
    """Tests de la méthode detect_circular_dependencies."""

    def test_no_cycle(self, service: PluginDependencyService) -> None:
        """Cas nominal : graphe acyclique → liste vide."""
        manifests = [
            _make_manifest(name="a", requires=["b"]),
            _make_manifest(name="b"),
        ]
        cycles = service.detect_circular_dependencies(manifests)
        assert cycles == []

    def test_simple_cycle(self, service: PluginDependencyService) -> None:
        """Cas d'erreur : A→B→A → cycle détecté."""
        manifests = [
            _make_manifest(name="a", requires=["b"]),
            _make_manifest(name="b", requires=["a"]),
        ]
        cycles = service.detect_circular_dependencies(manifests)
        assert len(cycles) > 0
        # Vérifier que le cycle contient a et b
        cycle_names = set()
        for cycle in cycles:
            cycle_names.update(cycle)
        assert "a" in cycle_names
        assert "b" in cycle_names

    def test_three_node_cycle(self, service: PluginDependencyService) -> None:
        """Cas d'erreur : A→B→C→A → cycle détecté."""
        manifests = [
            _make_manifest(name="a", requires=["b"]),
            _make_manifest(name="b", requires=["c"]),
            _make_manifest(name="c", requires=["a"]),
        ]
        cycles = service.detect_circular_dependencies(manifests)
        assert len(cycles) > 0
        cycle_names = set()
        for cycle in cycles:
            cycle_names.update(cycle)
        assert "a" in cycle_names
        assert "b" in cycle_names
        assert "c" in cycle_names


# ── TestValidateVersionConstraint ───────────────────────────────────────────


class TestValidateVersionConstraint:
    """Tests de la méthode validate_version_constraint."""

    def test_gte_constraint_satisfied(self, service: PluginDependencyService) -> None:
        """``"1.2.0"`` >= ``"1.0.0"`` → True."""
        assert service.validate_version_constraint("1.2.0", ">=1.0.0") is True

    def test_gte_constraint_not_satisfied(
        self, service: PluginDependencyService
    ) -> None:
        """``"0.9.0"`` >= ``"1.0.0"`` → False."""
        assert service.validate_version_constraint("0.9.0", ">=1.0.0") is False

    def test_eq_constraint(self, service: PluginDependencyService) -> None:
        """``"1.0.0"`` == ``"1.0.0"`` → True."""
        assert service.validate_version_constraint("1.0.0", "==1.0.0") is True

    def test_eq_constraint_not_satisfied(
        self, service: PluginDependencyService
    ) -> None:
        """``"1.1.0"`` == ``"1.0.0"`` → False."""
        assert service.validate_version_constraint("1.1.0", "==1.0.0") is False

    def test_tilde_constraint(self, service: PluginDependencyService) -> None:
        """``"1.1.5"`` ~= ``"1.1.0"`` → True (>=1.1.0, <1.2.0)."""
        assert service.validate_version_constraint("1.1.5", "~=1.1.0") is True

    def test_tilde_constraint_not_satisfied(
        self, service: PluginDependencyService
    ) -> None:
        """``"1.2.0"`` ~= ``"1.1.0"`` → False (>=1.1.0, <1.2.0)."""
        assert service.validate_version_constraint("1.2.0", "~=1.1.0") is False

    def test_lt_constraint(self, service: PluginDependencyService) -> None:
        """``"0.5.0"`` < ``"1.0.0"`` → True."""
        assert service.validate_version_constraint("0.5.0", "<1.0.0") is True

    def test_ne_constraint(self, service: PluginDependencyService) -> None:
        """``"2.0.0"`` != ``"1.0.0"`` → True."""
        assert service.validate_version_constraint("2.0.0", "!=1.0.0") is True

    def test_invalid_constraint_format(self, service: PluginDependencyService) -> None:
        """Format invalide → False."""
        assert service.validate_version_constraint("1.0.0", "bad") is False
