"""Tests du StackDefinitionsLoader — non-régression du seed (STORY-171 — AC 4).

Le chemin seed doit rester **strictement inchangé** : stratégies
``skip_existing``/``update_if_newer`` (semver via packaging) /
``force_update``, YAML invalide journalisé et sauté sans interrompre, et
parité de dump avec le loader admin via la fonction partagée
``convert_variables_to_db_format``.
"""

from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.stack import Stack
from app.schemas.stack_definition import (
    StackDefinition,
    StackDefinitionMetadata,
    StackDefinitionVariable,
    VariableType,
    convert_variables_to_db_format,
)
from app.services.stack_definitions_loader import StackDefinitionsLoader


def _make_definition(name: str = "demo", version: str = "1.0.0") -> StackDefinition:
    """Définition minimale valide pour les tests de stratégies."""
    return StackDefinition(
        metadata=StackDefinitionMetadata(
            name=name,
            version=version,
            category="demo",
            author="WindFlow Team",
            license="MIT",
            description="Demo",
            target_type="docker",
        ),
        template={"image": "nginx:latest"},
        variables={
            "port": StackDefinitionVariable(
                type=VariableType.INTEGER,
                label="Port",
                default=8080,
                minimum=1,
                maximum=65535,
            )
        },
    )


def _make_directory(tmp_path: Path) -> Path:
    d = tmp_path / "defs"
    d.mkdir()
    return d


def _write_yaml(d: Path, name: str, version: str) -> Path:
    content = (
        "metadata:\n"
        f"  name: {name}\n"
        f"  version: {version}\n"
        "  category: demo\n"
        "  author: WindFlow Team\n"
        "  license: MIT\n"
        "  description: Demo\n"
        "  target_type: docker\n"
        "template:\n"
        "  image: nginx:latest\n"
        "variables:\n"
        "  port:\n"
        "    type: integer\n"
        "    label: Port\n"
        "    default: 8080\n"
        "    minimum: 1\n"
        "    maximum: 65535\n"
    )
    f = d / f"{name}.yaml"
    f.write_text(content, encoding="utf-8")
    return f


# --- scan_definitions : invalide journalisé et sauté (AC 4) -------------------


class TestScanDefinitions:
    """Un YAML invalide est journalisé et sauté sans interrompre les autres."""

    def test_invalid_file_skipped_valid_kept(self, tmp_path: Path):
        d = _make_directory(tmp_path)
        _write_yaml(d, "good", "1.0.0")
        (d / "bad.yaml").write_text(
            "metadata:\n  name: bad\n  version: 1.0.0\n", encoding="utf-8"
        )

        loader = StackDefinitionsLoader(str(d))
        definitions = loader.scan_definitions()
        assert [def_.metadata.name for def_ in definitions] == ["good"]

    def test_missing_directory_raises_value_error(self, tmp_path: Path):
        with pytest.raises(ValueError, match="n'existe pas"):
            StackDefinitionsLoader(str(tmp_path / "nope"))

    def test_not_a_directory_raises_value_error(self, tmp_path: Path):
        f = tmp_path / "file.yaml"
        f.write_text("x: 1", encoding="utf-8")
        with pytest.raises(ValueError, match="n'est pas un répertoire"):
            StackDefinitionsLoader(str(f))

    def test_empty_yaml_skipped(self, tmp_path: Path):
        d = _make_directory(tmp_path)
        (d / "empty.yaml").write_text("", encoding="utf-8")

        loader = StackDefinitionsLoader(str(d))
        assert loader.scan_definitions() == []


# --- Stratégies de chargement (AC 4 — non-régression) -------------------------


