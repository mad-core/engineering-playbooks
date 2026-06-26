from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .._constants import GENERATED_NOTE
from .._io import frontmatter, write
from .._manifest import GenContext


def gen_changelog(repo: Path, ctx: GenContext) -> None:
    limit = str(int(ctx.params("limit")["limit"]))
    fm = frontmatter(ctx.section, ctx.service, ctx.domain)
    try:
        log = subprocess.run(
            ["git", "log", "--no-merges", "--date=short",
             "--pretty=format:- %ad `%h` %s", "-n", limit,
             "--", ".", ":(exclude)docs/"],
            cwd=str(repo), capture_output=True, text=True, timeout=30,
        )
        entries = log.stdout.strip() if log.returncode == 0 else ""
    except Exception as e:  # noqa: BLE001
        entries = ""
        print(f"  git log failed: {e}", file=sys.stderr)
    if not entries:
        body = (f"{fm}\n# Changelog\n\n> **Status:** unknown — `git log` "
                "produced no output.\n")
    else:
        body = (
            f"{fm}\n# Changelog\n\n"
            f"{GENERATED_NOTE} (raw `git log`; centrally this is compacted to "
            "highlights — semantic grouping is a TODO for a human/LLM.)\n\n"
            f"## Recent history (last {limit} non-merge commits)\n\n" + entries + "\n"
        )
    write(repo, ctx.path, body)
