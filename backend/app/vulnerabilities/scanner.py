"""Vulnerability scanner using the OSV.dev API (free, no API key required)."""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

OSV_API_URL = "https://api.osv.dev/v1"

# Map common package ecosystems
ECOSYSTEM_MAP = {
    # Linux package managers
    "pacman": "Arch Linux",
    "dpkg": "Debian",
    "rpm": "Red Hat",
    "apk": "Alpine",
    # Generic
    "pip": "PyPI",
    "npm": "npm",
    "gem": "RubyGems",
    "cargo": "crates.io",
    "go": "Go",
}

SEVERITY_FROM_SCORE = [
    (9.0, "critical"),
    (7.0, "high"),
    (4.0, "medium"),
    (0.1, "low"),
    (0.0, "unknown"),
]


def score_to_severity(score: float | None) -> str:
    if score is None:
        return "unknown"
    for threshold, severity in SEVERITY_FROM_SCORE:
        if score >= threshold:
            return severity
    return "unknown"


async def query_osv(package_name: str, version: str | None, ecosystem: str = "Arch Linux") -> list[dict]:
    """Query OSV.dev for vulnerabilities affecting a specific package.

    Returns a list of vulnerability dicts with keys:
        cve_id, severity, score, summary, details_url, affected_versions, fixed_version
    """
    results = []

    payload: dict = {
        "package": {
            "name": package_name,
            "ecosystem": ecosystem,
        }
    }
    if version:
        payload["version"] = version

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(f"{OSV_API_URL}/query", json=payload)

            if resp.status_code != 200:
                return []

            data = resp.json()
            vulns = data.get("vulns", [])

            for vuln in vulns:
                # Extract CVE ID
                cve_id = vuln.get("id", "")
                aliases = vuln.get("aliases", [])
                for alias in aliases:
                    if alias.startswith("CVE-"):
                        cve_id = alias
                        break

                # Extract CVSS score
                score = None
                severity_str = "unknown"
                for sev in vuln.get("severity", []):
                    if sev.get("type") == "CVSS_V3":
                        try:
                            # Extract score from CVSS vector
                            vector = sev.get("score", "")
                            # Some entries have numeric score directly
                            if isinstance(vector, (int, float)):
                                score = float(vector)
                            # Try to find score in database_specific
                        except (ValueError, TypeError):
                            pass

                db_specific = vuln.get("database_specific", {})
                if score is None and db_specific.get("severity"):
                    severity_str = db_specific["severity"].lower()
                elif score is not None:
                    severity_str = score_to_severity(score)

                # Map text severity if no numeric score
                if severity_str == "unknown":
                    for sev in vuln.get("severity", []):
                        s = sev.get("score", "").lower() if isinstance(sev.get("score"), str) else ""
                        if "critical" in s or (score and score >= 9.0):
                            severity_str = "critical"
                        elif "high" in s or (score and score >= 7.0):
                            severity_str = "high"

                # Find fixed version
                fixed_version = None
                affected_ranges = ""
                for affected in vuln.get("affected", []):
                    for rng in affected.get("ranges", []):
                        for event in rng.get("events", []):
                            if "fixed" in event:
                                fixed_version = event["fixed"]
                    # Build affected version string
                    versions = affected.get("versions", [])
                    if versions:
                        if len(versions) <= 5:
                            affected_ranges = ", ".join(versions)
                        else:
                            affected_ranges = f"{versions[0]} ... {versions[-1]} ({len(versions)} versions)"

                details_url = f"https://osv.dev/vulnerability/{vuln['id']}"

                results.append({
                    "cve_id": cve_id,
                    "severity": severity_str,
                    "score": score,
                    "summary": (vuln.get("summary") or vuln.get("details", ""))[:500],
                    "details_url": details_url,
                    "affected_versions": affected_ranges or None,
                    "fixed_version": fixed_version,
                })

    except Exception as e:
        logger.error(f"Error querying OSV for {package_name}: {e}")

    return results


async def batch_query_osv(packages: list[dict], ecosystem: str = "Arch Linux") -> dict[str, list[dict]]:
    """Query OSV for multiple packages. Returns {package_name: [vulns]}.

    Uses the batch endpoint for efficiency.
    """
    if not packages:
        return {}

    queries = []
    pkg_keys = []
    for pkg in packages:
        query: dict = {
            "package": {
                "name": pkg["name"],
                "ecosystem": ecosystem,
            }
        }
        if pkg.get("version"):
            query["version"] = pkg["version"]
        queries.append(query)
        pkg_keys.append(pkg["name"])

    results: dict[str, list[dict]] = {}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # OSV batch endpoint handles up to 1000 queries
            for i in range(0, len(queries), 1000):
                batch = queries[i:i + 1000]
                batch_keys = pkg_keys[i:i + 1000]

                resp = await client.post(
                    f"{OSV_API_URL}/querybatch",
                    json={"queries": batch},
                )

                if resp.status_code != 200:
                    logger.error(f"OSV batch query failed: {resp.status_code}")
                    continue

                data = resp.json()
                for j, result in enumerate(data.get("results", [])):
                    vulns = result.get("vulns", [])
                    if vulns and j < len(batch_keys):
                        # For packages with vulns, do individual query for full details
                        pkg_name = batch_keys[j]
                        pkg_version = packages[i + j].get("version")
                        detailed = await query_osv(pkg_name, pkg_version, ecosystem)
                        if detailed:
                            results[pkg_name] = detailed

    except Exception as e:
        logger.error(f"Error in batch OSV query: {e}")

    return results
