"""Engine entry: orchestrates platform detection, context, plan, execution.

Invoked by bootstrap.sh as a script; bootstrap/ is imported as a package via
the parent dir on sys.path.
"""

import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bootstrap import __version__  # noqa: E402
from bootstrap.cli import parse  # noqa: E402
from bootstrap.exitcodes import (  # noqa: E402
    EX_OK,
    EX_USAGE,
    EX_PLATFORM,
    EX_CONTEXT,
    EX_COMPONENT,
    EX_CONFLICT,
)
from bootstrap.runlog import RunLog, default_log_path  # noqa: E402


def main(argv=None):
    args = parse(argv if argv is not None else sys.argv[1:])
    if args.version:
        print(f"bootstraps engine {__version__}")
        return EX_OK
    if args.headless and not args.profile:
        print("bootstrap: --headless requires --profile", file=sys.stderr)
        return EX_USAGE

    from bootstrap.platform_detect import detect, UnsupportedPlatform, describe
    from bootstrap.engine import Engine

    log = RunLog(default_log_path())
    log.start(argv or sys.argv[1:])
    log(f"log file: {log.path}")
    try:
        try:
            platform_info = detect()
        except UnsupportedPlatform as exc:
            log(f"ERROR: unsupported platform: {exc}")
            return _finish(log, EX_PLATFORM)
        log(f"platform: {describe(platform_info)}")

        engine = Engine(args, platform_info, log)
        code = engine.run()
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EX_USAGE
    except Exception as exc:  # unexpected engine error
        log(f"ERROR: unexpected engine failure: {exc!r}")
        code = EX_USAGE
    return _finish(log, code)


def _finish(log, code):
    log.end(code)
    return code


if __name__ == "__main__":
    sys.exit(main())