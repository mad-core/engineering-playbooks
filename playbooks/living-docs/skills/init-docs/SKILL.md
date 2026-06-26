---
name: init-docs
description: >-
  Onboard a target repo into living-docs: make it docs-ready and leave it
  scaffolded-but-undocumented. Use when the user asks to "init docs",
  "set up living docs", "onboard a repo to docs", "bootstrap the docs
  manifest", "make this repo docs-ready", or runs /init-docs. Detects the repo
  type, enables the living-docs plugin in .claude/settings.json, bootstraps
  docs/.docs-manifest.yaml from the matching contract, drops the docs CI
  caller workflows, and prints the secrets/vars checklist. Does NOT author or
  fill any doc content — that is the generate-docs skill, run separately and
  afterward. Idempotent.
---

# Initialize a repo for living-docs (`/init-docs`)

This skill makes **one target repo** docs-ready. When it finishes, the repo
has: the living-docs plugin enabled, a `docs/.docs-manifest.yaml` **skeleton**
copied from the contract for its area, the docs CI caller workflows in place,
and a printed checklist of the secrets/vars an operator must set. It then
**stops** — the docs are scaffolded but **undocumented**.

**Scope boundary.** This skill never writes doc *content*. Authoring/filling
the `/docs` tree is the **`generate-docs`** skill, run separately afterward.
`/init-docs` only lays the substrate `generate-docs` needs.

> **User prompts use `AskUserQuestion`.** Every decision below (the service
> slug, the repo type when ambiguous, the branch model, which contract) is put
> to the user through the `AskUserQuestion` tool — never as a plain-chat
> `(yes/no)`. The number of questions, headers, and options are the model's
> call given what the repo inspection already determined; ask only what you
> could not infer. Free-text is only for values with no discrete universe (e.g.
> a custom service slug after the user picks "other").

## Where the inputs live (this playbook)

This skill is part of the **living-docs** playbook and reads two of its
directories (paths relative to the playbook root, available as
`${CLAUDE_PLUGIN_ROOT}` when installed):

- **`contracts/`** — one `<area>.yaml` per engineering area (today: only
  `backend.yaml`). The filename stem is the area token; the directory listing
  *is* the set of supported types. See `contracts/README.md`.
- **`workflow-templates/`** — the `docs-validate.yml` / `docs-sync.yml` caller
  workflows dropped into the target repo.

The deterministic work (manifest copy, settings merge, workflow drops) lives in
the bundled `gen_docs` package — this skill is the interactive wrapper that
inspects, asks, then calls it. The two deterministic entry points are
`gen_docs bootstrap` and `gen_docs init-scaffold`.

## Procedure

### Step 1 — Inspect the target repo and detect its type

Confirm you are pointed at the intended repo (its root is the working
directory or an explicit path). Inspect it to detect the **area**:

- **backend** — server-side service: a `src/` package with application logic,
  an HTTP app object and/or lambda handlers, a settings module, DynamoDB/SQL
  persistence, `pytest`/`behave` tests.
- **frontend** — a web/mobile app: `package.json` with a UI framework, a
  `src/components` or `app/` tree, a bundler config.
- **infra** — IaC: Terraform/CloudFormation/CDK, pipeline definitions, little
  or no application code.
- **etl** — data pipelines: batch/stream jobs, DAGs, transform steps.

Determine the candidate type from these signals. **Only ask** (via
`AskUserQuestion`) when the signals are ambiguous or conflicting; if detection
is confident, state what you detected and move on.

### Step 2 — Resolve the inputs (ask only what you must)

Gather, preferring inference over questions:

- **`service_slug`** — defaults to the repo name (the directory / remote name).
  Confirm or let the user override (free-text allowed for a custom slug).
- **type / contract** — the detected area selects `contracts/<type>.yaml`. If
  detection was ambiguous, ask the user to pick from the **types that actually
  have a contract file** (enumerate `contracts/*.yaml` — never offer a type
  whose contract is missing).
- **branch model** — which branches the CI callers trigger on (the templates
  default to `pull_request → [develop, main]` and `push → [develop]`). Ask only
  if the repo's default branch is not `develop`/`main`.

### Step 3 — Gate: the contract must exist for the chosen type

Resolve `contracts/<type>.yaml`. **If it does not exist, STOP gracefully:**
tell the user that area's contract is **pending** (only the areas with a file
in `contracts/` are supported today — backend) and that onboarding cannot
continue for this type. **Do NOT auto-generate a half-baked contract** and do
not fall back to a different area's contract.

### Step 4 — Enable the plugin + drop the CI callers (deterministic)

Run the deterministic file-drop helper against the target repo:

```
gen_docs init-scaffold --repo <target> \
  --workflow-templates ${CLAUDE_PLUGIN_ROOT}/workflow-templates
```

This merges `.claude/settings.json` (adds the `360hd` marketplace and enables
`living-docs@360hd`, without clobbering existing keys) so the `generate-docs`
fill skill is available afterward, and copies `docs-validate.yml` /
`docs-sync.yml` into `.github/workflows/`. It is idempotent — existing settings
keys are preserved and existing workflow files are skipped unless `--force`.

### Step 5 — Install the engine and bootstrap the manifest (deterministic)

Install the `gen_docs` package from this repo's subdirectory (idempotent; skip
if `gen_docs` already resolves):

```
pip install "git+https://github.com/mad-core/engineering-playbooks.git#subdirectory=playbooks/living-docs/package"
```

Then copy the manifest **skeleton** from the chosen contract:

```
gen_docs bootstrap --repo <target> --service <service_slug> \
  --contract ${CLAUDE_PLUGIN_ROOT}/contracts/<type>.yaml
```

This writes `docs/.docs-manifest.yaml` with `triggers.paths` / `produces.params`
left as `null` (to be resolved later by `generate-docs`/`adapt`) and stamps the
bootstrap commit. If the manifest already exists, `bootstrap` refuses unless
`--force` — surface that and let the user decide (via `AskUserQuestion`) whether
to overwrite or to reconcile instead with `gen_docs migrate --contract …`.

### Step 6 — Print the secrets/vars checklist

The repo is now docs-ready. Print the operator checklist (these are set in
GitHub, out of band — this skill cannot set them):

- **Repo variable `SERVICE_SLUG`** = `<service_slug>` — read by both caller
  workflows as `${{ vars.SERVICE_SLUG }}`.
- **Secret `DOCS_SYNC_TOKEN`** — the token the docs-sync reusable uses to push
  the docs PR.
- **Secret `ANTHROPIC_API_KEY`** — for the LLM authoring step in the reusable.

Then state plainly what was done and what was intentionally left out: the docs
structure exists but **no content has been authored** — run the `generate-docs`
skill (on a ticket branch) to fill it.

## Definition of done

- Repo type detected (or chosen) and a contract exists for it.
- `.claude/settings.json` enables `living-docs@360hd` (other keys preserved).
- `docs/.docs-manifest.yaml` skeleton written from the contract for `<service>`.
- `docs-validate.yml` + `docs-sync.yml` present in `.github/workflows/`.
- The secrets/vars checklist is printed.
- **No doc content authored.** Re-running the whole flow changes nothing
  (idempotent). If the area has no contract, the run stopped and said so.
