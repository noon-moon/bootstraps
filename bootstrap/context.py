"""Context loader (task 4.2): private repo supplying instance data.

Shapes (documented in docs/context-schema.md):
- profiles.toml / context.toml: machine profile variants
- resources.json: project resource definitions (merged into manifest)
- credentials.json: credential *references* only ({env: NAME}|{file: PATH})
- models.json: per-role model preferences (selected model per run-as role)
- hooks/: post-install scripts (require --allow-hooks in headless)

Precedence: interactive choice > context > shipped default (D6).
Fail-closed (spec instance-context R4): missing/invalid context in headless
-> EX_CONTEXT before any mutation. Credential references resolve at use.
"""

import json
import os


class ContextError(Exception):
    pass


def _is_headless(args):
    return bool(getattr(args, "headless", False))


class Context:
    def __init__(self, path, profiles=None, resources=None, models=None,
                 credential_refs=None, hooks=None):
        self.path = path
        self.profiles = profiles or {}
        self.resources = resources or {}
        self.models = models or {}
        self.credential_refs = credential_refs or {}
        self.hooks = hooks or []

    def describe(self):
        n_res = sum(len(v) for v in self.resources.values()) if isinstance(self.resources, dict) else len(self.resources)
        return f"path={self.path} profiles={len(self.profiles)} resources={n_res} models={len(self.models)}"

    def resolve_credential(self, ref_name):
        """Resolve a credential REFERENCE at the moment of use. Returns the
        secret value or raises ContextError. Never logs the value."""
        ref = self.credential_refs.get(ref_name)
        if not ref:
            raise ContextError(f"credential reference '{ref_name}' not defined in context")
        if isinstance(ref, dict) and "env" in ref:
            val = os.environ.get(ref["env"])
            if not val:
                raise ContextError(
                    f"credential '{ref_name}' references env var {ref['env']!r}, which is unset"
                )
            return val
        if isinstance(ref, dict) and "file" in ref:
            try:
                with open(os.path.expanduser(ref["file"]), encoding="utf-8") as fh:
                    content = fh.read().strip()
            except OSError as exc:
                raise ContextError(f"credential '{ref_name}' file unreadable: {exc}") from exc
            if ref.get("key"):
                for line in content.splitlines():
                    if line.startswith(ref["key"] + "="):
                        return line.split("=", 1)[1].strip()
                raise ContextError(f"credential '{ref_name}' key {ref.get('key')!r} not found in file")
            return content
        raise ContextError(f"credential '{ref_name}' has an unsupported reference shape")

    def apply_to_manifest(self, manifest):
        manifest.merge_resources(self.resources)

    def run_hooks(self, dev_root, log, allowed=True):
        if not self.hooks:
            return
        if not allowed:
            log("context hooks present but not allowed (--allow-hooks); skipping")
            return
        import subprocess

        for hook in self.hooks:
            log(f"context hook: {os.path.basename(hook)}")
            r = subprocess.run(["bash", hook], capture_output=True, text=True, cwd=dev_root)
            if r.returncode != 0:
                raise ContextError(f"hook failed: {hook}\n{r.stderr[-400:]}")