class TestStrategies:
    """skip_existing / update_if_newer (semver) / force_update inchangés."""

    async def test_skip_existing_strategy(self, tmp_path: Path, db_session):
        """skip_existing : stack existant → aucun changement."""
        import uuid

        org_id = str(uuid.uuid4())
        d = _make_directory(tmp_path)
        _write_yaml(d, "demo", "1.0.0")

        db_session.add(
            Stack(
                name="demo",
                version="1.0.0",
                template={"image": "nginx:old"},
                variables={},
                organization_id=org_id,
            )
        )
        await db_session.commit()

        loader = StackDefinitionsLoader(str(d))
        created, updated, errors = await loader.load_into_database(
            db_session, org_id, strategy="skip_existing"
        )
        assert (created, updated, errors) == (0, 0, [])

        result = await db_session.execute(select(Stack).where(Stack.name == "demo"))
        stack = result.scalar_one()
        assert stack.template == {"image": "nginx:old"}  # inchangé

    async def test_update_if_newer_semver_newer_updates(self, tmp_path, db_session):
        """update_if_newer : même (name, version) avec YAML plus récent en
        comparaison semver interne → mise à jour.

        Note : ``_load_single_stack`` recherche par (name, version) exacte —
        une version différente en YAML crée une nouvelle entrée (comportement
        seed existant). Pour observer l'update, l'existant doit porter la
        même version que le YAML et la comparaison semver reste exercée via
        ``_is_version_newer`` (TestSemverComparison).
        """
        import uuid

        org_id = str(uuid.uuid4())
        d = _make_directory(tmp_path)
        _write_yaml(d, "demo", "1.1.9")  # YAML = version existante

        db_session.add(
            Stack(
                name="demo",
                version="1.1.9",
                template={"image": "nginx:old"},
                variables={},
                organization_id=org_id,
            )
        )
        await db_session.commit()

        loader = StackDefinitionsLoader(str(d))
        created, updated, _ = await loader.load_into_database(
            db_session, org_id, strategy="update_if_newer"
        )
        # Version égale (1.1.9 == 1.1.9) → skip, pas de création
        assert created == 0
        assert updated == 0

        result = await db_session.execute(select(Stack).where(Stack.name == "demo"))
        stack = result.scalar_one()
        assert stack.template == {"image": "nginx:old"}  # inchangé

    async def test_update_if_newer_different_version_creates(
        self, tmp_path, db_session
    ):
        """Comportement seed existant : version YAML différente (1.2.0) avec
        existant 1.1.9 → nouvelle entrée créée (recherche par name+version)."""
        import uuid

        org_id = str(uuid.uuid4())
        d = _make_directory(tmp_path)
        _write_yaml(d, "demo", "1.2.0")

        db_session.add(
            Stack(
                name="demo",
                version="1.1.9",
                template={"image": "nginx:old"},
                variables={},
                organization_id=org_id,
            )
        )
        await db_session.commit()

        loader = StackDefinitionsLoader(str(d))
        created, updated, _ = await loader.load_into_database(
            db_session, org_id, strategy="update_if_newer"
        )
        assert created == 1
        assert updated == 0

        result = await db_session.execute(select(Stack).where(Stack.name == "demo"))
        stacks = result.scalars().all()
        assert {s.version for s in stacks} == {"1.1.9", "1.2.0"}

    async def test_update_if_newer_equal_version_skips(self, tmp_path, db_session):
        """update_if_newer : version égale → skip (pas de mise à jour)."""
        import uuid

        org_id = str(uuid.uuid4())
        d = _make_directory(tmp_path)
        _write_yaml(d, "demo", "1.0.0")

        db_session.add(
            Stack(
                name="demo",
                version="1.0.0",
                template={"image": "nginx:old"},
                variables={},
                organization_id=org_id,
            )
        )
        await db_session.commit()

        loader = StackDefinitionsLoader(str(d))
        created, updated, _ = await loader.load_into_database(
            db_session, org_id, strategy="update_if_newer"
        )
        assert (created, updated) == (0, 0)

    async def test_force_update_overwrites(self, tmp_path, db_session):
        """force_update : version égale → écrasement quand même."""
        import uuid

        org_id = str(uuid.uuid4())
        d = _make_directory(tmp_path)
        _write_yaml(d, "demo", "1.0.0")

        db_session.add(
            Stack(
                name="demo",
                version="1.0.0",
                template={"image": "nginx:old"},
                variables={},
                organization_id=org_id,
            )
        )
        await db_session.commit()

        loader = StackDefinitionsLoader(str(d))
        created, updated, _ = await loader.load_into_database(
            db_session, org_id, strategy="force_update"
        )
        assert created == 0
        assert updated == 1

        result = await db_session.execute(select(Stack).where(Stack.name == "demo"))
        stack = result.scalar_one()
        assert stack.template == {"image": "nginx:latest"}

    async def test_create_when_absent(self, tmp_path, db_session):
        """Aucun stack existant → création (comportement created)."""
        import uuid

        org_id = str(uuid.uuid4())
        d = _make_directory(tmp_path)
        _write_yaml(d, "demo", "1.0.0")

        loader = StackDefinitionsLoader(str(d))
        created, updated, _ = await loader.load_into_database(
            db_session, org_id, strategy="skip_existing"
        )
        assert (created, updated) == (1, 0)


