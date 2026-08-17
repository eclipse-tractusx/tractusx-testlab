# TCK Syntax Reference — `v1-alpha`

**Companion to [ADR-0001](./ADR-0001-tck-declarative-syntax.md).**
Audience: TCK authors (Expert Groups, TCK Developers) and Engine implementers.

### Notation used in this document

| Marker | Meaning |
|---|---|
| **[SPEC]** | Specified in the Test Suite Development presentation (2026-07-26). Normative. |
| **[OBS]** | Observed in the worked `certificate-management-tck` example in the deck, but not written out in the field-by-field slides. Treated as normative; flagged so it can be confirmed. |
| **[PROP]** | Proposed here to close a gap. **Not yet ratified** — see ADR-0001 §2 D10 and §6. |

Field tables use: `R` = required, `O` = optional.

---

## 1. Package Layout

**[SPEC]** An uncompiled TCK is a directory. The Test Suite Frontend generates it when building a TCK; it can
also be written by hand.

```
certificate-management-v2.0/
├── index.yaml                      # TCK manifest — input to compilation
├── tests/                          # one YAML file per test case
│   ├── catalog_policy_validation.yaml
│   ├── request_certificate.yaml
│   ├── validate_payload.yaml
│   ├── push_certificate.yaml
│   ├── available_notification.yaml
│   ├── send_feedback.yaml
│   ├── expose_testlab_asset.yaml
│   ├── certificate_asset_validation.yaml
│   └── error_handling.yaml
├── testdata/                       # payloads/fixtures — any format, not only JSON
│   ├── request_certificate_body.json
│   ├── push_certificate_body.json
│   ├── send_feedback_body.json
│   ├── available_notification_body.json
│   ├── expose_available_notification_body.json
│   ├── certificate_available_response.json
│   ├── expose_certificate_data_response.json
│   └── error_unknown_cert_type_body.json
└── schemas/                        # JSON Schemas for request/response validation
    ├── bpc-v3.1.0.json
    └── business_partner_certificate_schema.json
```

| Path | Contents |
|---|---|
| `index.yaml` | Manifest: metadata, dataspace + infrastructure requirements, environment config, ordered test list. |
| `tests/` | Test case declarations imported by `index.yaml`. |
| `testdata/` | Data usable across tests. **Does not need to be JSON** — hence the `type:` field on each entry. |
| `schemas/` | JSON Schemas used to validate requests and responses. |

**Compilation** produces a single `.tck` archive, optimised for execution, with optional encryption.

### Naming conventions **[PROP]**

- Directory: `<standard-short-name>-v<tck-version>` (e.g. `certificate-management-v2.0`).
- Test files: `snake_case.yaml`, named after the behaviour tested, not the sequence number — order lives in
  `index.yaml`, so renumbering never touches filenames.
- Test data / schema files: `snake_case.json`; include the model version where one exists
  (`business_partner_certificate_schema-v3.0.1.json`).

---

## 2. Common Header

**[SPEC]** Every declaration file begins with the same two fields. A parser reads them first and only then
decides how to interpret the rest of the document.

```yaml
kind: tck          # or: test
syntax: v1-alpha
```

| Field | R/O | Values | Notes |
|---|---|---|---|
| `kind` | R | `tck` \| `test` | Fixed. Used in every declaration file so the parser knows how to read it. |
| `syntax` | R | `v1-alpha` | Engine/Test Lab library syntax version, i.e. which technical capabilities are available. Should not change often. |

> ⚠️ **Known inconsistency [PROP-P6].** The `index.yaml` screenshot on slide 17 shows `testlab: v1-alpha` and a
> top-level `namespace: ccm-v0.0.1`; the field specification on slide 18 shows `syntax: v1-alpha` and no
> manifest-level `namespace`. **This document treats slide 18 as normative**: the key is `syntax:` everywhere,
> and `namespace:` appears **only in test files**. Confirm before freezing `v1-alpha`.

---

## 3. `index.yaml` — the TCK Manifest

Order of top-level blocks: header → `metadata` → `dataspace` → `infrastructure` → `env` → `tests`.

### 3.1 Header **[SPEC]**

```yaml
kind: tck
syntax: v1-alpha

id: certificate-management-tck-v0.0.1
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | Descriptive ID of the TCK. Referenced by every test file's `namespace`, and forms the first segment of every event `id`. **[PROP]** `^[a-z0-9]([a-z0-9-]*[a-z0-9])?$`, globally unique within the Catena-X TCK repository. |

### 3.2 `metadata` **[SPEC]**

```yaml
metadata:
  name: "Certificate Management TCK"
  version: "v0.0.1"
  description: >
    Validate CCMAPI certificate management workflow per CX-0135 v3.1.0:
    (1) Request certificate from provider
    (2) Validate certificate payload against schema
    (3) Await provider feedback callback
    (4) Send feedback notification and await acknowledgment
    (5) Expose TestLab as provider and verify SUT consumer behavior
  authors:
    - name: Certificate Management Expert Group
      email: ccm-eg@catena-x.net
      company: Catena-X Automotive Network e.V.
  copyright_holders:
    - "2026 Catena-X Automotive Network e.V."
  license: LicenseRef-Proprietary
  standards:
    - id: CX-0135
      version: v3.1.0
  tags:
    - CCM
