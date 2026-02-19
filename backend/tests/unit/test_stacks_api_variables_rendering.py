"""Tests pour le rendu des variables dans les endpoints stacks API."""

import pytest
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.api.v1.stacks import _render_stack_variables
from app.schemas.stack import StackResponse, StackListResponse


class TestStacksAPIVariablesRendering:
    """Tests pour le rendu des macros dans les variables des stacks."""

    def test_stack_list_response_fields(self):
        """Vérifie que StackListResponse contient uniquement les champs demandés."""
        fields = StackListResponse.model_fields.keys()
        expected_fields = {
            "id", "version", "category", "name", "description",
            "icon_url", "author", "license", "rating", "tags", "downloads"
        }
        assert set(fields) == expected_fields

    def test_render_stack_variables_with_password_macro(self):
        """Test que les macros generate_password sont rendues dans les variables."""
        # Créer un stack avec une macro dans les variables
        stack = StackResponse(
            id="test-stack-id",
            name="PostgreSQL",
            description="PostgreSQL Database",
            version="1.0.0",
            category="database",
            icon_url=None,
            author="WindFlow",
            license="MIT",
            template={"version": "3.8"},
            variables={
                "POSTGRES_PASSWORD": {
                    "default": "{{ generate_password(24) }}",
                    "description": "Database password"
                },
                "POSTGRES_USER": {
                    "default": "postgres",
                    "description": "Database user"
                }
            },
            tags=["database", "postgresql"],
            is_public=True,
            downloads=0,
            rating=0.0,
            screenshots=[],
            documentation_url=None,
            organization_id="org-123",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )

        # Rendre les variables
        rendered_stack = _render_stack_variables(stack)

        # Vérifier que la macro a été rendue
        postgres_password = rendered_stack.variables["POSTGRES_PASSWORD"]["default"]
        assert postgres_password != "{{ generate_password(24) }}"
        assert len(postgres_password) == 24
        assert isinstance(postgres_password, str)

        # Vérifier que les autres variables sont intactes
        assert rendered_stack.variables["POSTGRES_USER"]["default"] == "postgres"

    def test_render_stack_variables_with_multiple_macros(self):
        """Test que plusieurs macros génèrent des valeurs différentes."""
        stack = StackResponse(
            id="test-stack-id",
            name="Multi-Service Stack",
            description="Stack with multiple passwords",
            version="1.0.0",
            category="multi",
            icon_url=None,
            author="WindFlow",
            license="MIT",
            template={"version": "3.8"},
            variables={
                "DB_PASSWORD": {
                    "default": "{{ generate_password(16) }}"
                },
                "ADMIN_PASSWORD": {
                    "default": "{{ generate_password(16) }}"
                },
                "API_SECRET": {
                    "default": "{{ generate_secret(32) }}"
                }
            },
            tags=["multi"],
            is_public=True,
            downloads=0,
            rating=0.0,
            screenshots=[],
            documentation_url=None,
            organization_id="org-123",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )

        # Rendre les variables
        rendered_stack = _render_stack_variables(stack)

        # Vérifier que toutes les macros ont été rendues
        db_password = rendered_stack.variables["DB_PASSWORD"]["default"]
        admin_password = rendered_stack.variables["ADMIN_PASSWORD"]["default"]
        api_secret = rendered_stack.variables["API_SECRET"]["default"]

        assert db_password != "{{ generate_password(16) }}"
        assert admin_password != "{{ generate_password(16) }}"
        assert api_secret != "{{ generate_secret(32) }}"

        # Vérifier que les valeurs sont différentes
        assert db_password != admin_password
        assert db_password != api_secret
        assert admin_password != api_secret

        # Vérifier les longueurs
        assert len(db_password) == 16
        assert len(admin_password) == 16
        assert len(api_secret) == 32

    def test_render_stack_variables_without_macros(self):
        """Test que les variables sans macros restent inchangées."""
        stack = StackResponse(
            id="test-stack-id",
            name="Simple Stack",
            description="Stack without macros",
            version="1.0.0",
            category="simple",
            icon_url=None,
            author="WindFlow",
            license="MIT",
            template={"version": "3.8"},
            variables={
                "APP_NAME": {
                    "default": "myapp"
                },
                "PORT": {
                    "default": "8080"
                }
            },
            tags=["simple"],
            is_public=True,
            downloads=0,
            rating=0.0,
            screenshots=[],
            documentation_url=None,
            organization_id="org-123",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )

        # Rendre les variables
        rendered_stack = _render_stack_variables(stack)

        # Vérifier que les variables sont inchangées
        assert rendered_stack.variables["APP_NAME"]["default"] == "myapp"
        assert rendered_stack.variables["PORT"]["default"] == "8080"

    def test_render_stack_variables_with_empty_variables(self):
        """Test que les stacks sans variables ne causent pas d'erreur."""
        stack = StackResponse(
            id="test-stack-id",
            name="Empty Variables Stack",
            description="Stack with no variables",
            version="1.0.0",
            category="empty",
            icon_url=None,
            author="WindFlow",
            license="MIT",
            template={"version": "3.8"},
            variables={},
            tags=["empty"],
            is_public=True,
            downloads=0,
            rating=0.0,
            screenshots=[],
            documentation_url=None,
            organization_id="org-123",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )

        # Rendre les variables
        rendered_stack = _render_stack_variables(stack)

        # Vérifier que le stack est retourné sans erreur
        assert rendered_stack.variables == {}

    def test_render_stack_variables_generates_new_values_each_time(self):
        """Test que chaque appel génère de nouvelles valeurs."""
        stack = StackResponse(
            id="test-stack-id",
            name="PostgreSQL",
            description="PostgreSQL Database",
            version="1.0.0",
            category="database",
            icon_url=None,
            author="WindFlow",
            license="MIT",
            template={"version": "3.8"},
            variables={
                "PASSWORD": {
                    "default": "{{ generate_password(24) }}"
                }
            },
            tags=["database"],
            is_public=True,
            downloads=0,
            rating=0.0,
            screenshots=[],
            documentation_url=None,
            organization_id="org-123",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00"
        )

        # Rendre les variables plusieurs fois
        rendered_stack_1 = _render_stack_variables(stack)
        rendered_stack_2 = _render_stack_variables(stack)
        rendered_stack_3 = _render_stack_variables(stack)

        # Vérifier que chaque appel génère une valeur différente
        password_1 = rendered_stack_1.variables["PASSWORD"]["default"]
        password_2 = rendered_stack_2.variables["PASSWORD"]["default"]
        password_3 = rendered_stack_3.variables["PASSWORD"]["default"]

        assert password_1 != password_2
        assert password_2 != password_3
        assert password_1 != password_3

        # Vérifier que toutes les valeurs ont la bonne longueur
        assert len(password_1) == 24
        assert len(password_2) == 24
        assert len(password_3) == 24