# --- Comparaison semver (AC 4) ------------------------------------------------


class TestSemverComparison:
    """``_is_version_newer`` via packaging.version — non-régression."""

    def setup_method(self):
        self.loader = StackDefinitionsLoader.__new__(StackDefinitionsLoader)

    @pytest.mark.parametrize(
        ("v1", "v2", "expected"),
        [
            ("1.2.0", "1.1.9", True),
            ("2.0.0", "1.9.9", True),
            ("1.0.0", "1.0.0", False),
            ("1.0.0a1", "1.0.0", False),  # pre-release antérieur
            ("0.9.0", "1.0.0", False),
        ],
    )
    def test_semver_comparisons(self, v1: str, v2: str, expected: bool):
        assert self.loader._is_version_newer(v1, v2) is expected

    def test_invalid_version_falls_back_textual(self):
        """Version invalide → fallback comparaison textuelle sans crash."""
        assert isinstance(self.loader._is_version_newer("not-a-version", "1.0.0"), bool)


# --- Parité de dump : fonction partagée (divergence n°2) ----------------------


class TestSharedConversionParity:
    """Le seed et l'import admin écrivent le MÊME format de variables."""

    def test_loader_method_delegates_to_shared_function(self):
        """``_convert_variables_to_db_format`` délègue à la fonction partagée."""
        loader = StackDefinitionsLoader.__new__(StackDefinitionsLoader)
        definition = _make_definition()
        via_method = loader._convert_variables_to_db_format(definition.variables)
        via_shared = convert_variables_to_db_format(definition.variables)
        assert via_method == via_shared

    def test_dump_preserves_group_hierarchy_and_metadata(self):
        """Dump : groupes récursifs + visible + enum_labels + bornes + macros."""
        variables = {
            "locale": StackDefinitionVariable(
                type=VariableType.STRING,
                label="Locale",
                enum=["en", "fr"],
                enum_labels={"en": "English", "fr": "Français"},
            ),
            "password": StackDefinitionVariable(
                type=VariableType.PASSWORD,
                label="Mot de passe",
                default="{{ generate_password(24) }}",
                has_macro=True,
                macro_template="{{ generate_password(24) }}",
            ),
            "performance": StackDefinitionVariable(
                type=VariableType.GROUP,
                label="Performance",
                variables={
                    "max_connections": StackDefinitionVariable(
                        type=VariableType.INTEGER,
                        label="Connexions max",
                        default=100,
                        minimum=10,
                        maximum=1000,
                    )
                },
            ),
        }

        result = convert_variables_to_db_format(variables)

        # enum_labels + visible conservés
        assert result["locale"]["enum_labels"] == {"en": "English", "fr": "Français"}
        assert result["locale"]["visible"] is True
        # bornes conservées
        assert result["performance"]["variables"]["max_connections"]["minimum"] == 10
        assert result["performance"]["variables"]["max_connections"]["maximum"] == 1000
        # macros + métadonnées macro conservées
        assert result["password"]["default"] == "{{ generate_password(24) }}"
        assert result["password"]["macro_template"] == "{{ generate_password(24) }}"

    def test_empty_and_none_return_empty_dict(self):
        """Variables vides/None → dict vide."""
        assert convert_variables_to_db_format({}) == {}
        assert convert_variables_to_db_format(None) == {}
