import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assets.models import Asset
from app.assets.schemas import AssetDetailResponse, AssetResponse
from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("", response_model=PaginatedResponse[AssetResponse])
async def list_assets(
    pagination: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Asset).where(Asset.tenant_id == user.tenant_id)
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Asset.hostname).offset(pagination.offset).limit(pagination.page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.get("/{asset_id}", response_model=AssetDetailResponse)
async def get_asset(
    asset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.software))
        .where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset not found")
    return asset


@router.get("/{asset_id}/software")
async def get_asset_software(
    asset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Asset)
        .options(selectinload(Asset.software))
        .where(Asset.id == asset_id, Asset.tenant_id == user.tenant_id)
    )
    asset = result.scalar_one_or_none()
    if not asset:
        raise NotFoundError("Asset not found")
    return [
        {"name": s.name, "version": s.version, "publisher": s.publisher} for s in asset.software
    ]
