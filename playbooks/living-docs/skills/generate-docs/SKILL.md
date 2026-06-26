---
name: generate-docs
description: >-
  Generate or update a repo's structured /docs tree, driven entirely by its
  docs/.docs-manifest.yaml. Use when the user asks to "generate docs",
  "regenerate /docs", "update the docs", "fill the docs structure",
  "documentar el repo", or to produce the agent-generated documentation PR.
  Reads the manifest, runs the deterministic generators (gen_docs), and
  authors the remaining sections as pure Markdown — contract-agnostic
  (works for any stack/domain the manifest declares), faithful to the code,
  never merges to main. If docs/.docs-manifest.yaml is missing, STOP and
  point the user to /init-docs.
---

# Generate / update `/docs`

This skill keeps a repo's `/docs` tree alive: it (re)generates and updates the
documentation for **one repo**, driven **entirely by that repo's
`docs/.docs-manifest.yaml`**. The repo is the single source of truth for
content; the manifest is the single source of truth for *structure* — what
docs exist, what each must contain, how each is produced, and when each goes
stale.

**Contract-agnostic by design.** This skill and its `gen_docs` engine carry
**no** knowledge of any particular stack, domain, or documentation contract.
There is no hardcoded section list, no assumed directory layout, no per-stack
rule. Everything specific to a repo lives in its manifest. The same skill
documents a backend service, a frontend app, a library, or a data pipeline —
the manifest is what differs, not this skill.

> **User prompts use `AskUserQuestion`.** Every decision this skill puts to the
> user (e.g. how to resolve an ambiguous manifest field, whether to proceed
> when something looks off) is asked through the `AskUserQuestion` tool — never
> as a plain-chat `(yes/no)`. The widget shape is the model's call given the
> runtime context.

---

## Hard gate — the manifest must already exist

Before anything else, check for `docs/.docs-manifest.yaml`:

- **If it is missing → STOP.** This skill does **not** bootstrap, scaffold, or
  set up a docs structure. Tell the user to run **`/init-docs`** first (the
  onboarding/init flow), which writes the manifest from a contract.
  Do not run `gen_docs bootstrap` yourself and do not invent a manifest.
- Confirm you are on a **ticket branch**, not `main`/`develop`. If you are on a
  protected branch, ask (via `AskUserQuestion`) before creating one.

The manifest's presence is the contract that this repo has opted into living
docs. Without it there is nothing to drive generation, and guessing a structure
would violate the faithfulness rule below.

## Hard rules

- **Source stays pure Markdown.** No presentation, icons, or platform syntax —
  a downstream pipeline owns presentation; you keep the truth.
- **Faithful, not inventive.** Every claim must trace to the code, config,
  schema, tests, CI, or existing docs. If something can't be determined, mark
  it explicitly — never guess.
- **Deterministic.** Two runs on the same repo state produce consistent output.
  Record any accepted inconsistency in the run report.
- **Manifest-driven frontmatter.** Every file carries exactly the four-field
  contract frontmatter; `service`, `domain`, and each `section` come from the
  manifest, never assumed. Add nothing else (`title`, `status`, `owner`, …).
- **Idempotent.** The first run authors the docs from scratch; reruns update
  only what changed (the linter classifies what needs work — see below).
- **Never merge to `main`.** Scope ends at an agent-generated PR.

## The manifest is the contract (`docs/.docs-manifest.yaml`)

Everything derives from the manifest. Read it first and treat each entry as the
spec for one doc. The fields you act on (generic across every contract):

| Field | Meaning |
|---|---|
| `path` | where the doc lives (the engine writes exactly here) |
| `section` | the doc's section → goes into its frontmatter |
| `kind` | `deterministic` (a generator owns it), `heuristic` (code-derived, LLM-authored, updated on drift), or `manual` (intent-level, age-based) |
| `description` | the **must-contain** rule for this doc — the contract for its body |
| `triggers.paths` | repo paths that, when they change, mean this doc may be stale |
| `triggers.discovery_hint` | guidance for finding this repo's concrete paths |
| `produces.command` / `produces.params` | the generator + its repo-specific params (e.g. a source root, a settings module) |
| `acknowledged_at_commit` | the commit the doc was last reconciled against (drift baseline) |

Top-level `service` and `domain` apply to the whole repo. The manifest — not
this skill — decides which docs are mandatory, where they live, and what they
must say.

## Procedure

### Step A — Read and adapt the manifest (the critical step)

Everything downstream is only as good as the manifest, so this is where the
work is. For **every** entry, make sure the repo-specific fields are filled by
*inspecting this repo*:

