<!--

Eclipse Tractus-X - Tractus-X TestLab

Copyright (c) 2026 Catena-X Automotive Network e.V.
Copyright (c) 2026 Contributors to the Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

This work is made available under the terms of the
Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
which is available at
https://creativecommons.org/licenses/by/4.0/legalcode.

SPDX-License-Identifier: CC-BY-4.0

-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# Writing Tests

This walkthrough creates a TCK from scratch in the `v1-alpha` syntax. The files below are complete: together they
form a TCK that passes `testlab validate` and `testlab compile`. The [TCK Syntax](../../tck-syntax/index.md) reference
defines every key they use.

## Project Structure

```
my-certificate-tck/
├── index.yaml                              # TCK manifest (entry point)
├── tests/
│   ├── ping_catalog.yaml                   # Test 1
│   └── request_certificate.yaml            # Test 2
├── schemas/
│   └── certificate_schema.json             # JSON Schema used by validate/schema
└── testdata/
    └── request_body.json                   # Request payload
```

- `index.yaml` — declares the TCK: metadata, dataspace, infrastructure requirements, environment, and the test list
- `tests/` — one YAML file per test
- `schemas/` — JSON Schema files declared under `env.schemas`
- `testdata/` — payload files declared under `env.testdata`

## Step 1 — Create the TCK Manifest (index.yaml)

The manifest declares everything tests share: variables, schemas, testdata, what infrastructure a run needs, and the
ordered test list.

```yaml title="my-certificate-tck/index.yaml"
kind: tck
syntax: v1-alpha

id: my-certificate-tck

metadata:
  name: "Certificate Verification TCK"
  version: "v1.0"
  description: >
    Validate the certificate management workflow per CX-0135 v3.1.0.
  authors:
    - name: Your Team
      email: team@example.com
      company: Example Corp
  license: Apache-2.0
  standards:
    - id: CX-0135
      version: v3.1.0

dataspace:
  ecosystem: Catena-X
  version: saturn

infrastructure:
  engine:
    connector:
      required: true
  sut:
    connector:
      required: true

env:
  variables:
    - id: callback_timeout_s
      uses: variable/type/number
      name: Seconds to wait for the SUT's callback
      with:
        source: input
        scope: sut
      returns:
        value: { type: number }

    - id: ccm_usage_policy
      uses: config/connector/policy
      name: Required CCMAPI usage policy
      with:
        source: value
        value:
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
      source: certificate_schema.json

  testdata:
    - id: request_body
      source: request_body.json
      type: application/json

tests:
  - id: ping_catalog.yaml
    name: Query the SUT catalog
  - id: request_certificate.yaml
    name: Request a certificate and await the callback
```

Key points:

