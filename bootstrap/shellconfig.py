"""Managed .zshrc block (tasks 6.1, 6.2; spec bootstrap-execution R5/R7).

Marker-delimited block; rerun replaces only between markers; conflict outside
markers -> ZshrcConflict (mapped to exit 5). Never executes or exports the
live zshrc. The block body is the reviewed default in defaults/zshrc block.
"""

import os

BEGIN = "# >>> bootstraps managed >>>"
END = "# <<< bootstraps managed <<<"

BLOCK_BODY = """# Managed by bootstraps: content between these markers is replaced on rerun.
# Everything outside the markers is yours and is preserved.
export PATH="$HOME/.cargo/bin:$PATH"
[ -f "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh"
# oh-my-zsh
export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="refined"
plugins=(git fzf)
[ -d "$ZSH" ] && source "$ZSH/oh-my-zsh.sh\""""


class ZshrcConflict(Exception):
    pass


def _zshrc_path():
    return os.path.expanduser("~/.zshrc")


def zshrc_managed_ok():
    path = _zshrc_path()
    if not os.path.isfile(path):
        return False
    content = open(path, encoding="utf-8").read()
    return BEGIN in content and END in content


def apply_zshrc_block(log):
    path = _zshrc_path()
    if os.path.isfile(path):
        content = open(path, encoding="utf-8").read()
        if BEGIN in content and END in content:
            pre = content.split(BEGIN, 1)[0]
            post = content.split(END, 1)[1]
            new = pre + BEGIN + "\n" + BLOCK_BODY + "\n" + END + post
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(new)
            log(f"updated managed block in {path}")
            return
        if "bootstraps managed" in content:
            raise ZshrcConflict(
                f"{path} contains a malformed bootstraps managed block; resolve manually"
            )
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n" + BEGIN + "\n" + BLOCK_BODY + "\n" + END + "\n")
        log(f"appended managed block to {path}")
    else:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(BEGIN + "\n" + BLOCK_BODY + "\n" + END + "\n")
        log(f"created {path} with managed block")