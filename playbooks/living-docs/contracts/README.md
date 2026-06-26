# `contracts/` — documentation contracts per engineering area

A **contract** is a stack-shaped template for a repo's `docs/.docs-manifest.yaml`:
the set of docs a given *kind* of service should carry, what each must contain,
which generator (if any) produces it, and which code paths make it stale. It is
the one place stack-specific knowledge lives — the `gen_docs` engine itself is
contract-agnostic and hardcodes nothing.

## One file per area — adding one needs no code change

The convention is the whole mechanism:

```
contracts/
  backend.yaml      # domain: backend   (the only area today)
  frontend.yaml     # ← drop one here to support frontend, no code edit
  infra.yaml        # ← …infra
  etl.yaml          # ← …data pipelines
```

- The **filename stem is the area/type token** (`backend` → `backend.yaml`).
- `/init-docs` detects the target repo's type and resolves the contract by
  convention: `contracts/<type>.yaml`. It enumerates this directory to know
  which areas are supported — so **a new area is a new file, nothing else**.
- The engine only ever receives a `--contract <path>`; it has no notion of
  "backend" or any other area. Neither `gen_docs` nor `/init-docs` carries a
  per-area branch to edit.

If `/init-docs` detects a type that has **no** contract yet, it stops and tells
the user that area's contract is pending — it never auto-generates a half-baked
one.

## Contract shape

Each contract is a manifest template. Top-level: `schema_version`, `domain`,
`service` (a placeholder, overridden at bootstrap), `generator_skill`, and a
`docs:` list. Every doc entry carries:

| Field | Filled by | Meaning |
|---|---|---|
| `path`, `section`, `kind`, `description` | the contract | the doc's identity and must-contain rule |
| `triggers.paths` | `adapt` (starts `null`) | concrete repo paths that make this doc stale |
| `triggers.discovery_hint` | the contract | *categorical* guidance for finding those paths |
| `triggers.hint` / `triggers.max_age_days` | the contract | linter hint / age threshold (manual docs) |
| `produces.command` / `produces.params_needed` | the contract | the generator + the params it needs |
| `produces.params` | `adapt` (starts `null`) | the repo-specific values for those params |
| `acknowledged_at_commit` | `bootstrap` (starts `null`) | drift baseline |

`kind` is one of `deterministic` (a generator owns the file), `heuristic`
(code-derived, LLM-authored, re-checked on path drift — includes generator
*skeletons* the fill skill completes), or `manual` (intent-level, age-based).

See [`backend.yaml`](backend.yaml) for the worked example and
[`../package/`](../package/) for the engine that consumes it.
