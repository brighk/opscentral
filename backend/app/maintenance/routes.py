import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.maintenance.models import MaintenanceWindow
from app.maintenance.schemas import (
    MaintenanceWindowCreate,
    MaintenanceWindowUpdate,
    MaintenanceWindowResponse,
)

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"])


@router.get("", response_model=list[MaintenanceWindowResponse])
async def list_windows(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaintenanceWindow)
        .where(MaintenanceWindow.tenant_id == user.tenant_id)
        .order_by(MaintenanceWindow.start_time.desc())
    )
    return result.scalars().all()


@router.get("/active", response_model=list[MaintenanceWindowResponse])
async def list_active_windows(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return windows that are active right now (used by frontend banner)."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.tenant_id == user.tenant_id,
            MaintenanceWindow.is_active.is_(True),
            MaintenanceWindow.start_time <= now,
            MaintenanceWindow.end_time >= now,
        )
    )
    return result.scalars().all()


@router.post("", response_model=MaintenanceWindowResponse)
async def create_window(
    data: MaintenanceWindowCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    window = MaintenanceWindow(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        start_time=data.start_time,
        end_time=data.end_time,
        scope=data.scope,
        scope_ids=data.scope_ids,
        is_active=data.is_active,
        created_by=user.id,
    )
    db.add(window)
    await db.commit()
    await db.refresh(window)
    return window


@router.put("/{window_id}", response_model=MaintenanceWindowResponse)
async def update_window(
    window_id: uuid.UUID,
    data: MaintenanceWindowUpdate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.id == window_id,
            MaintenanceWindow.tenant_id == user.tenant_id,
        )
    )
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    if data.name is not None:
        window.name = data.name
    if data.description is not None:
        window.description = data.description
    if data.start_time is not None:
        window.start_time = data.start_time
    if data.end_time is not None:
        window.end_time = data.end_time
    if data.scope is not None:
        window.scope = data.scope
    if data.scope_ids is not None:
        window.scope_ids = data.scope_ids
    if data.is_active is not None:
        window.is_active = data.is_active

    await db.commit()
    await db.refresh(window)
    return window


@router.delete("/{window_id}")
async def delete_window(
    window_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MaintenanceWindow).where(
            MaintenanceWindow.id == window_id,
            MaintenanceWindow.tenant_id == user.tenant_id,
        )
    )
    window = result.scalar_one_or_none()
    if not window:
        raise HTTPException(status_code=404, detail="Maintenance window not found")

    await db.delete(window)
    await db.commit()
    return {"detail": "Maintenance window deleted"}
