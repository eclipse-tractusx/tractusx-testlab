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

# YAML Syntax Cheat Sheet

Quick reference for the TestLab YAML test authoring format (`testlab: v1-alpha`).

---

## Document Types

| Kind | Purpose | Required key |
|------|---------|--------------|
| `kind: tck` | Test Collection Kit — groups tests with shared config | `tests:` |
| `kind: test` | Single test case | `steps:` (≥1 step) |

## TCK File Structure (index.yaml)

Only TCKs declare `env:`. Tests inherit it via `namespace:` matching.

```yaml
kind: tck
testlab: v1-alpha
id: my-tck
namespace: my-namespace-v1.0
metadata:
  name: "My TCK"
  version: "1.0.0"
  description: "What this TCK certifies"
  dataspace_version: saturn
  standards:
    - id: CX-0135
      version: v3.1.0
  tags: [tag1, tag2]
env:
  variables:
    provider_url: ""
    timeout_seconds: 300
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
    my_schema:
      file: my_schema.json
  testdata:
    sample_body:
      file: sample_body.json
tests:
  - tests/test_one.yaml
  - tests/test_two.yaml
```

---

## Test File Structure

Tests have NO `env:` block — they inherit everything from their parent TCK.

```yaml
kind: test
testlab: v1-alpha
id: my-test
namespace: my-namespace-v1.0
metadata:
  name: "My Test"
  version: "1.0"
  description: "What this test validates"
setup: []
steps: []
teardown: []
```

---

## Step Structure

```yaml
- id: step_id
  uses: category/action
  name: "Human-readable label"
  with:
    param: value
    ref_param: ${{ steps.other_step.output }}
  returns:
    output_name:
      type: string
      class: SemanticClass
  validate:
    - uses: validate/assert
      with: { input: output_name, operator: not_null }
  if: "${{ success() }}"
  on_failure: abort
  timeout_s: 30.0
```

**Field order:** `id` → `uses` → `name` → `with` → `returns` → `validate` → `if` → `on_failure` → `timeout_s`

---

## Variable References (`${{ ... }}`)

| Pattern | Resolves to |
|---------|-------------|
| `${{ env.provider_url }}` | TCK environment variable |
| `${{ env.services.name.output }}` | Service output (e.g., `.connector_service`) |
| `${{ env.testdata.data_name }}` | Testdata file content |
| `${{ env.schemas.schema_name }}` | Schema file content |
| `${{ steps.step_id.output_name }}` | Output from a step in `steps:` |
| `${{ setup.step_id.output_name }}` | Output from a step in `setup:` |
| `${{ env.var_id.field }}` | Output field of a typed `env.variables` definition (e.g., `.policy`) |
| `${{ metadata.dataspace_version }}` | Metadata field value |
| `${{ testdata.data_name }}` | Shorthand for testdata reference |

---

## Conditionals (`if:`)

| Expression | Meaning |
|------------|---------|
| `${{ success() }}` | All previous steps passed (default) |
| `${{ failure() }}` | At least one previous step failed |
| `${{ always() }}` | Always executes |
| `${{ steps.step_id.outcome == 'success' }}` | Specific step outcome check |
| `${{ steps.step_id.outcome == 'failure' }}` | Specific step failed |
| `${{ steps.step_id.outcome == 'skipped' }}` | Specific step was skipped |

---

## Returns Block

```yaml
returns:
  output_name:
    type: string          # string | integer | object | array | boolean
    class: AssetId        # Semantic class (for type filtering)
```

**Common classes:** `AssetId`, `PolicyId`, `AgreementId`, `AuthToken`, `StatusCode`, `ResponseBody`, `ResponseHeaders`, `Uuid`, `Url`, `Bpn`, `ConnectorService`, `DataplaneUrl`, `MockInstance`, `Policy`, `String`

---

## Validate Block

Assertions reference the step's **own output names** directly (not `${{ }}` for local outputs):

