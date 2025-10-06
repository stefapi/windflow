"""
API de gestion des stacks - Administration.

Endpoints pour l'administration et la gestion des stacks marketplace.
Remplace les scripts seed_stacks.py et check_stacks.py.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from ....database import get_db
from ....models.stack import Stack
from ....models.organization import Organization
from ....models.deployment import Deployment
from ....schemas.stack import StackCreate, StackUpdate, StackResponse
from ....services.stack_service import StackService
from ....services.stack_loader_service import StackLoaderService
from ....auth.dependencies import get_current_superadmin

router = APIRouter()


# ============================================================================
# SCHEMAS
# ============================================================================

class StackDefinitionInfo(BaseModel):
    """Informations sur une définition YAML de stack."""

    filename: str
    name: str
    version: str
    category: str
    description: str
    is_public: bool
    tags: List[str]
    variables_count: int
    is_valid: bool
    validation_errors: Optional[List[str]] = None


class ImportResult(BaseModel):
    """Résultat d'un import de stack."""

    stack_id: str
    stack_name: str
    status: str  # created, updated, skipped, error
    message: Optional[str] = None


class ImportStats(BaseModel):
    """Statistiques d'import de stacks."""

    total: int
    created: int
    updated: int
    skipped: int
    errors: int
    results: List[ImportResult]


class SyncStatus(BaseModel):
    """Statut de synchronisation des stacks."""

    total_definitions: int
    total_imported: int
    new_stacks: List[str]
    modified_stacks: List[str]
    up_to_date: List[str]
    obsolete_stacks: List[str]


class StackUsageStats(BaseModel):
    """Statistiques d'usage d'un stack."""

    stack_id: str
    stack_name: str
    total_deployments: int
    successful_deployments: int
    failed_deployments: int
    success_rate: float
    organizations_using: int
    last_deployment: Optional[str] = None


class StacksOverview(BaseModel):
    """Vue d'ensemble des stacks."""

    total_stacks: int
    public_stacks: int
    private_stacks: int
    stacks_by_category: Dict[str, int]
    most_deployed: List[Dict[str, Any]]
    recently_added: List[Dict[str, Any]]


# ============================================================================
# 1. GESTION DES DÉFINITIONS YAML
# ============================================================================

@router.get("/definitions", response_model=List[StackDefinitionInfo])
async def list_stack_definitions(
    current_user = Depends(get_current_superadmin)
) -> List[StackDefinitionInfo]:
    """
    Liste toutes les définitions YAML de stacks disponibles.

    Équivalent à: seed_stacks.py --list
    """
    stacks_dir = Path(__file__).parent.parent.parent.parent / "stacks_definitions"

    if not stacks_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Répertoire stacks_definitions non trouvé: {stacks_dir}"
        )

    definitions = []
    yaml_files = list(stacks_dir.glob("*.yaml"))

    for yaml_file in yaml_files:
        if yaml_file.name.startswith("_"):
            continue

        try:
            data = StackLoaderService.load_from_yaml(yaml_file)
            metadata = data.get("metadata", {})

            # Valider la définition
            is_valid = True
            validation_errors = []
            try:
                StackLoaderService.validate_stack_definition(data)
            except Exception as e:
                is_valid = False
                validation_errors.append(str(e))

            definitions.append(StackDefinitionInfo(
                filename=yaml_file.name,
                name=metadata.get("name", "N/A"),
                version=metadata.get("version", "N/A"),
                category=metadata.get("category", "N/A"),
                description=metadata.get("description", ""),
                is_public=metadata.get("is_public", False),
                tags=metadata.get("tags", []),
                variables_count=len(data.get("variables", {})),
                is_valid=is_valid,
                validation_errors=validation_errors if validation_errors else None
            ))

        except Exception as e:
            definitions.append(StackDefinitionInfo(
                filename=yaml_file.name,
                name="ERROR",
                version="N/A",
                category="N/A",
                description="",
                is_public=False,
                tags=[],
                variables_count=0,
                is_valid=False,
                validation_errors=[str(e)]
            ))

    return definitions


