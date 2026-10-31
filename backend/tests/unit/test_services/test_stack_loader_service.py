"""Tests du StackLoaderService refondu (STORY-171 — AC 1/2/4).

Le service est un **consommateur du moteur unique** (schéma Pydantic strict
``StackDefinition``) : aucun test ne doit faire passer une règle propre au
service — tout vient du moteur.

Couverture :
- **Parité AC 1** : chaque YAML réel du dépôt (``stacks_definitions/*.yaml``,
  excluant ``_*``) valide sans exception et produit un ``StackCreate`` au
  format dump (groupes imbriqués, bornes, ``enum_labels``, macros brutes) ;
- **Régression du bug corrigé** : types ``integer``/``group`` acceptés
  (avant : rejetés par la validation manuelle allégée) ;
- **Cas invalides → ValidationError** : pseudo-type ``enum``, métadonnées
  incomplètes, ``enum_labels`` orphelin, ``target_type`` invalide, template
  vide, YAML mal formé ;
- **Divergence n°3 corrigée** : template **sans clé ``services``** accepté ;
- **AC 4** : ``load_all_from_directory`` saute les invalides sans interrompre,
  ignore les fichiers ``_``.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.stack import StackCreate
from app.services.stack_definitions_loader import StackDefinitionsLoader
from app.services.stack_loader_service import StackLoaderService

# Répertoire réel du dépôt (parité sur les YAML de production)
REPO_DEFINITIONS = (
    Path(__file__).parent.parent.parent.parent.parent / "stacks_definitions"
)

REPO_YAML_FILES = sorted(
    f for f in REPO_DEFINITIONS.glob("*.yaml") if not f.name.startswith("_")
)


def _valid_yaml_content() -> str:
    """YAML minimal valide aux règles du moteur strict."""
    return (
        "metadata:\n"
        "  name: demo\n"
        "  version: 1.0.0\n"
        "  category: demo\n"
        "  author: WindFlow Team\n"
        "  license: MIT\n"
        "  description: Demo stack\n"
        "  target_type: docker\n"
        "template:\n"
        "  image: nginx:latest\n"
        "variables:\n"
        "  host_port:\n"
        "    type: integer\n"
        "    label: Port\n"
        "    default: 8080\n"
        "    minimum: 1\n"
        "    maximum: 65535\n"
    )


# --- Parité AC 1 : YAML réels du dépôt ---------------------------------------


class TestRepoYamlsParity:
    """AC 1 : chaque YAML du dépôt passe le moteur (admin) ET le seed."""

    def test_repo_contains_yaml_files(self):
        """Garde-fou : le dépôt expose bien des YAML à tester (sinon parité vide)."""
        assert len(REPO_YAML_FILES) >= 2, "attendu au moins postgresql + baserow"

    @pytest.mark.parametrize("yaml_file", REPO_YAML_FILES, ids=lambda f: f.name)
    def test_load_definition_valid_on_repo_yamls(self, yaml_file: Path):
        """Chemin admin : ``load_definition`` valide sans exception (AC 1)."""
        definition = StackLoaderService.load_definition(yaml_file)
        assert definition.metadata.name
        assert definition.template

    @pytest.mark.parametrize("yaml_file", REPO_YAML_FILES, ids=lambda f: f.name)
    def test_seed_loader_validates_same_files(self, yaml_file: Path):
        """Chemin seed : ``StackDefinitionsLoader`` accepte les mêmes fichiers."""
        loader = StackDefinitionsLoader(str(REPO_DEFINITIONS))
        definition = loader._parse_yaml_file(yaml_file)
        assert definition.metadata.name

    @pytest.mark.parametrize("yaml_file", REPO_YAML_FILES, ids=lambda f: f.name)
    def test_to_stack_create_maps_target_type(self, yaml_file: Path):
        """Parité seed/import : ``target_type`` du YAML propagé (divergence n°6)."""
        definition = StackLoaderService.load_definition(yaml_file)
        stack_create = StackLoaderService.to_stack_create(definition, "org-001")
        assert isinstance(stack_create, StackCreate)
        assert stack_create.target_type == definition.metadata.target_type

    def test_postgresql_variables_dump_format(self):
        """Format dump : groupe ``performance`` imbriqué + bornes ``host_port``."""
        yaml_file = REPO_DEFINITIONS / "postgresql.yaml"
        if not yaml_file.exists():
            pytest.skip("postgresql.yaml absent de ce dépôt")

        definition = StackLoaderService.load_definition(yaml_file)
        stack_create = StackLoaderService.to_stack_create(definition, "org-001")

        variables = stack_create.variables
        # Groupe récursif conservé (divergence n°2 corrigée : plus d'aplatissement)
        assert variables["performance"]["type"] == "group"
        sub_vars = variables["performance"]["variables"]
        assert "max_connections" in sub_vars
        # Bornes numériques servies (B9 — AC 3 backend)
        assert variables["host_port"]["minimum"] == 1
        assert variables["host_port"]["maximum"] == 65535
        assert sub_vars["max_connections"]["minimum"] == 10
        assert sub_vars["max_connections"]["maximum"] == 1000
        # enum_labels conservés (perdus par l'ancien normalize_variables)
        assert "enum_labels" in variables["locale"]

    def test_postgresql_macro_kept_raw(self):
        """Arbitrage divergence n°4 : macros brutes conservées à l'import."""
        yaml_file = REPO_DEFINITIONS / "postgresql.yaml"
        if not yaml_file.exists():
            pytest.skip("postgresql.yaml absent de ce dépôt")

        definition = StackLoaderService.load_definition(yaml_file)
        stack_create = StackLoaderService.to_stack_create(definition, "org-001")
        # La macro n'est PAS rendue à l'import — rendu à la volée au GET
        assert (
            stack_create.variables["postgres_password"]["default"]
            == "{{ generate_password(24) }}"
        )


# --- Régression du bug : integer / group acceptés ----------------------------


class TestIntegerAndGroupAccepted:
    """Avant STORY-171 : ``integer``/``group`` rejetés par la validation manuelle."""

    def test_integer_type_accepted(self, tmp_path: Path):
        """Type ``integer`` accepté par le moteur (bug postgresql.yaml/baserow.yaml)."""
        f = tmp_path / "integer.yaml"
        f.write_text(_valid_yaml_content(), encoding="utf-8")
        definition = StackLoaderService.load_definition(f)
        assert definition.variables["host_port"].type.value == "integer"

    def test_group_type_accepted(self, tmp_path: Path):
        """Type ``group`` (variables récursives) accepté par le moteur."""
        content = _valid_yaml_content() + (
            "  performance:\n"
            "    type: group\n"
            "    label: Performance\n"
            "    variables:\n"
            "      max_connections:\n"
            "        type: integer\n"
            "        label: Connexions max\n"
            "        default: 100\n"
            "        minimum: 10\n"
            "        maximum: 1000\n"
        )
        f = tmp_path / "group.yaml"
        f.write_text(content, encoding="utf-8")
        definition = StackLoaderService.load_definition(f)
        group = definition.variables["performance"]
        assert group.type.value == "group"
        assert group.variables is not None
        assert group.variables["max_connections"].maximum == 1000

    def test_validate_stack_definition_wrapper_accepts_valid(self, tmp_path: Path):
        """Wrapper de compatibilité : dict brut valide → aucun lever d'exception."""
        import yaml

        f = tmp_path / "demo.yaml"
        f.write_text(_valid_yaml_content(), encoding="utf-8")
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        StackLoaderService.validate_stack_definition(data)


# --- Cas invalides → ValidationError du moteur --------------------------------


