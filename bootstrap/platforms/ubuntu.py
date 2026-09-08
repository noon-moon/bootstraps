"""Ubuntu adapter: APT prerequisite handling for fresh Ubuntu 24.04.

Privilege model (deployment contract): bootstrap runs as an UNPRIVILEGED
service user with NO sudo grant of any kind. The OPERATOR prereq phase
installs python3/zsh/git/curl/CA up front. This adapter therefore:

  1. checks which prerequisites are missing FIRST;
  2. if none are missing, returns WITHOUT any apt action (no apt update
     as non-root — that was a bug);
  3. if something is missing and we are root, installs it directly;
  4. if something is missing and we are NOT root, fails CLOSED with
     operator instructions (no `sudo -n true` probing, no "apt-only sudo"
     claims, no new grants invented here).
"""

import os

from ..shell import run, which, CommandError
from . import Adapter

PREREQ_PACKAGES = {"python3": "python3", "zsh": "zsh", "curl": "curl", "git": "git"}


def _apt_cmd():
    """apt-get invocation for the current privilege level: direct as root.
    Non-root has NO apt authority in this deployment (no sudo grants); the
    caller must have checked before mutating."""
    if os.geteuid() == 0:
        return ["apt-get"]
    raise CommandError(
        "apt-get as non-root", 1,
        "", "refusing: no apt authority as non-root (operator prereq phase "
        "must install missing packages; no sudo grant exists by design)",
    )


class UbuntuAdapter(Adapter):
    name = "ubuntu"

    def missing_prerequisites(self, log):
        """Names of prerequisite binaries not present on this host."""
        needed = [p for p in PREREQ_PACKAGES if not which(p)]
        if needed:
            log(f"apt prerequisites missing: {', '.join(needed)}")
        else:
            log("apt prerequisites already present (no apt action taken)")
        return needed

    def ensure_prerequisites(self, log):
        needed = self.missing_prerequisites(log)
        if not needed:
            return
        if os.geteuid() != 0:
            # Fail closed with operator instruction — never probe sudo, never
            # grant anything, never run apt as non-root.
            raise CommandError(
                "apt-get install (missing prerequisites as non-root)", 1,
                "",
                "missing: " + ", ".join(needed) + "\n"
                "operator: run the provisioning packages phase as root "
                "(provision-host) so these are installed BEFORE the "
                "unprivileged bootstrap; the runtime user has NO sudo by "
                "design",
            )
        log("apt: updating package lists")
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        run([*(_apt_cmd()), "update", "-qq"], env=env)
        log(f"apt install prerequisites: {', '.join(needed)}")
        run([*(_apt_cmd()), "install", "-y", "-qq",
             *(PREREQ_PACKAGES[p] for p in needed)], env=env)

    def install_package(self, name, log, cask=False):
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        log(f"apt install {name}")
        run([*(_apt_cmd()), "install", "-y", "-qq", name], env=env)

    def install_many(self, names, log):
        if not names:
            return
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        log(f"apt install: {', '.join(names)}")
        run([*(_apt_cmd()), "install", "-y", "-qq", *names], env=env)

    def has(self, name, cask=False):
        out = run(["dpkg-query", "-W", "-f=${Status}", name], check=False)
        return out.returncode == 0 and "install ok installed" in out.stdout