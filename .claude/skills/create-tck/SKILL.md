---
name: create-tck
description: Author a Tractus-X TestLab TCK (Test Case Kit) — an index.yaml manifest plus test scripts in the harmonized v1-alpha engine dialect — and validate it with the testlab CLI and the cx-test-suite IDE checks. Use whenever creating or editing a TCK, a test case YAML, env variables/testdata/schemas, or when validating/compiling TestLab YAML.
---

# Creating a TCK (Test Case Kit)

A TCK is a portable, compilable test package for certifying a System Under Test (SUT)
against a Catena-X standard. You author it as a directory of YAML + JSON files, then
compile it into a `.tck` artifact with the `testlab` CLI.

## Authoritative sources — and the stale ones

Author **only** against the engine dialect. Ground truth, in priority order:

1. `src/tractusx_testlab/models/authoring/definitions.py` — the Pydantic models the compiler enforces
2. `docs/specification/syntax/tck-syntax.md` — the harmonized syntax spec
3. `docs/specification/reference/steps.md` — the generated step catalog (57 steps; regenerate with `testlab docs`, never hand-edit)
4. `docs/developer/ide-engine-contract-parity.md` + `docs/developer/contract-conflict-decisions.md` (C01–C47) — the canonical engine↔IDE contract; the decisions file wins on conflict
5. `docs/examples/certificate-management-v2/raw/` — the shipped reference TCK

**Do not follow** `docs/specification/reference/syntax/cheat-sheet.md`,
`docs/specification/walkthrough/writing-test-scripts.md`,
`docs/specification/walkthrough/compiling-packages.md`, or
`docs/specification/schemas/*-v2.schema.json`. They document a stale dialect
(`testlab:` header key, `steps:` phase, flat `env.variables` map, `env.services:`,
`tck.yaml`, `.tckpkg`, operators `regex`/`greater_than`) that the compiler rejects.

## Source layout

```
<standard-short-name>-v<version>/
├── index.yaml          # TCK manifest — the input to `testlab compile`
├── tests/*.yaml        # one file per test case, snake_case.yaml
├── testdata/*.json     # request/response payload fixtures
└── schemas/*.json      # JSON Schemas used by validate/schema
```

Every YAML file starts with the Apache-2.0 license header block (copy it from
`docs/examples/certificate-management-v2/raw/index.yaml`) followed by the
AI-generated-code subtitle (`##` comment lines, with your actual tool/model names).

## index.yaml (`kind: tck`)

Block order: header → `metadata` → `dataspace` → `infrastructure` → `env` → `tests`.

```yaml
kind: tck
syntax: v1-alpha

id: certificate-management-tck-v0.0.1        # ^[a-z][a-z0-9_.-]{0,99}$

metadata:
  name: "Certificate Management TCK"
  version: "v0.0.1"
  description: >
    What this TCK certifies, one numbered line per test.
  authors: [{ name: ..., email: ..., company: ... }]
  copyright_holders: ["2026 ..."]
  license: LicenseRef-Proprietary
  standards: [{ id: CX-0135, version: v3.1.0 }]
  tags: [CCM]

dataspace:
  ecosystem: Catena-X
  version: saturn            # saturn (EDC v0.11+, DSP 2025-1) or jupiter (EDC v0.8–0.10)

infrastructure:              # declare per side what capability is required
  engine:
    connector: { required: true, standard: { id: CX-0018, version: v4.2.0 } }
  sut:
    connector: { required: true, standard: { id: CX-0018, version: v4.2.0 } }

env:
  variables:                 # a LIST of step-shaped entries — never a flat key: value map
    - id: shell_descriptor_id             # what the operator must tell the run; never the
      uses: variable/type/string          # SUT's DSP address or BPN — those are bindings
      with: { source: input, scope: sut } # or config/connector/policy, config/connector/asset
      returns:
        value: { type: string }
    - id: ccm_usage_policy
      uses: config/connector/policy
      with:
        source: value                     # inline value instead of runtime input
        value: { permissions: [ ... ] }   # the whole ODRL policy document
      returns:
        value: { type: object, class: Policy }
  schemas:
    - id: certificate_schema
      source: business_partner_certificate_schema-v3.0.1.json   # file in schemas/
  testdata:
    - id: request_certificate_body
      source: request_certificate_body.json                     # file in testdata/
      type: application/json

tests:                       # ordered; each id is the filename: ^[a-zA-Z0-9_\-.]+\.yaml$
  - id: request_certificate.yaml
    name: Request a certificate via CCMAPI
    skippable: true          # optional, default false — see below
```

