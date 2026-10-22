import re
import uuid
from datetime import UTC

from fastapi import APIRouter, Depends
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Tenant, User
from app.auth.schemas import (
    InviteUserRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserRoleRequest,
    UserResponse,
)
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from app.pagination import PaginationParams

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}-{uuid.uuid4().hex[:6]}"


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise BadRequestError("Email already registered")

    tenant = Tenant(
        name=body.company_name,
        slug=_slugify(body.company_name),
    )
    db.add(tenant)
    await db.flush()

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        is_admin=True,
        tenant_id=tenant.id,
    )
    db.add(user)
    await db.flush()

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(tenant.id)),
        refresh_token=create_refresh_token(str(user.id), str(tenant.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id)),
        refresh_token=create_refresh_token(str(user.id), str(user.tenant_id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")
    except JWTError:
        raise UnauthorizedError("Invalid refresh token") from None

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return TokenResponse(
        access_token=create_access_token(str(user.id), str(user.tenant_id)),
        refresh_token=create_refresh_token(str(user.id), str(user.tenant_id)),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_admin=user.is_admin,
        role=user.role,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.name if user.tenant else None,
    )


# --- User Management (admin only) ---


@router.get("/users")
async def list_users(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.post("/users/invite")
async def invite_user(
    body: InviteUserRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Invite a new user to the tenant."""
    if body.role not in ("admin", "operator", "viewer"):
        raise BadRequestError("Role must be admin, operator, or viewer")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise BadRequestError("Email already registered")

    new_user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=body.role,
        is_admin=(body.role == "admin"),
        tenant_id=user.tenant_id,
    )
    db.add(new_user)
    await db.flush()

    # Audit log
    from datetime import datetime

    from app.auth.audit_models import AuditLog

    db.add(
        AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            user_email=user.email,
            action="user.invite",
            resource_type="user",
            resource_id=str(new_user.id),
            details={"invited_email": body.email, "role": body.role},
            performed_at=datetime.now(UTC),
        )
    )

    return {"status": "invited", "user_id": str(new_user.id)}


@router.put("/users/{target_user_id}/role")
async def update_user_role(
    target_user_id: uuid.UUID,
    body: UpdateUserRoleRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    if body.role not in ("admin", "operator", "viewer"):
        raise BadRequestError("Role must be admin, operator, or viewer")

    result = await db.execute(
        select(User).where(
            User.id == target_user_id,
            User.tenant_id == user.tenant_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")

    if target.id == user.id:
        raise BadRequestError("Cannot change your own role")

    target.role = body.role
    target.is_admin = body.role == "admin"

    # Audit log
    from datetime import datetime

    from app.auth.audit_models import AuditLog

    db.add(
        AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            user_email=user.email,
            action="user.role_change",
            resource_type="user",
            resource_id=str(target.id),
            details={"new_role": body.role, "target_email": target.email},
            performed_at=datetime.now(UTC),
        )
    )

    return {"status": "updated", "role": body.role}


@router.delete("/users/{target_user_id}")
async def deactivate_user(
    target_user_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.id == target_user_id,
            User.tenant_id == user.tenant_id,
        )
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")
    if target.id == user.id:
        raise BadRequestError("Cannot deactivate yourself")

    target.is_active = False
    return {"status": "deactivated"}


@router.get("/audit-log")
async def get_audit_log(
    pagination: PaginationParams = Depends(),
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func as sa_func

    from app.auth.audit_models import AuditLog

    base = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    total_result = await db.execute(select(sa_func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(AuditLog.performed_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    logs = result.scalars().all()
    items = [
        {
            "id": log.id,
            "user_email": log.user_email,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "details": log.details,
            "performed_at": log.performed_at.isoformat(),
        }
        for log in logs
    ]
    return {
        "items": items,
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "pages": (total + pagination.page_size - 1) // pagination.page_size,
    }
