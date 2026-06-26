from __future__ import annotations

from pathlib import Path

from .._constants import GENERATED_NOTE
from .._io import frontmatter, write
from .._manifest import GenContext


def gen_ci_cd(repo: Path, ctx: GenContext) -> None:
    params = ctx.params("workflows_dir")
    workflows_rel = params["workflows_dir"]
    wf_dir = repo / workflows_rel
    fm = frontmatter(ctx.section, ctx.service, ctx.domain)
    if not wf_dir.exists():
        write(repo, ctx.path,
              f"{fm}\n# CI/CD\n\n> **Status:** not applicable — no "
              f"`{workflows_rel}/` directory.\n")
        return
    try:
        import yaml  # type: ignore
    except Exception:  # noqa: BLE001
        yaml = None

    sections = []
    for wf in sorted(wf_dir.glob("*.y*ml")):
        sections.append(f"### `{wf.name}`\n")
        if yaml is not None:
            try:
                data = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
                triggers = data.get("on") or data.get(True)
                sections.append(f"- **Triggers:** `{triggers}`")
                for job_name, job in (data.get("jobs") or {}).items():
                    steps = job.get("steps", []) if isinstance(job, dict) else []
                    names = [s.get("name") or s.get("uses") or "step"
                             for s in steps if isinstance(s, dict)]
                    sections.append(
                        f"- **Job `{job_name}`** ({len(names)} steps): "
                        + ", ".join(f"`{n}`" for n in names)
                    )
            except Exception as e:  # noqa: BLE001
                sections.append(f"- _parse error: {e}_")
        else:
            sections.append("- _PyYAML not available; install it or fill "
                            "the stage list manually from the workflow file._")
        sections.append("")
    body = (
        f"{fm}\n# CI/CD\n\n"
        f"{GENERATED_NOTE} (job/step structure auto-extracted; **what each "
        "stage gates is a TODO narrative for a human/LLM**.)\n\n"
        + "\n".join(sections)
        + "\n> TODO: describe what each stage gates (lint/test/coverage "
        "thresholds, deploy approval, etc.).\n"
    )
    write(repo, ctx.path, body)
