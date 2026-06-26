from __future__ import annotations

from pathlib import Path

# When set (by the linter), generators capture their output here instead of
# writing to disk. Keyed by the manifest `path` (the canonical doc path).
_DRY_BUF: dict[str, str] | None = None


def start_dry_run() -> None:
    """Redirect all write() calls to an in-memory buffer."""
    global _DRY_BUF
    _DRY_BUF = {}


def end_dry_run() -> dict[str, str] | None:
    """Stop capturing and return the accumulated buffer."""
    global _DRY_BUF
    out, _DRY_BUF = _DRY_BUF, None
    return out


def frontmatter(section: str, service: str, domain: str) -> str:
    """The four-field contract frontmatter. `domain` and `section` are
    manifest-driven — never assumed to be `backend`."""
    return (
        "---\n"
        f"service: {service}\n"
        f"domain: {domain}\n"
        f"section: {section}\n"
        "source_of_truth: repo\n"
        "---\n"
    )


def write(repo: Path, doc_path: str, body: str) -> None:
    """Write a generated doc to its manifest-declared `doc_path`.

    `doc_path` is the repo-relative path exactly as the manifest records it
    (e.g. `docs/02-architecture/source-tree.md`). No `docs/` prefix is
    assumed by the engine — the contract owns the layout.
    """
    body = body if body.endswith("\n") else body + "\n"
    if _DRY_BUF is not None:
        _DRY_BUF[doc_path] = body
        return
    dest = repo / doc_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    print(f"  wrote {doc_path}")
