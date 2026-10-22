"""Celery tasks for vulnerability scanning."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.alerting.models import Alert
from app.assets.models import Asset, SoftwareInventory
from app.config import settings
from app.tasks.celery_app import celery
from app.vulnerabilities.models import Vulnerability, VulnerabilityScan

logger = logging.getLogger(__name__)

SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")


def _get_sync_session():
    engine = create_engine(SYNC_DB_URL)
    return Session(engine)


# Map publisher/source hints to OSV ecosystems
def _guess_ecosystem(publisher: str | None, os_type: str | None) -> str:
    if publisher:
        p = publisher.lower()
        if "pacman" in p or "arch" in p:
            return "Arch Linux"
        if "dpkg" in p or "apt" in p or "debian" in p or "ubuntu" in p:
            return "Debian"
        if "rpm" in p or "redhat" in p or "fedora" in p or "centos" in p:
            return "Red Hat"
        if "apk" in p or "alpine" in p:
            return "Alpine"
        if "pip" in p or "pypi" in p:
            return "PyPI"
        if "npm" in p:
            return "npm"
    if os_type:
        ot = os_type.lower()
        if "arch" in ot or "manjaro" in ot:
            return "Arch Linux"
        if "debian" in ot or "ubuntu" in ot:
            return "Debian"
        if "redhat" in ot or "centos" in ot or "fedora" in ot or "rhel" in ot:
            return "Red Hat"
        if "alpine" in ot:
            return "Alpine"
    return "Arch Linux"  # Default


@celery.task(name="app.tasks.vuln_tasks.scan_all_assets")
def scan_all_assets():
    """Scan all assets for vulnerabilities."""
    session = _get_sync_session()
    try:
        assets = session.execute(select(Asset).where(Asset.status == "active")).scalars().all()

        for asset in assets:
            try:
                _scan_asset(session, asset)
            except Exception as e:
                logger.error(f"Error scanning asset {asset.id}: {e}")

        session.commit()
    finally:
        session.close()


def _scan_asset(session: Session, asset: Asset):
    """Scan a single asset's software inventory for vulnerabilities."""
    now = datetime.now(UTC)

    # Create scan record
    scan = VulnerabilityScan(
        tenant_id=asset.tenant_id,
        asset_id=asset.id,
        status="running",
        started_at=now,
    )
    session.add(scan)
    session.flush()

    # Get software inventory
    software = (
        session.execute(select(SoftwareInventory).where(SoftwareInventory.asset_id == asset.id))
        .scalars()
        .all()
    )

    if not software:
        scan.status = "completed"
        scan.packages_scanned = 0
        scan.completed_at = datetime.now(UTC)
        return

    ecosystem = _guess_ecosystem(
        software[0].publisher if software else None,
        asset.os_type,
    )

    # Build package list for batch query
    packages = [{"name": sw.name, "version": sw.version} for sw in software]

    # Run async scanner in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        from app.vulnerabilities.scanner import batch_query_osv

        results = loop.run_until_complete(batch_query_osv(packages, ecosystem))
    except Exception as e:
        scan.status = "failed"
        scan.error = str(e)
        scan.completed_at = datetime.now(UTC)
        logger.error(f"Vulnerability scan failed for asset {asset.id}: {e}")
        return
    finally:
        loop.close()

    total_vulns = 0
    new_critical = 0

    for pkg_name, vulns in results.items():
        # Find the software entry to get version
        sw_entry = next((s for s in software if s.name == pkg_name), None)
        sw_version = sw_entry.version if sw_entry else None

        for vuln_data in vulns:
            total_vulns += 1

            # Check if already tracked
            existing = session.execute(
                select(Vulnerability).where(
                    Vulnerability.asset_id == asset.id,
                    Vulnerability.cve_id == vuln_data["cve_id"],
                )
            ).scalar_one_or_none()

            if existing:
                # Update if severity changed
                if existing.severity != vuln_data["severity"]:
                    existing.severity = vuln_data["severity"]
                    existing.score = vuln_data.get("score")
                continue

            # New vulnerability
            vuln = Vulnerability(
                tenant_id=asset.tenant_id,
                asset_id=asset.id,
                software_name=pkg_name,
                software_version=sw_version,
                cve_id=vuln_data["cve_id"],
                severity=vuln_data["severity"],
                score=vuln_data.get("score"),
                summary=vuln_data.get("summary"),
                details_url=vuln_data.get("details_url"),
                affected_versions=vuln_data.get("affected_versions"),
                fixed_version=vuln_data.get("fixed_version"),
                first_detected_at=now,
            )
            session.add(vuln)

            if vuln_data["severity"] in ("critical", "high"):
                new_critical += 1

    # Update scan record
    scan.status = "completed"
    scan.packages_scanned = len(packages)
    scan.vulnerabilities_found = total_vulns
    scan.completed_at = datetime.now(UTC)

    # Fire alert for new critical/high vulnerabilities
    if new_critical > 0:
        alert = Alert(
            tenant_id=asset.tenant_id,
            rule_id=None,
            agent_id=asset.agent_id,
            status="firing",
            severity="critical" if new_critical >= 5 else "warning",
            title=f"New vulnerabilities found on {asset.hostname}",
            message=f"{new_critical} new critical/high severity vulnerabilities detected "
            f"across {len(results)} packages on {asset.hostname}.",
            fired_at=now,
        )
        session.add(alert)
