<!--

Eclipse Tractus-X - Software Development KIT

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

# Writing Test Scripts

This walkthrough guides you through creating a TCK project from scratch using the TestLab v1-alpha YAML syntax.

## Project Structure

A TCK project uses this layout:

```
my-certificate-tck/
├── index.yaml                              # TCK manifest (entry point)
├── tests/
│   ├── ping_catalog.yaml                   # Test 1
│   └── request_certificate.yaml            # Test 2
├── schemas/
│   └── certificate_schema.json             # JSON Schema for validation
└── testdata/
    └── request_body.json                   # Reusable request payload
```

- `index.yaml` — declares the TCK: metadata, environment, and test list
- `tests/` — one YAML file per test case
- `schemas/` — JSON Schema files referenced by the TCK
- `testdata/` — static JSON payloads referenced by steps

## Step 1 — Create the TCK Manifest (index.yaml)

The manifest declares everything tests share: variables, services, schemas, testdata, and the ordered test list.

```yaml
kind: tck
testlab: v1-alpha

id: my-certificate-tck
namespace: cert-v1.0

metadata:
  name: "Certificate Verification TCK"
  version: "v1.0"
  description: >
    Validate certificate management workflow per CX-0135 v3.1.0.
  authors:
    - name: Your Team
  license: Apache-2.0
  standards:
    - id: CX-0135
      version: v3.1.0
  dataspace_version: saturn

env:
  variables:
    provider_url: ""
    provider_bpn: ""
    consumer_bpn: ""
    certificate_type: "iso9001"
    sut_response_timeout: 300
    sut_dsp_url: ""
    sut_bpn: ""
  services:
    - name: testlab_connector
      uses: service/connector_service
      with:
        base_url: ${{ env.provider_url }}
        management_path: /management/v3
        dsp_path: /api/v1/dsp/2025-1
        dataspace_version: ${{ metadata.dataspace_version }}
        auth:
          type: api_key
          api_key: "test-api-key"
          api_key_header: "X-Api-Key"
      returns:
        connector_service:
          type: class
          class: ConnectorService
  schemas:
    - id: certificate_schema
      source: certificate_schema.json
  testdata:
    - id: request_body
      source: request_body.json

tests:
  - ping_catalog.yaml
  - request_certificate.yaml
```

> `schemas` and `testdata` are **lists** of `{ id, source }` entries — `source`
> is the file name under `schemas/` or `testdata/`. Each is bound to
> `${{ env.schemas.<id> }}` / `${{ env.testdata.<id> }}` at run time.

Key points:

- `kind: tck` + `testlab: v1-alpha` identify the file type and syntax version
- `env.variables` are simple `key: value` pairs — runtime inputs (such as `sut_dsp_url`) start empty and are supplied at run time
- `env.services` use the `uses:`/`with:`/`returns:` pattern
- `tests` lists relative paths to test files (no `!include`)

## Step 2 — Write Your First Test

Create `tests/ping_catalog.yaml`. Tests inherit the `env` from the TCK manifest and can reference its shared variables.

```yaml
kind: test
testlab: v1-alpha

id: ping-catalog
namespace: cert-v1.0

metadata:
  name: "Ping Catalog"
  version: "1.0"
  description: >
    Query the SUT catalog to verify connectivity.

steps:
  - id: query_catalog
    uses: connector/consumer/query_catalog
    name: Query SUT catalog
    with:
      counter_party_address: ${{ env.sut_dsp_url }}
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "like"
          operand_right: "%"
    returns:
      status_code:
        type: integer
        class: StatusCode
      datasets:
        type: array
        class: CatalogDatasets
    validate:
      - uses: validate/assert
        with: { input: status_code, operator: equals, value: 200 }
      - uses: validate/assert
        with: { input: datasets, operator: not_null }
```

Key points:

- `kind: test` identifies this as a test file
- `namespace` must match the TCK's namespace
- Tests have **no** `env:` block — they inherit from the TCK
- `${{ env.sut_dsp_url }}` references a shared environment variable
- Each step declares `returns:` and optional `validate:` blocks

## Step 3 — Add Setup, Steps, and Teardown

A more complex test can use `setup:` (mock endpoints), `steps:` (test logic), and `teardown:` (cleanup).

