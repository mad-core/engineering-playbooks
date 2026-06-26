"""Git-index queries shared by generators and the linter.

Single source of truth for "what's in the repo": the git index, never the
working tree. Cached per-process so a full `lint` or `gen all` run pays at
most one `git ls-files` invocation per (repo, pathspec).

Rationale: the structure linter and the deterministic tree generators
previously read the filesystem (`Path.iterdir`, `glob.glob`). That made
their output depend on stray bytecode (`__pycache__`, `.pyc`), build
artifacts, and other gitignored cruft — so `make lint` could pass locally
while CI failed on a clean checkout. Routing every "is this in the repo?"
question through `git ls-files` eliminates that class of bug by
construction.
"""
from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def _ls_files(repo_str: str, pathspec: str) -> tuple[str, ...]:
    """Tracked paths under `pathspec` (empty string = whole repo).

    Returned paths are repo-relative, forward-slashed (git's native form).
    Returns an empty tuple if `repo` is not a git repo or git is missing —
    callers degrade gracefully rather than raising.
    """
    cmd = ["git", "-C", repo_str, "ls-files"]
    if pathspec:
        cmd += ["--", pathspec]
    try:
        out = subprocess.run(
            cmd, check=True, capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ()
    return tuple(line for line in out.splitlines() if line)


def tracked_paths(repo: Path) -> tuple[str, ...]:
    """All git-tracked paths in `repo`, repo-relative."""
    return _ls_files(str(repo), "")


def tracked_under(repo: Path, root_rel: str) -> tuple[str, ...]:
    """Tracked paths under `root_rel/` (or matching `root_rel` exactly)."""
    return _ls_files(str(repo), root_rel)
