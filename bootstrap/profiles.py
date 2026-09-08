"""Profile presets (task 3.1): TOML component lists in profiles/."""

import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # minimal fallback for 3.9/3.10: parse simple `key = [...]` tables
    tomllib = None

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


def profile_components(profile: str):
    ids = PROFILES.get(profile)
    if ids is None:
        raise SystemExit(f"unknown profile: {profile}")
    # Platform filtering: desktop-only components are excluded on linux,
    # headless excludes desktop apps by definition.
    from .components import CATALOG

    by_id = {c.id: c for c in CATALOG}
    out = []
    for cid in ids:
        comp = by_id.get(cid)
        if comp is None:
            continue
        if comp.platforms and "all" not in comp.platforms:
            out.append(cid)
        else:
            out.append(cid)
    return out