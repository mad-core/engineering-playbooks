from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MANIFEST_REL = "docs/.docs-manifest.yaml"


def _git_head(repo: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def _yaml_module():
    try:
        import yaml  # type: ignore
    except ImportError as e:
        print(f"error: PyYAML is required ({e}). "
              "Install with `pip install pyyaml`.", file=sys.stderr)
        raise SystemExit(2) from e
    return yaml


def _install_literal_str_representer(yaml) -> None:
    """Render multi-line strings with the `|` block style (readable diffs)."""
    def repr_str(dumper, data):
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)
    yaml.add_representer(str, repr_str)


def load_manifest(repo: Path) -> dict | None:
    """Read docs/.docs-manifest.yaml. Returns None if missing."""
    path = repo / MANIFEST_REL
    if not path.exists():
        return None
    yaml = _yaml_module()
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def produced_subcommand(entry: dict) -> str | None:
    """The generator subcommand an entry declares (``produces.command[1]``).

    The program name (``command[0]``) is ignored on purpose: a manifest may
    record it as ``gen_docs`` or the legacy ``gen_docs.py`` — only the
    subcommand selects the generator.
    """
    cmd = (entry.get("produces") or {}).get("command") or []
    return cmd[1] if len(cmd) >= 2 else None


def entries_producing(manifest: dict, subcommand: str) -> list[dict]:
    """Every manifest entry whose `produces.command` runs `subcommand`."""
    if not manifest:
        return []
    return [e for e in (manifest.get("docs") or [])
            if produced_subcommand(e) == subcommand]


def resolve_params(entry: dict, *names: str) -> dict:
    """Read `produces.params` for one manifest entry.

    Honors defaults declared in `produces.params_needed[<name>].default`.
    Fails clearly (exit 2) if any required value is still missing — that is
    a not-yet-adapted manifest, not a stack assumption.
    """
    produces = entry.get("produces") or {}
    needed = produces.get("params_needed") or {}
    params = produces.get("params") or {}

    out: dict = {}
    missing: list[str] = []
    for name in names:
        val = params.get(name)
        if val is not None:
            out[name] = val
        elif name in needed and "default" in (needed[name] or {}):
            out[name] = needed[name]["default"]
        else:
            missing.append(name)
    if missing:
        path = entry.get("path", "<doc>")
        print(
            f"error: {path} requires `produces.params.{{{','.join(missing)}}}` "
            f"to be set in {MANIFEST_REL}. Run the `adapt` agent or set them "
            "manually.", file=sys.stderr,
        )
        raise SystemExit(2)
    return out


@dataclass
class GenContext:
    """Everything a generator needs, sourced entirely from the manifest.

    No generator hardcodes a doc path, a `section`, or the `domain`; they all
    come from `entry` / the manifest top-level, so the same generators work
    for any contract the manifest declares.
    """

    service: str
    domain: str
    entry: dict

    @property
    def path(self) -> str:
        """The doc's output path, as declared in the manifest (repo-relative)."""
        return self.entry["path"]

    @property
    def section(self) -> str:
        return self.entry.get("section", "")

    def params(self, *names: str) -> dict:
        return resolve_params(self.entry, *names)
