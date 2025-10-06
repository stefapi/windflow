"""
Script de chargement des stacks depuis des définitions YAML.

Ce script charge tous les stacks définis dans le répertoire stacks_definitions/
et les importe dans la base de données du marketplace WindFlow.

Usage:
    python -m app.scripts.seed_stacks [OPTIONS]

Options:
    --list          Liste les stacks disponibles sans les importer
    --stack NAME    Charger uniquement le stack spécifié
    --force         Forcer la mise à jour des stacks existants
    --dry-run       Valider les fichiers sans importer
    --help          Afficher cette aide
"""

import asyncio
import sys
from pathlib import Path
from argparse import ArgumentParser

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import AsyncSessionLocal
from app.services.stack_service import StackService
from app.services.stack_loader_service import StackLoaderService
from app.models.organization import Organization
from sqlalchemy import select


async def get_default_organization(db):
    """Récupère l'organisation par défaut."""
    result = await db.execute(select(Organization))
    org = result.scalar_one_or_none()

    if not org:
        print("❌ Aucune organisation trouvée.")
        print("   Veuillez d'abord initialiser la base de données avec seed_database.")
        sys.exit(1)

    return org


async def list_stacks():
    """Liste tous les stacks disponibles dans le répertoire."""
    stacks_dir = Path(__file__).parent.parent / "stacks_definitions"

    if not stacks_dir.exists():
        print(f"❌ Répertoire non trouvé: {stacks_dir}")
        return

    yaml_files = list(stacks_dir.glob("*.yaml"))

    if not yaml_files:
        print(f"ℹ️  Aucun fichier YAML trouvé dans {stacks_dir}")
        return

    print(f"\n📦 Stacks disponibles ({len(yaml_files)}):\n")

    for yaml_file in yaml_files:
        if yaml_file.name.startswith("_"):
            continue

        try:
            data = StackLoaderService.load_from_yaml(yaml_file)
            metadata = data.get("metadata", {})

            print(f"  • {yaml_file.name}")
            print(f"    Nom: {metadata.get('name', 'N/A')}")
            print(f"    Version: {metadata.get('version', 'N/A')}")
            print(f"    Catégorie: {metadata.get('category', 'N/A')}")
            print(f"    Public: {'Oui' if metadata.get('is_public') else 'Non'}")
            print(f"    Variables: {len(data.get('variables', {}))}")
            print()

        except Exception as e:
            print(f"  ✗ {yaml_file.name} - Erreur: {e}\n")


async def validate_stacks():
    """Valide tous les stacks sans les importer."""
    stacks_dir = Path(__file__).parent.parent / "stacks_definitions"

    if not stacks_dir.exists():
        print(f"❌ Répertoire non trouvé: {stacks_dir}")
        return False

    yaml_files = list(stacks_dir.glob("*.yaml"))

    if not yaml_files:
        print(f"ℹ️  Aucun fichier YAML trouvé dans {stacks_dir}")
        return True

    print(f"\n🔍 Validation de {len(yaml_files)} stack(s)...\n")

    errors = []
    for yaml_file in yaml_files:
        if yaml_file.name.startswith("_"):
            continue

        try:
            data = StackLoaderService.load_from_yaml(yaml_file)
            StackLoaderService.validate_stack_definition(data)
            print(f"  ✓ {yaml_file.name} - Valide")

        except Exception as e:
            errors.append((yaml_file.name, str(e)))
            print(f"  ✗ {yaml_file.name} - Erreur: {e}")

    if errors:
        print(f"\n❌ {len(errors)} erreur(s) de validation trouvée(s)")
        return False
    else:
        print(f"\n✅ Tous les stacks sont valides")
        return True


async def import_single_stack(stack_name: str, force: bool = False):
    """Importe un stack spécifique."""
    stacks_dir = Path(__file__).parent.parent / "stacks_definitions"
    yaml_file = stacks_dir / f"{stack_name}.yaml"

    if not yaml_file.exists():
        print(f"❌ Stack non trouvé: {yaml_file}")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        org = await get_default_organization(db)

        print(f"\n📦 Import de {stack_name}...\n")

        try:
            stack, created = await StackService.upsert_from_yaml(
                db,
                yaml_file,
                org.id,
                force_update=force
            )

            if created:
                print(f"✅ Stack créé avec succès: {stack.name}")
            else:
                if force:
                    print(f"↻ Stack mis à jour: {stack.name}")
                else:
                    print(f"⊝ Stack déjà existant (utilisez --force pour mettre à jour): {stack.name}")

            print(f"   ID: {stack.id}")
            print(f"   Version: {stack.version}")
            print(f"   Catégorie: {stack.category}")

        except Exception as e:
            print(f"❌ Erreur lors de l'import: {e}")
            sys.exit(1)


async def import_all_stacks(force: bool = False):
    """Importe tous les stacks du répertoire."""
    stacks_dir = Path(__file__).parent.parent / "stacks_definitions"

    if not stacks_dir.exists():
        print(f"❌ Répertoire non trouvé: {stacks_dir}")
        sys.exit(1)

    async with AsyncSessionLocal() as db:
        org = await get_default_organization(db)

        print(f"\n📦 Import des stacks depuis {stacks_dir}...")
        print(f"   Organisation: {org.name} ({org.id})\n")

        stats = await StackService.import_all_from_directory(
            db,
            stacks_dir,
            org.id,
            force_update=force
        )

        # Afficher les statistiques
        print(f"\n📊 Résultat de l'import:\n")
        print(f"  ✓ Créés: {stats['created']}")
        print(f"  ↻ Mis à jour: {stats['updated']}")
        print(f"  ⊝ Ignorés: {stats['skipped']}")
        print(f"  ✗ Erreurs: {len(stats['errors'])}")

        if stats['errors']:
            print(f"\n⚠️  Erreurs détaillées:\n")
            for error in stats['errors']:
                print(f"  • {error['stack']}: {error['error']}")

        if stats['created'] or stats['updated']:
            print(f"\n✅ Import terminé avec succès!")
        elif stats['skipped']:
            print(f"\nℹ️  Tous les stacks existaient déjà (utilisez --force pour mettre à jour)")


def main():
    """Point d'entrée principal du script."""
    parser = ArgumentParser(
        description="Charge les stacks depuis des définitions YAML"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="Lister les stacks disponibles sans les importer"
    )

    parser.add_argument(
        "--stack",
        type=str,
        help="Charger uniquement le stack spécifié (nom du fichier sans .yaml)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer la mise à jour des stacks existants"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Valider les fichiers sans importer"
    )

    args = parser.parse_args()

    # Afficher le titre
    print("\n" + "=" * 60)
    print("  WindFlow - Chargement des Stacks Marketplace")
    print("=" * 60)

    try:
        if args.list:
            # Lister les stacks disponibles
            asyncio.run(list_stacks())

        elif args.dry_run:
            # Valider sans importer
            success = asyncio.run(validate_stacks())
            sys.exit(0 if success else 1)

        elif args.stack:
            # Importer un stack spécifique
            asyncio.run(import_single_stack(args.stack, args.force))

        else:
            # Importer tous les stacks
            asyncio.run(import_all_stacks(args.force))

        print("\n" + "=" * 60 + "\n")

    except KeyboardInterrupt:
        print("\n\n⚠️  Import annulé par l'utilisateur\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erreur inattendue: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
