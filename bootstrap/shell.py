"""Shell command helper shared by adapters and components."""

import shutil
import subprocess


def run(cmd, check=True, capture=True, env=None, cwd=None, timeout=None):
    """Run a command list; return CompletedProcess. On failure with check=True,
    raise CommandError carrying returncode and (truncated) output."""
    printed = " ".join(cmd)
    proc = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        env=env,
        cwd=cwd,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise CommandError(
            printed,
            proc.returncode,
            (proc.stdout or "")[-800:],
            (proc.stderr or "")[-800:],
        )
    return proc


def which(name):
    return shutil.which(name)


class CommandError(Exception):
    def __init__(self, cmd, code, out, err):
        self.cmd = cmd
        self.code = code
        self.stdout = out
        self.stderr = err
        super().__init__(f"command failed ({code}): {cmd}\n{err or out}".strip())