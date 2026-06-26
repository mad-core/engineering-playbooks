from __future__ import annotations

from pathlib import Path


def gen_adapt(repo: Path, service: str) -> None:
    print("adapt is not implemented as a deterministic step. Expected behavior:")
    print("  - Read every entry with triggers.paths==null or produces.params==null.")
    print("  - For each, build a prompt from `description` + `triggers.discovery_hint`")
    print("    + `produces.params_needed` and dispatch a subagent that inspects the")
    print("    repo and returns concrete values.")
    print("  - Write the values back into docs/.docs-manifest.yaml.")
    raise SystemExit(1)
