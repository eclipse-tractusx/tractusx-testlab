---
name: create-tck-standalone
description: Author a Tractus-X TestLab TCK (Test Case Kit) — an index.yaml manifest plus test-case YAML scripts in the harmonized v1-alpha dialect — without access to the testlab or cx-test-suite repositories. Fully self-contained; includes the complete step catalog (reference/step-catalog.md), all syntax rules, and how the result is validated in the cx-test-suite IDE. Use whenever creating or editing a TCK, test-case YAML, or TestLab env variables/testdata/schemas.
---

# Creating a TCK (Test Case Kit) — standalone reference

A TCK is a portable test package that certifies a System Under Test (SUT) against a
Catena-X standard. It is authored as a directory of YAML + JSON files and compiled by
the TestLab engine (CLI `testlab compile`, or the cx-test-suite IDE's Compile button —
both run the same compiler). This document is the complete authoring contract
(syntax `v1-alpha`, harmonized engine↔IDE contract, 2026-08); do not rely on any
other TestLab documentation you may encounter — older documents describe a
`testlab:`/`steps:`/flat-`env.variables` dialect the compiler rejects.

The full catalog of the 57 available steps — every `uses:` id with its exact `with:`
params and outputs — is in [reference/step-catalog.md](reference/step-catalog.md).
**Always look a step up there before using it**: params are strictly typed and an
undeclared or misspelled key is a compile error.

## Source layout

```
<standard-short-name>-v<version>/
├── index.yaml          # TCK manifest — the compiler's input
├── tests/*.yaml        # one file per test case, snake_case.yaml
├── testdata/*.json     # request/response payload fixtures
└── schemas/*.json      # JSON Schemas used by validate/schema
```

Every YAML file starts with this license header (adjust years/holders), followed by
the AI-attribution subtitle with your actual tool and model:

```yaml
################################################################################
# Catena-X - Test Suite
#
# Copyright (c) 2026 Catena-X Automotive Network e.V.
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: <tool>, Model: <model>).
## It was reviewed and tested by a human committer.
```

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

infrastructure:              # per side, which capability the run requires
  engine:                    # the test engine's own side
    connector: { required: true, standard: { id: CX-0018, version: v4.2.0 } }
  sut:                       # the system under test
    connector: { required: true, standard: { id: CX-0018, version: v4.2.0 } }

env:
  variables:                 # a LIST of step-shaped entries — never a flat key: value map
    - id: shell_descriptor_id
      uses: variable/type/string
      with: { source: input, scope: sut }   # operator supplies the value at run time
      returns:
        value: { type: string }
    - id: ccm_usage_policy
      uses: config/connector/policy
      name: Required CCMAPI Usage Policy
      with:
        source: value                       # inline literal instead of runtime input
        value:                              # the whole ODRL policy document
          permissions:
            - action: use
              constraints:
                and:
                  - left_operand: UsagePurpose
                    operator: isAnyOf
                    right_operand: "cx.ccm.base:1"
      returns:
        value: { type: object, class: Policy }
  schemas:
    - id: certificate_schema
      source: business_partner_certificate_schema-v3.0.1.json   # file in schemas/
  testdata:
    - id: request_certificate_body
      source: request_certificate_body.json                     # file in testdata/
      type: application/json

tests:                       # ordered; each id is the exact filename in tests/
  - id: request_certificate.yaml            # ^[a-zA-Z0-9_\-.]+\.yaml$
    name: Request a certificate via CCMAPI
    skippable: true                         # optional, default false
