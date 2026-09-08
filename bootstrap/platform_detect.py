"""Platform detection and support boundary (spec: bootstrap-execution R1).

Supported: macOS (arm64, x86_64) -> Homebrew; Ubuntu 24.04 (amd64, arm64) -> APT.
Anything else: print unsupported platform, exit EX_PLATFORM, no changes.
"""

import platform
import subprocess
import sys

SUPPORTED = {
    ("darwin", "arm64"): "macos",
    ("darwin", "x86_64"): "macos",
    ("linux", "x86_64"): "ubuntu",
    ("linux", "aarch64"): "ubuntu",
}


def _ubuntu_version() -> str:
    try:
        out = subprocess.run(
            ["lsb_release", "-ds"], capture_output=True, text=True, timeout=10
        )
        if out.returncode == 0 and "Ubuntu" in out.stdout:
            # Pull version from /etc/os-release for precision
            rel = {}
            with open("/etc/os-release", encoding="utf-8") as fh:
                for line in fh:
                    if "=" in line:
                        k, _, v = line.partition("=")
                        rel[k.strip()] = v.strip().strip('"')
            return rel.get("VERSION_ID", "")
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def detect() -> dict:
    """Return {'system': darwin|linux, 'machine': ..., 'profile': macos|ubuntu,
    'version': ...} or raise UnsupportedPlatform."""
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine == "amd64":  # python reports x86_64 normally, but normalize
        machine = "x86_64"
    if machine == "arm64" and system == "linux":
        machine = "aarch64"

    key = (system, machine)
    if key not in SUPPORTED:
        raise UnsupportedPlatform(f"{system} {machine}")

    info = {
        "system": system,
        "machine": machine,
        "profile": SUPPORTED[key],
        "version": platform.mac_ver()[0] if system == "darwin" else "",
    }
    if info["profile"] == "ubuntu":
        version = _ubuntu_version()
        if not version.startswith("24.04"):
            raise UnsupportedPlatform(
                f"Ubuntu {version or '(unknown version)'} (supported: 24.04)"
            )
        info["version"] = version
    return info


class UnsupportedPlatform(Exception):
    pass


def describe(info: dict) -> str:
    return f"{info['system']} {info['machine']} -> profile '{info['profile']}' (version {info['version'] or 'n/a'})"