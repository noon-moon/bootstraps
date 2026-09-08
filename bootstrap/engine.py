"""Engine orchestration: detect -> context -> selection -> plan -> confirm ->
workspace -> components -> doctrine -> summary.

Exit mapping per D5. Plan preview happens before any mutation (spec R3/R4).
"""

import json
import os
import sys

from .exitcodes import (
    EX_OK,
    EX_CONTEXT,
    EX_COMPONENT,
    EX_CONFLICT,
)
from .platforms import get_adapter
from .components import CATALOG, build_registry, resolve_closure, ComponentFailure


class Engine:
    def __init__(self, args, platform_info, log):
        self.args = args
        self.platform = platform_info
        self.log = log
        self.profile = args.profile
        self.interactive = not args.headless

    # ---- selection -----------------------------------------------------
    def selection(self):
        """Resolve selected component ids: explicit override > selection file
        > profile > interactive wizard."""
        a = self.args
        if a.components:
            ids = [c.strip() for c in a.components.split(",") if c.strip()]
            return self._validate_ids(ids)
        if a.selection:
            with open(a.selection, encoding="utf-8") as fh:
                data = json.load(fh)
            ids = data.get("components") or []
            return self._validate_ids(ids, source=f"selection file {a.selection}")
        if a.profile:
            from .profiles import profile_components

            return profile_components(a.profile, self.platform["profile"])
        if not self.interactive:
            from .profiles import profile_components

            return profile_components("headless-server", self.platform["profile"])
        from .wizard import wizard_selection

        return wizard_selection(a, self.platform, self.log)

    def _validate_ids(self, ids, source="components flag"):
        known = {c.id for c in CATALOG}
        unknown = [i for i in ids if i not in known]
        if unknown:
            self.log(f"ERROR: unknown component(s) in {source}: {', '.join(unknown)}")
            raise SystemExit(1)
        return ids

    # ---- run -----------------------------------------------------------
    def run(self):
        log = self.log

        # 1. Context (fail-closed in headless)
        from .context import load_context, ContextError

        try:
            ctx = load_context(self.args, log)
        except ContextError as exc:
            log(f"ERROR: {exc}")
            return EX_CONTEXT

        # 2. Selection + dependency closure
        selected = self.selection()
        registry = build_registry(self.platform)
        try:
            plan_ids, blocked = resolve_closure(selected, registry)
        except ComponentFailure as exc:
            log(f"ERROR: {exc}")
            return EX_COMPONENT

        if blocked:
            log("plan: declined prerequisites blocked the following selections:")
            for component_id, reason in blocked:
                log(f"  - {component_id}: {reason}")
            return EX_COMPONENT

        # 3. Plan preview (before ANY mutation)
        log("plan:")
        for cid in plan_ids:
            comp = registry[cid]
            log(f"  - {cid} ({comp.summary})")
        log(f"workspace: {os.path.expanduser(self.args.dev_root)}")
        if ctx:
            log(f"context: {ctx.describe()}")

        if self.args.dry_run:
            log("dry-run: no changes made")
            return EX_OK

        if self.interactive and not self.args.yes:
            from .wizard import confirm_plan

            if not confirm_plan():
                log("aborted by user before any change")
                return EX_OK

        # 3b. Deferred context clone (--clone-context): now that the plan is
        # confirmed, perform the clone and reload context (R3 wiring).
        from .context import (
            deferred_clone_pending,
            perform_deferred_clone,
        )

        if deferred_clone_pending():
            try:
                ctx = perform_deferred_clone(self.args, log)
            except ContextError as exc:
                log(f"ERROR: {exc}")
                return EX_CONTEXT
            if ctx is None:
                log("ERROR: deferred clone produced no context")
                return EX_CONTEXT
            log(f"context after clone: {ctx.describe()}")

        # 4. Adapter prerequisites
        adapter = get_adapter(self.platform["profile"])
        adapter.ensure_prerequisites(log)

        # 5. ~/dev workspace + manifest
        from .workspace import setup_workspace

        dev_root = setup_workspace(self.args, log)
        from .manifest import Manifest

        manifest = Manifest.load(dev_root)
        if ctx:
            ctx.apply_to_manifest(manifest)
        manifest.save()
        log(f"manifest: {manifest.path}")

        # 5b. Context post-install hooks (--allow-hooks gated; task 4.2)
        if ctx and ctx.hooks:
            ctx.run_hooks(dev_root, log, allowed=bool(self.args.allow_hooks))

        # 6. Components (failure-isolated; conflicts abort per D7)
        failures = {}
        conflict = None
        conflict_component = None
        for cid in plan_ids:
            if conflict:
                log(f"component {cid}: skipped (aborting after managed-file conflict)")
                continue
            comp = registry[cid]
            try:
                comp.ensure(adapter, ctx, dev_root, log)
            except ComponentFailure as exc:
                log(f"component {cid}: FAILED — {exc}")
                failures[cid] = str(exc)
            except ConflictError as exc:
                conflict = str(exc)
                conflict_component = cid
                log(f"ERROR: unmanaged-file conflict in component {cid}: {exc}")
            except Exception as exc:  # noqa: BLE001
                log(f"component {cid}: FAILED — unexpected: {exc!r}")
                failures[cid] = repr(exc)

        # 7. Doctrine (AGENTS.md) + shell config
        if conflict is None and not self.args.skip_doctrine:
            try:
                from .doctrine import install_doctrine

                install_doctrine(dev_root, log)
            except ConflictError as exc:
                conflict = str(exc)
                log(f"ERROR: unmanaged-file conflict: {exc}")

        # 8. Save selection for reuse
        if self.args.save_selection:
            with open(self.args.save_selection, "w", encoding="utf-8") as fh:
                json.dump(
                    {"schema_version": 1, "profile": self.profile, "components": plan_ids},
                    fh,
                    indent=2,
                )
            log(f"selection saved: {self.args.save_selection}")

        # 9. Summary
        log("summary:")
        done = [cid for cid in plan_ids if cid not in failures]
        if conflict:
            # Components skipped after a conflict are NOT done — do not list
            # them as installed (review G2 R4).
            conflict_idx = plan_ids.index(conflict_component) if conflict_component else len(plan_ids)
            done = [cid for cid in done if plan_ids.index(cid) < conflict_idx]
        log(f"  installed/verified: {', '.join(done) or '(none)'}")
        if conflict:
            log(f"  skipped after conflict: {', '.join(cid for cid in plan_ids if cid not in done and cid not in failures) or '(none)'}")
        if failures:
            for cid, why in failures.items():
                log(f"  failed: {cid} — {why}")
        if conflict:
            log("rerun after resolving the conflict; see docs in defaults/")
            return EX_CONFLICT
        if failures:
            return EX_COMPONENT
        return EX_OK


class ConflictError(Exception):
    """Managed-file conflict (markers malformed / foreign block present)."""