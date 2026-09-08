#!/usr/bin/env python3
"""Synthetic vault fixture for archivist qualification (task 3.1).

Builds a non-private synthetic vault with a remote (bare repo) and two
checkouts: canonical (the integration point, simulating the VPS/desktop
checkout) and desktop (simulating the Obsidian checkout). Content is
synthetic: no personal data.

Layout produced:
  <base>/vault-remote.git      bare remote
  <base>/vault-canonical/      canonical checkout (worktree integration)
  <base>/vault-desktop/        desktop Obsidian-checkout simulation
"""

import os
import shutil
import subprocess
from pathlib import Path

NOTE_CAPTURE = """---
tags: [capture]
Created: 2026-09-08
---

# Quarterly planning capture

Captured from a synthetic phone note. The archivist must file this under
Projects/Planning without altering a single word of the body below.

Body line one with a specific figure: 42 widgets.
Body line two with a proper noun: Foobarbaz Industries.
"""

NOTE_MOC = """---
tags: [scope]
---

# Planning

Hub note for the planning scope.

- [[Quarterly planning capture]]
"""

README = """# Synthetic vault

Fixture for archivist qualification. Entirely synthetic content.
"""


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def build(base):
    base = Path(base)
    if base.exists():
        shutil.rmtree(base)  # tests own their scratch base; rebuild cleanly
    base.mkdir(parents=True)

    remote = base / "vault-remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)

    canonical = base / "vault-canonical"
    canonical.mkdir()
    _git("init", "-q", cwd=canonical)
    _git("-c", "user.email=t@e.st", "-c", "user.name=t",
         "commit", "--allow-empty", "-qm", "init", cwd=canonical)
    _git("branch", "-M", "main", cwd=canonical)
    _git("remote", "add", "origin", str(remote), cwd=canonical)

    (canonical / "README.md").write_text(README)
    (canonical / "Projects").mkdir()
    (canonical / "Projects" / "Planning.md").write_text(NOTE_MOC)
    _git("add", "-A", cwd=canonical)
    _git("-c", "user.email=t@e.st", "-c", "user.name=t",
         "commit", "-qm", "seed synthetic vault", cwd=canonical)
    _git("push", "-q", "-u", "origin", "main", cwd=canonical)

    desktop = base / "vault-desktop"
    subprocess.run(
        ["git", "clone", "-q", str(remote), str(desktop)],
        check=True, capture_output=True, text=True,
    )
    # a pending capture staged in the desktop checkout's triage area, uncommitted
    triage = desktop / "_triage"
    triage.mkdir()
    (triage / "2026-09-08-quarterly-planning.md").write_text(NOTE_CAPTURE)

    return {
        "base": str(base),
        "remote": str(remote),
        "canonical": str(canonical),
        "desktop": str(desktop),
        "pending_capture": str(triage / "2026-09-08-quarterly-planning.md"),
    }


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(build(sys.argv[1] if len(sys.argv) > 1 else "/tmp/archivist-fixture"), indent=2))