# Changelog

All notable changes to the `living-docs` playbook are documented here. Versioning is automated via [release-please](https://github.com/googleapis/release-please) — do not hand-edit `version` in `plugin.json`.

## Unreleased

### Features

* **living-docs:** relocate the `generate-backend-docs` skill and its deterministic `gen_docs` engine out of `mad` and republish them as the standalone `living-docs` playbook. Pure relocation/rename — no behavior change. Onboarding/init and the docs contract live in a separate playbook.

### Code Refactoring

* **living-docs:** make the engine and skill **manifest-driven and contract-agnostic** — generation/validation run strictly per `docs/.docs-manifest.yaml`, with no hardcoded stack, layout, section list, or domain. `gen_docs all` runs only the generators the manifest declares (stack-specific ones like the OpenAPI dump fire only when declared); `service`/`domain`/`section` are read from the manifest. `bootstrap`/`migrate` now take a `--contract` path (no bundled template); the skill is rewritten generic and stops with a pointer to `/init-docs` when the manifest is absent. Backend output verified byte-equivalent to the F1 baseline (only the generated-by provenance note differs). Renamed the skill `generate-backend-docs` → `generate-docs`.
