from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import decode_token
from app.database.session import get_db
from app.repositories.user_repository import UserRepository

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token payload")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User not found")

    if not user.is_active:
        raise UnauthorizedError("User account is deactivated")

    return user


async def require_role(required_roles: list[str]):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise ForbiddenError(
                f"This action requires one of: {', '.join(required_roles)}"
            )
        return current_user
    return role_checker


async def get_admin_or_pm(current_user=Depends(get_current_user)):
    if current_user.role not in ["admin", "procurement_manager"]:
        raise ForbiddenError("This action requires admin or procurement_manager role")
    return current_user


async def get_admin(current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise ForbiddenError("This action requires admin role")
    return current_user
