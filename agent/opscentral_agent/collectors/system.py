import logging
import os
import platform
import socket
import subprocess
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


def collect_system_info() -> dict:
    """Collect full system inventory info. Works on Linux, Windows, and macOS."""
    uname = platform.uname()
    mem = psutil.virtual_memory()

    # Disk: use "/" on Linux/macOS, "C:\\" on Windows
    root_path = "C:\\" if platform.system() == "Windows" else "/"
    try:
        disk = psutil.disk_usage(root_path)
        disk_total_gb = round(disk.total / (1024**3), 2)
    except Exception:
        disk_total_gb = 0

    ip_addresses = []
    mac_addresses = []
    for _iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                ip_addresses.append(addr.address)
            try:
                if (
                    addr.family == psutil.AF_LINK
                    and addr.address
                    and addr.address != "00:00:00:00:00:00"
                ):
                    mac_addresses.append(addr.address)
            except AttributeError:
                pass

    return {
        "hostname": socket.gethostname(),
        "os_type": uname.system.lower(),
        "os_version": f"{uname.system} {uname.release}",
        "cpu_model": _get_cpu_model(uname),
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "disk_total_gb": disk_total_gb,
        "ip_addresses": ip_addresses,
        "mac_addresses": mac_addresses,
        "architecture": uname.machine,
        "python_version": platform.python_version(),
    }


def _get_cpu_model(uname) -> str:
    """Get CPU model string across platforms."""
    if uname.processor:
        return uname.processor
    proc = platform.processor()
    if proc:
        return proc
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("model name"):
                    return line.split(":")[1].strip()
    except (FileNotFoundError, PermissionError):
        pass
    return uname.machine


def collect_software() -> list[dict]:
    """Collect installed software. Uses package manager + filesystem scan as fallback."""
    system = platform.system()

    if system == "Linux":
        software = _collect_linux_software()
    elif system == "Windows":
        software = _collect_windows_software()
    elif system == "Darwin":
        software = _collect_macos_software()
    else:
        software = []

    return software


# ---------------------------------------------------------------------------
# Linux: try every common package manager, then scan filesystem for the rest
# ---------------------------------------------------------------------------

_LINUX_PKG_MANAGERS = [
    # (command, args, parser)
    # Each parser takes stdout and returns list[dict]
    ("pacman", ["-Q"], "_parse_pacman"),
    ("dpkg-query", ["-W", "-f", "${Package}\t${Version}\n"], "_parse_tab"),
    ("rpm", ["-qa", "--queryformat", "%{NAME}\t%{VERSION}\n"], "_parse_tab"),
    ("emerge", ["--info", "--verbose"], None),  # handled specially
    ("equery", ["list", "-F", "$name\t$version", "*"], "_parse_tab"),
    ("qlist", ["-Iv"], "_parse_portage_qlist"),
    ("apk", ["list", "--installed"], "_parse_apk"),
    ("zypper", ["se", "--installed-only", "-s"], "_parse_zypper"),
    ("xbps-query", ["-l"], "_parse_xbps"),
    ("nix-env", ["-q"], "_parse_nix"),
]


