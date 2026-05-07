from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from src.database.models.accounts import UserGroupEnum, User, UserGroup
from src.database.session import get_db
from src.security.dependencies import get_current_user


class RoleChecker:
    def __init__(self, allowed_roles: list[UserGroupEnum]):
        self.allowed_roles = allowed_roles

    async def __call__(
        self,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        result = await db.execute(
            select(UserGroup).where(UserGroup.id == current_user.group_id)
        )
        group = result.scalars().first()

        if not group or group.name not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have enough permissions to perform this action.",
            )
        return current_user
