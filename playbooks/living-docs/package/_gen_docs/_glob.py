from __future__ import annotations

import re as _re
from pathlib import Path

from ._git import tracked_paths

_GLOB_REGEX_CACHE: dict[str, "_re.Pattern[str]"] = {}


def _glob_to_regex(pattern: str) -> "_re.Pattern[str]":
    """Translate a `**`-aware path glob to an anchored regex.

    Semantics (gitignore/pathspec-like, segment-aware):
      - `**`  zero or more path segments (incl. empty). Only as a full
              segment: `**/...`, `.../**`, `.../**/...`.
      - `*`   any chars within a single segment (does NOT cross `/`).
      - `?`   one char within a single segment.
      - `/`   literal separator.
      - other characters are literal (regex-escaped).
    """
    if pattern in _GLOB_REGEX_CACHE:
        return _GLOB_REGEX_CACHE[pattern]

    out: list[str] = ["^"]
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        # `**` only counts when surrounded by `/` or string boundaries.
        if c == "*" and i + 1 < n and pattern[i + 1] == "*":
            before_ok = (i == 0) or (pattern[i - 1] == "/")
            after = i + 2
            after_ok = (after >= n) or (pattern[after] == "/")
            if before_ok and after_ok:
                if after < n and pattern[after] == "/":
                    # `**/` — collapses the preceding `/` (already emitted)
                    # plus `**/` into "zero or more segments + /".
                    if out and out[-1] == _re.escape("/"):
                        out.pop()
                        out.append("(?:/.*)?/")
                    else:  # start of pattern: `**/foo`
                        out.append("(?:.*/)?")
                    i = after + 1
                else:
                    # `**` at end (no trailing `/`). `src/**` matches
                    # `src/foo` and `src/a/b` but NOT `src`.
                    if out and out[-1] == _re.escape("/"):
                        out.pop()
                        out.append("/.*")
                    else:
                        out.append(".*")
                    i = after
                continue
            # Fall through: treat as two single `*`s (degenerate, segment-bound).
        if c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(_re.escape(c))
            i += 1
    out.append("$")
    rx = _re.compile("".join(out))
    _GLOB_REGEX_CACHE[pattern] = rx
    return rx


def _path_matches_glob(path: str, pattern: str) -> bool:
    return bool(_glob_to_regex(pattern).match(path))


def _changed_paths_matching(changed: list[str], globs: list[str]) -> list[str]:
    """Return subset of `changed` matched by any of `globs`."""
    hits: list[str] = []
    for path in changed:
        if any(_path_matches_glob(path, g) for g in globs):
            hits.append(path)
    return hits


def _glob_match_repo(repo: Path, pat: str) -> bool:
    """True if `pat` matches any git-tracked path in the repo.

    Asks the git index, not the filesystem — gitignored artifacts
    (`__pycache__`, `.pyc`, build output) must not "rescue" a broken
    trigger glob whose intended target was removed/renamed.
    """
    return any(_path_matches_glob(p, pat) for p in tracked_paths(repo))


def _self_test_glob() -> None:
    """Sanity checks for the glob → regex translator. Raises on regression."""
    cases = [
        # (path, pattern, expected)
        ("src/a.py", "src/**", True),
        ("src/a/b/c.py", "src/**", True),
        ("src", "src/**", False),
        ("tests/a.py", "src/**", False),
        ("src/a.py", "src/*", True),
        ("src/a/b.py", "src/*", False),
        ("foo.py", "**/foo.py", True),
        ("a/foo.py", "**/foo.py", True),
        ("a/b/foo.py", "**/foo.py", True),
        ("a/b/bar.py", "**/foo.py", False),
        ("src/foo.py", "src/**/foo.py", True),
        ("src/a/foo.py", "src/**/foo.py", True),
        ("src/a/b/foo.py", "src/**/foo.py", True),
        ("src/a/foo.txt", "src/**/foo.py", False),
        ("src/main.py", "src/*.py", True),
        ("src/a/main.py", "src/*.py", False),
        (".github/workflows/ci.yml", ".github/workflows/**", True),
        ("requirements.txt", "requirements.txt", True),
        ("requirements-dev.txt", "requirements-*.txt", True),
        ("requirements.txt.bak", "requirements-*.txt", False),
    ]
    for path, pat, expected in cases:
        got = _path_matches_glob(path, pat)
        if got != expected:
            raise AssertionError(
                f"glob mismatch: pattern={pat!r} path={path!r} "
                f"expected={expected} got={got} "
                f"regex={_glob_to_regex(pat).pattern}"
            )
