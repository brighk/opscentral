"""Sync report generation functions.

These are called from Celery tasks using the sync database session.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def calculate_compliance_score(tenant_id: uuid.UUID, db: Session) -> dict:
    """Calculate compliance sub-scores for a tenant."""
    from app.agents.models import Agent
    from app.assets.models import Asset
    from app.healthchecks.models import HealthCheck
    from app.vulnerabilities.models import Vulnerability

    # Agent coverage: percentage of assets with active agents
    asset_count = db.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id)
    ).scalar() or 0
    agent_count = db.execute(
        select(func.count())
        .select_from(Agent)
        .where(Agent.tenant_id == tenant_id, Agent.is_active == True)  # noqa: E712
    ).scalar() or 0

    agent_coverage_score = min(100.0, (agent_count / max(asset_count, 1)) * 100)

    # Vulnerability score: lower vulns = higher score
    unresolved_vulns = db.execute(
        select(func.count())
        .select_from(Vulnerability)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.is_resolved == False,  # noqa: E712
        )
    ).scalar() or 0

    critical_vulns = db.execute(
        select(func.count())
        .select_from(Vulnerability)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.is_resolved == False,  # noqa: E712
            Vulnerability.severity == "critical",
        )
    ).scalar() or 0

    if unresolved_vulns == 0:
        vulnerability_score = 100.0
    else:
        penalty = min(100, (critical_vulns * 20) + (unresolved_vulns * 2))
        vulnerability_score = max(0, 100 - penalty)

    # Uptime score: percentage of health checks that are "up"
    total_checks = db.execute(
        select(func.count())
        .select_from(HealthCheck)
        .where(HealthCheck.tenant_id == tenant_id, HealthCheck.is_active == True)  # noqa: E712
    ).scalar() or 0
    up_checks = db.execute(
        select(func.count())
        .select_from(HealthCheck)
        .where(
            HealthCheck.tenant_id == tenant_id,
            HealthCheck.is_active == True,  # noqa: E712
            HealthCheck.last_status == "up",
        )
    ).scalar() or 0

    uptime_score = (up_checks / max(total_checks, 1)) * 100

    # Patching score: based on resolved vs total vulns
    total_vulns = db.execute(
        select(func.count())
        .select_from(Vulnerability)
        .where(Vulnerability.tenant_id == tenant_id)
    ).scalar() or 0
    resolved_vulns = total_vulns - unresolved_vulns

    patching_score = (resolved_vulns / max(total_vulns, 1)) * 100 if total_vulns > 0 else 100.0

    overall = (
        agent_coverage_score * 0.25
        + vulnerability_score * 0.30
        + uptime_score * 0.25
        + patching_score * 0.20
    )

    return {
        "overall_score": round(overall, 1),
        "patching_score": round(patching_score, 1),
        "uptime_score": round(uptime_score, 1),
        "vulnerability_score": round(vulnerability_score, 1),
        "agent_coverage_score": round(agent_coverage_score, 1),
        "calculated_at": datetime.now(timezone.utc),
    }


def generate_security_posture(tenant_id: uuid.UUID, db: Session) -> str:
    """Generate security posture report content."""
    scores = calculate_compliance_score(tenant_id, db)
    return f"Security Posture Report\nOverall Score: {scores['overall_score']}/100"


def generate_asset_inventory(tenant_id: uuid.UUID, db: Session) -> str:
    """Generate asset inventory report content."""
    from app.assets.models import Asset

    assets = db.execute(
        select(Asset).where(Asset.tenant_id == tenant_id).order_by(Asset.hostname)
    ).scalars().all()

    lines = ["Asset Inventory Report", f"Total Assets: {len(assets)}", ""]
    for a in assets:
        lines.append(f"- {a.hostname} ({a.os_type or 'Unknown OS'})")
    return "\n".join(lines)


def generate_uptime_summary(tenant_id: uuid.UUID, db: Session) -> str:
    """Generate uptime summary report content."""
    from app.healthchecks.models import HealthCheck

    checks = db.execute(
        select(HealthCheck).where(HealthCheck.tenant_id == tenant_id)
    ).scalars().all()

    lines = ["Uptime Summary Report", f"Total Health Checks: {len(checks)}", ""]
    for c in checks:
        lines.append(f"- {c.name}: {c.last_status or 'unknown'}")
    return "\n".join(lines)


def generate_vulnerability_report(tenant_id: uuid.UUID, db: Session) -> str:
    """Generate vulnerability report content."""
    from app.vulnerabilities.models import Vulnerability

    vulns = db.execute(
        select(Vulnerability)
        .where(
            Vulnerability.tenant_id == tenant_id,
            Vulnerability.is_resolved == False,  # noqa: E712
        )
        .order_by(Vulnerability.severity)
    ).scalars().all()

    lines = ["Vulnerability Report", f"Unresolved Vulnerabilities: {len(vulns)}", ""]
    for v in vulns:
        lines.append(f"- [{v.severity.upper()}] {v.cve_id or 'N/A'}: {v.software_name}")
    return "\n".join(lines)
