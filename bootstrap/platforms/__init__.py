"""Adapter interface: each platform profile provides a package manager facade.

macOS  -> Homebrew (install non-interactively if absent; formulae + casks).
Ubuntu -> APT (apt-get update/install; bootstrap Zsh + Python early).
"""


class Adapter:
    name = "base"

    def ensure_prerequisites(self, log):
        """Install what the engine itself needs before components run."""
        raise NotImplementedError

    def install_package(self, name, log, cask=False):
        raise NotImplementedError

    def install_many(self, names, log):
        raise NotImplementedError

    def has(self, name, cask=False):
        raise NotImplementedError


def get_adapter(profile: str):
    if profile == "macos":
        from .macos import MacOSAdapter

        return MacOSAdapter()
    if profile == "ubuntu":
        from .ubuntu import UbuntuAdapter

        return UbuntuAdapter()
    raise LookupError(f"no adapter for profile {profile!r}")