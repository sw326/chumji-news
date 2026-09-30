#!/usr/bin/env python3
"""Opt-in, local checkpoint control for one news run (no scheduler operations)."""
import argparse
from contextlib import contextmanager
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
PAUSED = 75
STAGES = ("collect", "summarize", "publish")


def today():
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


def fingerprint(mode):
    code = hashlib.sha256()
    for path in sorted(ROOT.rglob("*")):
        parts = path.relative_to(ROOT).parts
        if path.is_file() and "tests" not in parts and (path.suffix in {".py", ".sh"} or "prompts" in parts):
            code.update(str(path.relative_to(ROOT)).encode())
            code.update(path.read_bytes())
    # Execution/session IDs differ between cron and the owner's later resume.
    # Fingerprint meaningful model/connection settings, not caller bookkeeping.
    stable_openclaw = {"OPENCLAW_BIN", "OPENCLAW_MODEL", "OPENCLAW_FALLBACK_MODELS",
                       "OPENCLAW_CONFIG_PATH", "OPENCLAW_STATE_DIR", "OPENCLAW_GATEWAY_URL",
                       "OPENCLAW_GATEWAY_TOKEN", "OPENCLAW_GATEWAY_PASSWORD"}
    settings = {k: v for k, v in os.environ.items()
                if (k.startswith("CHUMJI_NEWS_") or k in stable_openclaw or k in {"JQ_BIN", "HOME"})
                and not k.startswith("CHUMJI_NEWS_CONTROL_")}
    if mode == "--publish":
        # Only explicit publication touches credential files. Store digests, never
        # their values; replacing a destination/account file blocks later resume.
        for key, default in (
            ("CHUMJI_NEWS_SUPABASE_ENV", Path.home() / ".config/supabase/chumji-news.env"),
            ("CHUMJI_NEWS_TELEGRAM_TOKEN_FILE", Path.home() / ".openclaw/secrets/telegram-macmini-bot-token"),
        ):
            path = Path(os.environ.get(key, str(default))).expanduser().resolve()
            settings[key + "_content_hash"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return code.hexdigest(), hashlib.sha256(json.dumps(settings, sort_keys=True).encode()).hexdigest()


@contextmanager
def locked(run, name, nonblocking=False):
    with (run / name).open("a+") as handle:
        flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if nonblocking else 0)
        fcntl.flock(handle, flags)
        # Closing only our descriptor preserves a lock inherited by a live child.
        yield handle


def read(run):
    state = json.loads((run / "state.json").read_text())
    if state.get("version") != 1 or state.get("runner") != str(ROOT):
        raise ValueError("checkpoint belongs to another runner/version")
    return state


def write(run, state):
    # Caller holds state.lock; only opaque metadata/hashes are stored here.
    fd, name = tempfile.mkstemp(prefix=".state-", dir=run)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(state, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, run / "state.json")
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_artifacts(run, state):
    for name, digest in state["artifacts"].items():
        if Path(name).name != name:
            raise ValueError("invalid artifact name")
        if hashlib.sha256((run / "artifacts" / name).read_bytes()).hexdigest() != digest:
            raise ValueError("checkpoint artifact changed: " + name)


def internal(run, action, stage, files):
    with locked(run, "state.lock"):
        state = read(run)
        if action == "enter":
            if state["status"] != "running":
                raise ValueError("run is not running")
            if (state["code_hash"], state["settings_hash"]) != fingerprint(state["mode"]):
                raise ValueError("runner code or environment changed; next stage blocked")
            verify_artifacts(run, state)
            if stage in state["completed"]:
                print("skip")
                return 0
            if state["pause_requested"]:
                state.update(status="paused", active_stage=None)
                write(run, state)
                return PAUSED
            expected = STAGES[len(state["completed"])]
            if stage != expected:
                raise ValueError("invalid stage order")
            if stage == "publish" and state["date"] != today():
                raise ValueError("publication checkpoint is from another KST date")
            state["active_stage"] = stage
            write(run, state)  # publish intent precedes any external write
            print("run")
        else:
            if state["status"] != "running" or state["active_stage"] != stage:
                raise ValueError("stage completion does not match active stage")
            for name in files:
                if Path(name).name != name:
                    raise ValueError("invalid artifact name")
                state["artifacts"][name] = hashlib.sha256((run / "artifacts" / name).read_bytes()).hexdigest()
            state["completed"].append(stage)
            state["active_stage"] = None
            write(run, state)
    return 0


