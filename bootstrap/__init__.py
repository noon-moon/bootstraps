"""bootstraps engine (stdlib-only Python 3).

Layout: bootstrap/ package. Entry: bootstrap.sh shim -> __main__.py.

Design refs: openspec/changes/initialize-project-workspace/design.md
- D1 stdlib-only engine, sh shim entry
- D5 exit codes: 0 ok, 2 unsupported platform, 3 invalid context,
  4 component failure(s), 5 unmanaged-file conflict, 1 usage error
- D6 context precedence: interactive choice > context > shipped default
"""

from .exitcodes import (
    EX_OK,
    EX_USAGE,
    EX_PLATFORM,
    EX_CONTEXT,
    EX_COMPONENT,
    EX_CONFLICT,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "EX_OK",
    "EX_PLATFORM",
    "EX_CONTEXT",
    "EX_COMPONENT",
    "EX_CONFLICT",
]