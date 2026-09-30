#!/usr/bin/env python3
"""Scheduled news entrypoint: one managed attempt per profile/KST date, no auto-resume."""
import argparse
import json
import os
from pathlib import Path
import sys

try:
    from . import task_control as control
except ImportError:
    import task_control as control


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("morning", "it", "trend"))
    profile = parser.parse_args(argv).profile
    os.umask(0o077)
    root = Path(os.environ.get("CHUMJI_NEWS_CHECKPOINT_ROOT",
                               str(Path.home() / ".local/state/chumji-news/checkpoints")))
    run = root.expanduser().resolve() / profile / control.today()
    if not run.exists():
        # Atomic directory creation in start arbitrates concurrent invocations.
        # No forced replay if a competing start wins the race.
        return control.main(["start", profile, "--publish", "--directory", str(run)])
    try:
        with control.locked(run, "worker.lock", nonblocking=True):
            with control.locked(run, "state.lock"):
                state = control.read(run)
                if (state["profile"], state["mode"], state["date"]) != (profile, "--publish", control.today()):
                    raise ValueError("existing checkpoint identity mismatch")
                status = state["status"]
        print(json.dumps({"run": str(run), "status": status, "action": "not_restarted"}))
        if status == "completed":
            return 0
        return control.PAUSED if status == "paused" else 2
    except (OSError, ValueError, KeyError) as error:
        print(f"existing checkpoint requires inspection; not restarted: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
