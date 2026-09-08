"""Component registry: catalog, dependency closure, per-component isolation
(task 2.1). Closure resolution reports declined-prerequisite blockers instead
of silently installing them (spec R3)."""

from .base import Component, ComponentFailure

CATALOG = []


def register(cls):
    CATALOG.append(cls())
    return cls


def build_registry(platform_info):
    """Return {id: instance}, filtered to platform-appropriate entries."""
    profile = platform_info["profile"]
    return {
        c.id: c
        for c in CATALOG
        if "all" in c.platforms or profile in c.platforms
    }


def resolve_closure(selected, registry):
    """Expand selected ids through deps. Returns (ordered_ids, blocked).
    A selected component whose prerequisite was NOT itself selected is a
    blocker (spec R3: never silently install a declined prerequisite)."""
    blocked = []
    seen = set()
    order = []

    def visit(cid, chain):
        if cid in seen:
            return
        comp = registry.get(cid)
        if comp is None:
            blocked.append((cid, "not available on this platform"))
            return
        for dep in comp.deps:
            if dep not in selected and dep not in seen:
                blocked.append((cid, f"requires prerequisite '{dep}' which was not selected"))
                return
            if dep in chain:
                blocked.append((cid, "dependency cycle"))
                return
            visit(dep, chain + [cid])
        seen.add(cid)
        order.append(cid)

    for cid in selected:
        visit(cid, [])
    return order, blocked