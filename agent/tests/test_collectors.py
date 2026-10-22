import socket

import pytest

from opscentral_agent.collectors import (
    collect_cpu,
    collect_disk,
    collect_memory,
    collect_network,
    collect_process_summary,
    collect_processes,
    collect_system_info,
)
from opscentral_agent.collectors.system import (
    _parse_apk,
    _parse_nix,
    _parse_pacman,
    _parse_portage_qlist,
    _parse_tab,
    _parse_xbps,
    _parse_zypper,
    _split_name_version,
)

# --- live collectors (run against the CI machine on every OS) ---


@pytest.mark.parametrize(
    "collector",
    [collect_cpu, collect_memory, collect_disk, collect_network, collect_process_summary],
)
def test_metric_collectors_return_well_formed_metrics(collector):
    metrics = collector()
    assert metrics, f"{collector.__name__} returned nothing"
    for metric in metrics:
        assert isinstance(metric["name"], str) and metric["name"]
        assert isinstance(metric["value"], int | float)
        assert isinstance(metric["unit"], str)


def test_percent_metrics_are_in_range():
    metrics = {m["name"]: m["value"] for m in collect_cpu() + collect_memory()}
    assert 0 <= metrics["cpu_percent"] <= 100
    assert 0 <= metrics["memory_percent"] <= 100


def test_collect_processes_respects_top_n():
    processes = collect_processes(top_n=5)
    assert 0 < len(processes) <= 5
    assert {"pid", "name", "cpu_percent", "memory_mb"} <= processes[0].keys()


def test_collect_system_info():
    info = collect_system_info()
    assert info["hostname"] == socket.gethostname()


# --- package manager output parsers ---


def test_parse_tab_dpkg_rpm():
    out = "nginx\t1.24.0-2ubuntu1\nopenssl\t3.0.13-0ubuntu3\nmalformed-line\n"
    assert _parse_tab(out) == [
        {"name": "nginx", "version": "1.24.0-2ubuntu1"},
        {"name": "openssl", "version": "3.0.13-0ubuntu3"},
    ]


def test_parse_pacman():
    assert _parse_pacman("linux 6.9.7.arch1-1\nbash 5.2.026-2\n") == [
        {"name": "linux", "version": "6.9.7.arch1-1"},
        {"name": "bash", "version": "5.2.026-2"},
    ]


def test_parse_apk():
    out = (
        "busybox-1.36.1-r29 x86_64 {busybox} (GPL-2.0-only)\n"
        "ca-certificates-bundle-20240705-r0 x86_64\n"
    )
    assert _parse_apk(out) == [
        {"name": "busybox", "version": "1.36.1-r29"},
        {"name": "ca-certificates-bundle", "version": "20240705-r0"},
    ]


def test_parse_portage_qlist():
    assert _parse_portage_qlist("sys-apps/portage-3.0.65\ndev-lang/python-3.12.4_p3\n") == [
        {"name": "portage", "version": "3.0.65"},
        {"name": "python", "version": "3.12.4_p3"},
    ]


def test_parse_zypper_skips_header_and_separator():
    out = (
        "S  | Name    | Type    | Version   | Arch   | Repository\n"
        "---+---------+---------+-----------+--------+-----------\n"
        "i+ | vim     | package | 9.1.0330  | x86_64 | Main\n"
        "i  | openssl | package | 3.1.4-1.1 | x86_64 | Main\n"
    )
    assert _parse_zypper(out) == [
        {"name": "vim", "version": "9.1.0330"},
        {"name": "openssl", "version": "3.1.4-1.1"},
    ]


def test_parse_xbps():
    assert _parse_xbps("ii bash-5.2.21_1   GNU Bourne Again Shell\n") == [
        {"name": "bash", "version": "5.2.21_1"}
    ]


def test_parse_nix():
    assert _parse_nix("hello-2.12.1\nnodejs-20.15.0\n") == [
        {"name": "hello", "version": "2.12.1"},
        {"name": "nodejs", "version": "20.15.0"},
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("python3-pip-24.0", ("python3-pip", "24.0")),
        ("lib32-glibc-2.39-4", ("lib32-glibc-2.39", "4")),
        ("no-version-here", ("no-version-here", "")),
        ("1password-8.10", ("1password", "8.10")),
    ],
)
def test_split_name_version(raw, expected):
    assert _split_name_version(raw) == expected
