"""macOS adapter: Homebrew formulae + casks (task 1.3).

Homebrew installed non-interactively when absent (official installer script
with NONINTERACTIVE=1). Intel vs Apple Silicon install paths handled by the
script itself; we verify `brew` afterwards.
"""

from ..shell import run, which, CommandError
from . import Adapter

BREW_INSTALL_CMD = [
    "/bin/bash",
    "-c",
    'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
]


class MacOSAdapter(Adapter):
    name = "macos"

    def ensure_prerequisites(self, log):
        if which("brew"):
            log("homebrew: present")
            return
        log("homebrew: not found; installing non-interactively")
        try:
            run(["/bin/bash", "-c", 'NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'])
        except CommandError as exc:  # noqa: F821
            raise RuntimeError(
                "Homebrew install failed; install it manually then rerun"
            ) from exc
        if not which("brew"):
            # Apple Silicon default path may need shell init; try the known
            # location before declaring failure.
            import os

            for candidate in ("/opt/homebrew/bin/brew", "/usr/local/bin/brew"):
                if os.path.exists(candidate):
                    os.environ["PATH"] = os.path.dirname(candidate) + os.pathsep + os.environ["PATH"]
                    break
        if not which("brew"):
            raise RuntimeError("homebrew installed but `brew` still not on PATH")

    def install_package(self, name, log, cask=False):
        cmd = ["brew", "install", name]
        if cask:
            cmd.insert(2, "--cask")
        log(f"brew install {name}{' (cask)' if cask else ''}")
        run(cmd)

    def install_many(self, names, log):
        if not names:
            return
        log(f"brew install: {', '.join(names)}")
        run(["brew", "install", *names])

    def has(self, name, cask=False):
        try:
            kind = "cask" if cask else "formula"
            out = run(["brew", "list", kind, name], check=False)
            return out.returncode == 0
        except CommandError:  # noqa: F821
            return False