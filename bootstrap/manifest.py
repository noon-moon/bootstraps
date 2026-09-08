"""Project/resource manifest v1 (task 5.2, spec dev-workspace R2/R3).

Kinds: repo, vault, backlog. Location: `path` (relative to dev root),
`host`+`path`, or `remote`. Roles: context, artifact. Registration is
descriptive only — never authorization (spec R3).
"""

import json
import os

SCHEMA_VERSION = 1

DEFAULT_PROJECTS = {
    "braindance": {"name": "Braindance", "resources": []},
    "no-great-deed": {"name": "No Great Deed", "resources": []},
    "infrastructure": {"name": "Infrastructure", "resources": []},
}

VALID_KINDS = {"repo", "vault", "backlog"}
VALID_ROLES = ("context", "artifact")


class ManifestError(Exception):
    pass


class Manifest:
    def __init__(self, dev_root, data=None):
        self.dev_root = dev_root
        self.path = os.path.join(dev_root, "projects.json")
        self.data = data or {
            "schema_version": SCHEMA_VERSION,
            "projects": json.loads(json.dumps(DEFAULT_PROJECTS)),
        }

    @classmethod
    def load(cls, dev_root):
        path = os.path.join(dev_root, "projects.json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as fh:
                try:
                    data = json.load(fh)
                except json.JSONDecodeError as exc:
                    raise ManifestError(f"invalid manifest {path}: {exc}") from exc
            m = cls(dev_root, data)
            m.validate()
            return m
        return cls(dev_root)

    def save(self):
        self.validate()
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2)
            fh.write("\n")

    def merge_resources(self, resources):
        """Merge context resource definitions into the manifest. Context wins
        for instance data; projects context doesn't touch keep shipped
        defaults."""
        projects = self.data.setdefault("projects", {})
        for project_id, project_entry in resources.items():
            if isinstance(project_entry, dict):
                proj_name = project_entry.get("name", project_id)
                new_resources = project_entry.get("resources", [])
            elif isinstance(project_entry, list):
                proj_name = project_id
                new_resources = project_entry
            else:
                continue
            proj = projects.setdefault(project_id, {"name": proj_name, "resources": []})
            existing = {r.get("id") for r in proj.get("resources", []) if isinstance(r, dict)}
            for res in new_resources:
                if not isinstance(res, dict) or not res.get("id"):
                    continue
                if res["id"] in existing:
                    proj["resources"] = [
                        res if (isinstance(r, dict) and r.get("id") == res["id"]) else r
                        for r in proj["resources"]
                    ]
                else:
                    proj["resources"].append(res)
                    existing.add(res["id"])

    def validate(self):
        data = self.data
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ManifestError(
                f"schema_version must be {SCHEMA_VERSION}, got {data.get('schema_version')!r}"
            )
        projects = data.get("projects")
        if not isinstance(projects, dict):
            raise ManifestError("projects must be an object")
        for pid, proj in projects.items():
            if not isinstance(proj, dict):
                raise ManifestError(f"project {pid}: must be an object")
            for res in proj.get("resources", []):
                self._validate_resource(pid, res)
        return True

    def validate_or_report(self, log):
        try:
            self.validate()
            return True
        except ManifestError as exc:
            log(f"ERROR: invalid manifest: {exc}")
            return False

    @staticmethod
    def _validate_resource(pid, res):
        if not isinstance(res, dict):
            raise ManifestError(f"project {pid}: resource must be an object")
        rid = res.get("id")
        if not rid or not isinstance(rid, str):
            raise ManifestError(f"project {pid}: resource needs string 'id'")
        kind = res.get("kind")
        if kind not in VALID_KINDS:
            raise ManifestError(
                f"project {pid} resource {rid}: kind must be one of {sorted(VALID_KINDS)}, got {kind!r}"
            )
        roles = res.get("roles", [])
        if not isinstance(roles, list) or any(
            r not in VALID_ROLES for r in roles
        ):
            raise ManifestError(
                f"project {pid} resource {rid}: roles must be within {VALID_ROLES}, got {roles!r}"
            )
        has_path = "path" in res
        has_host = "host" in res
        has_remote = "remote" in res
        if not (has_path or has_host or has_remote):
            raise ManifestError(
                f"project {pid} resource {rid}: needs one of path/host/remote"
            )
        if has_path:
            p = res["path"]
            if os.path.isabs(p):
                raise ManifestError(
                    f"project {pid} resource {rid}: path must be relative to dev root, got {p!r}"
                )
            if ".." in p.replace("\\", "/").split("/"):
                raise ManifestError(
                    f"project {pid} resource {rid}: path may not contain '..': {p!r}"
                )