```

| Field | R/O | Type | Notes |
|---|---|---|---|
| `name` | R | string | Label shown to the user. |
| `version` | R | string | For version control. Quote it — unquoted `1.0` parses as a float. |
| `description` | O | string | Detailed text. Use `>` folded scalars for multi-line. |
| `authors[]` | R | list | Important for having a contact person/group. |
| `authors[].name` | R | string | Person or expert group. |
| `authors[].email` | R | string | Contact address. |
| `authors[].company` | R | string | Organisation. |
| `copyright_holders[]` | R | list\<string\> | Format `[YEAR] [COMPANY]`. |
| `license` | R | string | SPDX identifier or `LicenseRef-*` (e.g. `LicenseRef-Proprietary`). |
| `standards[]` | R | list | **The standards this TCK certifies against.** Drives the conformity report. |
| `standards[].id` | R | string | e.g. `CX-0135`. |
| `standards[].version` | R | string | e.g. `v3.1.0`. |
| `tags[]` | O | list\<string\> | Used for search in the Frontend. |

### 3.3 `dataspace` **[SPEC]**

```yaml
dataspace:
  ecosystem: Catena-X
  version: saturn
```

| Field | R/O | Notes |
|---|---|---|
| `ecosystem` | R | Reserved attribute allowing the same testing framework to serve other dataspaces. Currently `Catena-X`. |
| `version` | R | **Mandatory** — attaches the report to the version of the dataspace tested (e.g. `saturn`, `neptune`). |

### 3.4 `infrastructure` **[SPEC]**

Declares what must exist on each side for the TCK to be runnable. Verified during the **Boot** phase, before
any test executes.

```yaml
infrastructure:
  engine:                      # what the Test Suite backend must provide
    connector:
      required: true
      standard:
        id: CX-0018
        version: v4.2.0
    submodel_server:           # engine-only — where provider payloads are uploaded
      required: true
  sut:                         # System Under Test — the Service Provider's side
    connector:
      required: true
      standard:
        id: CX-0018
        version: v4.2.0
    dtr:
      required: true
      standard:
        id: CX-0002
        version: v1.0.5
```

| Field | R/O | Notes |
|---|---|---|
| `engine` | R | Requirements on the Test Suite backend. Important for setting up the backend's "EDC clients". |
| `sut` | R | Requirements on the System Under Test. |
| `<side>.connector` | R | EDC requirement. |
| `<side>.dtr` | O | Digital Twin Registry requirement — optional per the deck. |
| `engine.submodel_server` | O | Backend the engine uploads provider submodel payloads to. Engine-only: a test never names a server of its own. |
| `*.required` | R | bool. |
| `*.standard` | O | Single `{id, version}` the component must comply with. One capability certifies one standard; the report carries that pair. `version` inherits `dataspace.version` when omitted. |

**[PROP]** Component keys are a closed vocabulary per `syntax` version, and the vocabulary is the
engine's binding model — the two sides are asymmetric, so each side accepts only what it can bind.
`v1-alpha`: `engine` → `connector`, `dtr`, `submodel_server`; `sut` → `connector`, `dtr`. Adding a
component type (e.g. `bpn_did_resolver`) is a `syntax` bump.

### 3.5 `env` — Environmental Configuration **[SPEC]**

Data to be used / imported / generated at runtime. Three sub-blocks: `variables`, `schemas`, `testdata`.

#### 3.5.1 `env.variables`

Array of variable configurations resolved at runtime. Each entry reuses the **step syntax** (`uses` / `with` /
`returns`), which is why a variable can be an input prompt, a generated value, or a literal config object.

```yaml
env:
  variables:
    - id: sut_counter_party_id
      uses: variable/type/string
      with:
        source: input
      returns:
        value:
          type: string

    - id: sut_counter_party_address
      uses: variable/type/string
      with:
        source: input
      returns:
        value:
          type: string

    - id: ccm_usage_policy
      uses: config/connector/policy
      name: Required CCMAPI Usage Policy
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
                  - left_operand: FrameworkAgreement
                    operator: eq
                    right_operand: "DataExchangeGovernance:1.0"
      returns:
        policy:
          type: object
          class: Policy
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | Variable key. Used as the runtime identifier: `${{ env.<id> }}`. |
| `uses` | R | Variable "definition"/type — same concept as a step definition. More types are available and the set is extensible. |
| `name` | O | **[OBS]** Human-readable label; shown to the user when `source: input`. |
| `with` | R | Configuration for the definition. |
| `with.source` | R | `input` \| `generated` \| `value`. See below. |
| `with.value` | O | Present when `source: value`. The literal payload. |
| `returns` | R | Declares the outputs of this variable type. Key names are **fixed per definition type** (e.g. `value` for `variable/type/*`, `policy` for `config/connector/policy`). |
| `returns.<key>.type` | R | `string` \| `object` \| `number` \| `array` \| `bool`. |
| `returns.<key>.class` | O | Semantic type (e.g. `Policy`, `AuthToken`, `DataplaneUrl`). |

**`with.source` semantics [SPEC]:**

| Value | Meaning | Resolution point |
|---|---|---|
| `input` | The Service Provider supplies it in the Configuration phase (BPN, counter-party address/ID, credentials). | Before Boot; emits `tck.variable.input.required` / `tck.variable.input.received`. |
| `generated` | The Engine generates it (e.g. a random asset ID). | During variable resolution; the value is shown to the user as configuration to apply to their SUT. |
| `value` | A literal declared in the manifest (policies, fixed config). | Statically at load. |

**Variable definition types [OBS/PROP]** — `v1-alpha` baseline:

