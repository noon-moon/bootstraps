"""All catalog components (tasks 2.2–2.8).

Sources fixed per design D4: nvm (Node LTS), rustup, Homebrew/apt packages,
official installers for agent CLIs, npm globals for Backlog/OpenSpec/TypeScript/Quartz.
Every component: check() cheap, install(), verify() concrete.
"""

import json
import os
import shutil
import subprocess
from .base import Component, ComponentFailure
from .registry import register
from ..shell import run, which


def _node_prefix_bin():
    home = os.path.expanduser("~")
    return os.path.join(home, ".nvm", "versions", "node", "lts", "bin") if False else _nvm_current_bin()


def _nvm_current_bin():
    home = os.path.expanduser("~")
    nvm_dir = os.path.join(home, ".nvm")
    alias_path = os.path.join(nvm_alias_dir(nvm_root(nvm_home())) , "default") if False else None
    return alias_path


def nvm_home():
    return os.path.expanduser("~/.nvm")


def nvm_root(home=None):
    return home or nvm_home()


def nvm_alias_dir(root):
    return os.path.join(root, "alias")


def _nvm_bin_dir():
    """Path to the nvm-installed Node LTS bin, or None."""
    versions_root = os.path.expanduser("~/.nvm/versions/node")
    if not os.path.isdir(versions_root):
        return None
    try:
        versions = sorted(
            (d for d in os.listdir(versions_root) if d.startswith("v")),
            key=lambda v: [int(x) for x in v[1:].split(".")[:3]],
        )
    except (OSError, ValueError):
        return None
    lts = [v for v in versions if int(v[1:].split(".")[1]) % 2 == 0]  # even minor = LTS
    pick = lts[-1] if lts else (versions[-1] if versions else None)
    return os.path.join(versions_root, pick, "bin") if pick else None


def _npm_env():
    env = dict(os.environ)
    node_bin = _nvm_bin_dir()
    if node_bin := node_bin_path():
        env["PATH"] = node_bin + os.pathsep + env.get("PATH", "")
    return env


def node_bin_path():
    b = _nvm_bin_dir()
    if b and shutil.which("node", path=b):
        return b
    return None


def npm_global_install(pkg, log):
    env = _npm_env()
    if not shutil.which("npm", path=env["PATH"]):
        raise ComponentFailure("npm not found after Node install")
    log(f"npm install -g {pkg}")
    subprocess.run(["npm", "install", "-g", pkg], env=env, check=False,
                   capture_output=True, text=True)


# ---- base toolchain ------------------------------------------------------

@register
class Git(Component):
    id = "git"
    summary = "Git version control"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("git"))

    def install(self, a, ctx, dev_root, log):
        if not shutil.which("git"):
            a.install_package("git", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("git"))


@register
class Rust(Component):
    id = "rust"
    summary = "Rust toolchain via rustup"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("cargo") or shutil.which(os.path.expanduser("~/.cargo/bin/cargo")))

    def install(self, a, ctx, dev_root, log):
        log("rustup: installing stable toolchain")
        r = subprocess.run(
            ["sh", "-c", "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise ComponentFailure(f"rustup installer failed: {r.stderr[-400:]}")

    def verify(self, a, ctx, dev_root, log):
        cargo = shutil.which("cargo") or os.path.expanduser("~/.cargo/bin/cargo")
        return os.path.exists(cargo)


@register
class Node(Component):
    id = "node"
    summary = "Node LTS via nvm (provides npm)"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(node_bin_path())

    def install(self, a, ctx, dev_root, log):
        if not shutil.which("curl"):
            a.install_package("curl", log)
        log("nvm: installing + Node LTS")
        r = subprocess.run(
            ["bash", "-c", 'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && . ~/.nvm/nvm.sh && nvm install --lts && nvm alias default lts/*'],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise ComponentFailure(f"nvm/node install failed: {r.stderr[-400:]}")

    def verify(self, a, ctx, dev_root, log):
        return bool(node_bin_path())


@register
class Fzf(Component):
    id = "fzf"
    summary = "fuzzy finder"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("fzf"))

    def install(self, a, ctx, dev_root, log):
        a.install_package("fzf", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("fzf"))


@register
class Docker(Component):
    id = "docker"
    summary = "Docker (Desktop on macOS; docker-ce on Ubuntu)"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("docker"))

    def install(self, a, ctx, dev_root, log):
        if a.name == "macos":
            a.install_package("docker", log, cask=True)  # Docker Desktop
        else:
            log("docker-ce: apt repository setup")
            for cmd in (
                "apt-get install -y -qq ca-certificates curl gnupg",
                "install -m 0755 -d /etc/apt/keyrings",
                "curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc",
                "chmod a+r /etc/apt/keyrings/docker.asc",
                'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list',
                "apt-get update -qq",
                "apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin",
            ):
                r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
                if r.returncode != 0:
                    raise ComponentFailure(f"docker setup failed at: {cmd}\n{r.stderr[-300:]}")

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("docker"))


# ---- agent CLIs -----------------------------------------------------------

