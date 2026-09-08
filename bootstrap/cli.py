"""CLI argument parsing, --help, exit-code contract (task 1.1)."""

import argparse
import sys

from .exitcodes import (
    EX_OK,
    EX_USAGE,
    EX_PLATFORM,
    EX_CONTEXT,
    EX_COMPONENT,
    EX_CONFLICT,
)

EXIT_NAMES = {
    EX_OK: "success",
    EX_USAGE: "usage error",
    EX_PLATFORM: "unsupported platform",
    EX_CONTEXT: "invalid context",
    EX_COMPONENT: "component failure",
    EX_CONFLICT: "unmanaged-file conflict",
}

EPILOG = """exit codes:
  0  success
  1  usage error
  2  unsupported platform
  3  invalid context (headless fail-closed)
  4  component failure(s) — see summary
  5  unmanaged-file conflict
"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bootstrap",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Bootstraps: initialize a machine with selectable defaults "
        "and a project-aware ~/dev workspace.",
        epilog=EPILOG,
    )
    p.add_argument("--version", action="store_true", help="print engine version")
    p.add_argument("--headless", action="store_true", help="non-interactive run")
    p.add_argument(
        "--profile",
        choices=["personal", "work", "headless-server"],
        help="preset profile (headless requires this)",
    )
    p.add_argument("--selection", metavar="FILE", help="saved selection JSON")
    p.add_argument("--save-selection", metavar="FILE", help="write selection JSON")
    p.add_argument("--context", metavar="PATH", help="private context repo clone")
    p.add_argument(
        "--clone-context", metavar="URL", help="clone context repo (needs deploy key)"
    )
    p.add_argument(
        "--allow-hooks", action="store_true", help="permit context post-install hooks"
    )
    p.add_argument("--yes", "-y", action="store_true", help="assume confirmation")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="show plan and exit without mutating (implies --yes for plan preview)",
    )
    p.add_argument(
        "--dev-root", metavar="PATH", default="~/dev", help="workspace root (default ~/dev)"
    )
    p.add_argument(
        "--skip-doctrine", action="store_true", help="skip AGENTS.md/zshrc managed files"
    )
    p.add_argument(
        "--components", metavar="LIST", help="comma-separated subset override"
    )
    return p


def parse(argv):
    p = build_parser()
    try:
        return p.parse_args(argv)
    except UsageExit as exc:
        raise
    except SystemExit as exc:
        # argparse exits 2 on usage errors; EX_PLATFORM is also 2. Map usage
        # errors to EX_USAGE=1 so the documented contract holds (review G1
        # observation 1).
        raise UsageError(str(exc)) from exc


class UsageExit(SystemExit):
    """--help/--version style exits that should surface exit code 0."""


class UsageError(Exception):
    """Bad flag/arguments; maps to exit 1 (never 2, which is platform)."""