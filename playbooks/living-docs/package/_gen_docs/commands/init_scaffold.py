from __future__ import annotations

import json
import sys
from pathlib import Path

# Default wiring for the Mad living-docs plugin. These are the only
# values the engine knows; everything path-shaped (the workflow templates) is
# passed in by the caller, mirroring how `bootstrap` takes `--contract`.
DEFAULT_MARKETPLACE = "360hd"
DEFAULT_PLUGIN = "living-docs"
DEFAULT_GITHUB_ORG = "mad-core"
MARKETPLACE_REPO_SUFFIX = "engineering-playbooks"

SETTINGS_REL = ".claude/settings.json"
WORKFLOWS_REL = ".github/workflows"


def _merge_settings(
    repo: Path, marketplace: str, plugin: str, github_org: str
) -> list[str]:
    """Enable the plugin in the target repo's `.claude/settings.json`.

    Idempotent and non-destructive: an existing marketplace entry (which may be
    version-pinned) is left untouched; only missing keys are added. Returns a
    list of human-readable change notes.
    """
    dest = repo / SETTINGS_REL
    notes: list[str] = []

    data: dict = {}
    if dest.exists():
        try:
            data = json.loads(dest.read_text(encoding="utf-8")) or {}
        except json.JSONDecodeError as e:
            print(f"error: {SETTINGS_REL} is not valid JSON ({e}); "
                  "fix it before re-running init-docs.", file=sys.stderr)
            raise SystemExit(1) from e
        if not isinstance(data, dict):
            print(f"error: {SETTINGS_REL} must be a JSON object.",
                  file=sys.stderr)
            raise SystemExit(1)

    markets = data.setdefault("extraKnownMarketplaces", {})
    if not isinstance(markets, dict):
        print(f"error: `extraKnownMarketplaces` in {SETTINGS_REL} must be an "
              "object.", file=sys.stderr)
        raise SystemExit(1)
    if marketplace not in markets:
        markets[marketplace] = {
            "source": {
                "source": "github",
                "repo": f"{github_org}/{MARKETPLACE_REPO_SUFFIX}",
            }
        }
        notes.append(f"added marketplace `{marketplace}`")
    else:
        notes.append(f"marketplace `{marketplace}` already present — left as is")

    enabled = data.setdefault("enabledPlugins", {})
    if not isinstance(enabled, dict):
        print(f"error: `enabledPlugins` in {SETTINGS_REL} must be an object.",
              file=sys.stderr)
        raise SystemExit(1)
    plugin_key = f"{plugin}@{marketplace}"
    if enabled.get(plugin_key) is True:
        notes.append(f"plugin `{plugin_key}` already enabled")
    else:
        enabled[plugin_key] = True
        notes.append(f"enabled plugin `{plugin_key}`")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return notes


def _drop_workflows(
    repo: Path, templates_dir: Path, force: bool
) -> list[str]:
    """Copy the caller workflow templates into `.github/workflows/`.

    The `*.yml` files are copied verbatim — they reference
    `${{ vars.SERVICE_SLUG }}`, a repo variable set out-of-band (see the
    secrets/vars checklist), so no content substitution is needed. Idempotent:
    an existing file is skipped unless `--force`. Returns change notes.
    """
    notes: list[str] = []
    if not templates_dir.exists():
        print(f"error: workflow templates dir not found at {templates_dir}",
              file=sys.stderr)
        raise SystemExit(2)

    dest_dir = repo / WORKFLOWS_REL
    dest_dir.mkdir(parents=True, exist_ok=True)

    sources = sorted(templates_dir.glob("*.yml"))
    if not sources:
        notes.append(f"no *.yml templates found in {templates_dir}")
    for src in sources:
        dest = dest_dir / src.name
        if dest.exists() and not force:
            notes.append(f"skipped {WORKFLOWS_REL}/{src.name} (exists; "
                         "use --force to overwrite)")
            continue
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        notes.append(f"wrote {WORKFLOWS_REL}/{src.name}")
    return notes


def gen_init_scaffold(
    repo: Path,
    workflow_templates: Path | None,
    marketplace: str = DEFAULT_MARKETPLACE,
    plugin: str = DEFAULT_PLUGIN,
    github_org: str = DEFAULT_GITHUB_ORG,
    force: bool = False,
) -> int:
    """Deterministic onboarding file-drops for /init-docs.

    Two stateless, idempotent steps: enable the plugin in the repo's
    `.claude/settings.json`, and drop the workflow caller templates into
    `.github/workflows/`. This is the deterministic core the interactive
    /init-docs skill wraps — it asks, then calls this. Authoring no content,
    bootstrapping no manifest (that is `bootstrap`).
    """
    print(f"init-scaffold: {repo}")

    print(f"  {SETTINGS_REL}:")
    for note in _merge_settings(repo, marketplace, plugin, github_org):
        print(f"    - {note}")

    if workflow_templates is not None:
        print(f"  {WORKFLOWS_REL}:")
        for note in _drop_workflows(repo, workflow_templates, force):
            print(f"    - {note}")
    else:
        print(f"  {WORKFLOWS_REL}: skipped (no --workflow-templates given)")

    return 0
