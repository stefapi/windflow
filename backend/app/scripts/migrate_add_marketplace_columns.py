"""
Script de migration pour ajouter les colonnes marketplace manquantes à la table stacks.
"""

import asyncio
import sys
from pathlib import Path

# Ajouter le répertoire parent au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import db
from sqlalchemy import text

async def main():
    """Ajoute les colonnes manquantes à la table stacks."""

    print("=" * 60)
    print("Migration : Ajout des colonnes marketplace à la table stacks")
    print("=" * 60)

    await db.connect()

    try:
        async with db.session() as session:
            # Liste des colonnes à ajouter
            columns_to_add = [
                ("icon_url", "VARCHAR(500)"),
                ("screenshots", "TEXT"),  # JSON sera stocké comme TEXT en SQLite
                ("documentation_url", "VARCHAR(500)"),
                ("author", "VARCHAR(255)"),
                ("license", "VARCHAR(100) DEFAULT 'MIT'"),
            ]

            for column_name, column_type in columns_to_add:
                try:
                    sql = text(f"ALTER TABLE stacks ADD COLUMN {column_name} {column_type}")
                    await session.execute(sql)
                    print(f"✅ Colonne '{column_name}' ajoutée avec succès")
                except Exception as e:
                    if "duplicate column name" in str(e).lower():
                        print(f"⚠️  Colonne '{column_name}' existe déjà")
                    else:
                        print(f"❌ Erreur lors de l'ajout de '{column_name}': {e}")

            await session.commit()
            print("=" * 60)
            print("Migration terminée avec succès !")
            print("=" * 60)

    except Exception as e:
        print(f"❌ Erreur fatale: {e}")
        raise
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
