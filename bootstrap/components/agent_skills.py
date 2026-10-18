"""Wizard seam (task 4.2): the agent-skills component installs global skills
via tools/scripts/install-skills using --json-plan for plan preview and saved
defaults for invocation. Standalone install-skills remains fully usable."""

import json
import os
import subprocess

from .base import Component, ComponentFailure
from .registry import register

BEADS_ROLES = (
    "beads-orchestrator", "beads-designer", "beads-planner",
    "beads-implementer", "beads-code-reviewer", "beads-experimental-reviewer",
)
LEGACY_ROLES = (
    "run-as-orchestrator", "run-as-designer", "run-as-planner",
    "run-as-implementer", "run-as-code-reviewer",
    "run-as-experimental-reviewer", "run-as-archivist",
)


def _legacy_paths():
    base = os.path.expanduser("~/.config/opencode")
    for name in LEGACY_ROLES:
        for path in (os.path.join(base, "skills", name), os.path.join(base, "agents", f"{name}.md")):
            if os.path.lexists(path):
                yield path


def _find_installer(ctx, dev_root):
    candidates = []
    if ctx and ctx.resources:
        for project in ctx.resources.values():
            if isinstance(project, dict):
                for res in project.get("resources", []):
                    if res.get("id") == "bootstraps" and res.get("path"):
                        candidates.append(os.path.join(dev_root, res["path"]))
    canonical = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates.append(canonical)
    for c in candidates:
        cand = os.path.join(c, "tools", "scripts", "install-skills")
        if os.path.isfile(cand):
            return cand, c
    return None, None


@register
class AgentSkills(Component):
    id = "agent-skills"
    summary = "Global agent skills via install-skills (roles + flows)"
    deps = ("git",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        skills = os.path.expanduser("~/.config/opencode/skills")
        # R4: islink alone reports broken installs as healthy — require the
        # link to RESOLVE (isdir through the link). Always rerun install on
        # check() failure; it is idempotent and repairs dangling links.
        return not any(_legacy_paths()) and all(os.path.isdir(os.path.join(skills, n)) for n in BEADS_ROLES)

    def install(self, a, ctx, dev_root, log):
        installer, canonical = _find_installer(ctx, dev_root)
        if not installer:
            raise ComponentFailure(
                "install-skills not found: clone the bootstraps repo or register "
                "it in the project manifest so the skills component can find it"
            )
        # Plan preview first (json seam), then install with saved defaults.
        plan = subprocess.run([installer, "--json-plan"], capture_output=True, text=True)
        if plan.returncode != 0:
            raise ComponentFailure(f"install-skills --json-plan failed: {plan.stderr[-300:]}")
        try:
            plan_data = json.loads(plan.stdout)
        except json.JSONDecodeError as exc:
            raise ComponentFailure(f"invalid plan JSON from install-skills: {exc}") from exc
        log(f"agent-skills plan: {len(plan_data.get('skills', []))} skills, "
            f"harnesses: {', '.join(plan_data.get('harnesses', []))}")

        old = [name for name in LEGACY_ROLES if os.path.isdir(
            os.path.join(canonical, "tools", "skills", "roles", name))]
        if old:
            cleanup = subprocess.run(
                [installer, "--skills", *old, "--harness", "opencode",
                 "--canonical", canonical, "--uninstall"],
                capture_output=True, text=True,
            )
            if cleanup.returncode != 0:
                raise ComponentFailure(f"legacy role uninstall failed: {(cleanup.stderr or cleanup.stdout)[-400:]}")
            log(cleanup.stdout.strip() or "legacy roles: none installed")
        remaining = list(_legacy_paths())
        if remaining:
            raise ComponentFailure("legacy role files remain (preserved as unmanaged/user-edited): "
                                   + ", ".join(remaining))

        cmd = [installer, "--skills", *BEADS_ROLES, "--harness", "opencode", "--canonical", canonical]
        models_path = os.path.join(ctx.path, "models.json") if ctx else None
        if models_path and os.path.isfile(models_path):
            cmd += ["--models", models_path]
        log(f"agent-skills: {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise ComponentFailure(f"install-skills failed: {(r.stderr or r.stdout)[-400:]}")
        log(r.stdout.strip() or "agent-skills: installed")

    def verify(self, a, ctx, dev_root, log):
        skills = os.path.expanduser("~/.config/opencode/skills")
        ok = not any(_legacy_paths()) and all(os.path.isdir(os.path.join(skills, n)) for n in BEADS_ROLES)
        if not ok:
            log("agent-skills verify: global skills not discoverable (dangling or missing)")
        return ok
