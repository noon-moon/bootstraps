"""Run log: printed path at start and end; no resolved secrets (D5/4.1).

Credential *references* may appear (their names), never their resolved values.
Values matching common secret shapes are redacted defensively.
"""

import re
import sys
from datetime import datetime, timezone

_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{8,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{15,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),
    re.compile(r"tskey-auth-[A-Za-z0-9]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),
    re.compile(r"://[^\s/:@]+:[^\s@]+@"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"((?:api[_-]?key|token|password|secret)\s*[=:]\s*)\S+", re.I),
]


def redact(text: str) -> str:
    out = text
    # Replace the ENTIRE match (never re-emit the secret). For the keyword
    # pattern keep the keyword so logs stay readable.
    out = _KEYWORD_PAT.sub(lambda m: m.group(1) + "***REDACTED***", out)
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


_KEYWORD_PAT = _SECRET_PATTERNS[-1]


class RunLog:
    """File + stderr mirror. Secrets redacted on write."""

    def __init__(self, log_path):
        self.path = log_path
        self._fh = open(log_path, "a", encoding="utf-8")

    def start(self, argv):
        self("=== bootstraps run started ===")
        # Redact the argv actually passed (never sys.argv blindly), and log
        # only scheme+host for any URL argument that may embed credentials.
        safe = [redact(_strip_url_credentials(a)) for a in argv]
        self("argv: " + " ".join(safe for safe in safe))

    def __call__(self, message: str):
        line = redact(message)
        self._fh.write(line + "\n")
        self._fh.flush()
        print(line, file=sys.stderr)

    def end(self, exit_code: int):
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self(f"=== bootstraps run ended {stamp} exit={exit_code} log={self.path} ===")
        self._fh.close()


def _strip_url_credentials(url: str) -> str:
    import re

    return re.sub(r"(://)[^/@\s]+:[^@\s]+@", r"\1<credentials>@", url)


def default_log_path() -> str:
    import os
    import tempfile

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = os.environ.get("BOOTSTRAPS_LOG_DIR") or os.path.join(
        os.path.expanduser("~"), ".local", "state", "bootstraps"
    )
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = tempfile.gettempdir()
    return os.path.join(base, f"bootstrap-{stamp}.log")