```yaml
validate:
  - uses: validate/assert
    with:
      input: status_code
      operator: equals
      value: 200
  - uses: validate/assert
    with:
      input: "${{ steps.other_step.output }}"  # cross-step refs use ${{ }}
      operator: not_null
```

**Operators:**

| Operator | Description |
|----------|-------------|
| `equals` | Exact match |
| `not_equals` | Not equal |
| `not_null` | Value is not null |
| `not_empty` | Value is not empty |
| `contains` | Contains substring/element |
| `not_contains` | Does not contain |
| `regex` | Matches regular expression |
| `status_code` | HTTP status code match |
| `greater_than` | Numeric > |
| `less_than` | Numeric < |
| `greater_or_equal` | Numeric ≥ |
| `less_or_equal` | Numeric ≤ |
| `between` | Numeric range (inclusive) |

### JSON Schema Validation (`validate/schema`)

`validate/schema` validates a value against a full [JSON Schema](https://json-schema.org)
document — distinct from the scalar operators above, which compare single values.
The `schema` is normally a reference to a file declared in the TCK `env.schemas`
block; the step fails (marking the step FAILED) when the payload does not conform,
reporting the offending field paths.

```yaml
- id: validate_twin
  uses: validate/schema
  with:
    input: "${{ steps.query_dt.response_body }}"     # dict, list, or JSON string
    schema: "${{ env.schemas.shell_descriptor_schema }}"
```

An inline schema object is also accepted — useful for a one-off existence check,
e.g. asserting an array `contains` an element with a given field:

```yaml
- id: has_submodel_value_endpoint
  uses: validate/schema
  with:
    input: "${{ steps.query_dt.response_body }}"
    schema:
      type: object
      required: [submodelDescriptors]
      properties:
        submodelDescriptors:
          type: array
          contains:
            type: object
            properties:
              endpoints:
                type: array
                contains:
                  properties:
                    interface: { const: SUBMODEL-VALUE-3.1 }
```

---

## Extracting Values (`json_path_extract`)

`json_path_extract` reads a value out of a dict/list using a dot-separated path,
storing it in a variable for later steps.

```yaml
- id: get_asset_id
  uses: json_path_extract
  with:
    source: response_body        # variable NAME, or a ${{ }} expression
    path: "datasets.0.id"        # dot path; numeric segments index lists
    store_in_variable: asset_id  # optional; step output is the value either way
```

- **`source`** — either the *name* of a context variable (`response_body`), or a
  `${{ }}` expression that resolves to the data itself
  (`"${{ steps.query.response_body }}"`). Both forms work.
- **`path`** — dot-separated. Numeric segments index into lists (`endpoints.0.href`).

**Predicate filters** — select the first list element whose field matches a value,
instead of relying on a positional index:

| Path | Selects |
|------|---------|
| `items[id=abc].value` | first `items` element with `id == abc` |
| `endpoints[interface='SUBMODEL-VALUE-3.1']` | quote values that contain `.`, `;`, `#`, etc. |
| `descriptors.endpoints[interface='…']` | steps over an intermediate array — no index needed |
| `descriptors[endpoints.interface='…'].id` | select by a **nested** field (dotted predicate key) |

Quote a predicate value (`'…'`) when it contains dots or other separators —
interface names and semantic IDs always need quoting. A predicate that matches
nothing raises a clear error rather than returning a wrong value.

---

## Utility Steps

**`util/parse_kv`** — parse a delimited `key=value` string (e.g. an EDC
`subprotocolBody`) into a dict, or select one key. Each pair is split on the
**first** `=` only, so a value may itself contain `=` (a URL query string, base64).

```yaml
- id: get_edc_asset_id
  uses: util/parse_kv
  with:
    input: "${{ subprotocol_body }}"   # "dspEndpoint=https://…;id=urn:uuid:1234"
    select: id                          # omit to return the whole dict
    store_in_variable: edc_asset_id
    # pair_separator: ";"   (default)
    # kv_separator: "="     (default)
```

**`util/base64`** — encode or decode a string with base64 / base64url. The
AAS DTR requires an `aas_identifier` to be **base64url**-encoded before it goes
in a request path, so `url_safe: true` is the common case. Decoding restores
padding automatically, so an unpadded value round-trips without extra `=`.

```yaml
- id: encode_aas_id
  uses: util/base64
  with:
    input: "${{ env.variables.twin_id }}"   # "urn:uuid:1234" or a URL
    mode: encode                             # encode (default) | decode
    url_safe: true                           # -/_ instead of +//; needed for DTR
    strip_padding: false                     # drop trailing '=' when encoding
    store_in_variable: aas_identifier_b64
```

**`util/log`** — echo a resolved value to stdout and the run log while authoring.
Asserts nothing and always passes; remove once a test is finalised.

```yaml
- id: show_href
  uses: util/log
  with:
    message: SUBMODEL-VALUE-3.1 href
    value: "${{ submodel_value_href }}"
```

---

## Complex Variables (TCK only)

Typed variables in `env.variables` cover everything a test needs before its steps
run: runtime inputs, generated values, and reusable access policies. Declare each
one once and reference it via `${{ env.<id>.<field> }}`.

```yaml
env:
  variables:
    # Runtime input collected from the SUT operator
    - id: sut_dsp_url
      uses: variable/type/string
      name: SUT DSP Endpoint URL
      with:
        source: input
      returns:
        value:
          type: string
          class: Url
          placeholder: "https://connector.example.com/api/dsp"

    # Constant value with a default
    - id: sut_response_timeout
      uses: variable/type/integer
      with:
        value: 300
      returns:
        value:
          type: integer

    # Reusable access policy, referenced wherever a step needs it
    - id: usage_policy
      uses: config/connector/policy
      name: Required usage policy
      with:
        value:
          permissions:
            - action: use
              constraints:
                and:
                  - left_operand: UsagePurpose
                    operator: isAnyOf
                    right_operand: "cx.ccm.base:1"
      returns:
        policy:
          type: object
          class: Policy
```

**Reference in tests:** `${{ env.sut_dsp_url.value }}`, `${{ env.usage_policy.policy }}`.

---

## Failure Policies (`on_failure:`)

| Policy | Behavior |
|--------|----------|
| `abort` | Stop immediately, run teardown (default) |
| `continue` | Log warning, proceed to next step |
| `skip_rest` | Skip remaining steps, run teardown |


## Common `uses:` Handlers

| Prefix | Examples |
|--------|----------|
| `mock/` | `mock/api`, `mock/wait/http_request` |
| `connector/` | `connector/pull_data_filtered`, `connector/create_asset`, `connector/health_check` |
| `util/` | `util/generate_uuid`, `util/log`, `util/parse_kv`, `util/base64` |
| `validate/` | `validate/assert`, `validate/field`, `validate/schema` |
| `variable/` | `variable/type/string`, `variable/type/integer`, `variable/type/boolean` |
| `config/` | `config/connector/policy` |
| `service/` | `service/connector_service` |
| _(no prefix)_ | `json_path_extract` |

See [Extracting Values](#extracting-values-json_path_extract) and
[Utility Steps](#utility-steps) below for the extraction and helper handlers.


## Dataspace Versions

| Version | EDC Compatibility | Protocol |
|---------|-------------------|----------|
| `saturn` | EDC v0.11+ | DSP 2025-1 |
| `jupiter` | EDC v0.8–0.10 | Legacy DSP |

Set in `metadata.dataspace_version` or per-service via `with.dataspace_version`.


## Variable Resolution Priority

1. **Runtime variables** — CLI `--var` flags or API input
2. **TCK environment** — `env.variables` in the TCK file
3. **Step outputs** — resolved at execution time