def execute(run, resume=False):
    # Inherit this FD into the pipeline, so a killed controller cannot create
    # a second local writer while its existing shell is still alive.
    with locked(run, "worker.lock", nonblocking=True) as worker:
        with locked(run, "state.lock"):
            state = read(run)
            if state["status"] == "completed":
                raise ValueError("already completed; no replay")
            if state["active_stage"] in {"summarize", "publish"}:
                raise ValueError("previous model/publication outcome is unresolved; automatic resume blocked")
            if state["mode"] == "--publish" and state["date"] != today():
                raise ValueError("publication checkpoint is from another KST date")
            if (state["code_hash"], state["settings_hash"]) != fingerprint(state["mode"]):
                raise ValueError("runner code or environment changed; resume blocked")
            verify_artifacts(run, state)
            state.update(status="running", active_stage=None)
            if resume:
                state["pause_requested"] = False
            write(run, state)
        env = os.environ | {"CHUMJI_NEWS_CONTROL_DIR": str(run),
                            "CHUMJI_NEWS_CONTROL_DATE": state["date"]}
        print(json.dumps({"run": str(run), "status": "running"}), file=sys.stderr, flush=True)
        result = subprocess.run([str(ROOT / "run_profile.sh"), state["profile"], state["mode"]],
                                env=env, pass_fds=(worker.fileno(),))
        with locked(run, "state.lock"):
            state = read(run)
            if result.returncode == 0:
                expected = list(STAGES if state["mode"] == "--publish" else STAGES[:2])
                if state["completed"] != expected:
                    raise ValueError("pipeline exited without expected checkpoints")
                state["status"] = "completed"
            elif state["status"] != "paused":
                state["status"] = ("needs_attention" if state["active_stage"] in {"summarize", "publish"}
                                   else "failed")
            state["last_exit"] = result.returncode
            write(run, state)
        return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    start = commands.add_parser("start")
    start.add_argument("profile", choices=("morning", "it", "trend"))
    start.add_argument("--publish", action="store_true", help="explicit publication; default dry-run still uses a model")
    start.add_argument("--directory", type=Path, required=True, help="new private checkpoint directory outside Git")
    start.add_argument("--start-paused", action="store_true")
    for name in ("status", "pause", "resume"):
        commands.add_parser(name).add_argument("directory", type=Path)
    helper = commands.add_parser("_checkpoint", help=argparse.SUPPRESS)
    helper.add_argument("directory", type=Path)
    helper.add_argument("operation", choices=("enter", "complete"))
    helper.add_argument("stage", choices=STAGES)
    helper.add_argument("files", nargs="*")
    args = parser.parse_args(argv)
    os.umask(0o077)
    run = args.directory.expanduser().resolve()
    try:
        if args.action == "start":
            run.mkdir(mode=0o700, parents=True, exist_ok=False)
            (run / "artifacts").mkdir(mode=0o700)
            code, settings = fingerprint("--publish" if args.publish else "--dry-run")
            state = {"version": 1, "runner": str(ROOT), "profile": args.profile,
                     "mode": "--publish" if args.publish else "--dry-run", "date": today(),
                     "code_hash": code, "settings_hash": settings, "completed": [], "artifacts": {},
                     "active_stage": None, "status": "paused" if args.start_paused else "created",
                     "pause_requested": args.start_paused}
            with locked(run, "state.lock"):
                write(run, state)
            if args.start_paused:
                print(json.dumps({"run": str(run), "status": "paused"}))
                return 0
            return execute(run)
        if args.action == "_checkpoint":
            return internal(run, args.operation, args.stage, args.files)
        if args.action == "resume":
            return execute(run, resume=True)
        with locked(run, "state.lock"):
            state = read(run)
            if args.action == "pause":
                if state["status"] != "completed":
                    state["pause_requested"] = True
                    write(run, state)
            # Do not expose artifacts, credentials or environment contents.
            view = {k: state[k] for k in ("status", "active_stage", "completed", "pause_requested", "date", "profile", "mode")}
        try:
            with locked(run, "worker.lock", nonblocking=True):
                view["local_worker_active"] = False
        except BlockingIOError:
            view["local_worker_active"] = True
        if not view["local_worker_active"] and view["status"] == "running":
            view["status"] = "interrupted_unverified"
        view["schedule"] = "unchanged"
        view["remote_session"] = "not_inspected"
        print(json.dumps(view, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