@register
class OpenCode(Component):
    id = "opencode"
    summary = "OpenCode CLI (official installer)"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("opencode"))

    def install(self, a, ctx, dev_root, log):
        r = subprocess.run(
            ["bash", "-c", "curl -fsSL https://opencode.ai/install | bash"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise ComponentFailure(f"opencode installer failed: {r.stderr[-300:]}")

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("opencode"))


@register
class ClaudeCode(Component):
    id = "claude-code"
    summary = "Claude Code CLI"
    deps = ("node",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("claude"))

    def install(self, a, ctx, dev_root, log):
        npm_global_install("@anthropic-ai/claude-code", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("claude"))


@register
class Codex(Component):
    id = "codex"
    summary = "Codex CLI"
    deps = ("node",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("codex"))

    def install(self, a, ctx, dev_root, log):
        npm_global_install("@openai/codex", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("codex"))


# ---- npm-global tools -----------------------------------------------------

@register
class Backlog(Component):
    id = "backlog"
    summary = "Backlog.md CLI (npm global)"
    deps = ("node",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("backlog"))

    def install(self, a, ctx, dev_root, log):
        npm_global_install("backlog.md", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("backlog"))


@register
class OpenSpec(Component):
    id = "openspec"
    summary = "OpenSpec CLI (npm)"
    deps = ("node",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("openspec"))

    def install(self, a, ctx, dev_root, log):
        npm_global_install("@fission-ai/openspec", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("openspec"))


@register
class TypeScript(Component):
    id = "typescript"
    summary = "TypeScript compiler (npm global)"
    deps = ("node",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("tsc"))

    def install(self, a, ctx, dev_root, log):
        npm_global_install("typescript", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("tsc"))


@register
class Quartz(Component):
    id = "quartz"
    summary = "Quartz site generator (npm)"
    deps = ("node", "npm" if False else "git")
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("npx") and _npm_list_has("quartz"))

    def install(self, a, ctx, dev_root, log):
        npm_global_install("quartz", log)

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("quartz")) or _npm_list_has("quartz")


def _npm_list_has(pkg):
    env = _npm_env()
    try:
        r = subprocess.run(["npm", "list", "-g", "--depth=0", pkg],
                           env=env, capture_output=True, text=True)
        return r.returncode == 0 and pkg in (r.stdout or "")
    except OSError:
        return False


# ---- desktop / platform-specific ------------------------------------------

@register
class OhMyZsh(Component):
    id = "oh-my-zsh"
    summary = "Oh My Zsh framework"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return os.path.isdir(os.path.expanduser("~/.oh-my-zsh"))

    def install(self, a, ctx, dev_root, log):
        if not shutil.which("zsh"):
            a.install_package("zsh", log)
        r = subprocess.run(
            ["bash", "-c", 'RUNZSH=no KEEP_ZSHRC=yes sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended'],
            capture_output=True, text=True,
        )
        if r.returncode != 0 and not os.path.isdir(os.path.expanduser("~/.oh-my-zsh")):
            raise ComponentFailure(f"oh-my-zsh install failed: {r.stderr[-300:]}")

    def verify(self, a, ctx, dev_root, log):
        return os.path.isdir(os.path.expanduser("~/.oh-my-zsh"))


@register
class ShellConfig(Component):
    id = "shell-config"
    summary = "Reviewed .zshrc managed block (see change S6)"
    deps = ("oh-my-zsh",)
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        from ..shellconfig import zshrc_managed_ok
        return zshrc_managed_ok()

    def install(self, a, ctx, dev_root, log):
        from ..shellconfig import apply_zshrc_block

        apply_zshrc_block(log)

    def verify(self, a, ctx, dev_root, log):
        from ..shellconfig import zshrc_managed_ok
        return zshrc_managed_ok()


@register
class Tailscale(Component):
    id = "tailscale"
    summary = "Tailscale overlay network (optional)"
    deps = ()
    platforms = ("all",)

    def check(self, a, ctx, dev_root, log):
        return bool(shutil.which("tailscale"))

    def install(self, a, ctx, dev_root, log):
        if a.name == "macos":
            a.install_package("tailscale", log, cask=True)
        else:
            r = subprocess.run(
                ["bash", "-c", "curl -fsSL https://tailscale.com/install.sh | sh"],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                raise ComponentFailure(f"tailscale install failed: {r.stderr[-300:]}")

    def verify(self, a, ctx, dev_root, log):
        return bool(shutil.which("tailscale"))


@register
class ITerm2(Component):
    id = "iterm2"
    summary = "iTerm2 terminal (macOS)"
    deps = ()
    platforms = ("macos",)

    def check(self, a, ctx, dev_root, log):
        return a.has("iterm2", cask=True)

    def install(self, a, ctx, dev_root, log):
        a.install_package("iterm2", log, cask=True)

    def verify(self, a, ctx, dev_root, log):
        return a.has("iterm2", cask=True)


@register
class Obsidian(Component):
    id = "obsidian"
    summary = "Obsidian vault interface (desktop only)"
    deps = ()
    platforms = ("macos",)

    def check(self, a, ctx, dev_root, log):
        return a.has("obsidian", cask=True)

    def install(self, a, ctx, dev_root, log):
        a.install_package("obsidian", log, cask=True)

    def verify(self, a, ctx, dev_root, log):
        return a.has("obsidian", cask=True)