def _collect_linux_software() -> list[dict]:
    """Try package managers in order, then scan common binary dirs for source-installed software."""
    software = []

    # 1. Try each package manager
    for cmd, args, parser_name in _LINUX_PKG_MANAGERS:
        if parser_name is None:
            continue  # skip entries without a parser (emerge --info is metadata, not a list)
        try:
            result = subprocess.run(
                [cmd, *args],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout.strip():
                parser = globals()[parser_name]
                software = parser(result.stdout)
                if software:
                    logger.info(f"Collected {len(software)} packages via {cmd}")
                    break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # 2. Portage: if no equery/qlist, read /var/db/pkg directly (works on any Gentoo)
    if not software:
        software = _scan_portage_db()

    # 3. Scan filesystem for source-installed binaries not tracked by any package manager
    source_installed = _scan_filesystem_binaries(software)
    software.extend(source_installed)

    return software[:500]  # cap at 500


def _parse_pacman(stdout: str) -> list[dict]:
    """Parse `pacman -Q` output: 'package version'"""
    software = []
    for line in stdout.strip().split("\n"):
        parts = line.split(None, 1)
        if len(parts) == 2:
            software.append({"name": parts[0], "version": parts[1]})
    return software[:500]


def _parse_tab(stdout: str) -> list[dict]:
    """Parse tab-separated 'name\\tversion' output (dpkg, rpm, equery)."""
    software = []
    for line in stdout.strip().split("\n"):
        parts = line.split("\t", 1)
        if len(parts) >= 2:
            software.append({"name": parts[0], "version": parts[1]})
    return software[:500]


def _parse_portage_qlist(stdout: str) -> list[dict]:
    """Parse `qlist -Iv` output: 'category/name-version'"""
    software = []
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # e.g. "sys-apps/portage-2.3.99"
        cat_name_ver = line.split("/", 1)[1] if "/" in line else line
        # Split name from version: last hyphen before a digit
        name, version = _split_name_version(cat_name_ver)
        software.append({"name": name, "version": version})
    return software[:500]


def _parse_apk(stdout: str) -> list[dict]:
    """Parse `apk list --installed` output: 'name-version-rN description'"""
    software = []
    for line in stdout.strip().split("\n"):
        # e.g. "busybox-1.35.0-r17 x86_64 {busybox} (GPL-2.0-only)"
        parts = line.split(None, 1)
        if parts:
            name, version = _split_name_version(parts[0])
            software.append({"name": name, "version": version})
    return software[:500]


def _parse_zypper(stdout: str) -> list[dict]:
    """Parse `zypper se --installed-only -s` table output."""
    software = []
    for line in stdout.strip().split("\n"):
        if "|" not in line or line.startswith("-") or line.startswith("S"):
            continue
        cols = [c.strip() for c in line.split("|")]
        # Columns: Status | Name | Type | Version | Arch | Repository
        if len(cols) >= 4:
            software.append({"name": cols[1], "version": cols[3]})
    return software[:500]


def _parse_xbps(stdout: str) -> list[dict]:
    """Parse `xbps-query -l` output: 'ii name-version description'"""
    software = []
    for line in stdout.strip().split("\n"):
        parts = line.split(None, 2)
        if len(parts) >= 2:
            name, version = _split_name_version(parts[1])
            software.append({"name": name, "version": version})
    return software[:500]


def _parse_nix(stdout: str) -> list[dict]:
    """Parse `nix-env -q` output: 'name-version'"""
    software = []
    for line in stdout.strip().split("\n"):
        name, version = _split_name_version(line.strip())
        if name:
            software.append({"name": name, "version": version})
    return software[:500]


def _split_name_version(s: str) -> tuple[str, str]:
    """Split 'name-1.2.3' into ('name', '1.2.3'). Handles multiple hyphens."""
    # Walk backwards to find the last hyphen before a digit
    for i in range(len(s) - 1, 0, -1):
        if s[i] == "-" and i + 1 < len(s) and s[i + 1].isdigit():
            return s[:i], s[i + 1 :]
    return s, ""


def _scan_portage_db() -> list[dict]:
    """Read /var/db/pkg directly — works on any Gentoo/Funtoo even without equery."""
    db_path = Path("/var/db/pkg")
    if not db_path.is_dir():
        return []

    software = []
    try:
        for category in db_path.iterdir():
            if not category.is_dir() or category.name.startswith("."):
                continue
            for pkg in category.iterdir():
                if not pkg.is_dir():
                    continue
                name, version = _split_name_version(pkg.name)
                software.append({"name": f"{category.name}/{name}", "version": version})
                if len(software) >= 500:
                    return software
    except PermissionError:
        pass

    return software


def _scan_filesystem_binaries(known_packages: list[dict]) -> list[dict]:
    """
    Scan common binary directories for executables not tracked by a package manager.
    Catches source-installed software in /usr/local, /opt, ~/.local, etc.
    """
    known_names = {pkg["name"].split("/")[-1] for pkg in known_packages}

    scan_dirs = [
        "/usr/local/bin",
        "/usr/local/sbin",
        "/opt",
        os.path.expanduser("~/.local/bin"),
    ]

    found = []
    seen = set()

    for scan_dir in scan_dirs:
        dir_path = Path(scan_dir)
        if not dir_path.is_dir():
            continue

        try:
            if scan_dir == "/opt":
                # /opt usually has subdirectories per application
                for app_dir in dir_path.iterdir():
                    if not app_dir.is_dir() or app_dir.name.startswith("."):
                        continue
                    name = app_dir.name
                    if name not in known_names and name not in seen:
                        version = _try_get_version(app_dir)
                        found.append(
                            {
                                "name": name,
                                "version": version,
                                "publisher": f"source-installed ({scan_dir})",
                            }
                        )
                        seen.add(name)
            else:
                for binary in dir_path.iterdir():
                    if not binary.is_file():
                        continue
                    if not os.access(str(binary), os.X_OK):
                        continue
                    name = binary.name
                    if name in known_names or name in seen:
                        continue
                    # Skip common non-application files
                    if name.startswith(".") or name.startswith("_"):
                        continue
                    version = _try_get_binary_version(binary)
                    found.append(
                        {
                            "name": name,
                            "version": version,
                            "publisher": f"source-installed ({scan_dir})",
                        }
                    )
                    seen.add(name)
                    if len(found) >= 100:
                        return found
        except PermissionError:
            continue

    return found


def _try_get_version(app_dir: Path) -> str:
    """Try to find a version for an /opt application."""
    # Check for VERSION or version file
    for name in ("VERSION", "version", "version.txt", ".version"):
        vfile = app_dir / name
        if vfile.is_file():
            try:
                return vfile.read_text().strip().split("\n")[0][:50]
            except Exception:
                pass
    return ""


def _try_get_binary_version(binary: Path) -> str:
    """Try running `binary --version` to extract a version string."""
    try:
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            first_line = result.stdout.strip().split("\n")[0]
            # Extract version-like pattern from the first line
            import re

            match = re.search(r"(\d+\.\d+[\.\d]*)", first_line)
            if match:
                return match.group(1)
            return first_line[:60]
    except (subprocess.TimeoutExpired, PermissionError, OSError):
        pass
    return ""


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------


def _collect_windows_software() -> list[dict]:
    """Collect from Windows registry (both 64-bit and 32-bit paths) + scan Program Files."""
    software = []

    # Registry query via PowerShell — covers both 64 and 32-bit
    ps_cmd = (
        "$paths = @("
        '"HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",'
        '"HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*",'
        '"HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*"'
        "); "
        "foreach ($p in $paths) { "
        "Get-ItemProperty $p -ErrorAction SilentlyContinue "
        "| Where-Object { $_.DisplayName -ne $null } "
        "| Select-Object DisplayName, DisplayVersion, Publisher "
        "} | Sort-Object DisplayName -Unique "
        "| ConvertTo-Csv -NoTypeInformation"
    )
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines[1:401]:  # skip header, cap at 400
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 1 and parts[0]:
                    software.append(
                        {
                            "name": parts[0],
                            "version": parts[1] if len(parts) > 1 else None,
                            "publisher": parts[2] if len(parts) > 2 else None,
                        }
                    )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Also scan Program Files for anything not in the registry
    known_names = {s["name"].lower() for s in software}
    for pf_dir in [r"C:\Program Files", r"C:\Program Files (x86)"]:
        pf = Path(pf_dir)
        if not pf.is_dir():
            continue
        try:
            for app_dir in pf.iterdir():
                if app_dir.is_dir() and app_dir.name.lower() not in known_names:
                    software.append(
                        {
                            "name": app_dir.name,
                            "version": "",
                            "publisher": f"found in {pf_dir}",
                        }
                    )
        except PermissionError:
            pass

    return software[:500]


# ---------------------------------------------------------------------------
# macOS
# ---------------------------------------------------------------------------


def _collect_macos_software() -> list[dict]:
    """Collect from /Applications + Homebrew if available."""
    software = []

    # 1. /Applications directory
    apps_dir = Path("/Applications")
    if apps_dir.is_dir():
        for app in apps_dir.iterdir():
            if app.suffix == ".app":
                name = app.stem
                version = _get_macos_app_version(app)
                software.append({"name": name, "version": version})

    # 2. Homebrew
    try:
        result = subprocess.run(
            ["brew", "list", "--versions"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    software.append({"name": parts[0], "version": parts[1]})
                elif len(parts) == 1:
                    software.append({"name": parts[0], "version": ""})
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return software[:500]


def _get_macos_app_version(app_path: Path) -> str:
    """Read version from an app's Info.plist."""
    plist = app_path / "Contents" / "Info.plist"
    if not plist.is_file():
        return ""
    try:
        result = subprocess.run(
            ["defaults", "read", str(plist), "CFBundleShortVersionString"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""
