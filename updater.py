"""Controlled, non-destructive updater for news-reader.

This module intentionally keeps update mechanics outside Flask so the old process
can be stopped before replacing the working tree and the new process can be
health-checked independently. It never runs reset --hard, clean, pull, or
changes the configured origin remote.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import time
import urllib.error
import urllib.request
from pathlib import Path

REPOSITORY_URL = "https://github.com/xusz12/news-reader.git"
RUNTIME_DIR = Path(os.getenv("NEWS_READER_UPDATER_DIR", tempfile.gettempdir()))
LOCK_PATH = RUNTIME_DIR / "news-reader-updater.lock"
STATE_PATH = RUNTIME_DIR / "news-reader-updater-state.json"
VERSION_TAG_RE = r"^v\d+(?:\.\d+){2,3}$"


def parse_version(tag: str) -> tuple[int, ...] | None:
    import re
    if not isinstance(tag, str) or not re.fullmatch(VERSION_TAG_RE, tag):
        return None
    return tuple(int(part) for part in tag[1:].split("."))


def is_stable_tag(tag: str) -> bool:
    return parse_version(tag) is not None


def _run(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "git_failed").strip()[:500])
    return result.stdout.strip()


def git_state(repo: Path) -> dict[str, str | bool]:
    status = _run(repo, "status", "--porcelain", "--untracked-files=all")
    head = _run(repo, "rev-parse", "HEAD")
    branch = _run(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    return {"clean": not status, "head": head, "branch": branch, "detached": not bool(branch)}


def _write_state(payload: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATE_PATH)


def _wait_for_pid(pid: int, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    raise RuntimeError("old_process_not_stopped")


def _stop_child(child: subprocess.Popen | None) -> None:
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def _launch(repo: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(repo / "app.py")], cwd=repo,
                            env=os.environ.copy(), start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _wait_healthy(url: str, commit: str, child: subprocess.Popen, timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    base = url.rsplit("/api/version", 1)[0]
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return False
        if _health_check(url, commit):
            try:
                for path in ("/", "/static/app.js", "/static/style.css"):
                    with urllib.request.urlopen(base + path, timeout=2) as response:
                        if response.status != 200:
                            raise OSError("static_health_failed")
                return True
            except (OSError, ValueError):
                pass
        time.sleep(0.5)
    return False


def _health_check(url: str, expected_commit: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("ok") is True and payload.get("commit") == expected_commit
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def apply_update(
    repo: Path,
    tag: str,
    commit: str,
    version: str,
    *,
    old_pid: int | None = None,
    launch: bool = False,
    health_url: str = "http://127.0.0.1:8080/api/version",
    run_id: str = "",
) -> dict:
    """Fetch and fast-forward to a checked tag, preserving all user files.

    ``launch`` is opt-in so unit tests and operators can perform the Git phase
    without starting a real service. Production invokes the CLI with launch.
    """
    if not is_stable_tag(tag) or tag != version or parse_version(version) is None:
        raise ValueError("invalid_stable_version")
    if not isinstance(commit, str) or len(commit) != 40 or any(c not in "0123456789abcdefABCDEF" for c in commit):
        raise ValueError("invalid_commit")
    repo = repo.resolve()
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise ValueError("not_git_repository")

    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("update_in_progress") from exc

        state = git_state(repo)
        old_head = str(state["head"])
        progress = {"tag": tag, "version": version, "commit": commit, "old_head": old_head, "run_id": run_id}
        old_stopped = False
        new_child = None
        merged = False
        def report(status: str, **extra: object) -> None:
            _write_state({**progress, "status": status, "updated_at": int(time.time()), **extra})
        report("validating")
        try:
            if not state["clean"]:
                raise RuntimeError("dirty_worktree")
            if state["detached"]:
                raise RuntimeError("detached_head")
            if launch and (old_pid is None or old_pid <= 0):
                raise ValueError("missing_controlled_process")
            report("fetching")
            # Fetch only FETCH_HEAD; no local tag ref or origin mutation.
            _run(repo, "fetch", "--no-tags", REPOSITORY_URL, f"refs/tags/{tag}")
            fetched_commit = _run(repo, "rev-parse", "FETCH_HEAD^{commit}")
            if fetched_commit.lower() != commit.lower():
                raise RuntimeError("tag_commit_mismatch")
            try:
                target_manifest = json.loads(_run(repo, "show", f"{commit}:version.json"))
            except (ValueError, RuntimeError) as exc:
                raise RuntimeError("target_version_manifest_missing") from exc
            if not isinstance(target_manifest, dict) or target_manifest.get("version") != tag or target_manifest.get("repository") != REPOSITORY_URL:
                raise RuntimeError("target_version_mismatch")
            ancestor_check = subprocess.run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", old_head, commit],
                capture_output=True, check=False,
            )
            if ancestor_check.returncode != 0:
                raise RuntimeError("target_not_descendant")
            if git_state(repo) != state:
                raise RuntimeError("worktree_changed")
            if launch:
                report("stopping_old")
                try:
                    os.kill(old_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                _wait_for_pid(old_pid)
                old_stopped = True
            report("merging")
            _run(repo, "merge", "--ff-only", commit)
            merged = True
            if _run(repo, "rev-parse", "HEAD") != commit:
                raise RuntimeError("post_merge_commit_mismatch")
            report("starting_new" if launch else "updated")
            if launch:
                new_child = _launch(repo)
                report("checking_health")
                if not _wait_healthy(health_url, commit, new_child):
                    raise RuntimeError("health_check_failed")
                report("healthy")
            return {"ok": True, "status": "healthy" if launch else "updated", "commit": commit, "version": version}
        except Exception as exc:
            failure = str(exc)[:500]
            if not launch or not old_stopped:
                report("failed", error=failure)
                raise
            report("rolling_back", error=failure)
            try:
                _stop_child(new_child)
                current = git_state(repo)
                if not current["clean"] or current["detached"] or current["branch"] != state["branch"]:
                    raise RuntimeError("rollback_unsafe_worktree_changed")
                if merged:
                    if current["head"] != commit:
                        raise RuntimeError("rollback_unsafe_head_changed")
                    # --keep refuses overwriting user modifications; never --hard/clean.
                    _run(repo, "reset", "--keep", old_head)
                elif current["head"] != old_head:
                    raise RuntimeError("rollback_unsafe_head_changed")
                old_child = _launch(repo)
                if not _wait_healthy(health_url, old_head, old_child):
                    raise RuntimeError("old_version_health_check_failed")
                report("rolled_back", error=failure, active_commit=old_head)
            except Exception as rollback_exc:
                report("rollback_failed", error=failure, rollback_error=str(rollback_exc)[:500])
            raise
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="start managed news-reader server")
    parser.add_argument("--repo")
    parser.add_argument("--tag")
    parser.add_argument("--commit")
    parser.add_argument("--version")
    parser.add_argument("--pid", type=int)
    parser.add_argument("--health-url", default="http://127.0.0.1:8080/api/version")
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    if args.serve:
        env = os.environ.copy()
        env["NEWS_READER_MANAGED"] = "1"
        return subprocess.call([sys.executable, str(Path(__file__).resolve().parent / "app.py")],
                               cwd=Path(__file__).resolve().parent, env=env)
    if not all((args.repo, args.tag, args.commit, args.version, args.pid)):
        parser.error("update requires --repo, --tag, --commit, --version and --pid")
    try:
        apply_update(Path(args.repo), args.tag, args.commit, args.version, old_pid=args.pid, launch=True, health_url=args.health_url, run_id=args.run_id)
        return 0
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