Rules: `source: input` variables **must** declare `scope: engine|sut`. **Every
variable publishes one value under `value`** — write
`returns: { value: { type: <the verb's type> } }`, add `class: Policy` / `class: Asset`
for the two `config/connector/*` verbs, and reference the whole variable as
`${{ env.<id> }}`. The compiler rejects any other `returns:` key, an unknown
`uses:` verb, a type the verb does not publish, and a variable that neither
carries a `with.value` nor asks the operator for one. Tests run sequentially but
**independently** — a test must never read another test's outputs; anything shared
belongs in `env`. `id`, `name` and `skippable` are the only keys an entry accepts.

`skippable: true` marks a test the operator may omit at run time via the
`skip_tests` variable — use it when the standard makes the behaviour a MAY or the
deployment optional, and leave it off for anything normative. The player refuses
the whole run if `skip_tests` names a test that is not marked, so a mandatory test
can never be skipped.

## Test scripts (`kind: test`)

```yaml
kind: test
syntax: v1-alpha

namespace: certificate-management-tck-v0.0.1   # MUST equal the TCK id
id: request-certificate

metadata:
  name: "Request Certificate"
  version: "v1.0.0"
  description: >
    What is exercised and what is asserted.

setup: [ ... ]       # optional; no validate: allowed here
execution: [ ... ]   # required phase — never `steps:`
teardown: [ ... ]    # optional; no validate:; always runs, even after failure
```

Test files have **no `env:` block** — they inherit the manifest's.

### The counter-party is a binding, not a variable

Never declare `counter_party_address` / `counter_party_id` as `env` variables, and never
pass them to a connector step that addresses the system under test. Both default to the
infrastructure binding — `infrastructure.sut.connector.dsp_url` and
`infrastructure.sut.connector.participant_id` — which `sut.connector.required: true`
already obliges the operator to supply. Declaring them again asks for the same values
twice. Pass them explicitly only to address somebody the binding does not describe.

### Step shape

Field order: `id → uses → name → with → returns → validate → if → timeout_s`.

```yaml
execution:
  - id: pull_ccmapi_endpoint            # ^[a-z][a-z0-9_]{0,49}$, unique per test
    uses: connector/consumer/pull_data_filtered
    name: Discover CCMAPI offer and obtain dataplane credentials
    with:                               # no counter_party_address / counter_party_id:
      expected_policies: "${{ env.ccm_usage_policy }}"   # they default to the
                                          # bound SUT connector
    returns:
      edr_token: { type: string, class: AuthToken }
      dataplane_url: { type: string }
    validate:
      - uses: validate/assert
        with: { input: edr_token, operator: not_null }

  - id: request_certificate
    uses: connector/dataplane/http_request
    with:
      method: POST
      dataplane_url: "${{ execution.pull_ccmapi_endpoint.dataplane_url }}"
      path: "/companycertificate/request"
      edr_token: "${{ execution.pull_ccmapi_endpoint.edr_token }}"
      headers: { Content-Type: "application/json" }
      body: "${{ env.testdata.request_certificate_body }}"
    returns:
      status_code: { type: integer }
      response_body: { type: object, class: ResponseBody }
    validate:
      - uses: validate/field
        with: { input: status_code, operator: equals, value: 200 }
      - uses: validate/schema
        with: { input: response_body, schema: "${{ env.schemas.certificate_schema }}" }
```

- `returns.<key>.type` ∈ `string|object|number|integer|bool|array`; optional `class` ∈
  `AuthToken, DataplaneUrl, StatusCode, ResponseBody, Policy, Asset, MockInstance, Uuid, Url, Bpn`.
- A `returns:` key resolves **only if the step's contract declares it** — no fallback to
  the raw HTTP response. Universal slots readable on any step: `value, request, response,
  status_code, headers, body, duration_ms, response_body, response_headers`.
- There is **no `save_as`/`register`/exports channel**: every step publishes all its
  top-level output fields as context variables under their own names.
- Optional control keys: `if:` (condition) and `timeout_s: 30.0`.

### References — `${{ ... }}` only (ADR-0010)

`${{ env.<var-id> }}` · `${{ env.schemas.<id> }}` · `${{ env.testdata.<id> }}` ·
`${{ execution.<step-id>.<return-key> }}` · `${{ setup.<step-id>.<key> }}` ·
`${{ metadata.<key> }}` · `${{ infrastructure.<engine|sut>.<capability> }}`

Never `@var` or `${var}`. References resolve **backwards only** within one test —
forward or cross-test references are compile errors. A reference that is the whole value
may be unquoted; embedded in a longer string it must be quoted. In `validate` blocks,
a step's own outputs are referenced by bare name (`input: status_code`).

### Assertions

Exactly three validation steps: `validate/assert {input, operator, value}`,
`validate/field {input, path: "header.messageId", operator, value}`,
`validate/schema {input, schema}`. Operator vocabulary (only these):

