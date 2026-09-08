"""~/dev workspace create/reuse (task 5.1, spec dev-workspace R1)."""

import os


def setup_workspace(args, log):
    dev_root = os.path.abspath(os.path.expanduser(args.dev_root))
    if os.path.isdir(dev_root):
        log(f"workspace: reusing existing {dev_root} (no existing resource will be moved or removed)")
    else:
        os.makedirs(dev_root, exist_ok=True)
        log(f"created {dev_root}")
    for sub in ("repo", "worktrees", "tools"):
        path = os.path.join(dev_root, sub)
        if not os.path.isdir(path):
            os.makedirs(path)
            log(f"created {path}")
    return dev_root