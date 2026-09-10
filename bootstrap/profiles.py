"""Profile presets (task 3.1). Presets are component id lists; platform
filtering happens here so e.g. headless --profile personal on Ubuntu never
selects desktop-only components (review G1 obs. 11).

Context-supplied profiles (deployment override): a context may define its
own profile as an EXPLICIT component subset under
context.toml `[profiles.<name>] components = [...]`. Unknown component ids
are REJECTED, not ignored (fail-closed) — a typo must never silently shrink
the deployment.
"""

PROFILES = {
    "personal": [
        "git", "rust", "node", "typescript", "docker", "opencode",
        "claude-code", "codex", "backlog", "openspec", "fzf",
        "oh-my-zsh", "shell-config", "iterm2", "obsidian", "quartz",
    ],
    "work": [
        "git", "rust", "node", "typescript", "docker", "opencode",
        "claude-code", "codex", "backlog", "openspec", "fzf",
        "oh-my-zsh", "shell-config", "tailscale",
    ],
    # Shipped preset (previous committed default — unchanged; deployments
    # that need a narrower set use a context-defined profile).
    "headless-server": [
        "git", "rust", "node", "docker", "opencode", "backlog",
        "openspec", "tailscale",
    ],
}

# Context profiles MUST be an explicit subset; unsupported ids are rejected.
KNOWN_COMPONENT_IDS = None  # populated lazily from the catalog


def _catalog_ids():
    global KNOWN_COMPONENT_IDS
    if KNOWN_COMPONENT_IDS is None:
        from .components import CATALOG
        KNOWN_COMPONENT_IDS = {c.id for c in CATALOG}
    return KNOWN_COMPONENT_IDS


def context_profile_components(profile_def, platform_profile: str = None):
    """Resolve a context-defined profile into component ids. profile_def is
    either a list of ids or a dict {"components": [...]}. Unknown ids raise
    ValueError (caller maps to a fail-closed error) — unsupported inputs are
    REJECTED, never silently ignored."""
    if isinstance(profile_def, dict):
        ids = profile_def.get("components")
        if ids is None:
            raise ValueError("context profile must define a 'components' list")
    elif isinstance(profile_def, list):
        ids = profile_def
    else:
        raise ValueError(f"context profile must be a list or object, got {type(profile_def).__name__}")
    if not isinstance(ids, list) or not ids:
        raise ValueError("context profile components must be a non-empty list")
    known = _catalog_ids()
    unknown = [c for c in ids if not isinstance(c, str) or c not in known]
    if unknown:
        raise ValueError(
            f"context profile contains unsupported component id(s): "
            f"{unknown}; known ids: {sorted(known)}"
        )
    # Platform filter (same rule as preset profiles): an id whose platforms
    # exclude this platform is a config error here, not silently dropped —
    # the operator asked for it explicitly.
    from .components import CATALOG
    by_id = {c.id: c for c in CATALOG}
    for cid in ids:
        comp = by_id[cid]
        if platform_profile and "all" not in comp.platforms:
            if platform_profile not in comp.platforms:
                raise ValueError(
                    f"context profile component '{cid}' is not available on "
                    f"platform '{platform_profile}'"
                )
    return list(ids)


def profile_components(profile: str, platform_profile: str = None):
    """Return platform-appropriate component ids for the preset. Components
    whose `platforms` exclude the current platform profile are dropped, so a
    declined/absent prerequisite never silently appears (spec R3)."""
    ids = PROFILES.get(profile)
    if ids is None:
        raise SystemExit(f"unknown profile: {profile}")
    from .components import CATALOG

    by_id = {c.id: c for c in CATALOG}
    out = []
    for cid in ids:
        comp = by_id.get(cid)
        if comp is None:
            continue
        if platform_profile and "all" not in comp.platforms:
            if platform_profile not in comp.platforms:
                continue
        out.append(cid)
    return out