- `triggers.paths` — resolve the entry's `discovery_hint` against the actual
  tree. The hint describes *categorically* what to look for (e.g. "the
  application-logic layer", "the settings module", "the CI workflows"); your
  job is to find the **concrete** paths/globs in this repo and fill them.
- `produces.params` — for entries a generator produces, fill the params it
  needs (e.g. the source/test root, the app object, the Makefile, the
  workflows dir) from what the repo actually uses — not from a default.

Run `gen_docs lint` to see exactly which entries still need adapting (it emits
`run-adapt` / `adapt-pending` findings) and which are ready. Write the
discovered values back into `docs/.docs-manifest.yaml`. This adapt pass is the
one place repo-specific intelligence enters; do it carefully, because both
generation and drift-detection key off these values.

### Step B — Generate the deterministic substrate

Run the bundled engine (installed as the `gen_docs` console command from this
playbook's `package/`; see the README for the pip one-liner):

```
gen_docs all --repo . --service <slug>
```

`gen_docs all` runs **only** the generators the manifest declares — a doc fires
its generator only if an entry's `produces.command` selects it, so
stack-specific generators (e.g. an OpenAPI dump) never run for a repo that
doesn't declare them. This lays down the exact, no-judgement substrate
(source/test trees, anything script-produced) and any skeletons. Skeleton
generators are skipped when their output already exists (preserving prose);
force a regenerate with the explicit subcommand, e.g. `gen_docs config`.

Do this **before** authoring so the cheap, exact parts aren't redone by hand.

### Step C — Author / update the remaining sections

For every `heuristic` or `manual` entry, write (first run) or update (rerun)
the doc body to satisfy that entry's `description` — the must-contain rule —
staying faithful to the code. Let the linter tell you what to touch:

```
gen_docs lint                 # classify every entry; exit 1 on errors
gen_docs lint --emit-prompts  # JSON: a ready-to-use subagent prompt per finding
```

The linter is the **work-dispatcher**. It does not author anything itself; each
finding carries an `action`:

| Action | Meaning | Who acts |
|---|---|---|
| `regenerate-script` | re-run a deterministic generator | the engine |
| `run-adapt` | fill missing manifest fields by inspecting the repo | adapt pass |
| `dispatch-subagent` | author or update the doc body | per-doc subagent |
| `manual-fix` | a trigger glob matches nothing (probable rename) | edit the manifest |
| `re-ack` | `acknowledged_at_commit` not in history (squash/rebase) | re-ack the entry |

On a **rerun**, the linter diffs each entry's `triggers.paths` against
`acknowledged_at_commit..HEAD` and only flags docs whose source actually moved —
that is what makes updates incremental and the whole flow idempotent.

#### Subagent model policy

When a finding's action is `dispatch-subagent` or `run-adapt`, honor its
`action.model`:

- **`sonnet`** — first fill / first adapt: the doc has never been authored
  (`adapted_heuristic` is null) or the manifest is being adapted for the first
  time. These passes read the repo and write the reasoning future runs depend
  on.
- **`haiku`** — incremental updates against a focused diff once
  `adapted_heuristic` is set.

Don't promote a Haiku update to Sonnet because a diff looks large — that means
the heuristic needs rewriting, not a bigger model.

### Step D — Apply the filling rules

For every doc, replace any `Status: TODO`/skeleton block with one of:

- **Real content** — when the code/config supports it.
- **`not applicable` + one-line reason** — when the manifest declares it but
  this repo genuinely has no such thing.
- **`unknown` + reason** — when it can't be determined from the repo.

Silence is not allowed: an empty or stale section must say so explicitly.

### Step E — Run report (telemetry)

Emit a short report: count of entries filled vs skipped (with the skip reason
for each), and — on a rerun — a diff note against the previous output, flagging
or accepting any inconsistency.

### Step F — Open the PR

Open a PR from the ticket branch, clearly labeled as agent-generated (title
prefix `[agent-generated]`, the `docs`/`agent-led` labels), linking the
originating ticket. **Do not merge.** Fold reviewer feedback back into this
skill (versioned prompts), not as one-off edits.

---

## Definition of done

- Every entry the manifest declares is satisfied: deterministic substrate
  regenerated, heuristic/manual docs authored or updated.
- Every unfillable section carries a defined, consistently applied marker.
- Output is deterministic (or the inconsistency is documented + accepted).
- The manifest reflects this repo (adapted `triggers.paths` / `produces.params`).
- An agent-generated PR is open on the ticket branch, not merged to `main`.