| `uses` | Purpose | `returns` keys |
|---|---|---|
| `variable/type/string` | Scalar string variable | `value` |
| `variable/type/number` **[PROP]** | Scalar number | `value` |
| `variable/type/bool` **[PROP]** | Boolean | `value` |
| `variable/type/object` **[PROP]** | Structured object | `value` |
| `config/connector/policy` | An ODRL policy used for provisioning/catalog/negotiation | `policy` |
| `config/connector/asset` | An asset definition used for provisioning | `asset` |

Policies and assets are **never inlined in a step**. Each is declared once here and passed to every
step that needs it as a single input — `policy` on the consumer side
(`connector/consumer/pull_data_filtered`) and both of them on the provider side:

```yaml
env:
  variables:
    - id: ccm_api_asset
      uses: config/connector/asset
      name: CCMAPI Asset
      with:
        source: value
        value:
          name: CCMAPI Notification Asset
          base_url: "https://backend.example.com/ccm"
          properties:
            dct:type:
              "@id": "https://w3id.org/catenax/taxonomy#CCMAPI"
            cx-common:version: "3.0"
      returns:
        asset:
          type: object
          class: Asset

# in a test
- id: create_asset
  uses: connector/provider/create_asset
  with:
    asset: "${{ env.ccm_api_asset.asset }}"

- id: create_policy
  uses: connector/provider/create_policy
  with:
    policy: "${{ env.ccm_usage_policy.policy }}"
```

#### 3.5.2 `env.schemas` **[SPEC]**

List of JSON Schemas used across the tests in this TCK.

```yaml
  schemas:
    - id: certificate_schema
      source: business_partner_certificate_schema-v3.0.1.json
      # digest: "sha256:…"        # [PROP-P7]
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | Runtime identifier: `${{ env.schemas.<id> }}`. |
| `source` | R | Filename in `/schemas` where the content is located. |
| `digest` | O **[PROP]** | `sha256:<hex>` integrity check recorded by the compiler. |

#### 3.5.3 `env.testdata` **[SPEC]**

List of test data usable across the tests in this TCK.

```yaml
  testdata:
    - id: available_notification_body
      source: available_notification_body.json
      type: application/json
    - id: certificate_available_response
      source: certificate_available_response.json
      type: application/json
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | Runtime identifier: `${{ testdata.<id> }}`. |
| `source` | R | Filename in `/testdata`. |
| `type` | R | Media type. **Exists because test data does not need to be JSON.** |

### 3.6 `tests` — Execution Order **[SPEC]**

