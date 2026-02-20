import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import NotFoundError
from app.reports.models import ComplianceScore, Report, ReportSchedule
from app.reports.schemas import (
    ComplianceScoreResponse,
    ReportCreate,
    ReportResponse,
    ReportScheduleCreate,
    ReportScheduleResponse,
)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("", response_model=list[ReportResponse])
async def list_reports(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report)
        .where(Report.tenant_id == user.tenant_id)
        .order_by(Report.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("", response_model=ReportResponse)
async def generate_report(
    body: ReportCreate,
    user: User = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    valid_types = [
        "security_posture",
        "asset_inventory",
        "uptime_summary",
        "vulnerability_report",
    ]
    if body.report_type not in valid_types:
        from app.exceptions import BadRequestError

        raise BadRequestError(f"Invalid report type. Must be one of: {', '.join(valid_types)}")

    report = Report(
        tenant_id=user.tenant_id,
        created_by=user.id,
        report_type=body.report_type,
        format=body.format,
        status="generating",
        parameters=body.parameters,
    )
    db.add(report)
    await db.flush()

    # Queue Celery task
    try:
        from app.tasks.report_tasks import generate_report as generate_report_task

        generate_report_task.delay(str(report.id))
    except Exception:
        report.status = "queued"

    return report


@router.delete("/{report_id}")
async def delete_report(
    report_id: uuid.UUID,
    user: User = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.tenant_id == user.tenant_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report not found")
    await db.delete(report)
    return {"status": "deleted"}


@router.get("/{report_id}/download")
async def download_report(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Report).where(
            Report.id == report_id,
            Report.tenant_id == user.tenant_id,
        )
    )
    report = result.scalar_one_or_none()
    if not report:
        raise NotFoundError("Report not found")
    if report.status != "ready" or not report.file_path:
        from app.exceptions import BadRequestError

        raise BadRequestError("Report is not ready for download")
    return FileResponse(report.file_path, filename=f"{report.report_type}.{report.format}")


@router.get("/compliance", response_model=ComplianceScoreResponse | None)
async def get_compliance_score(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ComplianceScore)
        .where(ComplianceScore.tenant_id == user.tenant_id)
        .order_by(ComplianceScore.calculated_at.desc())
        .limit(1)
    )
    score = result.scalar_one_or_none()
    if not score:
        return None
    return score


@router.get("/compliance/history", response_model=list[ComplianceScoreResponse])
async def get_compliance_history(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(ComplianceScore)
        .where(
            ComplianceScore.tenant_id == user.tenant_id,
            ComplianceScore.calculated_at >= cutoff,
        )
        .order_by(ComplianceScore.calculated_at.desc())
    )
    return result.scalars().all()


# --- Schedules ---

@router.get("/schedules", response_model=list[ReportScheduleResponse])
async def list_schedules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReportSchedule)
        .where(ReportSchedule.tenant_id == user.tenant_id)
        .order_by(ReportSchedule.created_at.desc())
    )
    return result.scalars().all()


@router.post("/schedules", response_model=ReportScheduleResponse)
async def create_schedule(
    body: ReportScheduleCreate,
    user: User = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timedelta, timezone

    if body.frequency not in ("weekly", "monthly"):
        from app.exceptions import BadRequestError

        raise BadRequestError("Frequency must be 'weekly' or 'monthly'")

    next_run = datetime.now(timezone.utc) + (
        timedelta(weeks=1) if body.frequency == "weekly" else timedelta(days=30)
    )

    schedule = ReportSchedule(
        tenant_id=user.tenant_id,
        created_by=user.id,
        report_type=body.report_type,
        frequency=body.frequency,
        recipients=body.recipients,
        next_run_at=next_run,
    )
    db.add(schedule)
    await db.flush()
    return schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: uuid.UUID,
    user: User = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise NotFoundError("Schedule not found")
    await db.delete(schedule)
    return {"status": "deleted"}
