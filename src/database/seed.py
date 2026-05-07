from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.models.accounts import UserGroup, UserGroupEnum


async def seed_user_groups(db: AsyncSession) -> None:
    for group_name in UserGroupEnum:
        result = await db.execute(select(UserGroup).where(UserGroup.name == group_name))
        if not result.scalar_one_or_none():
            db.add(UserGroup(name=group_name))
    await db.commit()
