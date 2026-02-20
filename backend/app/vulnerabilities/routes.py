import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.pagination import PaginationParams
from app.vulnerabilities.models import Vulnerability, VulnerabilityScan

router = APIRouter(prefix="/api/v1/vulnerabilities", tags=["vulnerabilities"])


@router.get("")
async def list_vulnerabilities(
    asset_id: uuid.UUID | None = Query(None),
    severity: str | None = Query(None),
    is_resolved: bool | None = Query(None),
    pagination: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = (
        select(Vulnerability)
        .where(Vulnerability.tenant_id == user.tenant_id)
    )
    if asset_id:
        base = base.where(Vulnerability.asset_id == asset_id)
    if severity:
        base = base.where(Vulnerability.severity == severity)
    if is_resolved is not None:
        base = base.where(Vulnerability.is_resolved == is_resolved)

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Vulnerability.first_detected_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    vulns = result.scalars().all()

    items = [
        {
            "id": str(v.id),
            "asset_id": str(v.asset_id),
            "software_name": v.software_name,
            "software_version": v.software_version,
            "cve_id": v.cve_id,
            "severity": v.severity,
            "score": v.score,
            "summary": v.summary,
            "details_url": v.details_url,
            "fixed_version": v.fixed_version,
            "is_resolved": v.is_resolved,
            "first_detected_at": v.first_detected_at.isoformat(),
        }
        for v in vulns
    ]
    return {
        "items": items,
        "total": total,
        "page": pagination.page,
        "page_size": pagination.page_size,
        "pages": (total + pagination.page_size - 1) // pagination.page_size,
    }


@router.get("/summary")
async def vulnerability_summary(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get vulnerability counts by severity across all assets."""
    counts = await db.execute(
        select(
            Vulnerability.severity,
            func.count().label("count"),
        )
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.is_resolved == False,  # noqa: E712
        )
        .group_by(Vulnerability.severity)
    )

    severity_counts = {row.severity: row.count for row in counts.all()}

    total = sum(severity_counts.values())
    return {
        "total": total,
        "critical": severity_counts.get("critical", 0),
        "high": severity_counts.get("high", 0),
        "medium": severity_counts.get("medium", 0),
        "low": severity_counts.get("low", 0),
        "unknown": severity_counts.get("unknown", 0),
    }


@router.get("/by-asset")
async def vulnerabilities_by_asset(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get vulnerability counts grouped by asset."""
    from app.assets.models import Asset

    result = await db.execute(
        select(
            Vulnerability.asset_id,
            Asset.hostname,
            Vulnerability.severity,
            func.count().label("count"),
        )
        .join(Asset, Asset.id == Vulnerability.asset_id)
        .where(
            Vulnerability.tenant_id == user.tenant_id,
            Vulnerability.is_resolved == False,  # noqa: E712
        )
        .group_by(Vulnerability.asset_id, Asset.hostname, Vulnerability.severity)
    )
    rows = result.all()

    # Group by asset
    assets: dict = {}
    for row in rows:
        aid = str(row.asset_id)
        if aid not in assets:
            assets[aid] = {
                "asset_id": aid,
                "hostname": row.hostname,
                "critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0,
            }
        assets[aid][row.severity] = assets[aid].get(row.severity, 0) + row.count
        assets[aid]["total"] += row.count

    return sorted(assets.values(), key=lambda a: a["total"], reverse=True)


@router.get("/scans")
async def list_scans(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(VulnerabilityScan)
        .where(VulnerabilityScan.tenant_id == user.tenant_id)
        .order_by(VulnerabilityScan.started_at.desc())
        .limit(50)
    )
    scans = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "asset_id": str(s.asset_id) if s.asset_id else None,
            "status": s.status,
            "packages_scanned": s.packages_scanned,
            "vulnerabilities_found": s.vulnerabilities_found,
            "error": s.error,
            "started_at": s.started_at.isoformat(),
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        }
        for s in scans
    ]


@router.post("/scan")
async def trigger_scan(
    user: User = Depends(get_current_user),
):
    """Trigger an immediate vulnerability scan of all assets."""
    from app.tasks.vuln_tasks import scan_all_assets
    scan_all_assets.delay()
    return {"status": "scan_queued"}


@router.post("/{vuln_id}/resolve")
async def resolve_vulnerability(
    vuln_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.exceptions import NotFoundError

    result = await db.execute(
        select(Vulnerability).where(
            Vulnerability.id == vuln_id,
            Vulnerability.tenant_id == user.tenant_id,
        )
    )
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise NotFoundError("Vulnerability not found")

    vuln.is_resolved = True
    vuln.resolved_at = datetime.now(timezone.utc)
    return {"status": "resolved"}