- `kind: tck` + `syntax: v1-alpha` identify the file type and syntax version. Only `syntax`, `id` and `metadata.name` are required.
- `dataspace.version` selects the dataspace release (`saturn`, `jupiter`) the connector steps run against.
- `infrastructure` says which capabilities each side must have bound. The connectors themselves — URLs, API keys,
  the SUT's DSP address and participant ID — are **not** declared here or anywhere in the TCK: the operator binds them
  at run time (see [Executing Tests](executing-tests.md#step-1--bind-the-infrastructure)).
- `env.variables` is a **list** of step-shaped entries. Each publishes one value under `returns.value`, referenced as
  `${{ env.<id> }}`:
    - `with.source: value` carries a literal (`with.value`).
    - `with.source: input` asks the operator at run time and must say who owes the value: `scope: engine` or `scope: sut`.
    - `uses` is the variable's type: `variable/type/string|integer|number|boolean|object|array`, or
      `config/connector/policy` / `config/connector/asset` for the two connector documents (`class: Policy` / `class: Asset`).
- `schemas` and `testdata` are lists of `{ id, source }` entries — `source` is the file name under `schemas/` or
  `testdata/` — referenced as `${{ env.schemas.<id> }}` and `${{ env.testdata.<id> }}`.
- `tests` lists the test files in execution order. `id` is the file name; `name` and `skippable` are optional.

## Step 2 — Write Your First Test

Create `tests/ping_catalog.yaml`:

```yaml title="my-certificate-tck/tests/ping_catalog.yaml"
kind: test
syntax: v1-alpha

namespace: my-certificate-tck
id: ping-catalog

metadata:
  name: "Ping Catalog"
  version: "1.0"
  description: >
    Query the SUT catalog to verify connectivity.

execution:
  - id: query_catalog
    uses: connector/consumer/query_catalog
    name: Query SUT catalog
    with:
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CCMAPI"
    returns:
      datasets:
        type: array
    validate:
      - uses: validate/assert
        name: the SUT offers at least one CCMAPI dataset
        with: { input: datasets, operator: length_gt, value: 0 }
```

Key points:

- `kind: test` identifies a test file; `namespace` must equal the manifest's `id`.
- Tests have **no** `env:` block — they read the manifest's.
- The test's steps live under `execution:`. `setup:` and `teardown:` are optional.
- No counter-party is named: connector steps default `counter_party_address` and `counter_party_id` to the bound SUT connector.
- `returns:` declares which of the step's outputs the test reads; `validate:` entries read those names directly (`input: datasets`).

## Step 3 — Add Setup and Chain Steps

A more complex test exposes a mock endpoint in `setup:`, negotiates access to the SUT's API, calls it through the
data plane, and waits for the SUT's callback.

```yaml title="my-certificate-tck/tests/request_certificate.yaml"
kind: test
syntax: v1-alpha

namespace: my-certificate-tck
id: request-certificate

metadata:
  name: "Request Certificate"
  version: "1.0"
  description: Send a certificate request and verify the SUT calls back.

setup:
  - id: callback
    uses: mock/api
    name: Expose the callback endpoint the SUT answers on
    with:
      method: POST
      path: "/certificate/callback"
      response_status: 200
    returns:
      mock: { type: object, class: MockInstance }
      full_mock_url: { type: string, class: Url }

execution:
  - id: pull_endpoint
    uses: connector/consumer/pull_data_filtered
    name: Negotiate access to the CCMAPI offer
    with:
      expected_policies: ${{ env.ccm_usage_policy }}
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CCMAPI"
    returns:
      dataplane_url: { type: string, class: DataplaneUrl }
      edr_token: { type: string, class: AuthToken }
    validate:
      - uses: validate/assert
        with: { input: edr_token, operator: not_null }

  - id: send_request
    uses: connector/dataplane/http_request
    name: Send the certificate request through the data plane
    with:
      method: POST
      dataplane_url: ${{ execution.pull_endpoint.dataplane_url }}
      edr_token: ${{ execution.pull_endpoint.edr_token }}
      path: "/companycertificate/request"
      headers:
        Content-Type: "application/json"
      body: ${{ env.testdata.request_body }}
    returns:
      status_code: { type: integer, class: StatusCode }
      response_body: { type: object, class: ResponseBody }
    validate:
      - uses: validate/assert
        name: the request was accepted
        with: { input: status_code, operator: equals, value: 200 }
      - uses: validate/schema
        with:
          input: response_body
          schema: ${{ env.schemas.certificate_schema }}

  - id: wait_callback
    uses: mock/wait/http_request
    name: Wait for the SUT to call back
    with:
      mock: ${{ setup.callback.mock }}
      timeout_s: ${{ env.callback_timeout_s }}
    returns:
      request_body: { type: object, class: ResponseBody }
    validate:
      - uses: validate/field
        with:
          input: request_body
          path: "content.certificateStatus"
          operator: one_of
          value: ["RECEIVED", "ACCEPTED", "REJECTED"]
```

- `mock/api` registers an endpoint on the TestLab server; its `full_mock_url` is the address to hand the SUT, its
  `mock` is what `mock/wait/http_request` blocks on.
- `pull_data_filtered` publishes `dataplane_url` and `edr_token`, and `connector/dataplane/http_request` takes
  parameters of exactly those names.
- `teardown:` steps, when a test has them, run whatever happened before them — even after a failure.

## Step 4 — Understanding Variable References

All references use the `${{ }}` expression syntax:

| Pattern | Resolves to |
|---------|-------------|
| `${{ env.<id> }}` | A manifest variable's value |
| `${{ env.testdata.<id> }}` | A testdata file's content |
| `${{ env.schemas.<id> }}` | A schema file's content |
| `${{ setup.<step-id>.<output> }}` | A setup step's output (same test) |
| `${{ execution.<step-id>.<output> }}` | An earlier execution step's output (same test) |
| `${{ infrastructure.<engine\|sut>.<capability>.<field> }}` | A bound infrastructure value |

References resolve **backwards only**, within one test. A reference that is the whole value may be unquoted; one
embedded in a longer string must be quoted. `testlab validate` rejects a reference that names nothing and lists what is available.

## Step 5 — Assertions

Every step can include a `validate:` block. There are three assertion kinds — `validate/assert`, `validate/field`
(adds a `path` into the value) and `validate/schema`. Each entry may carry an optional `name:`; the run report calls
the check by it:

```yaml
validate:
  - uses: validate/assert
    name: the request was accepted        # optional
    with: { input: status_code, operator: equals, value: 200 }
  - uses: validate/field
    with: { input: response_body, path: "header.messageId", operator: matches_regex, value: "^urn:uuid:" }
  - uses: validate/assert/not_empty       # the operator may also be a suffix of uses
    with: { input: datasets, severity: SOFT }
  - uses: validate/assert
    with: { input: status_code, operator: between, min: 200, max: 299 }
```

Operators: `not_null`, `is_null`, `not_empty`, `equals`, `not_equals`, `contains`, `not_contains`, `matches_regex`,
`one_of`, `none_of`, `has_key`, `not_has_key`, `gt`, `gte`, `lt`, `lte`, `length_equals`, `length_gt`, `length_lt`,
`between` (`min`/`max`). When none is named, `not_null` applies. `severity: HARD` (the default) fails the step;
`severity: SOFT` is reported as a warning. A failed step aborts the rest of the test.

## Step 6 — Validate Against a Schema, Then Extract a Nested Value

A common pattern: fetch a document, validate its whole shape against a JSON Schema declared in `env.schemas`, then
pull a nested value out for a follow-up request. The steps below read a digital twin from the SUT's registry,
confirm it conforms, and extract the asset id from its `SUBMODEL-VALUE-3.1` endpoint.

```yaml
execution:
  # 1. Negotiate access to the SUT's Digital Twin Registry
  - id: dtr_access
    uses: connector/discover/digital-twin-registry/auth
    returns:
      dataplane_url: { type: string }
      edr_token: { type: string }

  # 2. Read the twin and validate the whole descriptor against a schema
  - id: query_dt
    uses: digital-twin-registry/consumer/dataplane/get_shell_descriptor
    with:
      aas_identifier: ${{ env.twin_id }}
      dataplane_url: ${{ execution.dtr_access.dataplane_url }}
      edr_token: ${{ execution.dtr_access.edr_token }}
    returns:
      value: { type: object, class: ResponseBody }
    validate:
      - uses: validate/schema
        with:
          input: value
          schema: ${{ env.schemas.shell_descriptor_schema }}

  # 3. Extract the SUBMODEL-VALUE-3.1 endpoint's subprotocolBody.
  #    The predicate steps over the descriptor/endpoint arrays without indices.
  - id: get_subprotocol_body
    uses: util/json_path_extract
    with:
      input: ${{ execution.query_dt.value }}
      path: "submodelDescriptors.endpoints[interface='SUBMODEL-VALUE-3.1'].protocolInformation.subprotocolBody"
    returns:
      value: { type: string }

  # 4. The subprotocolBody is "id=...;dspEndpoint=..." — pull just the asset id
  - id: get_asset_id
    uses: util/parse_kv
    with:
      input: ${{ execution.get_subprotocol_body.value }}
      select: id
    returns:
      value: { type: string }
```

- A step whose output is a single value (a document, a string) publishes it as `value`.
- `validate/schema` fails the step when the document does not match, reporting the offending field paths.
- The quotes around `'SUBMODEL-VALUE-3.1'` are required — predicate values that contain `.`, `;`, or `#` must be quoted.
- `util/parse_kv` splits each pair on the first `=` only, so a `dspEndpoint` value containing its own query string survives intact.

See the [Step Reference](../../api-reference/steps/index.md) for every step's inputs and outputs.

## Step 7 — Validate

```bash
testlab validate my-certificate-tck/index.yaml
```

```text
OK — index.yaml is valid (no issues)
```

A mistake is reported with the file it is in, before anything runs:

```text
  [ERROR] (execution step 0) tests/ping_catalog.yaml: Unknown step type 'connector/consumer/query_catalogue'
  [ERROR] (step 1) tests/request_certificate.yaml: '${{ execution.pull_endpont.edr_token }}' in param 'edr_token' names nothing this TCK supplies. Available: env.callback_timeout_s, env.ccm_usage_policy, …

Invalid — 2 error(s)
```

Continue to [Compiling Packages](compiling-packages.md).
