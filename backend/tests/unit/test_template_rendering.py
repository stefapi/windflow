"""Test simple pour valider le rendu des templates Jinja2 avec fonctions personnalisées."""

import pytest
from app.services.deployment_service import DeploymentService


def test_render_template_with_generate_password():
    """Test que generate_password() est correctement rendu dans les templates."""
    template = {
        "database": {
            "host": "localhost",
            "password": "{{ generate_password(24) }}",
            "user": "{{ db_user }}"
        }
    }

    variables = {
        "db_user": "admin"
    }

    result = DeploymentService._render_template(template, variables)

    # Vérifier que le mot de passe a été généré (pas la macro brute)
    assert result["database"]["password"] != "{{ generate_password(24) }}"
    # Vérifier que le mot de passe a la bonne longueur
    assert len(result["database"]["password"]) == 24
    # Vérifier que la variable utilisateur a été substituée
    assert result["database"]["user"] == "admin"
    # Vérifier que les autres valeurs sont intactes
    assert result["database"]["host"] == "localhost"


def test_render_template_with_generate_secret():
    """Test que generate_secret() est correctement rendu dans les templates."""
    template = {
        "app": {
            "secret_key": "{{ generate_secret(32) }}"
        }
    }

    result = DeploymentService._render_template(template, {})

    # Vérifier que le secret a été généré
    assert result["app"]["secret_key"] != "{{ generate_secret(32) }}"
    # Vérifier que le secret a la bonne longueur
    assert len(result["app"]["secret_key"]) == 32
    # Vérifier que c'est bien de l'hexadécimal
    assert all(c in '0123456789abcdef' for c in result["app"]["secret_key"])


def test_render_template_with_multiple_passwords():
    """Test que plusieurs appels à generate_password() génèrent des mots de passe différents."""
    template = {
        "passwords": {
            "admin": "{{ generate_password(16) }}",
            "user": "{{ generate_password(16) }}"
        }
    }

    result = DeploymentService._render_template(template, {})

    # Vérifier que les deux mots de passe sont différents
    assert result["passwords"]["admin"] != result["passwords"]["user"]
    # Vérifier que les deux ont la bonne longueur
    assert len(result["passwords"]["admin"]) == 16
    assert len(result["passwords"]["user"]) == 16


def test_render_template_with_nested_structures():
    """Test le rendu dans des structures imbriquées complexes."""
    template = {
        "services": {
            "postgres": {
                "environment": {
                    "POSTGRES_PASSWORD": "{{ generate_password(24) }}",
                    "POSTGRES_USER": "{{ db_user }}"
                }
            },
            "redis": {
                "environment": {
                    "REDIS_PASSWORD": "{{ generate_password(32) }}"
                }
            }
        }
    }

    variables = {
        "db_user": "postgres"
    }

    result = DeploymentService._render_template(template, variables)

    # Vérifier que tous les mots de passe ont été générés
    postgres_pwd = result["services"]["postgres"]["environment"]["POSTGRES_PASSWORD"]
    redis_pwd = result["services"]["redis"]["environment"]["REDIS_PASSWORD"]

    assert postgres_pwd != "{{ generate_password(24) }}"
    assert redis_pwd != "{{ generate_password(32) }}"
    assert len(postgres_pwd) == 24
    assert len(redis_pwd) == 32
    assert postgres_pwd != redis_pwd

    # Vérifier que la variable utilisateur a été substituée
    assert result["services"]["postgres"]["environment"]["POSTGRES_USER"] == "postgres"


def test_render_template_string():
    """Test le rendu d'une simple chaîne avec macro."""
    template = "Password: {{ generate_password(12) }}"

    result = DeploymentService._render_template(template, {})

    # Vérifier que la macro a été rendue
    assert result != template
    assert result.startswith("Password: ")
    # Extraire le mot de passe et vérifier sa longueur
    password = result.replace("Password: ", "")
    assert len(password) == 12


def test_render_template_list():
    """Test le rendu dans une liste."""
    template = [
        "{{ generate_password(8) }}",
        "{{ generate_password(8) }}",
        "static_value"
    ]

    result = DeploymentService._render_template(template, {})

    # Vérifier que les macros ont été rendues
    assert result[0] != "{{ generate_password(8) }}"
    assert result[1] != "{{ generate_password(8) }}"
    assert len(result[0]) == 8
    assert len(result[1]) == 8
    # Vérifier que les deux sont différents
    assert result[0] != result[1]
    # Vérifier que la valeur statique est intacte
    assert result[2] == "static_value"