def load_context(args, log):
    """Resolve --context (local path) or --clone-context (headless deploy key
    path). Returns Context or None. Raises ContextError for fail-closed."""
    path = _resolve_context_path(args, log)
    if not path:
        if _is_headless(args) and getattr(args, "profile", None) == "headless-server":
            # Headless VPS profile without context: allowed only if the user
            # explicitly selected components (flag or selection file);
            # otherwise fail closed (spec R4).
            if not getattr(args, "components", None) and not getattr(
                args, "selection", None
            ):
                raise ContextError(
                    "headless run requires --context (instance data) or explicit "
                    "--components/--selection"
                )
        return None
    if not os.path.isdir(path):
        raise ContextError(f"context path does not exist: {path}")

    ctx = Context(path)
    _load_tomlish(os.path.join(path, "context.toml"), ctx, log)
    _load_json_into(os.path.join(path, "resources.json"), ctx, "resources", log)
    _load_json_into(os.path.join(path, "models.json"), ctx, "models", log)
    _load_json_into(os.path.join(path, "credentials.json"), ctx, "credential_refs", log)
    hooks_dir = os.path.join(path, "hooks")
    if os.path.isdir(hooks_dir):
        ctx.hooks = sorted(
            os.path.join(hooks_dir, f) for f in os.listdir(hooks_dir)
            if f.endswith(".sh") and os.access(os.path.join(hooks_dir, f), os.X_OK)
        )
    # Minimum-content contract (spec instance-context R1): a context repo must
    # supply at least a profile definition or project/resource definitions.
    if not ctx.profiles and not ctx.resources:
        raise ContextError(
            f"context at {path} is empty: needs context.toml (profile) or "
            "resources.json (project/resource definitions)"
        )
    log(f"context loaded: {ctx.describe()}")
    return ctx


def _resolve_context_path(args, log):
    reset_deferred_clone()  # one-shot per run; stale state never survives
    if getattr(args, "context", None):
        return os.path.abspath(os.path.expanduser(args.context))
    if getattr(args, "clone_context", None):
        # Clone happens DEFERRED (after plan/confirm) via ctx.clone_target;
        # here we only validate the URL shape. R3: no mutation before preview.
        ctx_url = args.clone_context
        if not ctx_url.startswith(("https://", "git@")):
            raise ContextError(
                "--clone-context must be an https:// or git@ URL "
                "(deploy key pre-provisioned)"
            )
        log(f"context repo will be cloned after plan confirmation: {ctx_url.split('@')[-1] if '@' in ctx_url else ctx_url}")
        _DEFERRED_CLONE["url"] = ctx_url
        _DEFERRED_CLONE["target"] = "~/dev/context"
        return None  # no local context yet; engine re-loads after clone
    return None


_DEFERRED_CLONE = {}


def reset_deferred_clone():
    _DEFERRED_CLONE.clear()


def deferred_clone_pending():
    return bool(_DEFERRED_CLONE.get("url"))


def perform_deferred_clone(args, log):
    """Called by the engine after plan confirmation. Returns a Context or
    None; raises ContextError on failure."""
    url = _DEFERRED_CLONE.get("url")
    if not url:
        return None
    target = os.path.expanduser(_DEFERRED_CLONE.get("target", "~/dev/context"))
    os.makedirs(os.path.dirname(target), exist_ok=True)
    log(f"cloning context repo into {target}")
    import subprocess

    r = subprocess.run(["git", "clone", url, target], capture_output=True, text=True)
    if r.returncode != 0:
        raise ContextError(f"context clone failed: {r.stderr[-300:]}")
    _DEFERRED_CLONE.clear()
    args.context = target
    return load_context(args, log)


def _load_json_into(path, ctx, attr, log):
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContextError(f"invalid context file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ContextError(f"context file {path} must contain an object")
    setattr(ctx, attr, data)


def _load_tomlish(path, ctx, log):
    if not os.path.isfile(path):
        return
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ContextError(f"invalid context file {path}: {exc}") from exc
    # minimal TOML subset: profile = "name" and [models] tables; full tomllib
    # when available
    import sys

    if sys.version_info >= (3, 11):
        import tomllib

        try:
            with open(path, "rb") as fh:
                data = tomllib.load(fh)
        except tomllib.TOMLDecodeError as exc:
            raise ContextError(f"invalid context file {path}: {exc}") from exc
        if "profile" in data:
            ctx.profiles["default"] = data["profile"]
        models = data.get("models")
        if isinstance(models, dict):
            ctx.models.update(models)
        return
    # fallback parser: profile = "x"
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("profile") and "=" in line:
            _, _, val = line.partition("=")
            ctx.profiles["default"] = val.strip().strip('"')
            break