@router.post("/validate")
async def validate_stack_definitions(
    current_user = Depends(get_current_superadmin)
) -> Dict[str, Any]:
    """
    Valide toutes les définitions YAML sans les importer.

    Équivalent à: seed_stacks.py --dry-run
    """
    stacks_dir = Path(__file__).parent.parent.parent.parent / "stacks_definitions"

    if not stacks_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Répertoire stacks_definitions non trouvé"
        )

    yaml_files = list(stacks_dir.glob("*.yaml"))
    valid_count = 0
    errors = []

    for yaml_file in yaml_files:
        if yaml_file.name.startswith("_"):
            continue

        try:
            data = StackLoaderService.load_from_yaml(yaml_file)
            StackLoaderService.validate_stack_definition(data)
            valid_count += 1
        except Exception as e:
            errors.append({
                "file": yaml_file.name,
                "error": str(e)
            })

    return {
        "total_files": len(yaml_files),
        "valid": valid_count,
        "invalid": len(errors),
        "all_valid": len(errors) == 0,
        "errors": errors
    }


@router.post("/import", response_model=ImportStats)
async def import_stacks(
    stack_name: Optional[str] = Body(None, description="Nom du stack à importer (sans .yaml)"),
    force_update: bool = Body(False, description="Forcer la mise à jour des stacks existants"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> ImportStats:
    """
    Importe un ou tous les stacks depuis les définitions YAML.

    Équivalent à:
    - seed_stacks.py (tous les stacks)
    - seed_stacks.py --stack NAME (stack spécifique)
    - seed_stacks.py --force (avec force_update=true)
    """
    # Récupérer l'organisation par défaut
    result = await db.execute(select(Organization))
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune organisation trouvée. Initialisez d'abord la base de données."
        )

    stacks_dir = Path(__file__).parent.parent.parent.parent / "stacks_definitions"

    if not stacks_dir.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Répertoire stacks_definitions non trouvé"
        )

    results: List[ImportResult] = []

    if stack_name:
        # Import d'un stack spécifique
        yaml_file = stacks_dir / f"{stack_name}.yaml"

        if not yaml_file.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Stack non trouvé: {stack_name}.yaml"
            )

        try:
            stack, created = await StackService.upsert_from_yaml(
                db, yaml_file, org.id, force_update=force_update
            )

            status_str = "created" if created else ("updated" if force_update else "skipped")
            results.append(ImportResult(
                stack_id=stack.id,
                stack_name=stack.name,
                status=status_str,
                message=f"Stack {status_str} successfully"
            ))

        except Exception as e:
            results.append(ImportResult(
                stack_id="",
                stack_name=stack_name,
                status="error",
                message=str(e)
            ))

    else:
        # Import de tous les stacks
        stats = await StackService.import_all_from_directory(
            db, stacks_dir, org.id, force_update=force_update
        )

        # Convertir les stats en résultats
        for error in stats.get("errors", []):
            results.append(ImportResult(
                stack_id="",
                stack_name=error["stack"],
                status="error",
                message=error["error"]
            ))

    # Calculer les statistiques finales
    created = sum(1 for r in results if r.status == "created")
    updated = sum(1 for r in results if r.status == "updated")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")

    return ImportStats(
        total=len(results),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        results=results
    )


