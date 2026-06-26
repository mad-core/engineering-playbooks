# `living-docs`

Living-documentation phase for Mad engineering — generate and keep a structured, faithful `/docs` tree alive against the code. This playbook bundles two things:

1. **The docs engine** — a deterministic, **contract-agnostic** Python package (`gen_docs`) that runs only the generators a repo's `docs/.docs-manifest.yaml` declares (source/test trees, an OpenAPI dump, scripts, changelog, config/CI skeletons, …) and lints the result. No stack, layout, or section list is hardcoded.
2. **The fill/update skill** — `generate-docs`, which reads the manifest, runs the engine, and authors/updates the non-scriptable sections as pure Markdown, then opens an agent-generated PR (never merges to `main`).

> **Scope.** This playbook is the docs **engine + fill/update skill** only — it documents a repo that is **already initialized** (i.e. already has `docs/.docs-manifest.yaml`). Bootstrapping/onboarding that manifest (the `init` flow, the documentation contract, and workflow templates) lives in a **separate** playbook — see COPE-143. If the manifest is missing, the skill stops and points you to `/init-docs`.

## What it does

Reads one repo as the single source of truth and (re)generates its `/docs` tree, **entirely driven by `docs/.docs-manifest.yaml`**:

1. Adapts the manifest to the repo (resolves each entry's `triggers.paths` / `produces.params` against the actual tree).
2. Runs the deterministic generators (`gen_docs all`) — only the ones the manifest declares — to lay down the exact, no-judgement substrate.
3. Authors every declared section as pure Markdown, faithful to the code — never invents prose.
4. Marks any unfillable section explicitly (`not applicable` / `unknown` + reason) and emits a short run report.
5. Opens an agent-generated PR on the ticket branch. **Never merges to `main`.**

Idempotent: the first run documents the repo from scratch; reruns diff against each entry's `acknowledged_at_commit` and update only what changed.

## When to use it

- "generate docs", "regenerate `/docs`", "update the docs", "fill the docs structure", "documentar el repo".
- Producing the agent-generated documentation PR for any already-initialized repo.

## Inputs

- The target repo, checked out on the ticket branch (not `main`), **with an existing `docs/.docs-manifest.yaml`** (created by `/init-docs`, COPE-143).

## Outputs

- A `/docs` tree covering every section the manifest declares, as pure Markdown.
- The deterministic substrate the manifest declares (e.g. source/test trees, scripts, changelog) and any completed skeletons (e.g. configuration, CI/CD).
- A run report (filled vs skipped, with reasons).
- An agent-generated PR on the ticket branch — not merged.

## How to invoke it

- In a Claude Code (or Cowork) session, trigger the skill by intent: `generate docs`, `regenerate /docs`, `update the docs`.
- The skill drives the bundled `gen_docs` console command for the deterministic passes.

## The docs engine (`gen_docs`)

The engine ships under [`package/`](package/) and installs a `gen_docs` console command. Install it straight from this repo's subdirectory:

```bash
pip install "git+https://github.com/mad-core/engineering-playbooks.git#subdirectory=playbooks/living-docs/package"
```

Then, from the target repo root (everything is read from `docs/.docs-manifest.yaml`):

```bash
gen_docs all --repo .      # run every generator the manifest declares
gen_docs lint              # classify each entry; dispatch work
gen_docs --help            # full subcommand list
```

The same logic runs without installing via `python3 package/gen_docs.py <cmd>`.

Each generator writes to the `path` its manifest entry declares — the table below is *what* each produces, not a fixed location:

| Subcommand | Produces | Kind |
|---|---|---|
| `source-tree` / `test-tree` | an ASCII tree of a declared root (from `git ls-files`) | deterministic |
| `api` | an OpenAPI spec dumped from a declared app object (stack-specific; runs only if declared) | deterministic |
| `scripts` | Makefile targets + a declared scripts dir | deterministic |
| `changelog` | recent history from `git log` | deterministic |
| `config` / `ci-cd` | settings keys / CI job structure | skeleton (TODO prose) |
| `bootstrap` / `migrate` | create / reconcile the manifest from a `--contract` template | manifest lifecycle |
| `adapt` / `lint` | fill repo-specific manifest fields / dispatch work | manifest lifecycle |

## Target tool

- **Claude Code** — primary: documentation is part of the engineering loop.
- **Cowork** — also supported: authoring docs is knowledge work.

## Org conventions encoded

- **Manifest-driven, pure Markdown, faithful, deterministic** — the repo is the single source of truth for content; the manifest is the single source of truth for structure; a downstream pipeline owns presentation. See [`skills/generate-docs/SKILL.md`](skills/generate-docs/SKILL.md) for the full process, frontmatter, and filling rules.
- **Never merges to `main`** — scope ends at an agent-generated PR; delivery and drift detection are separate tickets.
- **Init is separate** — this playbook never bootstraps a structure; `/init-docs` (COPE-143) owns the contract and the first manifest.
- **Versioning** is automated via release-please — never hand-edit `version` in `.claude-plugin/plugin.json`.
