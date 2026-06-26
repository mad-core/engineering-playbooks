from __future__ import annotations

import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

from .._glob import _changed_paths_matching, _glob_match_repo
from .._io import end_dry_run, start_dry_run
from .._manifest import (
    MANIFEST_REL,
    GenContext,
    _git_head,
    load_manifest,
    produced_subcommand,
)

_SUBAGENT_PROMPT_TEMPLATE = """\
You are updating `{doc}` for service `{service}`.

## Reason this was triggered
{trigger_reason}

## Generic contract for this doc
{description}

## Adapted heuristic (project-specific guidance, may be missing on first fill)
{adapted_heuristic}

## Frontmatter that MUST be in the output
service: {service}
domain: {domain}
section: {section}
source_of_truth: repo

## Current content of the doc
{current_content}

## Your mission
1. Read ONLY the paths listed under "Reason this was triggered" plus the doc \
itself. Do not roam the repo.
2. Decide: does the doc need to be updated? If not, return `decision: \
no-change` with a one-line reason. If yes, return the full updated markdown \
body.
3. If `Adapted heuristic` is "(none)" above, you must propose one: a broad, \
forward-looking description of how a future agent should decide whether \
this doc needs updating, using this repo's concrete paths and idioms.
4. Set `new_acknowledged_at_commit` to `{head_sha}`.

## Reply format (YAML, strict)
```yaml
decision: update | no-change
new_content: |
  <full markdown body of the doc, including frontmatter>   # if update
new_adapted_heuristic: |
  <broad guidance for future updates>
new_acknowledged_at_commit: {head_sha}
reason_if_no_change: <one line>                            # if no-change
```
"""


def _commit_exists(repo: Path, sha: str | None) -> bool:
    if not sha:
        return False
    r = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", sha],
                       capture_output=True)
    return r.returncode == 0


def _commit_date(repo: Path, sha: str) -> _dt.date | None:
    r = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%cs", sha],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return _dt.date.fromisoformat(r.stdout.strip())
    except ValueError:
        return None


def _git_diff_paths(repo: Path, base: str, head: str = "HEAD") -> list[str]:
    r = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", f"{base}..{head}"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.splitlines() if p.strip()]


def _regenerate_to_buffer(
    repo: Path, service: str, domain: str, entry: dict
) -> dict[str, str] | None:
    """Run an entry's generator with disk writes captured in-memory.

    Returns None on failure (unknown subcommand, missing params, etc.)."""
    from ..generators import ALL
    sub = produced_subcommand(entry)
    fn = ALL.get(sub) if sub else None
    if fn is None:
        return None
    start_dry_run()
    try:
        fn(repo, GenContext(service, domain, entry))
    except SystemExit:
        end_dry_run()
        return None
    except Exception:  # noqa: BLE001
        end_dry_run()
        return None
    return end_dry_run()


def _build_subagent_prompt(
    entry: dict,
    trigger_reason: str,
    current_content: str | None,
    service: str,
    domain: str,
    head_sha: str,
) -> str:
    ah = entry.get("adapted_heuristic")
    return _SUBAGENT_PROMPT_TEMPLATE.format(
        doc=entry["path"],
        service=service,
        domain=domain,
        section=entry.get("section", ""),
        description=(entry.get("description") or "").rstrip(),
        adapted_heuristic=(ah.rstrip() if isinstance(ah, str) else "(none)"),
        trigger_reason=trigger_reason,
        current_content=(
            "```\n" + current_content + "\n```"
            if current_content is not None
            else "FILE DOES NOT EXIST"
        ),
        head_sha=head_sha,
    )


def _finding(severity: str, code: str, doc: str, message: str,
             detail: dict | None = None, action: dict | None = None) -> dict:
    return {
        "severity": severity,
        "code": code,
        "doc": doc,
        "message": message,
        "detail": detail or {},
        "action": action or {},
    }


