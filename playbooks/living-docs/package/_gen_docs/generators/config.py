from __future__ import annotations

import ast
from pathlib import Path

from .._constants import GENERATED_NOTE
from .._io import frontmatter, write
from .._manifest import GenContext


def extract_settings_keys(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    keys.append(stmt.target.id)
                elif isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            keys.append(t.id)
    # drop dunders / pydantic Config noise, dedupe, stable order
    seen: list[str] = []
    for k in keys:
        if not k.startswith("_") and k not in ("model_config", "Config") and k not in seen:
            seen.append(k)
    return seen


def gen_config(repo: Path, ctx: GenContext) -> None:
    params = ctx.params("settings_module")
    src = repo / params["settings_module"]
    fm = frontmatter(ctx.section, ctx.service, ctx.domain)
    if not src.exists():
        body = (
            f"{fm}\n# Configuration\n\n"
            f"> **Status:** unknown — settings module declared at "
            f"`{params['settings_module']}` does not exist. Update the "
            "manifest or fill manually (keys, never values).\n"
        )
        write(repo, ctx.path, body)
        return
    keys = extract_settings_keys(src)
    rel = src.relative_to(repo)
    rows = "\n".join(f"| `{k}` | _TODO: purpose / default behaviour_ |" for k in keys) \
        or "| _(no keys detected — verify the parser)_ | |"
    body = (
        f"{fm}\n# Configuration\n\n"
        f"{GENERATED_NOTE} (keys auto-extracted from `{rel}`; **purpose text "
        "is a TODO for a human/LLM — keys only, never values**.)\n\n"
        "| Key | Purpose / default behaviour |\n|---|---|\n" + rows + "\n\n"
        "> Values and secrets are never documented here. Secret/PII scrub is "
        "a later hardening gate (G5).\n"
    )
    write(repo, ctx.path, body)