`not_null, is_null, not_empty, equals, not_equals, contains, not_contains,
matches_regex, one_of, none_of, has_key, not_has_key, gt, gte, lt, lte,
length_equals, length_gt, length_lt, between`

A failed validation fails its step; a failed step aborts the test (rest skipped,
teardown still runs). There are no soft assertions or per-step failure policies.

## Contract hard rules (from the parity doc)

- **One name, one shape**: no aliases, no dual spellings, no compat shims — ever.
- `with:` is strictly typed (`extra="forbid"`): an undeclared key is a compile error.
  Discover each step's exact params/outputs with
  `poetry run testlab docs --json -o -` (or `--step <uses-id> --json -o -`), or read
  `docs/specification/reference/steps.md`. **Always pass `-o -`** — without it the
  command overwrites the repo's generated `steps.md` (filtered to your `--step`
  selection); if that happens, restore it with a plain `poetry run testlab docs`.
- Step ids are `<category>/<module>/<function>`; module omitted only when the category
  has no sub-division (`util/log`, `flow/delay`, `validate/assert`). Always write ids in full.
- Steps **never** name their service: no `service:`/`connector_service:` key exists —
  connector/DTR bindings are seeded from `infrastructure` at runtime.
- A parameter carries the same name as the output it consumes — e.g.
  `pull_data_filtered` publishes `dataplane_url`/`edr_token` and
  `connector/dataplane/http_request` reads exactly those names. Canonical data-plane
  pair is always `dataplane_url` + `edr_token`.
- Documents stay documents: `create_asset`/`create_policy`/`create_shell_descriptor`/
  `create_submodel_descriptor` take one whole-document param (`asset`, `policy`, …)
  fed from an `env` variable — never flattened fields.

## Validate your work (CLI loop)

Run from the tractusx-testlab repo root, in this order:

```bash
poetry run testlab validate <dir>/index.yaml            # fast gate; exit 1 + [ERROR] lines on failure
poetry run testlab compile <dir>/index.yaml -o out/     # full compile → out/<tck-id>.tck
poetry run testlab inspect out/<tck-id>.tck --json --variables --infrastructure
poetry run testlab run <dir>/index.yaml -c config.yaml  # optional: execute against a live setup
```

`validate` exits 0 with warnings ("Valid with N warning(s)") — read them anyway.
`compile` re-validates (JSON Schema → step registry + expression checks → IR build), so
"Unknown step type '<uses>'", undeclared-param, and unresolvable-reference errors all
surface there. `inspect --json` is the machine-readable self-check: confirm every step,
validation count, variable, and infrastructure requirement matches what you authored.

Regression checks when the TCK lives in this repo:

```bash
poetry run pytest tests/unit/compiler tests/integration/test_compile_e2e.py -q
poetry run pytest tests/examples/ccm/test_ccm_compile_all.py -q   # shipped examples still compile
```

## Validate in the IDE (cx-test-suite)

The IDE (checkout at `~/catenax-eV/cx-test-suite`) round-trips exactly this layout:

- **Import**: package `index.yaml` + `tests/` + `schemas/` + `testdata/` as a ZIP and
  import it as a project (`src/features/ide/services/project/projectImportExport.ts`).
  A clean import/export round-trip proves the YAML matches the shared authoring contract.
- **Compile button**: the IDE posts the YAML to `${backendUrl}/testlab/compile` and
  renders `{path, message}` errors — same compiler, so a CLI-green TCK must be IDE-green.
- **Block catalog**: every `uses:` you author must exist as a block under
  `public/blocks/` (listed in `index.json` — an unlisted block is invisible in the
  toolbox). Check drift with
  `poetry run python tools/compare_ide_parity.py --ide ~/catenax-eV/cx-test-suite --check`
  (exit 1 while any class A/B/C/G divergence remains; `--json out.json` for details).
- **IDE tests**: `npx vitest run` from the cx-test-suite checkout (includes
  `blockCatalogUses`, `toolboxCoverage`, `projectImportExport`, `modelToYaml`).
  Its `npm run typecheck`/eslint have pre-existing failures — not a signal.

## Common compile errors → fixes

| Error | Fix |
|---|---|
| `Unknown step type '<uses>'` | Wrong/renamed step id — look it up in `testlab docs --json -o -`; write the full `<category>/<module>/<function>` id |
| Extra/unknown field in `with:` | Param renamed or never existed; `extra="forbid"` — check the step contract |
| Referenced test file not found | `tests[].id` must be the exact filename in `tests/` |
| Unresolvable `${{ ... }}` | Forward/cross-test reference, or the step doesn't declare that `returns:` key |
| `source: input` variable rejected | Missing `scope: engine\|sut` |
| Operator rejected | Use the harmonized vocabulary (`matches_regex`, `gt`, …) — not `regex`/`greater_than` |
| Test's `namespace` mismatch | Must equal the manifest `id` exactly |
