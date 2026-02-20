import uuid

from fastapi import Depends, Header
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.auth.security import decode_token
from app.db.session import get_db
from app.exceptions import ForbiddenError, UnauthorizedError

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError()
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")

    result = await db.execute(
        select(User).options(selectinload(User.tenant)).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


async def get_agent_tenant_id(
    x_agent_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> tuple[uuid.UUID, uuid.UUID]:
    """Validate agent API key and return (agent_id, tenant_id)."""
    from app.agents.models import Agent

    result = await db.execute(
        select(Agent).where(Agent.api_key == x_agent_key, Agent.is_active == True)  # noqa: E712
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise UnauthorizedError("Invalid agent API key")
    return agent.id, agent.tenant_id


async def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        HTTPBearer(auto_error=False)
    ),
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate via JWT Bearer token or third-party API key."""
    if credentials:
        return await get_current_user(credentials, db)

    if x_api_key:
        import hashlib
        from datetime import datetime, timezone

        from app.api_keys.models import APIKey

        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        result = await db.execute(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active == True)  # noqa: E712
        )
        api_key = result.scalar_one_or_none()
        if not api_key:
            raise UnauthorizedError("Invalid API key")
        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("API key expired")

        api_key.last_used_at = datetime.now(timezone.utc)

        # Load the user who created this key as the acting user
        from app.auth.models import User as UserModel

        user_result = await db.execute(
            select(UserModel)
            .options(selectinload(UserModel.tenant))
            .where(UserModel.id == api_key.created_by)
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise UnauthorizedError("API key owner not found or inactive")
        return user

    raise UnauthorizedError("No authentication provided")


def require_role(*roles: str):
    """Dependency that checks the user has one of the specified roles.

    Usage:
        @router.post("/something")
        async def do_something(user: User = Depends(require_role("admin", "operator"))):
            ...
    """
    async def _check_role(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user = await get_current_user(credentials, db)
        if user.role not in roles:
            raise ForbiddenError(f"Requires role: {', '.join(roles)}")
        return user
    return _check_role
