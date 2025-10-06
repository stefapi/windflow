"""
Endpoints API pour l'import/export de stacks.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
from typing import Dict, Any

from ...database import get_db
from ...models.stack import Stack
from ...models.user import User
from ...auth.dependencies import get_current_user

router = APIRouter()


@router.get("/stacks/{stack_id}/export")
async def export_stack(
    stack_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Exporte un stack au format JSON."""

    stmt = select(Stack).where(Stack.id == stack_id)
    result = await db.execute(stmt)
    stack = result.scalar_one_or_none()

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stack not found"
        )

    # Vérifier les permissions
    if stack.organization_id != current_user.organization_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )

    # Format d'export
    export_data = {
        "version": "1.0",
        "stack": {
            "name": stack.name,
            "description": stack.description,
            "version": stack.version,
            "category": stack.category,
            "tags": stack.tags,
            "template": stack.template,
            "variables": stack.variables,
            "icon_url": stack.icon_url,
            "screenshots": stack.screenshots,
            "documentation_url": stack.documentation_url,
            "author": stack.author,
            "license": stack.license
        }
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="{stack.name}.json"'
        }
    )


@router.post("/stacks/import")
async def import_stack(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Importe un stack depuis un fichier JSON."""

    try:
        content = await file.read()
        import_data = json.loads(content)

        # Validation du format
        if import_data.get("version") != "1.0":
            raise ValueError("Version de format non supportée")

        if "stack" not in import_data:
            raise ValueError("Format invalide: 'stack' manquant")

        stack_data = import_data["stack"]

        # Créer le nouveau stack
        new_stack = Stack(
            name=stack_data["name"],
            description=stack_data.get("description"),
            version=stack_data.get("version", "1.0.0"),
            category=stack_data.get("category"),
            tags=stack_data.get("tags", []),
            template=stack_data["template"],
            variables=stack_data.get("variables", {}),
            icon_url=stack_data.get("icon_url"),
            screenshots=stack_data.get("screenshots", []),
            documentation_url=stack_data.get("documentation_url"),
            author=stack_data.get("author"),
            license=stack_data.get("license", "MIT"),
            organization_id=current_user.organization_id,
            is_public=False  # Importé en privé par défaut
        )

        db.add(new_stack)
        await db.commit()
        await db.refresh(new_stack)

        return {
            "message": "Stack imported successfully",
            "stack_id": new_stack.id,
            "name": new_stack.name
        }

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON file"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )
