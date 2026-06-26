from __future__ import annotations

import copy
import sys
from pathlib import Path

from .._manifest import (
    MANIFEST_REL,
    _git_head,
    _install_literal_str_representer,
    _yaml_module,
    load_manifest,
)

# Fields the contract owns (drift-comparable). Anything not listed here is
# project-owned and never compared.
_CONTRACT_OWNED_FIELDS = (
    "kind",
    "description",
    "triggers.discovery_hint",
    "triggers.hint",
    "triggers.max_age_days",
    "produces.type",
    "produces.command",
    "produces.params_needed_keys",  # compare key set only, not values
)


def _contract_view(entry: dict) -> dict:
    """Project an entry onto the contract-owned fields, for drift comparison."""
    triggers = entry.get("triggers") or {}
    produces = entry.get("produces") or {}
    return {
        "kind": entry.get("kind"),
        "description": (entry.get("description") or "").rstrip(),
        "triggers.discovery_hint": (triggers.get("discovery_hint") or "").rstrip(),
        "triggers.hint": (triggers.get("hint") or "").rstrip(),
        "triggers.max_age_days": triggers.get("max_age_days"),
        "produces.type": produces.get("type"),
        "produces.command": tuple(produces.get("command") or []),
        "produces.params_needed_keys": tuple(
            sorted((produces.get("params_needed") or {}).keys())
        ),
    }


def gen_migrate(repo: Path, contract: Path, dry_run: bool = False) -> int:
    """Reconcile docs/.docs-manifest.yaml against a contract template.

    The contract template is supplied by the caller (no contract is bundled in
    this engine). Returns the process exit code (0 = OK, 2 = setup error).
    Drift is reported but does not change the exit code.
    """
    yaml = _yaml_module()
    _install_literal_str_representer(yaml)

    manifest = load_manifest(repo)
    if manifest is None:
        print(f"error: {MANIFEST_REL} not found — run `bootstrap` first.",
              file=sys.stderr)
        return 2
    if not contract.exists():
        print(f"error: contract template not found at {contract}", file=sys.stderr)
        return 2
    with contract.open(encoding="utf-8") as fh:
        template = yaml.safe_load(fh)

    head = _git_head(repo)

    # Index entries by path.
    manifest_by_path = {e["path"]: e for e in (manifest.get("docs") or [])}
    template_by_path = {e["path"]: e for e in (template.get("docs") or [])}

    added: list[str] = []
    drift: list[tuple[str, list[str]]] = []
    local_only: list[str] = []

    # Rebuild docs list in CONTRACT order so the manifest mirrors the
    # contract structure; local-only entries are appended at the end.
    new_docs: list[dict] = []
    for path, t_entry in template_by_path.items():
        if path in manifest_by_path:
            m_entry = manifest_by_path[path]
            t_view, m_view = _contract_view(t_entry), _contract_view(m_entry)
            diffs = [k for k in t_view if t_view[k] != m_view[k]]
            if diffs:
                drift.append((path, diffs))
            new_docs.append(m_entry)
        else:
            entry = copy.deepcopy(t_entry)
            entry["acknowledged_at_commit"] = head
            new_docs.append(entry)
            added.append(path)

    for path, m_entry in manifest_by_path.items():
        if path not in template_by_path:
            local_only.append(path)
            new_docs.append(m_entry)

    # Update contract-owned top-level fields, preserve project-owned.
    new_manifest = dict(manifest)
    for top in ("schema_version", "domain", "generator_skill"):
        if top in template:
            new_manifest[top] = template[top]
    new_manifest["docs"] = new_docs

    # --- plan output ---
    print(f"migrate: {len(added)} added, {len(local_only)} local-only, "
          f"{len(drift)} drift.")
    for path in added:
        print(f"  + added:      {path}")
    for path in local_only:
        print(f"  ! local-only: {path}")
    for path, diffs in drift:
        short = ", ".join(diffs)
        print(f"  ~ drift:      {path}  ({short})")

    if not (added or drift or local_only):
        print("manifest already up to date.")
        return 0
    if dry_run:
        print("dry-run: no file written. Re-run without --dry-run to apply.")
        return 0
    if not added and not local_only:
        # Drift-only: nothing structural to write; flag and exit.
        print("drift-only run: no structural changes written. Decide per "
              "entry whether to propagate the contract change manually.")
        return 0

    # --- write back, preserving the file header ---
    dest = repo / MANIFEST_REL
    header = ""
    if dest.exists():
        header_lines = []
        for line in dest.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or not line.strip():
                header_lines.append(line)
            else:
                break
        if header_lines:
            header = "\n".join(header_lines).rstrip() + "\n\n"
    if not header:
        header = (
            "# docs/.docs-manifest.yaml — local source of truth for this\n"
            "# repo's /docs.\n\n"
        )

    with dest.open("w", encoding="utf-8") as fh:
        fh.write(header)
        yaml.dump(
            new_manifest, fh,
            sort_keys=False, default_flow_style=False,
            allow_unicode=True, width=100,
        )
    print(f"  wrote {MANIFEST_REL}")
    if added:
        print(f"  next: run `adapt` to fill triggers.paths / produces.params "
              f"for the {len(added)} added entr(y|ies).")
    return 0