class TestInvalidDefinitions:
    """Invalides → ValidationError Pydantic (erreurs détaillées côté admin)."""

    def _write_and_load(self, tmp_path: Path, content: str, name: str = "bad.yaml"):
        f = tmp_path / name
        f.write_text(content, encoding="utf-8")
        return StackLoaderService.load_definition(f)

    def test_enum_pseudo_type_rejected(self, tmp_path: Path):
        """Divergence n°5 : ``type: enum`` n'existe pas dans le schéma strict."""
        content = _valid_yaml_content().replace("type: integer", "type: enum")
        with pytest.raises(ValidationError):
            self._write_and_load(tmp_path, content)

    def test_metadata_missing_author_license_target_type(self, tmp_path: Path):
        """Métadonnées complètes requises (author/license/target_type obligatoires)."""
        content = (
            "metadata:\n"
            "  name: demo\n"
            "  version: 1.0.0\n"
            "  category: demo\n"
            "  description: Demo stack\n"
            "template:\n"
            "  image: nginx:latest\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            self._write_and_load(tmp_path, content)

        errors = exc_info.value.errors()
        fields = {".".join(str(i) for i in e["loc"]) for e in errors}
        assert "metadata.author" in fields
        assert "metadata.license" in fields
        assert "metadata.target_type" in fields

    def test_enum_labels_orphan_rejected(self, tmp_path: Path):
        """``enum_labels`` sans ``enum`` → rejet (validateur du schéma)."""
        content = _valid_yaml_content() + (
            "  locale:\n"
            "    type: string\n"
            "    label: Locale\n"
            "    enum_labels:\n"
            "      en_US: English\n"
        )
        with pytest.raises(ValidationError) as exc_info:
            self._write_and_load(tmp_path, content)

        errors = exc_info.value.errors()
        assert any("enum_labels" in ".".join(str(i) for i in e["loc"]) for e in errors)

    def test_invalid_target_type_rejected(self, tmp_path: Path):
        """``target_type`` fermé : ``lxd`` hors des 6 valeurs valides → rejet."""
        content = _valid_yaml_content().replace(
            "target_type: docker", "target_type: lxd"
        )
        with pytest.raises(ValidationError) as exc_info:
            self._write_and_load(tmp_path, content)

        errors = exc_info.value.errors()
        assert any("target_type" in ".".join(str(i) for i in e["loc"]) for e in errors)

    def test_empty_template_rejected(self, tmp_path: Path):
        """Template vide → rejet (validateur du schéma)."""
        content = _valid_yaml_content().replace(
            "template:\n  image: nginx:latest\n", "template: {}\n"
        )
        with pytest.raises(ValidationError):
            self._write_and_load(tmp_path, content)

    def test_template_without_services_accepted(self, tmp_path: Path):
        """Divergence n°3 : template container simple SANS ``services`` accepté."""
        definition = self._write_and_load(tmp_path, _valid_yaml_content())
        assert "services" not in definition.template

    def test_malformed_yaml_raises_yaml_error(self, tmp_path: Path):
        """YAML syntaxiquement invalide → yaml.YAMLError (pas de 500 silencieux)."""
        import yaml as yaml_module

        f = tmp_path / "broken.yaml"
        f.write_text("metadata: [unclosed\n  bad", encoding="utf-8")
        with pytest.raises(yaml_module.YAMLError):
            StackLoaderService.load_definition(f)

    def test_empty_yaml_raises_value_error(self, tmp_path: Path):
        """Fichier vide → ValueError explicite."""
        f = tmp_path / "empty.yaml"
        f.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="Empty YAML"):
            StackLoaderService.load_definition(f)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        """Fichier absent → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            StackLoaderService.load_definition(tmp_path / "nope.yaml")

    def test_validation_errors_have_no_input_value(self, tmp_path: Path):
        """Rules 40 : les erreurs formatées n'exposent pas la valeur d'input."""
        from app.schemas.stack_definition import format_validation_errors

        content = _valid_yaml_content().replace(
            "target_type: docker", "target_type: lxd"
        )
        f = tmp_path / "bad_target.yaml"
        f.write_text(content, encoding="utf-8")

        with pytest.raises(ValidationError) as exc_info:
            StackLoaderService.load_definition(f)

        formatted = format_validation_errors(exc_info.value)
        assert len(formatted) >= 1
        assert "lxd" not in " ".join(formatted)  # valeur d'input jamais exposée
        assert "target_type" in " ".join(formatted)  # champ fautif localisé


# --- load_all_from_directory (AC 4) -------------------------------------------


class TestLoadAllFromDirectory:
    """Fichiers invalides journalisés et sautés, fichiers ``_`` ignorés."""

    def test_invalid_file_skipped_without_breaking(self, tmp_path: Path):
        """Un invalide ne stoppe pas le chargement des autres (AC 4)."""
        (tmp_path / "_skip.yaml").write_text("placeholder: true", encoding="utf-8")
        (tmp_path / "good.yaml").write_text(_valid_yaml_content(), encoding="utf-8")
        (tmp_path / "bad.yaml").write_text(
            "metadata:\n  name: bad\n  version: 1.0.0\n", encoding="utf-8"
        )

        stacks = StackLoaderService.load_all_from_directory(tmp_path, "org-001")
        assert len(stacks) == 1
        assert stacks[0].name == "demo"

    def test_underscore_files_ignored(self, tmp_path: Path):
        """Fichiers commençant par ``_`` ignorés (convention du répertoire)."""
        (tmp_path / "_template.yaml").write_text(
            _valid_yaml_content(), encoding="utf-8"
        )
        (tmp_path / "good.yaml").write_text(_valid_yaml_content(), encoding="utf-8")

        stacks = StackLoaderService.load_all_from_directory(tmp_path, "org-001")
        assert all(s.name == "demo" for s in stacks)
        # Un seul stack malgré deux fichiers : _template.yaml ignoré
        assert len({s.name for s in stacks}) == 1
        assert len(stacks) == 1

    def test_missing_directory_returns_empty(self, tmp_path: Path):
        """Répertoire absent → liste vide (pas d'exception)."""
        stacks = StackLoaderService.load_all_from_directory(
            tmp_path / "inexistant", "org-001"
        )
        assert stacks == []

    def test_get_stack_filename_sluggified(self):
        """Helper conservé : nom → slug de fichier."""
        from app.schemas.stack import StackCreate

        sc = StackCreate(
            name="My Cool Stack!",
            template={"image": "nginx"},
            organization_id="org-001",
        )
        assert StackLoaderService.get_stack_filename(sc) == "my-cool-stack.yaml"
