"""Script pour vérifier les stacks importés."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.database import db
from app.models.stack import Stack
from app.models.organization import Organization
from app.models.user import User
from app.models.stack_review import StackReview
from app.models.user_favorite import user_favorites
from app.models.deployment import Deployment
from app.models.target import Target
from sqlalchemy import select

async def main():
    await db.connect()

    try:
        async with db.session() as session:
            result = await session.execute(select(Stack))
            stacks = result.scalars().all()

            print(f"\n✅ Nombre de stacks dans la marketplace: {len(stacks)}\n")

            for stack in stacks:
                print(f"📦 {stack.name} (v{stack.version})")
                print(f"   Catégorie: {stack.category}")
                print(f"   Description: {stack.description[:100]}...")
                print(f"   Public: {'Oui' if stack.is_public else 'Non'}")
                print(f"   Tags: {', '.join(stack.tags)}")
                print(f"   Variables: {len(stack.variables)} configurables")
                print()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
