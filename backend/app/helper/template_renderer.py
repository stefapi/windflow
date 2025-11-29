"""
Renderer Jinja2 centralisé pour templates de déploiement.

Fournit un moteur de rendu unifié avec toutes les fonctions personnalisées
disponibles pour tous les types de déploiement (Docker, Docker Compose, etc.)
"""

import logging
from typing import Dict, Any
from jinja2 import Template, TemplateSyntaxError, UndefinedError

from backend.app.helper.jinja_functions import JINJA_FUNCTIONS

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """
    Renderer Jinja2 avec fonctions personnalisées enregistrées.

    Permet de rendre des templates (dictionnaires ou strings) avec
    substitution de variables et accès aux fonctions utilitaires.
    """

    def __init__(self, additional_functions: Dict[str, Any] = None):
        """
        Initialise le renderer avec toutes les fonctions disponibles.

        Args:
            additional_functions: Fonctions supplémentaires à ajouter (optionnel)
        """
        # Copier les fonctions de base
        self.functions = JINJA_FUNCTIONS.copy()

        # Ajouter des fonctions supplémentaires si fournies
        if additional_functions:
            self.functions.update(additional_functions)

        logger.debug(f"TemplateRenderer initialisé avec {len(self.functions)} fonctions")

    def render_dict(
        self,
        template: Dict[str, Any],
        variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rend un dictionnaire avec substitution Jinja2 récursive.

        Parcourt récursivement toutes les valeurs du dictionnaire et
        applique la substitution Jinja2 sur les strings.

        Args:
            template: Dictionnaire template à rendre
            variables: Variables utilisateur à substituer

        Returns:
            Dictionnaire avec variables substituées

        Example:
            >>> renderer = TemplateRenderer()
            >>> template = {
            ...     "environment": {
            ...         "PASSWORD": "{{ generate_password(16) }}",
            ...         "USER": "{{ username }}"
            ...     }
            ... }
            >>> result = renderer.render_dict(template, {"username": "admin"})
            >>> len(result["environment"]["PASSWORD"])
            16
            >>> result["environment"]["USER"]
            'admin'
        """
        # Créer le contexte de rendu avec variables utilisateur + fonctions
        context = {**variables, **self.functions}

        # Rendre récursivement
        return self._render_value(template, context)

    def render_string(
        self,
        template_str: str,
        variables: Dict[str, Any]
    ) -> str:
        """
        Rend une string avec substitution Jinja2.

        Args:
            template_str: String template à rendre
            variables: Variables utilisateur à substituer

        Returns:
            String avec variables substituées

        Example:
            >>> renderer = TemplateRenderer()
            >>> result = renderer.render_string(
            ...     "Password: {{ generate_password(12) }}",
            ...     {}
            ... )
            >>> "Password:" in result
            True
            >>> len(result.split(": ")[1])
            12
        """
        # Créer le contexte de rendu
        context = {**variables, **self.functions}

        try:
            # Créer le template Jinja2
            jinja_template = Template(template_str)

            # Rendre avec le contexte
            rendered = jinja_template.render(**context)

            return rendered

        except TemplateSyntaxError as e:
            logger.error(f"Erreur de syntaxe Jinja2: {e}")
            # Retourner le template original en cas d'erreur
            return template_str

        except UndefinedError as e:
            logger.error(f"Variable non définie dans le template: {e}")
            # Retourner le template original en cas d'erreur
            return template_str

        except Exception as e:
            logger.error(f"Erreur lors du rendu Jinja2: {e}")
            # Retourner le template original en cas d'erreur
            return template_str

    def _render_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """
        Rend une valeur (peut être dict, list, str, etc.) de manière récursive.

        Args:
            value: Valeur à rendre
            context: Contexte de rendu (variables + fonctions)

        Returns:
            Valeur rendue
        """
        if isinstance(value, dict):
            # Dictionnaire : rendre récursivement chaque valeur
            return {
                key: self._render_value(val, context)
                for key, val in value.items()
            }

        elif isinstance(value, list):
            # Liste : rendre récursivement chaque élément
            return [
                self._render_value(item, context)
                for item in value
            ]

        elif isinstance(value, str):
            # String : appliquer la substitution Jinja2
            try:
                # Créer un template Jinja2
                jinja_template = Template(value)

                # Rendre avec le contexte
                rendered = jinja_template.render(**context)

                return rendered

            except TemplateSyntaxError as e:
                logger.warning(f"Erreur de syntaxe Jinja2 dans '{value}': {e}")
                return value

            except UndefinedError as e:
                logger.warning(f"Variable non définie dans '{value}': {e}")
                return value

            except Exception as e:
                logger.warning(f"Erreur lors du rendu de '{value}': {e}")
                return value

        else:
            # Types primitifs (int, bool, None, etc.) : retourner tel quel
            return value

    def get_available_functions(self) -> Dict[str, str]:
        """
        Retourne la liste des fonctions disponibles avec leur documentation.

        Returns:
            Dictionnaire {nom_fonction: docstring}
        """
        functions_doc = {}

        for name, func in self.functions.items():
            doc = func.__doc__ or "Pas de documentation disponible"
            # Prendre seulement la première ligne de la docstring
            first_line = doc.strip().split('\n')[0]
            functions_doc[name] = first_line

        return functions_doc

    def validate_template(
        self,
        template: Any,
        check_undefined: bool = True
    ) -> tuple[bool, list[str]]:
        """
        Valide un template sans le rendre.

        Vérifie la syntaxe Jinja2 et potentiellement les variables non définies.

        Args:
            template: Template à valider (dict, list ou str)
            check_undefined: Vérifier les variables non définies

        Returns:
            Tuple[bool, List[str]]: (Valide, Liste des erreurs)
        """
        errors = []

        def validate_value(value: Any, path: str = "root"):
            """Valide récursivement une valeur."""
            if isinstance(value, dict):
                for key, val in value.items():
                    validate_value(val, f"{path}.{key}")

            elif isinstance(value, list):
                for i, item in enumerate(value):
                    validate_value(item, f"{path}[{i}]")

            elif isinstance(value, str):
                # Vérifier la syntaxe Jinja2
                try:
                    Template(value)
                except TemplateSyntaxError as e:
                    errors.append(f"Erreur de syntaxe Jinja2 à {path}: {e}")
                except Exception as e:
                    errors.append(f"Erreur à {path}: {e}")

        # Valider le template
        validate_value(template)

        return len(errors) == 0, errors


# Instance globale du renderer par défaut
default_renderer = TemplateRenderer()


def render_template(
    template: Dict[str, Any],
    variables: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Fonction utilitaire pour rendre un template avec le renderer par défaut.

    Args:
        template: Template à rendre
        variables: Variables à substituer

    Returns:
        Template rendu
    """
    return default_renderer.render_dict(template, variables)


def render_string(
    template_str: str,
    variables: Dict[str, Any]
) -> str:
    """
    Fonction utilitaire pour rendre une string avec le renderer par défaut.

    Args:
        template_str: String template
        variables: Variables à substituer

    Returns:
        String rendue
    """
    return default_renderer.render_string(template_str, variables)