```

`id`, `name` and `skippable` are the only keys a test entry accepts.
`skippable: true` marks a test the operator may omit at run time via the
`skip_tests` variable — use it when the standard makes the behaviour a MAY or the
deployment optional, and leave it off for anything normative. The player refuses
the whole run if `skip_tests` names a test that is not marked skippable.

Env variable `uses:` verbs (these are the only env verbs — regular steps do not go
in `env`): `variable/type/string`, `variable/type/integer`, `variable/type/number`,
`variable/type/boolean`, `variable/type/object`, `variable/type/array` (simple typed
values), `config/connector/policy` (`class: Policy`) and `config/connector/asset`
(`class: Asset`). **Every variable publishes one value under `value`** — write
`returns: { value: { type: <the verb's type> } }`, add `class:` for the two
`config/` verbs, and reference the whole variable as `${{ env.<id> }}`. The
compiler rejects any other `returns:` key, a type the verb does not publish, and a
variable that neither carries a `with.value` nor asks the operator for one. With
`source: input` the `scope: engine|sut` key is **mandatory** and an optional
`with.placeholder` documents the expected shape for the operator.

Rules: tests run sequentially but **independently** — a test must never read another
test's outputs; anything shared belongs in `env`. Connector/DTR service endpoints are
never named in steps — the engine binds them from `infrastructure` at runtime.

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

setup: [ ... ]       # optional; validate: not allowed here
execution: [ ... ]   # required phase — the key is `execution`, never `steps`
teardown: [ ... ]    # optional; no validate:; always runs, even after a failure
```

Test files have **no `env:` block** — they inherit the manifest's.

### Step shape

Field order: `id → uses → name → with → returns → validate → if → timeout_s`.

```yaml
execution:
  - id: pull_ccmapi_endpoint            # ^[a-z][a-z0-9_]{0,49}$, unique per test
    uses: connector/consumer/pull_data_filtered
    name: Discover CCMAPI offer and obtain dataplane credentials
    with:                                 # counter_party_address / counter_party_id are
      expected_policies: "${{ env.ccm_usage_policy }}"   # omitted — see below
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CCMAPI"
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

- `returns:` names the step outputs this test consumes. `returns.<key>.type` ∈
  `string|object|number|integer|bool|array`; optional `class` ∈ `AuthToken,
  DataplaneUrl, StatusCode, ResponseBody, Policy, Asset, MockInstance, Uuid, Url, Bpn`.
- A `returns:` key resolves **only if the step's contract declares that output**
  (see the catalog) — there is no fallback to the raw HTTP response. Universal slots
  readable on any step: `value, request, response, status_code, headers, body,
  duration_ms, response_body, response_headers`.
- There is **no `save_as`/`register`/exports mechanism**: every step automatically
  publishes all its top-level output fields as context variables under their own names.
- Params are named after the outputs they consume: `pull_data_filtered` publishes
  `dataplane_url`/`edr_token`, and `connector/dataplane/http_request` reads exactly
  those names. The canonical data-plane pair is always `dataplane_url` + `edr_token`.
- Document-shaped params stay whole documents: `create_asset`/`create_policy`/
  `create_shell_descriptor`/`create_submodel_descriptor` take one document param
  (`asset`, `policy`, `shell_descriptor`, `submodel_descriptor`) fed from an env
  variable. Flat-field authoring is the separate `.../wizard/...` step family.
- Optional control keys: `if:` (list of Condition objects gating the step) and
  `timeout_s: 30.0`.

### The counter-party is a binding, not a variable

Never declare `counter_party_address` / `counter_party_id` as `env` variables, and
never pass them to a connector step that addresses the system under test. The engine
seeds both from the infrastructure binding the operator supplied —
`infrastructure.sut.connector.dsp_url` and `infrastructure.sut.connector.participant_id`
— which `infrastructure.sut.connector.required: true` already obliges them to give.
Declaring them again as `env` inputs asks the operator for the same two values twice
and lets the two copies disagree.

Pass them explicitly only to address somebody the binding does not describe — a second
provider, or an endpoint a discovery step resolved.

### References — `${{ ... }}` only

```
${{ env.<var-id> }}      ${{ env.schemas.<id> }}      ${{ env.testdata.<id> }}
${{ execution.<step-id>.<return-key> }}   ${{ setup.<step-id>.<key> }}
${{ metadata.<key> }}                 ${{ infrastructure.<engine|sut>.<capability> }}
```

Never `@var` or `${var}`. References resolve **backwards only** within one test —
forward references and cross-test references are compile errors. A reference that is
the entire YAML value may be unquoted; embedded inside a longer string it must be
quoted. Inside a step's own `validate:` block, that step's outputs are referenced by
bare name (`input: status_code`), no `${{ }}`.

### Assertions

Exactly three validation steps, usable only inside `validate:` blocks of
`execution` steps:

- `validate/assert` — `with: { input, operator, value }`
- `validate/field` — `with: { input, path: "header.messageId", operator, value }` (dot-separated path)
- `validate/schema` — `with: { input, schema: "${{ env.schemas.<id> }}" }` (inline schema object also accepted)

Operator vocabulary (only these — e.g. `regex` and `greater_than` are invalid):

```
not_null  is_null  not_empty  equals  not_equals  contains  not_contains
matches_regex  one_of  none_of  has_key  not_has_key  gt  gte  lt  lte
length_equals  length_gt  length_lt  between
```

A failed validation fails its step; a failed step aborts the test (remaining steps
skipped, teardown still runs). No soft assertions, no per-step failure policy.

### Step ids

Ids are `<category>/<module>/<function>`; the module segment is omitted only when
the category has no sub-division (`util/log`, `flow/delay`, `validate/assert`).
Always write ids in full. One name, one shape: there are no aliases, alternate
spellings, or backwards-compatible forms for any id, param, or output.

## How the cx-test-suite IDE consumes your TCK

The cx-test-suite web IDE is the visual editor for this exact format. Facts an
authoring agent should exploit:

- **Project import/export is the source layout zipped**: a ZIP containing
  `index.yaml`, `tests/`, `schemas/`, `testdata/` imports directly as an IDE project,
  and IDE export produces the same layout. Deliver your TCK as that ZIP and it is
  IDE-openable with zero conversion.
- **The Compile button runs the same compiler** (backend endpoint
  `POST <backend>/testlab/compile`) and shows each error as a file path + message.
  A TCK that compiles clean in the CLI is green in the IDE and vice versa.
- **Every step is a visual block** (catalog v4.0, 60 blocks): toolbox categories are
  Mock, Wait, Utility, Flow, Connector (Shortcuts/Consumer/Utilities/Dataplane/
  Provider), Digital Twin (Provider/Submodel/Consumer), Notification, HTTP, Security,
  Validation. Block params/outputs mirror the step contracts one-to-one, including
  the `class` tags. The only registered step without a block is
  `digital-twin/submodel/delete` — prefer alternatives when IDE editability matters.
- **Structured values are built with programmatic blocks** (`filter_expression`,
  `filter_expression_custom`, `condition_expression`, `asset_criterion`): in YAML you
  author them as the plain lists/objects shown above (`filters:` items with
  `operand_left/operator/operand_right`, `conditions:` with `input/path/operator/value`).

## Validating your work

Without repo access you cannot run the compiler yourself, so validate in two layers:

**1. Self-review checklist — walk it file by file before delivering:**

- [ ] Both header lines (`kind:` + `syntax: v1-alpha`) on every YAML file; license header present
- [ ] Every test's `namespace:` equals the manifest `id:` exactly
- [ ] Every `tests[].id` in index.yaml is the exact filename of a file in `tests/`
- [ ] Every `uses:` exists in [reference/step-catalog.md](reference/step-catalog.md), written in full
- [ ] Every `with:` key is declared by that step's contract (strict — extras are errors)
- [ ] Every required param of every used step is provided
- [ ] Every `returns:` key is an output the step's contract actually declares
- [ ] Every `${{ ... }}` points backwards to an earlier step in the same test, or to `env`
- [ ] Embedded references quoted; operators only from the vocabulary above
- [ ] `source: input` env variables carry `scope: engine|sut`
- [ ] Every `env.schemas`/`env.testdata` `source:` file exists in `schemas//testdata/`
- [ ] No `service:`, `save_as:`, `steps:` phase, or flat env map anywhere
- [ ] No test reads another test's outputs

**2. Compiler ground truth** — ask the user to import the ZIP into the cx-test-suite
IDE and press Compile (or, where the testlab CLI exists:
`testlab validate <dir>/index.yaml` then `testlab compile <dir>/index.yaml`, and
`testlab inspect <out>.tck --json --variables --infrastructure` for a machine-readable
summary). Fix every reported `{path, message}` error; treat warnings as findings too.

## Common compile errors → fixes

| Error | Fix |
|---|---|
| `Unknown step type '<uses>'` | Id wrong or abbreviated — copy the full id from the catalog |
| Extra/unknown field in `with:` | Param renamed or never existed — check the step's contract |
| Referenced test file not found | `tests[].id` must be the exact filename in `tests/` |
| Unresolvable `${{ ... }}` | Forward/cross-test reference, or the step doesn't declare that output |
| `source: input` variable rejected | Add `scope: engine` or `scope: sut` |
| Operator rejected | Use the harmonized vocabulary (`matches_regex`, `gt`, …) |
| `namespace` mismatch | Must equal the manifest `id` exactly |