def gen_lint(
    repo: Path,
    service: str,
    base: str | None = None,
    emit_prompts: bool = False,
    json_out: bool = False,
) -> int:
    """Classify every manifest entry; return exit code (0 = OK, 1 = errors)."""
    manifest = load_manifest(repo)
    if manifest is None:
        print(f"error: {MANIFEST_REL} not found — run /init-docs to scaffold it, "
              "or `gen_docs bootstrap --contract <path>`.",
              file=sys.stderr)
        return 2

    head = _git_head(repo) or ""
    domain = manifest.get("domain") or "unknown"
    findings: list[dict] = []

    for entry in manifest.get("docs") or []:
        doc = entry.get("path") or "<unknown>"
        kind = entry.get("kind")
        triggers = entry.get("triggers") or {}
        produces = entry.get("produces") or {}
        ack = entry.get("acknowledged_at_commit")
        ack_for_diff = base or ack

        # (1) adapt-pending — block further checks for this entry.
        pending: list[str] = []
        if triggers.get("paths") is None:
            pending.append("triggers.paths")
        if (produces.get("type") == "script"
                and produces.get("params") is None
                and (produces.get("params_needed") or {})):
            pending.append("produces.params")
        if pending:
            findings.append(_finding(
                "warning", "adapt-pending", doc,
                f"{', '.join(pending)} not filled — run `adapt` to discover it.",
                detail={"pending": pending},
                action={"type": "run-adapt",
                        "command": ["gen_docs", "adapt"],
                        "model": "sonnet"},
            ))
            continue

        # (2) orphan-commit — ack pointing to a non-existent SHA.
        if ack and not _commit_exists(repo, ack):
            findings.append(_finding(
                "error", "orphan-commit", doc,
                f"`acknowledged_at_commit` ({ack[:8]}) is not in current "
                "history (squash/rebase?). Re-ack against a real commit.",
                detail={"ack": ack},
                action={"type": "re-ack"},
            ))
            continue

        # (3) broken-trigger — any glob in triggers.paths that matches nothing.
        broken = [g for g in (triggers.get("paths") or [])
                  if not _glob_match_repo(repo, g)]
        if broken:
            findings.append(_finding(
                "error", "broken-trigger", doc,
                f"glob(s) match no file: {', '.join(broken)}. Likely a "
                "rename/refactor — update `triggers.paths` or re-run `adapt`.",
                detail={"broken_globs": broken},
                action={"type": "manual-fix"},
            ))
            # continue: still useful to know if other checks pass

        # Read current content (used by deterministic regen-diff and prompts).
        full_path = repo / doc
        current = full_path.read_text(encoding="utf-8") if full_path.exists() else None

        # (4) doc-missing — file declared in manifest but absent on disk.
        # Unified for all `kind`s: deterministic regenerates from a script;
        # heuristic/manual dispatch a subagent for first-fill authoring.
        if current is None:
            if kind == "deterministic":
                cmd = produces.get("command") or []
                findings.append(_finding(
                    "error", "deterministic-missing", doc,
                    "file does not exist — regenerate.",
                    action={"type": "regenerate-script", "command": cmd},
                ))
                continue
            if kind in ("heuristic", "manual"):
                trigger_reason = (
                    f"Doc declared in `{MANIFEST_REL}` but does not exist "
                    "on disk. First authoring: produce the full markdown "
                    "body from scratch using the contract description and "
                    "the paths under `triggers.paths` as source material."
                )
                # First-fill: adapted_heuristic is null in practice; honor
                # the documented model policy regardless.
                model = "sonnet" if entry.get("adapted_heuristic") is None \
                    else "haiku"
                action_missing: dict = {
                    "type": "dispatch-subagent", "model": model,
                }
                if emit_prompts:
                    action_missing["prompt"] = _build_subagent_prompt(
                        entry, trigger_reason, current, service, domain, head)
                findings.append(_finding(
                    "error", f"{kind}-missing", doc,
                    "file does not exist — dispatch subagent to author it.",
                    detail={"trigger_reason": trigger_reason},
                    action=action_missing,
                ))
                continue

        # (5) deterministic content drift.
        if kind == "deterministic":
            cmd = produces.get("command") or []
            buf = _regenerate_to_buffer(repo, service, domain, entry)
            if buf is None:
                findings.append(_finding(
                    "warning", "regen-skipped", doc,
                    "could not regenerate (missing params?). "
                    "Run `adapt` then retry.",
                    action={"type": "run-adapt"},
                ))
                continue
            regen = buf.get(doc, "")
            if regen != current:
                findings.append(_finding(
                    "error", "deterministic-stale", doc,
                    "regenerated output differs from on-disk file.",
                    detail={"diff_bytes": abs(len(regen) - len(current or ""))},
                    action={"type": "regenerate-script", "command": cmd},
                ))
            continue

        # (6) heuristic — diff between ack..HEAD intersected with triggers.
        if kind == "heuristic":
            if not ack_for_diff:
                findings.append(_finding(
                    "warning", "no-ack", doc,
                    "no `acknowledged_at_commit` to diff against. "
                    "Re-run bootstrap or ack manually.",
                ))
                continue
            changed = _git_diff_paths(repo, ack_for_diff, "HEAD")
            hits = _changed_paths_matching(changed, triggers.get("paths") or [])
            if hits:
                hint = (triggers.get("hint") or "").strip()
                trigger_reason = (
                    f"Files matching `triggers.paths` changed since "
                    f"`{ack_for_diff[:8]}`:\n"
                    + "\n".join(f"- `{p}`" for p in hits[:20])
                    + (f"\n… and {len(hits) - 20} more" if len(hits) > 20 else "")
                    + (f"\n\nLinter hint: {hint}" if hint else "")
                )
                model = "sonnet" if entry.get("adapted_heuristic") is None \
                    else "haiku"
                action: dict = {"type": "dispatch-subagent", "model": model}
                if emit_prompts:
                    action["prompt"] = _build_subagent_prompt(
                        entry, trigger_reason, current, service, domain, head)
                findings.append(_finding(
                    "warning", "heuristic-fired", doc,
                    f"{len(hits)} path(s) changed since ack — review.",
                    detail={"changed_paths": hits, "ack": ack_for_diff},
                    action=action,
                ))
            continue

        # (7) manual — age vs max_age_days.
        if kind == "manual":
            max_age = (triggers.get("max_age_days") or 0)
            if not ack or not max_age:
                continue
            cdate = _commit_date(repo, ack)
            if cdate is None:
                continue
            age = (_dt.date.today() - cdate).days
            if age > max_age:
                trigger_reason = (
                    f"This doc has not been re-validated in {age} days "
                    f"(threshold: {max_age}). No code path triggers it; "
                    "this is an age-based reminder."
                )
                model = "sonnet" if entry.get("adapted_heuristic") is None \
                    else "haiku"
                action = {"type": "dispatch-subagent", "model": model}
                if emit_prompts:
                    action["prompt"] = _build_subagent_prompt(
                        entry, trigger_reason, current, service, domain, head)
                findings.append(_finding(
                    "warning", "manual-aged", doc,
                    f"age {age}d > max_age_days={max_age}.",
                    detail={"age_days": age, "max_age_days": max_age},
                    action=action,
                ))
            continue

    # changelog drift is non-blocking: noisy on every commit, regenerated by CI
    _CHANGELOG_WARN_CODES = {"deterministic-stale", "deterministic-missing"}
    findings = [
        {**f, "severity": "warning"}
        if f["code"] in _CHANGELOG_WARN_CODES and f["doc"].endswith("changelog.md")
        else f
        for f in findings
    ]

    # --- output ---
    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")

    if json_out or emit_prompts:
        print(json.dumps({
            "summary": {"errors": errors, "warnings": warnings,
                        "total": len(findings)},
            "findings": findings,
        }, indent=2))
    else:
        for f in findings:
            sev = f["severity"].upper()
            print(f"[{sev}] {f['code']}  {f['doc']}")
            print(f"        {f['message']}")
            act = f["action"].get("type")
            if act:
                cmd = f["action"].get("command")
                if cmd:
                    print(f"        → {act}: {' '.join(cmd)}")
                else:
                    print(f"        → {act}")
            print()
        print(f"--- {errors} error(s), {warnings} warning(s), "
              f"{len(findings)} total ---")

    return 1 if errors else 0