@router.get("/imported", response_model=List[StackResponse])
async def list_imported_stacks(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    category: Optional[str] = Query(None),
    is_public: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> List[StackResponse]:
    """
    Liste tous les stacks actuellement importés en base de données.

    Équivalent à: check_stacks.py
    """
    query = select(Stack)

    # Filtres optionnels
    filters = []
    if category:
        filters.append(Stack.category == category)
    if is_public is not None:
        filters.append(Stack.is_public == is_public)

    if filters:
        query = query.where(and_(*filters))

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    stacks = result.scalars().all()

    return [StackResponse.model_validate(stack) for stack in stacks]


# ============================================================================
# 2. SYNCHRONISATION ET COMPARAISON
# ============================================================================

@router.get("/sync/status", response_model=SyncStatus)
async def get_sync_status(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> SyncStatus:
    """
    Compare les définitions YAML avec les stacks en base de données.

    Identifie:
    - Nouveaux stacks à importer
    - Stacks modifiés (version différente)
    - Stacks à jour
    - Stacks obsolètes (en DB mais plus de définition YAML)
    """
    stacks_dir = Path(__file__).parent.parent.parent.parent / "stacks_definitions"

    # Charger toutes les définitions YAML
    yaml_stacks = {}
    if stacks_dir.exists():
        for yaml_file in stacks_dir.glob("*.yaml"):
            if yaml_file.name.startswith("_"):
                continue

            try:
                data = StackLoaderService.load_from_yaml(yaml_file)
                metadata = data.get("metadata", {})
                yaml_stacks[metadata.get("name")] = metadata.get("version")
            except Exception:
                continue

    # Charger tous les stacks en DB
    result = await db.execute(select(Stack))
    db_stacks = {stack.name: stack.version for stack in result.scalars().all()}

    # Comparer
    new_stacks = [name for name in yaml_stacks if name not in db_stacks]
    modified_stacks = [
        name for name in yaml_stacks
        if name in db_stacks and yaml_stacks[name] != db_stacks[name]
    ]
    up_to_date = [
        name for name in yaml_stacks
        if name in db_stacks and yaml_stacks[name] == db_stacks[name]
    ]
    obsolete_stacks = [name for name in db_stacks if name not in yaml_stacks]

    return SyncStatus(
        total_definitions=len(yaml_stacks),
        total_imported=len(db_stacks),
        new_stacks=new_stacks,
        modified_stacks=modified_stacks,
        up_to_date=up_to_date,
        obsolete_stacks=obsolete_stacks
    )


@router.post("/sync/auto", response_model=ImportStats)
async def auto_sync_stacks(
    update_modified: bool = Body(True, description="Mettre à jour les stacks modifiés"),
    import_new: bool = Body(True, description="Importer les nouveaux stacks"),
    delete_obsolete: bool = Body(False, description="Supprimer les stacks obsolètes"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> ImportStats:
    """
    Synchronisation automatique des stacks.

    Options:
    - Importe les nouveaux stacks
    - Met à jour les stacks modifiés
    - Supprime optionnellement les stacks obsolètes
    """
    # Récupérer le statut de sync
    sync_status = await get_sync_status(db, current_user)

    # Récupérer l'organisation par défaut
    result = await db.execute(select(Organization))
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune organisation trouvée"
        )

    stacks_dir = Path(__file__).parent.parent.parent.parent / "stacks_definitions"
    results: List[ImportResult] = []

    # Importer les nouveaux stacks
    if import_new:
        for stack_name in sync_status.new_stacks:
            yaml_file = stacks_dir / f"{stack_name}.yaml"
            try:
                stack, _ = await StackService.upsert_from_yaml(
                    db, yaml_file, org.id, force_update=False
                )
                results.append(ImportResult(
                    stack_id=stack.id,
                    stack_name=stack.name,
                    status="created",
                    message="New stack imported"
                ))
            except Exception as e:
                results.append(ImportResult(
                    stack_id="",
                    stack_name=stack_name,
                    status="error",
                    message=str(e)
                ))

    # Mettre à jour les stacks modifiés
    if update_modified:
        for stack_name in sync_status.modified_stacks:
            yaml_file = stacks_dir / f"{stack_name}.yaml"
            try:
                stack, _ = await StackService.upsert_from_yaml(
                    db, yaml_file, org.id, force_update=True
                )
                results.append(ImportResult(
                    stack_id=stack.id,
                    stack_name=stack.name,
                    status="updated",
                    message="Stack updated to new version"
                ))
            except Exception as e:
                results.append(ImportResult(
                    stack_id="",
                    stack_name=stack_name,
                    status="error",
                    message=str(e)
                ))

    # Supprimer les stacks obsolètes (optionnel et dangereux)
    if delete_obsolete:
        for stack_name in sync_status.obsolete_stacks:
            try:
                result = await db.execute(
                    select(Stack).where(Stack.name == stack_name)
                )
                stack = result.scalar_one_or_none()

                if stack:
                    # Vérifier s'il y a des déploiements actifs
                    dep_result = await db.execute(
                        select(func.count(Deployment.id))
                        .where(Deployment.stack_id == stack.id)
                    )
                    deployment_count = dep_result.scalar()

                    if deployment_count > 0:
                        results.append(ImportResult(
                            stack_id=stack.id,
                            stack_name=stack.name,
                            status="skipped",
                            message=f"Cannot delete: {deployment_count} deployments exist"
                        ))
                    else:
                        await db.delete(stack)
                        await db.commit()
                        results.append(ImportResult(
                            stack_id=stack.id,
                            stack_name=stack.name,
                            status="deleted",
                            message="Obsolete stack deleted"
                        ))
            except Exception as e:
                results.append(ImportResult(
                    stack_id="",
                    stack_name=stack_name,
                    status="error",
                    message=str(e)
                ))

    # Calculer les statistiques
    created = sum(1 for r in results if r.status == "created")
    updated = sum(1 for r in results if r.status == "updated")
    skipped = sum(1 for r in results if r.status == "skipped")
    errors = sum(1 for r in results if r.status == "error")

    return ImportStats(
        total=len(results),
        created=created,
        updated=updated,
        skipped=skipped,
        errors=errors,
        results=results
    )


# ============================================================================
# 3. EXPORT ET BACKUP
# ============================================================================

@router.get("/{stack_id}/export")
async def export_stack_yaml(
    stack_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> Dict[str, Any]:
    """
    Exporte un stack en format YAML.

    Génère un fichier YAML depuis la configuration en base de données.
    """
    stack = await StackService.get_by_id(db, stack_id)

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack non trouvé: {stack_id}"
        )

    # Construire la structure YAML
    yaml_data = {
        "metadata": {
            "name": stack.name,
            "version": stack.version,
            "description": stack.description,
            "category": stack.category,
            "tags": stack.tags,
            "is_public": stack.is_public
        },
        "template": stack.template,
        "variables": stack.variables
    }

    return yaml_data


@router.post("/export/bulk")
async def export_multiple_stacks(
    stack_ids: List[str] = Body(..., description="Liste des IDs de stacks à exporter"),
    format: str = Body("yaml", description="Format d'export (yaml ou json)"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> Dict[str, Any]:
    """
    Exporte plusieurs stacks.
    """
    exported_stacks = {}

    for stack_id in stack_ids:
        stack = await StackService.get_by_id(db, stack_id)

        if stack:
            exported_stacks[stack.name] = {
                "metadata": {
                    "name": stack.name,
                    "version": stack.version,
                    "description": stack.description,
                    "category": stack.category,
                    "tags": stack.tags,
                    "is_public": stack.is_public
                },
                "template": stack.template,
                "variables": stack.variables
            }

    return {
        "format": format,
        "total_stacks": len(exported_stacks),
        "stacks": exported_stacks
    }


# ============================================================================
# 4. ADMINISTRATION AVANCÉE
# ============================================================================

@router.patch("/{stack_id}/toggle-visibility")
async def toggle_stack_visibility(
    stack_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> StackResponse:
    """
    Bascule la visibilité d'un stack (public <-> privé).
    """
    stack = await StackService.get_by_id(db, stack_id)

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack non trouvé: {stack_id}"
        )

    stack.is_public = not stack.is_public
    await db.commit()
    await db.refresh(stack)

    return StackResponse.model_validate(stack)


@router.post("/{stack_id}/duplicate")
async def duplicate_stack(
    stack_id: str,
    new_name: str = Body(..., description="Nom du nouveau stack"),
    organization_id: Optional[str] = Body(None, description="ID de l'organisation cible"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> StackResponse:
    """
    Duplique un stack existant.
    """
    original_stack = await StackService.get_by_id(db, stack_id)

    if not original_stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack non trouvé: {stack_id}"
        )

    # Vérifier que le nouveau nom n'existe pas déjà
    target_org_id = organization_id or original_stack.organization_id
    existing = await StackService.get_by_name(db, new_name, target_org_id)

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un stack nommé '{new_name}' existe déjà"
        )

    # Créer la copie
    stack_data = StackCreate(
        name=new_name,
        description=f"Copie de {original_stack.name}: {original_stack.description}",
        template=original_stack.template,
        variables=original_stack.variables,
        version=original_stack.version,
        category=original_stack.category,
        tags=original_stack.tags + ["duplicate"],
        is_public=False,  # Par défaut privé
        organization_id=target_org_id
    )

    new_stack = await StackService.create(db, stack_data)

    return StackResponse.model_validate(new_stack)


@router.delete("/{stack_id}")
async def delete_stack(
    stack_id: str,
    force: bool = Query(False, description="Forcer la suppression même avec déploiements"),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> Dict[str, str]:
    """
    Supprime un stack.

    Par défaut, refuse de supprimer si des déploiements existent.
    Utiliser force=true pour forcer la suppression.
    """
    stack = await StackService.get_by_id(db, stack_id)

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack non trouvé: {stack_id}"
        )

    # Vérifier s'il y a des déploiements
    result = await db.execute(
        select(func.count(Deployment.id))
        .where(Deployment.stack_id == stack_id)
    )
    deployment_count = result.scalar()

    if deployment_count > 0 and not force:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Impossible de supprimer: {deployment_count} déploiement(s) existent. Utilisez force=true pour forcer."
        )

    await db.delete(stack)
    await db.commit()

    return {
        "message": f"Stack '{stack.name}' supprimé avec succès",
        "stack_id": stack_id,
        "deployments_affected": str(deployment_count)
    }


# ============================================================================
# 5. STATISTIQUES ET MONITORING
# ============================================================================

@router.get("/stats/overview", response_model=StacksOverview)
async def get_stacks_overview(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> StacksOverview:
    """
    Vue d'ensemble des statistiques des stacks.
    """
    # Nombre total de stacks
    total_result = await db.execute(select(func.count(Stack.id)))
    total_stacks = total_result.scalar()

    # Stacks publics vs privés
    public_result = await db.execute(
        select(func.count(Stack.id)).where(Stack.is_public == True)
    )
    public_stacks = public_result.scalar()

    # Stacks par catégorie
    category_result = await db.execute(
        select(Stack.category, func.count(Stack.id))
        .group_by(Stack.category)
    )
    stacks_by_category = {cat: count for cat, count in category_result.all()}

    # Stacks les plus déployés
    most_deployed_result = await db.execute(
        select(
            Stack.id,
            Stack.name,
            func.count(Deployment.id).label("deployment_count")
        )
        .join(Deployment, Stack.id == Deployment.stack_id, isouter=True)
        .group_by(Stack.id, Stack.name)
        .order_by(func.count(Deployment.id).desc())
        .limit(5)
    )
    most_deployed = [
        {"stack_id": sid, "name": name, "deployments": count}
        for sid, name, count in most_deployed_result.all()
    ]

    # Stacks récemment ajoutés
    recently_added_result = await db.execute(
        select(Stack)
        .order_by(Stack.created_at.desc())
        .limit(5)
    )
    recently_added = [
        {
            "stack_id": stack.id,
            "name": stack.name,
            "version": stack.version,
            "created_at": stack.created_at.isoformat()
        }
        for stack in recently_added_result.scalars().all()
    ]

    return StacksOverview(
        total_stacks=total_stacks,
        public_stacks=public_stacks,
        private_stacks=total_stacks - public_stacks,
        stacks_by_category=stacks_by_category,
        most_deployed=most_deployed,
        recently_added=recently_added
    )


@router.get("/{stack_id}/usage", response_model=StackUsageStats)
async def get_stack_usage(
    stack_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> StackUsageStats:
    """
    Statistiques d'usage d'un stack spécifique.
    """
    stack = await StackService.get_by_id(db, stack_id)

    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack non trouvé: {stack_id}"
        )

    # Nombre total de déploiements
    total_result = await db.execute(
        select(func.count(Deployment.id))
        .where(Deployment.stack_id == stack_id)
    )
    total_deployments = total_result.scalar()

    # Déploiements réussis
    success_result = await db.execute(
        select(func.count(Deployment.id))
        .where(
            and_(
                Deployment.stack_id == stack_id,
                Deployment.status == "success"
            )
        )
    )
    successful_deployments = success_result.scalar()

    # Déploiements échoués
    failed_result = await db.execute(
        select(func.count(Deployment.id))
        .where(
            and_(
                Deployment.stack_id == stack_id,
                Deployment.status == "failed"
            )
        )
    )
    failed_deployments = failed_result.scalar()

    # Taux de succès
    success_rate = (
        (successful_deployments / total_deployments * 100)
        if total_deployments > 0
        else 0.0
    )

    # Nombre d'organisations utilisant ce stack
    org_result = await db.execute(
        select(func.count(func.distinct(Deployment.organization_id)))
        .where(Deployment.stack_id == stack_id)
    )
    organizations_using = org_result.scalar()

    # Dernier déploiement
    last_dep_result = await db.execute(
        select(Deployment.created_at)
        .where(Deployment.stack_id == stack_id)
        .order_by(Deployment.created_at.desc())
        .limit(1)
    )
    last_deployment = last_dep_result.scalar_one_or_none()

    return StackUsageStats(
        stack_id=stack_id,
        stack_name=stack.name,
        total_deployments=total_deployments,
        successful_deployments=successful_deployments,
        failed_deployments=failed_deployments,
        success_rate=success_rate,
        organizations_using=organizations_using,
        last_deployment=last_deployment.isoformat() if last_deployment else None
    )


# ============================================================================
# 6. RECHERCHE ET SANTÉ
# ============================================================================

@router.get("/health")
async def get_stacks_health(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> Dict[str, Any]:
    """
    Vérifie la santé des stacks et détecte les problèmes.
    """
    stacks_dir = Path(__file__).parent.parent.parent.parent / "stacks_definitions"

    issues = []
    warnings = []

    # Vérifier les définitions YAML
    if stacks_dir.exists():
        for yaml_file in stacks_dir.glob("*.yaml"):
            if yaml_file.name.startswith("_"):
                continue

            try:
                data = StackLoaderService.load_from_yaml(yaml_file)
                StackLoaderService.validate_stack_definition(data)
            except Exception as e:
                issues.append({
                    "type": "validation_error",
                    "file": yaml_file.name,
                    "message": str(e)
                })

    # Vérifier les stacks en DB sans définition YAML
    result = await db.execute(select(Stack))
    db_stacks = {stack.name: stack for stack in result.scalars().all()}

    yaml_stack_names = set()
    if stacks_dir.exists():
        for yaml_file in stacks_dir.glob("*.yaml"):
            if yaml_file.name.startswith("_"):
                continue
            try:
                data = StackLoaderService.load_from_yaml(yaml_file)
                yaml_stack_names.add(data.get("metadata", {}).get("name"))
            except Exception:
                pass

    for stack_name, stack in db_stacks.items():
        if stack_name not in yaml_stack_names:
            warnings.append({
                "type": "orphaned_stack",
                "stack_id": stack.id,
                "stack_name": stack_name,
                "message": "Stack en DB sans définition YAML"
            })

    return {
        "status": "healthy" if not issues else "degraded",
        "total_issues": len(issues),
        "total_warnings": len(warnings),
        "issues": issues,
        "warnings": warnings
    }


@router.get("/search")
async def search_stacks(
    q: Optional[str] = Query(None, description="Terme de recherche"),
    category: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
    is_public: Optional[bool] = Query(None),
    min_version: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_superadmin)
) -> Dict[str, Any]:
    """
    Recherche avancée de stacks.
    """
    query = select(Stack)

    # Filtres
    filters = []

    if q:
        # Recherche texte dans nom ou description
        from sqlalchemy import or_
        filters.append(
            or_(
                Stack.name.ilike(f"%{q}%"),
                Stack.description.ilike(f"%{q}%")
            )
        )

    if category:
        filters.append(Stack.category == category)

    if is_public is not None:
        filters.append(Stack.is_public == is_public)

    if tags:
        # Vérifier si le stack a au moins un des tags
        for tag in tags:
            filters.append(Stack.tags.contains([tag]))

    if filters:
        query = query.where(and_(*filters))

    # Compter le total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Appliquer pagination
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    stacks = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "results": [StackResponse.model_validate(stack) for stack in stacks]
    }
