import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.models import User
from app.dashboards.models import CustomDashboard, DashboardWidget
from app.db.session import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError

router = APIRouter(prefix="/api/v1/dashboards", tags=["dashboards"])


@router.get("")
async def list_dashboards(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomDashboard)
        .where(CustomDashboard.tenant_id == user.tenant_id)
        .order_by(CustomDashboard.is_default.desc(), CustomDashboard.created_at.desc())
    )
    dashboards = result.scalars().all()
    return [
        {
            "id": str(d.id),
            "name": d.name,
            "description": d.description,
            "is_default": d.is_default,
            "created_at": d.created_at.isoformat(),
        }
        for d in dashboards
    ]


@router.post("")
async def create_dashboard(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    dashboard = CustomDashboard(
        tenant_id=user.tenant_id,
        created_by=user.id,
        name=body.get("name", "New Dashboard"),
        description=body.get("description"),
    )
    db.add(dashboard)
    await db.flush()

    # Add widgets if provided
    for w in body.get("widgets", []):
        widget = DashboardWidget(
            dashboard_id=dashboard.id,
            widget_type=w.get("widget_type", "status_card"),
            title=w.get("title", "Widget"),
            config=w.get("config", {}),
            position_x=w.get("position_x", 0),
            position_y=w.get("position_y", 0),
            width=w.get("width", 6),
            height=w.get("height", 4),
        )
        db.add(widget)

    return {"id": str(dashboard.id), "name": dashboard.name}


@router.get("/{dashboard_id}")
async def get_dashboard(
    dashboard_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomDashboard)
        .options(selectinload(CustomDashboard.widgets))
        .where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise NotFoundError("Dashboard not found")

    return {
        "id": str(dashboard.id),
        "name": dashboard.name,
        "description": dashboard.description,
        "is_default": dashboard.is_default,
        "widgets": [
            {
                "id": str(w.id),
                "widget_type": w.widget_type,
                "title": w.title,
                "config": w.config,
                "position_x": w.position_x,
                "position_y": w.position_y,
                "width": w.width,
                "height": w.height,
            }
            for w in sorted(dashboard.widgets, key=lambda w: (w.position_y, w.position_x))
        ],
    }


@router.put("/{dashboard_id}")
async def update_dashboard(
    dashboard_id: uuid.UUID,
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomDashboard)
        .options(selectinload(CustomDashboard.widgets))
        .where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise NotFoundError("Dashboard not found")

    if "name" in body:
        dashboard.name = body["name"]
    if "description" in body:
        dashboard.description = body["description"]

    # Replace widgets if provided
    if "widgets" in body:
        # Delete old widgets
        for w in dashboard.widgets:
            await db.delete(w)
        await db.flush()

        for w in body["widgets"]:
            widget = DashboardWidget(
                dashboard_id=dashboard.id,
                widget_type=w.get("widget_type", "status_card"),
                title=w.get("title", "Widget"),
                config=w.get("config", {}),
                position_x=w.get("position_x", 0),
                position_y=w.get("position_y", 0),
                width=w.get("width", 6),
                height=w.get("height", 4),
            )
            db.add(widget)

    return {"status": "updated"}


@router.post("/{dashboard_id}/set-default")
async def set_default_dashboard(
    dashboard_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Unset all defaults for this tenant
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.tenant_id == user.tenant_id,
            CustomDashboard.is_default == True,  # noqa: E712
        )
    )
    for d in result.scalars().all():
        d.is_default = False

    # Set the new default
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise NotFoundError("Dashboard not found")

    dashboard.is_default = True
    return {"status": "set_default"}


@router.delete("/{dashboard_id}")
async def delete_dashboard(
    dashboard_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    dashboard = result.scalar_one_or_none()
    if not dashboard:
        raise NotFoundError("Dashboard not found")
    await db.delete(dashboard)
    return {"status": "deleted"}


@router.post("/{dashboard_id}/widgets")
async def add_widget(
    dashboard_id: uuid.UUID,
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CustomDashboard).where(
            CustomDashboard.id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Dashboard not found")

    widget = DashboardWidget(
        dashboard_id=dashboard_id,
        widget_type=body.get("widget_type", "status_card"),
        title=body.get("title", "Widget"),
        config=body.get("config", {}),
        position_x=body.get("position_x", 0),
        position_y=body.get("position_y", 0),
        width=body.get("width", 6),
        height=body.get("height", 4),
    )
    db.add(widget)
    await db.flush()
    return {"id": str(widget.id), "widget_type": widget.widget_type}


@router.delete("/{dashboard_id}/widgets/{widget_id}")
async def remove_widget(
    dashboard_id: uuid.UUID,
    widget_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DashboardWidget)
        .join(CustomDashboard)
        .where(
            DashboardWidget.id == widget_id,
            DashboardWidget.dashboard_id == dashboard_id,
            CustomDashboard.tenant_id == user.tenant_id,
        )
    )
    widget = result.scalar_one_or_none()
    if not widget:
        raise NotFoundError("Widget not found")
    await db.delete(widget)
    return {"status": "deleted"}
