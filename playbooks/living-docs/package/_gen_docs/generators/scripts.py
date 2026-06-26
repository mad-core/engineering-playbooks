from __future__ import annotations

from pathlib import Path

from .._constants import GENERATED_NOTE
from .._git import tracked_under
from .._io import frontmatter, write
from .._manifest import GenContext


def parse_makefile(repo: Path, makefile_rel: str = "Makefile") -> list[tuple[str, str]]:
    mk = repo / makefile_rel
    if not mk.exists():
        return []
    targets: list[tuple[str, str]] = []
    help_text: dict[str, str] = {}
    for line in mk.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        # `@echo "  make NAME  - description"` inside the help: target.
        if s.startswith('@echo "  make '):
            inner = s[len('@echo "  make '):].rstrip('"').rstrip()
            if " - " in inner:
                name, desc = inner.split(" - ", 1)
                help_text[name.strip()] = desc.strip()
        # Real target lines `name:` only. Skip indented recipes, comments,
        # .PHONY, and variable assignments (`:=` / `=`).
        if (
            line and not line[0].isspace()
            and not line.startswith(("#", "."))
            and ":" in line and ":=" not in line
            and "=" not in line.split(":", 1)[0]
        ):
            name = line.split(":", 1)[0].strip()
            if name and name not in (t[0] for t in targets):
                targets.append((name, help_text.get(name, "")))
    return targets


def gen_scripts(repo: Path, ctx: GenContext) -> None:
    params = ctx.params("makefile", "scripts_dir")
    targets = parse_makefile(repo, params["makefile"])
    # git ls-files instead of iterdir(): otherwise stray `__pycache__` /
    # `.pyc` in a local working tree would "rescue" a scripts/ dir that's
    # empty on disk in CI, producing different doc output local vs CI.
    scripts_rel = params["scripts_dir"].rstrip("/")
    prefix = scripts_rel + "/"
    real_scripts: list[str] = []
    for full in tracked_under(repo, scripts_rel):
        if not full.startswith(prefix):
            continue
        name = full[len(prefix):]
        if "/" in name:           # only direct children, mirror old behavior
            continue
        if name == "__init__.py":
            continue
        if not name.endswith((".py", ".sh")):
            continue
        real_scripts.append(name)
    real_scripts.sort()

    rows = "\n".join(
        f"| `make {n}` | {d or '_(no description in Makefile help — add one)_'} |"
        for n, d in targets
    ) or "| _(no targets)_ | |"
    scripts_block = (
        "\n".join(f"- `{scripts_rel}/{s}` — _purpose: TODO_" for s in real_scripts)
        if real_scripts
        else f"_No executable scripts in `{scripts_rel}/` (only package/cache files)._"
    )
    body = (
        f"{frontmatter(ctx.section, ctx.service, ctx.domain)}\n"
        "# Scripts\n\n"
        f"{GENERATED_NOTE}\n\n"
        "## Makefile targets\n\n"
        "| Target | Purpose |\n|---|---|\n" + rows + "\n\n"
        f"## `{scripts_rel}/` directory\n\n" + scripts_block + "\n"
    )
    write(repo, ctx.path, body)
