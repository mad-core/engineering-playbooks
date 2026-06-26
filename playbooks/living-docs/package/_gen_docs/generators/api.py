from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .._constants import GENERATED_NOTE
from .._io import frontmatter, write
from .._manifest import GenContext


def gen_api(repo: Path, ctx: GenContext) -> None:
    """Inline an OpenAPI spec dumped from a Python app object.

    This is a stack-specific generator (Python + an `app.openapi()` callable).
    It only ever runs when the manifest declares a doc that `produces` it, so
    a non-Python or non-HTTP service never triggers it.
    """
    params = ctx.params("app_module", "app_attr")
    module, attr = params["app_module"], params["app_attr"]

    code = (
        "import json,importlib;"
        f"m=importlib.import_module('{module}');"
        f"app=getattr(m,'{attr}');"
        "print(json.dumps(app.openapi(),indent=2,sort_keys=True))"
    )
    py = repo / "venv" / "bin" / "python"
    interp = str(py) if py.exists() else sys.executable
    spec, err = None, None
    try:
        out = subprocess.run(
            [interp, "-c", code], cwd=str(repo),
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "PYTHONPATH": str(repo)},
        )
        if out.returncode == 0 and out.stdout.strip():
            spec = out.stdout.strip()
        else:
            tail = (out.stderr or out.stdout).strip().splitlines()
            err = tail[-1] if tail else "unknown"
    except Exception as e:  # noqa: BLE001
        err = str(e)

    fm = frontmatter(ctx.section, ctx.service, ctx.domain)
    if spec:
        body = (
            f"{fm}\n# API Contract\n\n{GENERATED_NOTE}\n\n"
            f"OpenAPI dumped from `{module}:{attr}`. Reconstructable from "
            "`/raw` alone — never a dangling link.\n\n"
            "```json\n" + spec + "\n```\n"
        )
    else:
        body = (
            f"{fm}\n# API Contract\n\n"
            f"> **Status:** unknown — could not import `{module}:{attr}` to "
            f"dump OpenAPI.\n>\n> Reason: `{err}`\n>\n"
            f"> Recoverable reference: the app object is `{module}:{attr}`. "
            "Run the service and fetch `/openapi.json`, then inline it here.\n"
        )
    write(repo, ctx.path, body)
