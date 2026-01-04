"""
Routes de gestion des stacks Docker Compose.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.stack import StackResponse, StackCreate, StackUpdate
from ...services.stack_service import StackService
from ...auth.dependencies import get_current_active_user
from ...models.user import User
from ...helper.template_renderer import TemplateRenderer
from ...helper.jinja_functions import JinjaFunctions

router = APIRouter()


def _render_stack_variables(stack) -> StackResponse:
    """
    Rend les macros dans les variables par défaut d'un stack.

    Cette fonction génère de nouvelles valeurs pour les macros comme
    {{ generate_password(24) }} afin que le frontend reçoive des valeurs
    concrètes plutôt que les macros brutes.

    Args:
        stack: Stack SQLAlchemy avec variables potentiellement contenant des macros

    Returns:
        StackResponse avec variables rendues
    """
    # Convertir l'objet SQLAlchemy en StackResponse Pydantic
    stack_response = StackResponse.model_validate(stack)

    if not stack_response.variables:
        return stack_response

    # Créer un renderer pour exécuter les macros
    renderer = TemplateRenderer()

    # Rendre les variables (qui peuvent contenir des macros dans les defaults)
    rendered_variables = renderer.render_dict(stack_response.variables, {})

    # Créer une copie du stack avec les variables rendues
    stack_dict = stack_response.model_dump()
    stack_dict['variables'] = rendered_variables

    # Rendre le nom de déploiement par défaut si présent
    if stack.deployment_name:
        # Extraire les valeurs par défaut des variables pour le contexte
        context = {var_name: var_def.get('default') for var_name, var_def in rendered_variables.items() if 'default' in var_def}
        stack_dict['default_name'] = renderer.render_string(stack.deployment_name, context)
    else:
        stack_dict['default_name'] = None

    return StackResponse(**stack_dict)


@router.get("/", response_model=List[StackResponse])
async def list_stacks(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste les stacks Docker Compose de l'organisation.

    Les macros dans les variables par défaut (comme {{ generate_password(24) }})
    sont rendues pour que le frontend reçoive des valeurs concrètes.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List[StackResponse]: Liste des stacks avec variables rendues
    """
    stacks = await StackService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )

    # Rendre les macros dans les variables de chaque stack
    rendered_stacks = [_render_stack_variables(stack) for stack in stacks]

    return rendered_stacks


@router.get("/{stack_id}", response_model=StackResponse)
async def get_stack(
    stack_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère une stack par son ID.

    Les macros dans les variables par défaut (comme {{ generate_password(24) }})
    sont rendues pour que le frontend reçoive des valeurs concrètes.

    Args:
        stack_id: ID de la stack (string UUID)
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack demandée avec variables rendues

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier que la stack appartient à la même organisation
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    # Rendre les macros dans les variables avant de retourner
    return _render_stack_variables(stack)


@router.post("/", response_model=StackResponse, status_code=status.HTTP_201_CREATED)
async def create_stack(
    stack_data: StackCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée une nouvelle stack Docker Compose.

    Args:
        stack_data: Données de la stack à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack créée

    Raises:
        HTTPException: Si le nom existe déjà dans l'organisation
    """
    # Vérifier que le nom n'existe pas déjà dans l'organisation
    existing = await StackService.get_by_name(
        session,
        current_user.organization_id,
        stack_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stack avec le nom '{stack_data.name}' existe déjà"
        )

    stack = await StackService.create(session, stack_data, current_user.organization_id)
    return stack


@router.put("/{stack_id}", response_model=StackResponse)
async def update_stack(
    stack_id: str,
    stack_data: StackUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour une stack Docker Compose.

    Args:
        stack_id: ID de la stack à modifier
        stack_data: Nouvelles données de la stack
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack mise à jour

    Raises:
        HTTPException: Si la stack n'existe pas, accès refusé ou nom en conflit
    """
    # Vérifier que la stack existe
    existing_stack = await StackService.get_by_id(session, stack_id)
    if not existing_stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier les permissions
    if existing_stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if stack_data.name and stack_data.name != existing_stack.name:
        existing_name = await StackService.get_by_name(
            session,
            current_user.organization_id,
            stack_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stack avec le nom '{stack_data.name}' existe déjà"
            )

    stack = await StackService.update(session, stack_id, stack_data)
    return stack


@router.delete("/{stack_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stack(
    stack_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime une stack Docker Compose.

    Args:
        stack_id: ID de la stack à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    # Vérifier que la stack existe
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier les permissions
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    await StackService.delete(session, stack_id)
