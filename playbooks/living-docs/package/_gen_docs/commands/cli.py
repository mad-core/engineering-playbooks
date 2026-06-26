from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .._manifest import (
    MANIFEST_REL,
    GenContext,
    entries_producing,
    load_manifest,
    produced_subcommand,
)
from ..generators import ALL, SKELETON
from .adapt import gen_adapt
from .bootstrap import gen_bootstrap
from .init_scaffold import gen_init_scaffold
from .lint import gen_lint
from .migrate import gen_migrate

_INIT_HINT = (
    f"error: {MANIFEST_REL} not found — this repo is not initialized for "
    "living-docs.\n"
    "       Run /init-docs to scaffold the manifest, or "
    "`gen_docs bootstrap --contract <path>` with a contract template."
)


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "Manifest-driven /docs generators. Every layout decision is read "
            f"from {MANIFEST_REL}; nothing about a stack or a contract is "
            "hardcoded in this engine.\n\n"
            "Subcommands: all, bootstrap, init-scaffold, migrate, adapt, "
            "lint, " + ", ".join(ALL.keys())
        )
    )
    p.add_argument(
        "command",
        choices=["all", "bootstrap", "init-scaffold", "migrate", "adapt",
                 "lint", *ALL.keys()],
    )
    p.add_argument("--repo", default=".", help="repo root (default: cwd)")
    p.add_argument("--service", default=None,
                   help="override the service slug (default: manifest `service`)")
    p.add_argument("--contract", default=None,
                   help="path to a contract/template manifest — required by "
                        "`bootstrap` and `migrate` (no contract is bundled)")
    p.add_argument("--force", action="store_true",
                   help="overwrite existing files (bootstrap manifest / "
                        "init-scaffold workflow drops)")
    p.add_argument("--workflow-templates", default=None,
                   help="path to the workflow caller templates dir whose "
                        "`*.yml` init-scaffold drops into `.github/workflows/` "
                        "(no templates are bundled in this engine)")
    p.add_argument("--github-org", default="mad-core",
                   help="GitHub org for the marketplace repo (init-scaffold)")
    p.add_argument("--marketplace", default="360hd",
                   help="marketplace name to enable (init-scaffold)")
    p.add_argument("--plugin", default="living-docs",
                   help="plugin to enable in the target repo (init-scaffold)")
    p.add_argument("--dry-run", action="store_true",
                   help="show the plan without writing the manifest (migrate)")
    p.add_argument("--base", default=None,
                   help="git ref to diff against (lint; default: each entry's "
                        "acknowledged_at_commit)")
    p.add_argument("--json", action="store_true",
                   help="machine-readable output (lint)")
    p.add_argument("--emit-prompts", action="store_true",
                   help="include a fully-formed subagent prompt per finding "
                        "(lint); implies --json")
    args = p.parse_args()

    repo = Path(args.repo).resolve()

    # bootstrap is the only command that does NOT require an existing manifest;
    # it creates one from a caller-supplied contract template.
    if args.command == "bootstrap":
        if not args.contract:
            print("error: bootstrap requires --contract <path> to a contract "
                  "template manifest (no contract is bundled in this engine).",
                  file=sys.stderr)
            return 2
        return gen_bootstrap(repo, Path(args.contract).resolve(),
                             service=args.service, force=args.force)

    # init-scaffold drops onboarding files (settings + workflow callers); it
    # likewise needs no existing manifest. The deterministic core /init-docs
    # wraps.
    if args.command == "init-scaffold":
        templates = (Path(args.workflow_templates).resolve()
                     if args.workflow_templates else None)
        return gen_init_scaffold(
            repo, templates,
            marketplace=args.marketplace, plugin=args.plugin,
            github_org=args.github_org, force=args.force,
        )

    # Everything else is driven by the repo's own manifest.
    manifest = load_manifest(repo)
    if manifest is None:
        print(_INIT_HINT, file=sys.stderr)
        return 2
    service = args.service or manifest.get("service") or "service"
    domain = manifest.get("domain") or "unknown"

    if args.command == "migrate":
        if not args.contract:
            print("error: migrate requires --contract <path> to the contract "
                  "template to reconcile against.", file=sys.stderr)
            return 2
        return gen_migrate(repo, Path(args.contract).resolve(),
                           dry_run=args.dry_run)

    if args.command == "adapt":
        gen_adapt(repo, service)
        return 0

    if args.command == "lint":
        return gen_lint(
            repo, service,
            base=args.base,
            emit_prompts=args.emit_prompts,
            json_out=args.json or args.emit_prompts,
        )

    # Deterministic generators. Run STRICTLY what the manifest declares:
    # a generator fires only for a doc whose `produces.command` selects it,
    # so stack-specific generators (e.g. `api`/OpenAPI) never run for a repo
    # that does not declare them.
    to_run: list[tuple[str, dict]] = []
    if args.command == "all":
        # FULL generators always run; SKELETON generators are skipped when
        # their output already exists, preserving any authored prose. Force a
        # regenerate with the explicit subcommand (e.g. `gen_docs config`).
        for entry in manifest.get("docs") or []:
            sub = produced_subcommand(entry)
            if sub not in ALL:
                continue
            if sub in SKELETON and (repo / entry["path"]).exists():
                print(f"  skipping {sub}: file exists — "
                      f"run `gen_docs {sub}` to force regeneration")
                continue
            to_run.append((sub, entry))
    else:
        entries = entries_producing(manifest, args.command)
        if not entries:
            print(f"error: the manifest declares no doc produced by "
                  f"`{args.command}` — nothing to generate.", file=sys.stderr)
            return 1
        to_run = [(args.command, e) for e in entries]

    print(f"generating ({args.command}) for service '{service}' in {repo}")
    for sub, entry in to_run:
        ALL[sub](repo, GenContext(service, domain, entry))
    print("done.")
    return 0
