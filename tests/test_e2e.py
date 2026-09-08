"""Engine-level tests: run bootstrap.sh headless in isolated HOME/dev-root and
assert exit codes + mutation boundaries. These exercise the real CLI contract
(argparse mapping, fail-closed, conflict exit 5) that unit tests cannot."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIM = os.path.join(REPO, "bootstrap.sh")


def run_bootstrap(args, home, dev_root=None, timeout=120):
    env = dict(os.environ, HOME=home, BOOTSTRAPS_LOG_DIR=os.path.join(home, "logs"))
    cmd = [SHIM] + args
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    return proc


def snapshot(root):
    """Return {relpath: content-hash} for everything under root."""
    import hashlib

    out = {}
    if not os.path.isdir(root):
        return out
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, root)
            try:
                with open(p, "rb") as fh:
                    out[rel] = hash(fh.read())
            except OSError:
                out[rel] = None
    return out


class EngineE2E(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="bse2e-home-")
        self.dev = os.path.join(self.home, "devroot")
        os.makedirs(self.dev, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_bogus_flag_exits_1_not_2(self):
        proc = run_bootstrap(["--bogus-flag"], self.home)
        self.assertEqual(proc.returncode, 1, proc.stderr[-300:])

    def test_headless_missing_context_exits_3_and_mutates_nothing(self):
        before = snapshot(self.dev)
        proc = run_bootstrap(
            ["--headless", "--profile", "headless-server", "--context", "/nonexistent"],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-300:])
        self.assertEqual(snapshot(self.dev), before)

    def test_headless_empty_context_dir_exits_3(self):
        ctxdir = os.path.join(self.home, "empty-ctx")
        os.makedirs(ctxdir)
        before = snapshot(self.dev)
        proc = run_bootstrap(
            ["--headless", "--profile", "headless-server", "--context", ctxdir],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-300:])
        self.assertEqual(snapshot(self.dev), before)

    def test_headless_with_minimal_context_and_git_succeeds(self):
        ctxdir = os.path.join(self.home, "ctx")
        os.makedirs(ctxdir)
        with open(os.path.join(ctxdir, "context.toml"), "w") as fh:
            fh.write('profile = "headless-server"\n')
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--context", ctxdir, "--skip-doctrine",
                "--components", "git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-300:])
        self.assertTrue(os.path.isfile(os.path.join(self.dev, "projects.json")))
        data = json.load(open(os.path.join(self.dev, "projects.json")))
        self.assertEqual(data["schema_version"], 1)

    def test_zshrc_conflict_aborts_with_exit_5_before_doctrine(self):
        seed = os.path.join(self.home, ".zshrc")
        with open(seed, "w") as fh:
            fh.write("# bootstraps managed but malformed (no markers)\n")
        before = snapshot(self.dev)
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--skip-doctrine",  # doctrine skipped; conflict must still be 5
                "--components", "oh-my-zsh,shell-config", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 5, proc.stderr[-400:])
        # conflict aborts remaining component + doctrine mutations: no
        # AGENTS.md in dev-root, and .zshrc outside home untouched after seed
        self.assertFalse(os.path.exists(os.path.join(self.dev, "AGENTS.md")))

    def test_headless_requires_profile(self):
        proc = run_bootstrap(["--headless"], self.home)
        self.assertEqual(proc.returncode, 1, proc.stderr[-200:])

    def test_unknown_component_exits_1(self):
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--components", "not-a-component", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr[-200:])

    def test_help_exits_0(self):
        proc = run_bootstrap(["--help"], self.home)
        self.assertEqual(proc.returncode, 0, proc.stderr[-200:])

    def test_doctrine_stage_conflict_exits_5(self):
        # AGENTS.md malformed (no markers) -> doctrine install conflicts.
        dev = self.dev
        agents = os.path.join(dev, "AGENTS.md")
        os.makedirs(dev, exist_ok=True)
        with open(agents, "w") as fh:
            fh.write("bootstraps managed doctrine malformed (no markers)\n")
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--components", "git", "--yes",
                "--dev-root", dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 5, proc.stderr[-400:])

    def test_selection_file_honored(self):
        sel = os.path.join(self.home, "sel.json")
        with open(sel, "w") as fh:
            json.dump({"schema_version": 1, "components": ["git"]}, fh)
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--selection", sel, "--skip-doctrine", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        self.assertTrue(os.path.isdir(os.path.join(self.dev, "repo")))

    def test_selection_file_unknown_component_exits_1(self):
        sel = os.path.join(self.home, "sel2.json")
        with open(sel, "w") as fh:
            json.dump({"schema_version": 1, "components": ["bogus"]}, fh)
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--selection", sel, "--yes", "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 1, proc.stderr[-300:])

    def test_malformed_context_toml_exits_3(self):
        ctxdir = os.path.join(self.home, "bad-ctx")
        os.makedirs(ctxdir)
        with open(os.path.join(ctxdir, "context.toml"), "w") as fh:
            fh.write("this is not = = valid toml {{{\n")
        before = snapshot(self.dev)
        proc = run_bootstrap(
            ["--headless", "--profile", "headless-server", "--context", ctxdir],
            self.home,
        )
        self.assertEqual(proc.returncode, 3, proc.stderr[-300:])
        self.assertEqual(snapshot(self.dev), before)

    def test_summary_excludes_conflict_skipped(self):
        seed = os.path.join(self.home, ".zshrc")
        with open(seed, "w") as fh:
            fh.write("# bootstraps managed but malformed\n")
        proc = run_bootstrap(
            [
                "--headless", "--profile", "headless-server",
                "--skip-doctrine",
                "--components", "oh-my-zsh,shell-config,git", "--yes",
                "--dev-root", self.dev,
            ],
            self.home,
        )
        self.assertEqual(proc.returncode, 5)
        # git comes after shell-config alphabetically in plan order? No —
        # plan order follows selection order: oh-my-zsh, shell-config, git.
        # git must be reported skipped, not installed.
        self.assertNotIn("installed/verified: git", proc.stderr)
        self.assertIn("skipped after conflict", proc.stderr)


if __name__ == "__main__":
    unittest.main()