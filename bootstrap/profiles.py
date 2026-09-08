"""Profile presets (task 3.1). Presets are component id lists; platform
filtering happens here so e.g. headless --profile personal on Ubuntu never
selects desktop-only components (review G1 obs. 11)."""

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
    "headless-server": [
        "git", "rust", "node", "docker", "opencode", "backlog",
        "openspec", "tailscale",
    ],
}


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