"""Interactive wizard (task 3.2): preset -> toggles -> closure -> plan ->
confirm. Plan preview + confirmation happens before mutation (spec R3)."""

import sys


def _ask(prompt, default_yes=True):
    suffix = " [Y/n] " if default_yes else " [y/N] "
    try:
        raw = input(prompt + suffix).strip().lower()
    except EOFError:
        return default_yes
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def wizard_selection(args, platform_info, log):
    from .profiles import PROFILES
    from .components import CATALOG, build_registry

    print("\nSelect a preset:")
    names = list(PROFILES)
    for i, name in enumerate(names, 1):
        print(f"  {i}) {name}")
    choice = input("preset number/name (default personal): ").strip() or "1"
    if choice.isdigit() and 1 <= int(choice) <= len(names):
        profile = names[int(choice) - 1]
    elif choice in PROFILES:
        profile = choice
    else:
        profile = "personal"
    selected = set(PROFILES[profile])

    registry = build_registry(platform_info)
    print("\nToggle components (enter to keep current):")
    for comp in CATALOG:
        if comp.id not in registry:
            continue
        current = "x" if comp.id in selected else " "
        try:
            raw = input(f"  [{current}] {comp.id:<14} {comp.summary} (y/n/enter): ").strip().lower()
        except EOFError:
            raw = ""
        if raw == "y":
            selected.add(comp.id)
        elif raw == "n":
            selected.discard(comp.id)

    if platform_info["profile"] == "ubuntu":
        # desktop-only components are not installable via apt profile
        for desktop in ("iterm2", "obsidian"):
            if desktop in selected:
                print(f"  note: {desktop} is macOS-only; deselecting")
                selected.discard(desktop)

    return sorted(selected)


def confirm_plan():
    try:
        raw = input("Proceed with this plan? [y/N] ").strip().lower()
    except EOFError:
        return False
    return raw in ("y", "yes")