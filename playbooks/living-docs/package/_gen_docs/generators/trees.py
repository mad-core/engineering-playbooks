from __future__ import annotations

from pathlib import Path

from .._constants import GENERATED_NOTE
from .._git import tracked_under
from .._io import frontmatter, write
from .._manifest import GenContext


def render_tree(repo: Path, root_rel: str, label: str) -> str:
    """ASCII tree of `root_rel/`, built from git-tracked files only.

    Source of truth is `git ls-files`, not the filesystem walk: anything
    not committed (caches, bytecode, generated `__pycache__`, local build
    output) is invisible by construction, so local and CI produce byte-
    identical output regardless of working-tree cruft. No denylist needed.
    """
    files = tracked_under(repo, root_rel.rstrip("/"))
    if not files:
        return f"{label}/ (no tracked files)"

    # Build a nested dict from "/"-separated paths. Dirs map to dicts;
    # files map to None. ls-files only emits files, so internal nodes are
    # synthesized from the path segments.
    prefix = root_rel.rstrip("/") + "/"
    tree: dict = {}
    for full in files:
        rel = full[len(prefix):] if full.startswith(prefix) else full
        if not rel:
            continue
        cur = tree
        parts = rel.split("/")
        for p in parts[:-1]:
            nxt = cur.get(p)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[p] = nxt
            cur = nxt
        cur.setdefault(parts[-1], None)

    lines: list[str] = [label + "/"]

    def walk(node: dict, prefix: str) -> None:
        # dirs first, then files; each alphabetical → stable across runs.
        items = sorted(node.items(), key=lambda kv: (kv[1] is None, kv[0].lower()))
        for i, (name, child) in enumerate(items):
            last = i == len(items) - 1
            lines.append(
                f"{prefix}{'└── ' if last else '├── '}{name}"
                + ("/" if isinstance(child, dict) else "")
            )
            if isinstance(child, dict):
                walk(child, prefix + ("    " if last else "│   "))

    walk(tree, "")
    return "\n".join(lines)


def gen_source_tree(repo: Path, ctx: GenContext) -> None:
    root_rel = ctx.params("root")["root"]
    tree = render_tree(repo, root_rel, root_rel)
    body = (
        f"{frontmatter(ctx.section, ctx.service, ctx.domain)}\n"
        "# Source Tree\n\n"
        f"{GENERATED_NOTE}\n\n"
        f"Tree of `{root_rel}/` reconstructed from git-tracked files only "
        "(untracked artifacts — caches, bytecode, build output — are "
        "invisible by construction). CI re-runs this generator and diffs "
        "the result; a mismatch fails the structure linter (deterministic, "
        "no LLM).\n\n"
        "```\n" + tree + "\n```\n"
    )
    write(repo, ctx.path, body)


def gen_test_tree(repo: Path, ctx: GenContext) -> None:
    root_rel = ctx.params("root")["root"]
    tree = render_tree(repo, root_rel, root_rel)
    body = (
        f"{frontmatter(ctx.section, ctx.service, ctx.domain)}\n"
        "# Test Tree\n\n"
        f"{GENERATED_NOTE}\n\n"
        f"Tree of `{root_rel}/` reconstructed from git-tracked files only. "
        "Same CI re-run + diff as `source-tree.md`.\n\n"
        "```\n" + tree + "\n```\n"
    )
    write(repo, ctx.path, body)
