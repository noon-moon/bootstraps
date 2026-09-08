"""Component base class and failures."""

from ..exitcodes import EX_COMPONENT  # noqa: F401  (kept for exit mapping)


class ComponentFailure(Exception):
    """Raised by a component when installation/verification fails."""


class Component:
    """One catalog entry. Subclasses declare id, summary, deps, platforms and
    implement check/install/verify. check() -> bool: already satisfied."""

    id: str = ""
    summary: str = ""
    deps: tuple = ()
    platforms: tuple = ("all",)  # or subset like ("macos",)

    def check(self, adapter, ctx, dev_root, log) -> bool:
        return False

    def install(self, adapter, ctx, dev_root, log):
        raise NotImplementedError

    def verify(self, adapter, ctx, dev_root, log) -> bool:
        return True

    def ensure(self, adapter, ctx, dev_root, log):
        if self.check(adapter, ctx, dev_root, log):
            log(f"component {self.id}: already present, skipping")
            self.verify(adapter, ctx, dev_root, log)
            return
        log(f"component {self.id}: installing")
        self.install(adapter, ctx, dev_root, log)
        if not self.verify(adapter, ctx, dev_root, log):
            raise ComponentFailure(f"{self.id}: post-install verification failed")
        log(f"component {self.id}: verified")