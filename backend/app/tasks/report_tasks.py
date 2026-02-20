import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.report_tasks.generate_report")
def generate_report(report_id: str):
    """Generate a report (called async per report)."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    from app.config import settings
    from app.reports.models import Report

    engine = create_engine(settings.DATABASE_URL_SYNC)

    with Session(engine) as db:
        result = db.execute(select(Report).where(Report.id == uuid.UUID(report_id)))
        report = result.scalar_one_or_none()
        if not report:
            logger.error(f"Report {report_id} not found")
            return

        try:
            from app.reports.generators import (
                generate_asset_inventory,
                generate_security_posture,
                generate_uptime_summary,
                generate_vulnerability_report,
            )

            generators = {
                "security_posture": generate_security_posture,
                "asset_inventory": generate_asset_inventory,
                "uptime_summary": generate_uptime_summary,
                "vulnerability_report": generate_vulnerability_report,
            }

            gen_func = generators.get(report.report_type)
            if not gen_func:
                report.status = "failed"
                report.error = f"Unknown report type: {report.report_type}"
                db.commit()
                return

            content = gen_func(report.tenant_id, db)

            # Save as text file for now (WeasyPrint PDF generation is optional)
            import os
            import tempfile

            report_dir = os.path.join(tempfile.gettempdir(), "opscentral_reports")
            os.makedirs(report_dir, exist_ok=True)

            ext = "txt" if report.format == "csv" else "txt"
            file_path = os.path.join(report_dir, f"{report.id}.{ext}")
            with open(file_path, "w") as f:
                f.write(content)

            report.file_path = file_path
            report.status = "ready"
            db.commit()
            logger.info(f"Report {report_id} generated successfully")

        except Exception as e:
            report.status = "failed"
            report.error = str(e)[:1000]
            db.commit()
            logger.error(f"Report {report_id} failed: {e}")

    engine.dispose()


@celery.task(name="app.tasks.report_tasks.run_scheduled_reports")
def run_scheduled_reports():
    """Check for due report schedules and queue generation."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    from app.config import settings
    from app.reports.models import Report, ReportSchedule

    engine = create_engine(settings.DATABASE_URL_SYNC)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        result = db.execute(
            select(ReportSchedule).where(
                ReportSchedule.is_active == True,  # noqa: E712
                ReportSchedule.next_run_at <= now,
            )
        )
        schedules = result.scalars().all()

        for schedule in schedules:
            report = Report(
                tenant_id=schedule.tenant_id,
                created_by=schedule.created_by,
                report_type=schedule.report_type,
                format="pdf",
                status="generating",
            )
            db.add(report)
            db.flush()

            generate_report.delay(str(report.id))

            # Update next_run_at
            if schedule.frequency == "weekly":
                schedule.next_run_at = now + timedelta(weeks=1)
            else:
                schedule.next_run_at = now + timedelta(days=30)

        db.commit()

    engine.dispose()
    logger.info(f"Processed {len(schedules)} scheduled reports")


@celery.task(name="app.tasks.report_tasks.calculate_compliance_scores")
def calculate_compliance_scores():
    """Calculate compliance scores for all tenants (daily at 3 AM)."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from sqlalchemy import create_engine

    from app.auth.models import Tenant
    from app.config import settings
    from app.reports.generators import calculate_compliance_score
    from app.reports.models import ComplianceScore

    engine = create_engine(settings.DATABASE_URL_SYNC)

    with Session(engine) as db:
        result = db.execute(
            select(Tenant).where(Tenant.is_active == True)  # noqa: E712
        )
        tenants = result.scalars().all()

        for tenant in tenants:
            try:
                scores = calculate_compliance_score(tenant.id, db)
                db.add(ComplianceScore(tenant_id=tenant.id, **scores))
            except Exception as e:
                logger.error(f"Compliance score failed for tenant {tenant.id}: {e}")

        db.commit()

    engine.dispose()
    logger.info(f"Calculated compliance scores for {len(tenants)} tenants")
