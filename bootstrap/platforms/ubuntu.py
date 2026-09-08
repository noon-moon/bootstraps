"""Ubuntu adapter: APT + minimal-shell bootstrap of Zsh and Python (task 1.4).

Runs under sh/bash on a fresh droplet: installs python3 and zsh via apt-get
(non-interactive) before any component that requires them. Verified by the
fresh-container e2e test.
"""

import os
from ..shell import run, which, CommandError
from . import Adapter


class UbuntuAdapter(Adapter):
    name = "ubuntu"

    def ensure_prerequisites(self, log):
        log("apt: updating package lists")
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        run(["apt-get", "update", "-qq"], env=env)
        needed = [p for p in ("python3", "zsh", "curl", "git") if not which(p)]
        if needed:
            log(f"apt install prerequisites: {', '.join(needed)}")
            run(["apt-get", "install", "-y", "-qq", *needed], env=env)
        else:
            log("apt prerequisites already present")

    def install_package(self, name, log, cask=False):
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        log(f"apt install {name}")
        run(["apt-get", "install", "-y", "-qq", name], env=env)

    def install_many(self, names, log):
        if not names:
            return
        env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
        log(f"apt install: {', '.join(names)}")
        run(["apt-get", "install", "-y", "-qq", *names], env=env)

    def has(self, name, cask=False):
        out = run(["dpkg-query", "-W", "-f=${Status}", name], check=False)
        return out.returncode == 0 and "install ok installed" in out.stdout