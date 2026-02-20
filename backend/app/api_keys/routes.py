import hashlib
import secrets

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_keys.models import APIKey
from app.api_keys.schemas import APIKeyCreate, APIKeyCreatedResponse, APIKeyResponse
from app.auth.models import User
from app.db.session import get_db
from app.dependencies import require_role
from app.exceptions import NotFoundError

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


@router.post("", response_model=APIKeyCreatedResponse)
async def create_api_key(
    body: APIKeyCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    raw_key = f"oc_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(raw_key)
    key_prefix = raw_key[:8]

    api_key = APIKey(
        tenant_id=user.tenant_id,
        created_by=user.id,
        name=body.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    db.add(api_key)
    await db.flush()

    return APIKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=key_prefix,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
        raw_key=raw_key,
    )


@router.get("", response_model=list[APIKeyResponse])
async def list_api_keys(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(APIKey)
        .where(APIKey.tenant_id == user.tenant_id)
        .order_by(APIKey.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    import uuid as _uuid

    result = await db.execute(
        select(APIKey).where(
            APIKey.id == _uuid.UUID(key_id),
            APIKey.tenant_id == user.tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise NotFoundError("API key not found")

    api_key.is_active = False
    return {"status": "revoked"}