```yaml
kind: test
testlab: v1-alpha

id: request-certificate
namespace: cert-v1.0

metadata:
  name: "Request Certificate"
  version: "1.0"
  description: Send a certificate request and verify the SUT responds.

setup:
  - id: mock_response
    uses: mock/api
    name: Expose mock endpoint for SUT callback
    with:
      method: POST
      path: "/api/v1/certificate/callback"
      response_status: 200
      response_body: ${{ testdata.request_body }}
    returns:
      mock: { type: class, class: MockInstance }
      full_mock_url: { type: string }

steps:
  - id: send_request
    uses: connector/dataplane/http_request
    name: Send certificate request to SUT
    with:
      method: POST
      dataplane_url: ${{ env.sut_dsp_url }}
      path: "/certificate/request"
      headers:
        Content-Type: "application/json"
      body: ${{ env.testdata.request_body }}
    returns:
      status_code: { type: integer, class: StatusCode }
    validate:
      - uses: validate/assert
        with: { input: status_code, operator: equals, value: 200 }

  - id: wait_callback
    uses: mock/wait/http_request
    name: Wait for SUT to call back
    with:
      mock: ${{ setup.mock_response.mock }}
      timeout_s: ${{ env.sut_response_timeout }}
    returns:
      request_body: { type: object, class: ResponseBody }
    validate:
      - uses: validate/assert
        with: { input: request_body, operator: not_null }

teardown:
  - id: cleanup_mock
    uses: mock/cleanup
    name: Remove mock endpoint
    with:
      mock: ${{ setup.mock_response.mock }}
```

## Step 4 — Understanding Variable References

All references use the `${{ }}` expression syntax:

| Pattern | Resolves to |
|---------|-------------|
| `${{ env.my_var }}` | TCK-level variable |
| `${{ env.services.name.output }}` | Service output |
| `${{ env.testdata.name }}` | Testdata file content |
| `${{ env.schemas.name }}` | Schema file content |
| `${{ metadata.dataspace_version }}` | TCK metadata field |
| `${{ setup.id.output }}` | Setup step output (within same test) |
| `${{ steps.id.output }}` | Previous step output (within same test) |

## Step 5 — Assertions

Every step can include a `validate:` block with one or more assertions. Each
entry may carry an optional `name:` — nothing in the engine reads it, but the
run report calls the check by it, so four `validate/assert` entries on one step
say which requirement each one covers instead of printing the same id four
times:

```yaml
validate:
  - uses: validate/assert
    name: the request was accepted        # optional
    with: { input: status_code, operator: equals, value: 200 }
  - uses: validate/assert
    with: { input: response_body, operator: not_null }
  - uses: validate/assert
    with: { input: datasets, operator: contains, value: "expected-item" }
```

Available operators: `equals`, `not_null`, `contains`, `not_equals`, `greater_than`, `less_than`, `matches` (regex).

## Step 6 — Validate Against a Schema, Then Extract a Nested Value

A common pattern: query a response, validate its whole shape against a JSON
Schema declared in `env.schemas`, then pull a specific nested value out for a
follow-up request. The steps below query a digital twin, confirm it conforms,
and extract the data-plane `href` of its `SUBMODEL-VALUE-3.1` endpoint.

```yaml
steps:
  # 1. Query the twin and keep the whole body
  - id: query_dt
    uses: get_shell_descriptor
    with:
      aas_identifier: "${{ env.twin_id }}"
    returns:
      response_body:
        type: object
        class: ResponseBody

  # 2. Validate the whole descriptor against a schema from env.schemas
  - id: validate_dt
    uses: validate/schema
    with:
      input: "${{ steps.query_dt.response_body }}"
      schema: "${{ env.schemas.shell_descriptor_schema }}"

  # 3. Extract the SUBMODEL-VALUE-3.1 endpoint's subprotocolBody.
  #    The predicate steps over the descriptor/endpoint arrays without indices,
  #    so it does not depend on ordering or on any idShort.
  - id: get_subprotocol_body
    uses: json_path_extract
    with:
      source: response_body
      path: "submodelDescriptors.endpoints[interface='SUBMODEL-VALUE-3.1'].protocolInformation.subprotocolBody"
      store_in_variable: subprotocol_body

  # 4. The subprotocolBody is "dspEndpoint=...;id=..." — pull just the asset id
  - id: get_asset_id
    uses: util/parse_kv
    with:
      input: "${{ subprotocol_body }}"
      select: id
      store_in_variable: edc_asset_id
```

- `validate/schema` fails the step (and the test) when the body does not match
  the schema, reporting the offending field paths.
- The quotes around `'SUBMODEL-VALUE-3.1'` are required — predicate values that
  contain `.`, `;`, or `#` must be quoted.
- `util/parse_kv` splits each pair on the first `=` only, so a `dspEndpoint`
  value containing its own query string survives intact.

See the [Cheat Sheet](../reference/syntax/cheat-sheet.md#extracting-values-json_path_extract)
for the full predicate syntax and utility-step options.

## Key Differences from v0

| v0 (obsolete) | v1-alpha (current) |
|---------------|-------------------|
| `${variable}` | `${{ env.variable }}` |
| `type: connector_service` | `uses: service/connector_service` |
| `params:` | `with:` |
| `shared_variables:` | `env.variables:` (simple key-value) |
| `!include file.yaml` | `tests: [file.yaml]` (list of paths) |
| `CONNECTOR_PROVIDER` | `env.services.name.connector_service` |
| `cleanup:` | `teardown:` |
| `type: CONTAINS` (assertion) | `operator: contains` |
| No manifest kind | `kind: tck` / `kind: test` |