```yaml
tests:
  - id: catalog_policy_validation.yaml
    name: Validate CX-0135 catalog policy constraints
  - id: request_certificate.yaml
    name: Request a certificate via CCMAPI
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | **Name of the test file** in `/tests`. |
| `name` | R | Short name of the test, shown in the Preview and Mission Control views. |

**Execution semantics [SPEC]:**

- Tests are executed **in cascade / sequentially**, in array order.
- **Each test must be independent from every other test.** If one fails, the rest can still succeed — this is
  what lets a Service Provider see all non-conformities in a single run.
- Consequence: a test must never consume another test's `returns`. Anything shared belongs in `env`.
- The user may explicitly skip failed tests in the Mission Control view (emits `tck.test.skipped`).

---

## 4. Test File Syntax (`/tests/*.yaml`)

### 4.1 Header and Metadata **[SPEC]**

Very similar to the TCK declaration, with fewer fields because most of the context lives in the manifest.

```yaml
kind: test
syntax: v1-alpha

namespace: certificate-management-tck-v0.0.1
id: send-feedback-notification

metadata:
  name: "Send Feedback Notification"
  version: "1.0.0"
  description: >
    Send a CX-0135 CCMAPI status notification to the provider via EDC dataplane
    and await the provider's acknowledgment on a TestLab mock endpoint.
```

| Field | R/O | Notes |
|---|---|---|
| `kind` | R | `test`. |
| `syntax` | R | Must match the manifest's `syntax`. |
| `namespace` | R | **Must be the same `id` as the TCK manifest.** Binds the test to its TCK. |
| `id` | R | Descriptive ID of the test. Second segment of every event `id` this test emits. |
| `metadata.name` | R | Label for the user. |
| `metadata.version` | R | For version control. |
| `metadata.description` | O | Detailed text. |

### 4.2 Phases **[SPEC]**

Three phases, inspired by JUnit and PyTest. Each **contains a list of technical capability test steps /
building blocks**.

```yaml
setup:        # list of steps — same syntax as execution, WITHOUT `validate`
execution:    # list of steps — WITH `validate`
teardown:     # list of steps — same syntax as execution, WITHOUT `validate`
```

| Phase | R/O | `validate` allowed | Purpose |
|---|---|---|---|
| `setup` | O | ❌ | Pre-steps establishing preconditions. Runs START → PRE-STEP 1..N → END. |
| `execution` | R | ✅ | The test steps and their validations. |
| `teardown` | O | ❌ | After-steps, e.g. cleanup. |

**Execution control flow [SPEC]:**

```
START → TEST STEP 1 → [VALIDATION 1..n all pass] → TEST STEP 2 → [VALIDATION 2 FAILS]
                                                                        ↓
                                              TEST STEP N is skipped; test ABORTED → FAILED
```

> Continues to the next step **only if all validations passed**. If a validation fails, the test is aborted and
> then fails.

**[PROP]** `teardown` runs regardless of whether `execution` passed, failed or aborted — otherwise a failed
test leaves assets behind in a live dataspace. Teardown failures are reported as warnings and do not change the
test verdict.

> ⚠️ **[SPEC]** *Steps / building blocks are **not** meant to be usable in any phase.* Each capability declares
> which phases it is valid in; the compiler rejects a step used in a phase it does not support. **[PROP]** This
> is expressed as a `phases:` attribute on the `@step` annotation and published in the capability catalogue.

---

## 5. Step / Building Block Syntax

**[SPEC]** Based on GitHub Actions syntax. `execution` is an array of steps executed in sequential order.

### 5.1 Anatomy

```yaml
execution:
  - id: <unique-key-in-test-for-step>
    uses: <function-key mapped to a backend function with an @step annotation>
    name: <text description of what is being executed/tested>
    with:
      input-key-1: <input configuration data from standard>
      input-key-2: <input configuration data from standard>   # can be taken from a variable
      input-key-n: <…>
    returns:
      return-key-1:
        type: <string | object | number | bool | array>
        class: <semantic type>        # optional
      return-key-n:
        type: <data type>
        # …
    validate:
      - uses: <validation-function-key>
        with:
          input: <a variable which was returned and needs to be validated>
          # … more params, depending on the validation function
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | Unique within the test. Used to reference this step's outputs and as the third segment of event IDs. |
| `uses` | R | Capability key, mapped to a backend function carrying the `@step` annotation. |
| `name` | R | Text description of what is being executed/tested. Shown live in Mission Control and in the report. |
| `with` | O | Input parameters of the function named in `uses` — GitHub Actions style. Values may come from variables. |
| `returns` | O | Declares which outputs this step generates, so the user configuring the steps (and the compiler) knows what is available downstream. |
| `returns.<key>.type` | R | `string` \| `object` \| `number` \| `bool` \| `array`. |
| `returns.<key>.class` | O | Semantic type for the return (e.g. `AuthToken`, `DataplaneUrl`, `StatusCode`, `ResponseBody`, `Policy`). |
| `validate` | R in `execution` | Array of validations. Same syntax as a step, **but with no return**. |
| `validate[].uses` | R | Validation function key. |
| `validate[].with` | R | Inputs depend on the selected validation function; they validate the step's `returns` variables. |
| `cac` | O **[PROP]** | CAC identifiers this step/validation verifies. See §9.1. |
| `if` | O **[PROP]** | Expression guarding execution of the step or validation. See §9.2. |
| `expects` | O **[PROP]** | `pass` (default) \| `fail` — negative-test support. See §9.3. |

### 5.2 Expression / Reference Syntax **[OBS]**

Values are interpolated with `${{ … }}`.

| Form | Resolves to | Example |
|---|---|---|
| `${{ env.<var-id>.<return-key> }}` | A manifest variable's output | `${{ env.sut_connector.counter_party_address }}` |
| `${{ env.<var-id>.policy }}` | A policy variable | `${{ env.ccm_usage_policy.policy }}` |
| `${{ env.schemas.<schema-id> }}` | A declared JSON Schema | `${{ env.schemas.certificate_schema }}` |
| `${{ testdata.<testdata-id> }}` | A declared test data file's content | `${{ testdata.send_feedback_body }}` |
| `${{ execution.<step-id>.<return-key> }}` | A prior step's declared return | `${{ execution.pull_notification_endpoint.edr_token }}` |
| `${{ setup.<step-id>.<return-key> }}` **[PROP]** | A setup step's return | `${{ setup.create_asset.asset_id }}` |

> ⚠️ **Second known inconsistency.** Slide 20 declares the input variables as `sut_counter_party_id` and
> `sut_counter_party_address` (each with a `value` return key), but slide 29 references them as
> `${{ env.sut_connector.counter_party_address }}` — i.e. a single `sut_connector` variable with
> `counter_party_*` return keys. **This document treats slide 20 as normative**: a variable is referenced as
> `env.<variable-id>.<return-key>`, so the correct form is `${{ env.sut_counter_party_address.value }}`.
> Alternatively, ratify a compound `variable/type/connector` definition returning `counter_party_id` and
> `counter_party_address` — which is arguably the better modelling. **Decide before freezing `v1-alpha`.**

Rules **[PROP]**:

- References resolve **only backwards** within the same test, plus `env` / `testdata` globally.
- Referencing a step in a later phase, a later step, or another test is a compile error.
- Whole-value references may be unquoted; embedded references must be quoted:
  `path: "/companycertificate/request"` vs `dataplane_url: "${{ execution.x.dataplane_url }}"`.

### 5.3 Capability Naming **[SPEC]**

```
<root-capability> [ / <module> [ / <sub-module> ] ] / <function>
```

Modularisation is optional; sub-modules are permitted.

| Key | Effect |
|---|---|
| `connector/provider/create_asset` | Creates an asset in the EDC you specify |
| `http/http_request` | Executes an HTTP request to a URL you configure |
| `mock/api` | Mocks an API HTTP response |
| `connector/consumer/pull_data_filtered` **[OBS]** | Finds an endpoint by catalog filter and obtains dataplane credentials (EDR) |
| `connector/dataplane/http_request` **[OBS]** | Calls an API on the provider via the dataplane |

**Backend binding [SPEC]** — a step key maps to an annotated class in the Engine:

```python
class CreateAssetParams(ServiceParams):
    """Input contract of ``connector/provider/create_asset``."""

    asset_id: str = Field(default="", description="ID to register the asset under.")
    base_url: str = Field(default="", description="Backend URL the asset points at.")


class CreateAssetOutput(StepPayload):
    """Output contract of ``connector/provider/create_asset``."""

    asset_id: str = Field(description="ID of the asset that now exists at the provider.")


@step("connector/provider/create_asset")
class CreateAssetStep(BaseStep[CreateAssetParams, CreateAssetOutput]):
    """Register an asset at the provider connector."""

    params_model = CreateAssetParams
    output_model = CreateAssetOutput

    async def execute(self, params: CreateAssetParams, context: "StepContext",
                      definition: StepDefinition) -> StepOutput[CreateAssetOutput]:
        provider = context.get_provider_service(params.service_name())
        url = f"{context.get_provider_base_url()}/v3/assets"
        result, http_status = _create_or_conflict(
            provider.create_asset, asset_id=params.asset_id, base_url=params.base_url,
        )
        return StepOutput(
            value=CreateAssetOutput(asset_id=params.asset_id),
            request=HttpRequest(method="POST", url=url, body=params.model_dump(mode="json")),
            response=HttpResponse(
                status_code=http_status,
                body={"asset_id": params.asset_id, **(result if isinstance(result, dict) else {})},
            ),
        )
```

Note that `StepOutput` carries the captured `request` and `response` — this is what populates the debug event
log (§8).

**Root capabilities, `v1-alpha` [PROP]** — reserved so authors can predict where a capability lives:

| Root | Scope |
|---|---|
| `connector` | EDC operations. Modules: `provider`, `consumer`, `dataplane`. |
| `http` | Generic HTTP. Escape hatch for anything not yet modelled. |
| `mock` | Mock server provisioning — the Engine acting as a counterparty the SUT calls. |
| `dtr` | Digital Twin Registry operations (CX-0002). |
| `dataspace` | Core/identity services (Keycloak, portal, BPN resolution). |
| `variable` / `config` | Manifest-only definitions (§3.5.1), not usable as test steps. |
| `validate` | Validation functions (§5.4). |
| `util` | Waits, polling, value extraction, formatting. |

### 5.4 Validation Functions

**[OBS]** Observed in the worked example:

| `uses` | `with` | Checks |
|---|---|---|
| `validate/assert` | `input`, `operator` | Simple assertion on a returned value. Example: `{ input: edr_token, operator: not_null }`. |
| `validate/field` | `input`, `path` (O), `operator`, `value` | Field-level check, optionally at a JSON path within the returned object. |
| `validate/schema` | `input`, `schema` | Validates a returned object against a declared JSON Schema. |

```yaml
validate:
  - uses: validate/assert
    with: { input: edr_token, operator: not_null }

  - uses: validate/field
    with: { input: status_code, operator: equals, value: 200 }

  - uses: validate/field
    with:
      input: response_body
      path: "header.messageId"
      operator: matches_regex
      value: "^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

  - uses: validate/schema
    with:
      input: response_body
      schema: "${{ env.schemas.certificate_schema }}"

  - uses: validate/field
    with:
      input: request_body
      path: "content.certificateStatus"
      operator: one_of
      value: ["RECEIVED", "ACCEPTED", "REJECTED"]
```

**Operator vocabulary [PROP]** — ratifying this closes ADR gap P4:

| Operator | Applies to | Meaning |
|---|---|---|
| `equals` / `not_equals` | any | Exact comparison |
| `not_null` / `is_null` | any | Presence |
| `contains` / `not_contains` | string, array | Containment |
| `one_of` / `none_of` | any | Membership in `value` (a list) |
| `matches_regex` | string | Regular expression match |
| `gt` / `gte` / `lt` / `lte` | number | Numeric comparison |
| `has_key` / `not_has_key` | object | Key presence at `path` |
| `length_equals` / `length_gt` / `length_lt` | string, array | Size |

---

## 6. Mapping CACs to Syntax

This is the core translation TCK authors perform. **[SPEC]** for the CAC model; **[PROP]** for the `cac:` and
conditional constructs used below.

### 6.1 The CAC sentence

```
WHEN  <test step / action>        ← may come from an Enablement Service (CX-0018, CX-0002),
                                    Industry Core, or be a generic action like "http request"
WITH  <test data>
IF    <condition>                 ← supports conditionals for negative tests
MUST  <assertion>                 ← repeatable; combinable with AND / OR
```

### 6.2 Translation table

| CAC element | Syntax construct |
|---|---|
| `WHEN` | The step: `uses:` + `name:` |
| `WITH` | `with:` inputs, sourced from `${{ testdata.* }}` and `${{ env.* }}` |
| `IF` | `if:` on a step or validation **[PROP §9.2]** |
| `MUST` | One `validate:` entry |
| `MUST … AND MUST …` | Multiple `validate:` entries (implicit AND), or `validate/all_of` when nested under an `IF` |
| `MUST … OR MUST …` | `validate/any_of` with a nested `validations:` list **[PROP §9.2]** |
| CAC identity | `cac:` on the step or validation **[PROP §9.1]** |
| JSON Schema as MUST | `validate/schema` |

### 6.3 Worked example

CAC as written by the Expert Group:

> **CAC CCM-014** — *WHEN* the consumer issues an HTTP request to `/certificatemanagement/request` via the
> dataplane *WITH* a valid certificate request body, the response *MUST* have status `200` *AND* the body
> *MUST* conform to the Business Partner Certificate schema v3.0.1. *IF* the provider reports `failed`, the
> status *MUST* be `503` *OR* the body *MUST* contain an error code of `SERVICE_UNAVAILABLE`.

As YAML:

```yaml
- id: send_status_notification
  uses: connector/dataplane/http_request
  name: Call CX-0135 request api on the provider via dataplane
  cac: ["CX-0135:v3.1.0:CAC-014"]              # [PROP]
  with:
    method: POST
    dataplane_url: "${{ execution.pull_notification_endpoint.dataplane_url }}"
    path: "/companycertificate/request"
    edr_token: "${{ execution.pull_notification_endpoint.edr_token }}"
    headers:
      Content-Type: "application/json"
    body: "${{ testdata.send_feedback_body }}"
  returns:
    status_code:
      type: integer
      class: StatusCode
    response_body:
      type: object
      class: ResponseBody
  validate:
    # MUST … AND MUST … → two sibling validations
    - uses: validate/field
      with: { input: status_code, operator: equals, value: 200 }
    - uses: validate/schema
      with:
        input: response_body
        schema: "${{ env.schemas.certificate_schema }}"

    # IF … MUST … OR MUST …  → guarded any_of                          [PROP]
    - uses: validate/any_of
      if: "${{ execution.send_status_notification.response_body.status == 'failed' }}"
      cac: ["CX-0135:v3.1.0:CAC-015"]
      with:
        validations:
          - uses: validate/field
            with: { input: status_code, operator: equals, value: 503 }
          - uses: validate/field
            with:
              input: response_body
              path: "error.code"
              operator: equals
              value: "SERVICE_UNAVAILABLE"
```

### 6.4 Two views, one CAC set **[SPEC]**

The same CACs must be reachable from both directions:

- **TCK-oriented view:** `STANDARD → TCK → TEST CASE → CAC → (WHEN/WITH/IF/MUST)`
- **Standard-oriented view:** `STANDARD → USE CASE + SEQUENCE DIAGRAM → CAC → (WHEN/WITH/IF/MUST)`

A TCK is *compliant* when every CAC derived from the standard's use cases and sequence diagrams is covered by
at least one test case, and every test case's assertions trace back to a CAC. **[PROP]** With `cac:` in place,
the compiler can produce a coverage matrix (CACs declared by the standard vs. CACs referenced by the TCK) and
warn on gaps.

---

## 7. Complete Worked Example

### `index.yaml`

```yaml
kind: tck
syntax: v1-alpha

id: certificate-management-tck-v0.0.1

metadata:
  name: "Certificate Management TCK"
  version: "v0.0.1"
  description: >
    Validate CCMAPI certificate management workflow per CX-0135 v3.1.0:
    (1) Request certificate from provider
    (2) Validate certificate payload against schema
    (3) Await provider feedback callback
    (4) Send feedback notification and await acknowledgment
    (5) Expose TestLab as provider and verify SUT consumer behavior
  authors:
    - name: Certificate Management Expert Group
      email: ccm-eg@catena-x.net
      company: Catena-X Automotive Network e.V.
  copyright_holders:
    - "2026 Catena-X Automotive Network e.V."
  license: LicenseRef-Proprietary
  standards:
    - id: CX-0135
      version: v3.1.0
  tags:
    - CCM

dataspace:
  ecosystem: Catena-X
  version: saturn

infrastructure:
  engine:
    connector:
      required: true
      standard:
        id: CX-0018
        version: v4.2.0
  sut:
    connector:
      required: true
      standard:
        id: CX-0018
        version: v4.2.0
    dtr:
      required: true
      standard:
        id: CX-0002
        version: v1.0.5

env:
  variables:
    - id: sut_counter_party_id
      uses: variable/type/string
      with:
        source: input
      returns:
        value:
          type: string
    - id: sut_counter_party_address
      uses: variable/type/string
      with:
        source: input
      returns:
        value:
          type: string
    - id: ccm_usage_policy
      uses: config/connector/policy
      name: Required CCMAPI Usage Policy
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
                  - left_operand: FrameworkAgreement
                    operator: eq
                    right_operand: "DataExchangeGovernance:1.0"
      returns:
        policy:
          type: object
          class: Policy

  schemas:
    - id: certificate_schema
      source: business_partner_certificate_schema-v3.0.1.json

  testdata:
    - id: available_notification_body
      source: available_notification_body.json
      type: application/json
    - id: certificate_available_response
      source: certificate_available_response.json
      type: application/json
    - id: send_feedback_body
      source: send_feedback_body.json
      type: application/json
    - id: error_unknown_cert_type_body
      source: error_unknown_cert_type_body.json
      type: application/json

tests:
  - id: catalog_policy_validation.yaml
    name: Validate CX-0135 catalog policy constraints
  - id: request_certificate.yaml
    name: Request a certificate via CCMAPI
  - id: send_feedback_notification.yaml
    name: Send a feedback notification and await acknowledgment
```

### `tests/send_feedback_notification.yaml`

```yaml
kind: test
syntax: v1-alpha

namespace: certificate-management-tck-v0.0.1
id: send-feedback-notification

metadata:
  name: "Send Feedback Notification"
  version: "1.0.0"
  description: >
    Send a CX-0135 CCMAPI status notification to the provider via EDC dataplane
    and await the provider's acknowledgment on a TestLab mock endpoint.

execution:
  - id: pull_notification_endpoint
    uses: connector/consumer/pull_data_filtered
    name: Find CCMAPI endpoint and obtain dataplane credentials
    with:
      counter_party_address: "${{ env.sut_counter_party_address.value }}"
      counter_party_id: "${{ env.sut_counter_party_id.value }}"
      policy: "${{ env.ccm_usage_policy.policy }}"
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CCMAPI"
        - operand_left: "http://purl.org/dc/terms/subject"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CompanyCertificateManagementNotificationApi"
        - operand_left: "https://w3id.org/catenax/ontology/common#version"
          operator: "="
          operand_right: "3.0"
    returns:
      edr_token:
        type: string
        class: AuthToken
      dataplane_url:
        type: string
        class: DataplaneUrl
    validate:
      - uses: validate/assert
        with: { input: edr_token, operator: not_null }
      - uses: validate/assert
        with: { input: dataplane_url, operator: not_null }

  - id: send_status_notification
    uses: connector/dataplane/http_request
    name: Call CX-0135 request api on the provider via dataplane
    with:
      method: POST
      dataplane_url: "${{ execution.pull_notification_endpoint.dataplane_url }}"
      path: "/companycertificate/request"
      edr_token: "${{ execution.pull_notification_endpoint.edr_token }}"
      headers:
        Content-Type: "application/json"
      body: "${{ testdata.send_feedback_body }}"
    returns:
      status_code:
        type: integer
        class: StatusCode
      response_body:
        type: object
        class: ResponseBody
    validate:
      - uses: validate/field
        with: { input: status_code, operator: equals, value: 200 }
      - uses: validate/field
        with:
          input: response_body
          path: "header.messageId"
          operator: matches_regex
          value: "^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
      - uses: validate/schema
        with:
          input: response_body
          schema: "${{ env.schemas.certificate_schema }}"
      - uses: validate/field
        with:
          input: request_body
          path: "content.certificateStatus"
          operator: one_of
          value: ["RECEIVED", "ACCEPTED", "REJECTED"]
```

---

## 8. Execution Logs — CloudEvents / JSONL

### 8.1 Purpose **[SPEC]**

One syntax, two purposes:

- **Live Execution Tracking** — streaming events from Backend to Frontend during execution, over **SSE**
  (Server-Sent Events, normal HTTP/1.1, fragmented/chunked response). The Frontend opens the connection by
  calling `/tck/execute` and can call another API to close it (stop/pause). On error, events may carry
  recommendations, error traces and information about what was tested.
- **Execution Tracing & Debug** — the same structure, stored, containing the HTTP requests and responses sent
  and received, so incompatibilities can be diagnosed precisely after the fact and a CAB can verify the report.

### 8.2 Envelope **[SPEC]**

Format: **JSONL** — one JSON object per line.

```json
{
  "specversion": "1.0",
  "id": "certificate-management-tck/request-certificate/send_request_1/tck.test.step.failed/f8c367508a7d",
  "source": "connector/consumer/pull_data_filtered",
  "type": "tck.test.step.failed",
  "time": "2026-05-28T18:31:17.801Z",
  "sequence": 25,
  "data": { }
}
```

| Field | Notes |
|---|---|
| `specversion` | CloudEvents attribute — `1.0`. |
| `id` | Always unique. Format: `<tck-id>/<test-id>/<step-id>/<event-type>/<hash-from-data>`. |
| `source` | The function used in the step, or the origin of the event (e.g. `testlab/player/lifecycle`, `config/connector/policy`). |
| `type` | Event type. |
| `time` | When the event was emitted. |
| `sequence` | Emission order within the log. |
| `data` | **Each event type has a different data structure** — varies with what needs to be stored. |

### 8.3 Event type registry **[OBS + PROP]**

Observed in the example log; ratifying this list closes ADR gap P5. Segments not applicable to an event are
omitted from the `id` (lifecycle events have no `<step-id>`).

| Type | Emitted when | Typical `source` |
|---|---|---|
| `tck.start` | TCK run begins | `testlab/player/lifecycle` |
| `tck.boot.start` | Boot phase begins | `testlab/player/boot` |
| `tck.boot.requirements` | Infrastructure requirements evaluated | `testlab/player/boot` |
| `tck.boot.binding.start` / `.passed` | Connector binding established | `testlab/player/boot` |
| `tck.boot.service.start` / `.ready` | Internal reusable client/service started | `testlab/player/boot` |
| `tck.boot.passed` | Boot succeeded; the TCK is runnable | `testlab/player/boot` |
| `tck.variable.input.required` | A `source: input` variable is awaited | `testlab/variables` |
| `tck.variable.input.received` | The user supplied it | `testlab/variables` |
| `tck.variable.resolve.start` / `tck.variable.resolved` | Variable resolution | `config/connector/policy`, `testlab/variables` |
| `tck.tests.planned` | Ordered test list fixed for this run | `testlab/player/lifecycle` |
| `tck.test.start` | Test case begins | `testlab/player/lifecycle` |
| `tck.test.step.start` | Step begins | the capability key |
| `tck.test.step.update` | Progress within a long-running step | the capability key |
| `tck.test.step.passed` / `.failed` | Step verdict after validations | the capability key |
| `tck.test.passed` / `.failed` / `.skipped` | Test case verdict | `testlab/player/lifecycle` |
| `tck.end` | TCK run complete | `testlab/player/lifecycle` |
| `tck.boot.failed` **[PROP]** | Boot preconditions not met | `testlab/player/boot` |
| `tck.test.teardown.start` / `.passed` / `.failed` **[PROP]** | Teardown phase | `testlab/player/lifecycle` |

**[PROP]** Adding an event type is a `syntax` version bump, because the Frontend, report generator and CAB
tooling all parse `type`.

### 8.4 `data` payload **[PROP]**

Minimum contents so the log is sufficient for both live UI and CAB verification:

```json
{
  "data": {
    "step": { "id": "send_request_1", "uses": "connector/dataplane/http_request",
              "name": "Call CX-0135 request api on the provider via dataplane" },
    "cac": ["CX-0135:v3.1.0:CAC-014"],
    "request":  { "method": "POST", "url": "https://…/companycertificate/request",
                  "headers": {}, "body": {} },
    "response": { "status_code": 503, "headers": {}, "body": {} },
    "validations": [
      { "uses": "validate/field", "with": { "input": "status_code", "operator": "equals", "value": 200 },
        "result": "failed", "actual": 503,
        "message": "Expected status_code == 200, got 503" }
    ],
    "recommendation": "The provider returned 503. Verify the CCMAPI dataplane is reachable and the asset is published under taxonomy#CCMAPI."
  }
}
```

Headers containing credentials (EDR tokens, `Authorization`) **[PROP]** are redacted in the stored log and
replaced with a stable hash, so a stored trace never leaks a Service Provider's secrets to a CAB.

---

## 9. Proposed Extensions (unratified)

These correspond to ADR-0001 §2 D10 (P1–P7). They are written as they would appear once ratified.

### 9.1 CAC traceability — `cac:` (P1)

```yaml
- id: send_status_notification
  uses: connector/dataplane/http_request
  cac: ["CX-0135:v3.1.0:CAC-014"]
  validate:
    - uses: validate/field
      cac: ["CX-0135:v3.1.0:CAC-014"]
      with: { input: status_code, operator: equals, value: 200 }
```

- Format: `<standard-id>:<standard-version>:<cac-id>`.
- Valid on steps and on individual validations. A validation's `cac` overrides the step's for reporting.
- Every referenced standard must appear in `metadata.standards`. Compiler-enforced.
- Copied into event `data.cac` and into the conformity report, producing the CAC coverage matrix.

### 9.2 Conditionals — `if:`, `validate/any_of`, `validate/all_of` (P2)

Needed because the CAC model has `IF` plus `MUST … OR/AND … MUST`, and nothing in the step syntax expresses it.

```yaml
validate:
  - uses: validate/any_of                                  # OR
    if: "${{ execution.<step>.response_body.status == 'failed' }}"
    with:
      validations:
        - uses: validate/field
          with: { input: status_code, operator: equals, value: 503 }
        - uses: validate/field
          with: { input: response_body, path: "error.code",
                  operator: equals, value: "SERVICE_UNAVAILABLE" }

  - uses: validate/all_of                                  # explicit AND (sibling entries are already AND)
    with:
      validations: [ … ]
```

- `if:` evaluates to a boolean over `${{ }}`-resolvable values. If false, the step or validation is **skipped**,
  not failed, and emits a `skipped` result in the log.
- `any_of` passes if at least one nested validation passes; `all_of` if all do.
- Nesting depth limit: 2.

### 9.3 Negative tests — `expects:` and `validate/error` (P3)

```yaml
- id: request_unknown_cert_type
  uses: connector/dataplane/http_request
  name: Request a certificate of an unknown type (negative test)
  expects: fail
  with:
    body: "${{ testdata.error_unknown_cert_type_body }}"
  returns:
    status_code: { type: integer, class: StatusCode }
    response_body: { type: object, class: ResponseBody }
  validate:
    - uses: validate/error
      with:
        input: response_body
        status_code: 400
        error_code: "UNKNOWN_CERTIFICATE_TYPE"
```

- `expects: fail` inverts the step's own success criterion: a transport-level or application-level failure is
  the expected outcome, and a success is a test failure.
- `validate:` entries still apply and still must all pass.

### 9.4 Integrity digests (P7)

```yaml
schemas:
  - id: certificate_schema
    source: business_partner_certificate_schema-v3.0.1.json
    digest: "sha256:9f2c…"
```

Recorded by the compiler in the `.tck` package; verified at load. Prevents a schema or fixture being swapped
between authoring and execution.

---

## 10. Authoring Checklist

Before submitting a TCK for compilation:

- [ ] Every file declares `kind` and `syntax`.
- [ ] `metadata.standards[]` lists every standard the TCK certifies, with versions.
- [ ] `dataspace.version` is set.
- [ ] `infrastructure.engine` and `infrastructure.sut` reflect what the tests actually need.
- [ ] Every `tests[].id` resolves to a file in `/tests`.
- [ ] Every test's `namespace` equals the manifest `id`.
- [ ] Every test file's `execution` has at least one step, and every step at least one `validate`.
- [ ] Every `uses:` key exists in the capability catalogue for this `syntax` version.
- [ ] Every `${{ }}` reference resolves backwards to `env`, `testdata`, or a prior step's declared `returns`.
- [ ] **No test reads another test's outputs** — tests are independent.
- [ ] `teardown` removes everything `setup` and `execution` created in the live dataspace.
- [ ] Versions and numeric-looking strings are quoted (`version: "1.0"`, not `version: 1.0`).
- [ ] No secrets are hard-coded; credentials come from `source: input` variables.
- [ ] *(On ratification of P1)* Every validation carries a `cac:` reference, and coverage of the standard's CAC
      set is complete.

---

## 11. Source

*Test Suite Development — Achieving a "sustainable" certification environment*, Catena-X e.V., 2026-07-26.
Slides 8–12 (CAC structure and mapping), 14–15 (package structure), 17–21 (`index.yaml`), 23–32 (test, phase,
step and capability syntax), 36–39 (execution logs and SSE).
