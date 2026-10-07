<!--
 Eclipse Tractus-X - Tractus-X TestLab

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

# ADR-0013: Preconditions Specification

## Context

TCK tests validate SUT (System Under Test) behavior in a dataspace. Before tests can execute, certain prerequisites must be satisfied:

1. The SUT must be configured with specific policies, assets, and endpoints
2. TestLab must know the SUT's connectivity details
3. TestLab must generate and provide configuration artifacts for the SUT operator

Currently, ADR-0010 mentions `preconditions:` as a TCK manifest field but does not specify what preconditions ARE, how they are structured, or how they interact with the execution environment. The v1.0 implementation uses `type: policy` preconditions that conflate executable logic with configuration declarations.

**Based on:**

- [ADR-0010 — YAML Syntax v2](../ADR-0010-yaml-syntax-v2.md)
- [ADR-0012 — Compilation and Packaging](../ADR-0012-compilation-and-packaging.md)

## Status

Superseded by [ADR-0021](../ADR-0021-remove-precondition-concept.md)

## Date

2026-05-21

## Decision

### 1. Preconditions Are Configuration Contracts

Preconditions are **declarative specifications** of what must be true before test execution begins. They are NOT executable steps. They serve three purposes:

1. **Generate artifacts** for the SUT operator to configure their system
2. **Provide static templates** for the SUT operator to register in their system
3. **Collect inputs** from the SUT operator before execution starts
4. **Verify readiness** by executing automated checks against configured services

Preconditions form a checklist that the operator completes before running the TCK.

### 2. Precondition Categories

| Category | Direction | Purpose |
|----------|-----------|---------|
| `inject` | TestLab → Environment | TestLab retrieves/injects values from infrastructure into env variables via `seed` |
| `generate` | TestLab → User | TestLab produces a value and shows it to the user for SUT configuration |
| `provide` | TestLab → User | A template/object defined in YAML, shown to the user to copy and register in their SUT |
| `input` | User → TestLab | A value the user must provide before execution starts |
| `check` | TestLab → SUT | Executable verification that infrastructure is ready before tests run |

### 3. Namespace: `env.preconditions`

Precondition values are stored in a dedicated, **immutable** namespace:

```yaml
# Reference in tests (from the immutable preconditions namespace):
${{ env.preconditions.<precondition_id>.<field> }}

# Examples:
${{ env.preconditions.testlab_connector.dsp_url }}
${{ env.preconditions.counter_party_connector.dsp_url }}
${{ env.preconditions.usage_policy.policy }}
```

**Immutability rules:**

- `env.preconditions` is **frozen** after TCK start — no step can modify it
- `util/set_env` and `util/export_env` CANNOT write to `env.preconditions`
- The compiler rejects any `${{ env.preconditions.x.y }}` reference to an undefined precondition

**Relationship to other namespaces:**

| Namespace | Mutability | Scope | Set by |
|-----------|-----------|-------|--------|
| `env.variables` | Mutable | TCK execution | `util/set_env`, `util/export_env` |
| `env.services` | Immutable | TCK manifest | TCK author |
| `env.schemas` | Immutable | TCK manifest | TCK author |
| `env.testdata` | Immutable | TCK manifest | TCK author |
| `env.preconditions` | **Immutable** | **TCK start (pre-execution)** | **Generated + user input** |

### 4. YAML Syntax

Preconditions use the **same step syntax** as ADR-0010 (`id` → `uses` → `name` → `with` → `returns`). The `uses:` namespace determines the precondition category.

**Precondition namespace:**

| `uses:` value | Category | Direction |
|---------------|----------|-----------|
| `precondition/inject/{target}` | Injected values | TestLab → Environment |
| `precondition/generate` | Generated values | TestLab → User |
| `precondition/provide` | Static templates | TestLab → User |
| `precondition/input` | User-provided values | User → TestLab |
| Any non-`precondition/` `uses:` value | Executable check | TestLab → SUT |

!!! note "Executable checks"
    When a precondition's `uses:` value does NOT start with `precondition/`, it is treated as an executable check. It follows the full step syntax including `with:`, `returns:` (optional), and `validate:` (optional).

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

metadata:
  name: "Certificate Management TCK"

preconditions:
  # ── Generated values (TestLab → User) ─────────────────────────────
  - id: testlab_connector
    uses: precondition/generate
    name: TestLab Connector Configuration
    returns:
      dsp_url:
        type: string
        class: url
        generator: testlab_dsp_endpoint
      bpn:
        type: string
        class: bpn
        generator: testlab_bpn
      did:
        type: string
        class: did
        generator: testlab_did
      dataspace_version:
        type: string
        class: enum
        generator: dataspace_version

  - id: mock_discovery
    uses: precondition/generate
    name: Mock Discovery Service
    returns:
      discovery_url:
        type: string
        class: url
        generator: mock_discovery_endpoint

  # ── Static templates (TestLab → User) ─────────────────────────────
  - id: usage_policy
    uses: precondition/provide
    name: Required Usage Policy
    with:
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
                  right_operand: "DataExchangeAgreement:1"
    returns:
      policy:
        type: object
        class: policy

  - id: access_policy
    uses: precondition/provide
    name: Required Access Policy
    with:
      value:
        permissions:
          - action: access
            constraints:
              - left_operand: BusinessPartnerNumber
                operator: eq
                right_operand: "${{ vars.testlab_connector.bpn }}"
    returns:
      policy:
        type: object
        class: policy

  - id: register_aas_descriptor
    uses: precondition/provide
    name: AAS Shell Descriptor Registration
    with:
      value:
        idShort: "CertificateManagement"
        id: "${{ vars.testlab_connector.bpn }}-ccm"
        specificAssetIds:
          - name: "manufacturerPartId"
            value: "${{ vars.user_asset_info.manufacturer_part_id }}"
        submodelDescriptors:
          - idShort: "CompanyCertificate"
            id: "urn:uuid:$UUID$"
            semanticId:
              type: ExternalReference
              keys:
                - type: GlobalReference
                  value: "urn:samm:io.catenax.company_certificate:2.0.0#CompanyCertificate"
            endpoints:
              - interface: "SUBMODEL-3.0"
                protocolInformation:
                  href: "<<base_url>>/api/v3.0/submodel"
                  endpointProtocol: "HTTP"
                  endpointProtocolVersion: ["1.1"]
                  subprotocol: "DSP"
                  subprotocolBodyEncoding: "plain"
    returns:
      descriptor:
        type: object
        class: aas_descriptor

  # ── User inputs (User → TestLab) ─────────────────────────────────
  - id: counter_party_connector
    uses: precondition/input
    name: SUT Connector Details
    returns:
      counter_party_address:
        type: string
        class: url
        label: "SUT DSP Endpoint URL"
        placeholder: "https://my-connector.example.com/api/dsp"
      counter_party_id:
        type: string
        class: bpn
        label: "SUT Identity (BPN or DID)"
        placeholder: "BPNL000000000001"

  - id: user_asset_info
    uses: precondition/input
    name: Test Asset Information
    returns:
      global_asset_id:
        type: string
        class: asset_id
        label: "Global Asset ID"
        placeholder: "urn:uuid:..."
      manufacturer_part_id:
        type: string
        class: part_id
        label: "Manufacturer Part ID"
        placeholder: "MPN-12345"
      part_instance_id:
        type: string
        class: part_id
        label: "Part Instance ID (optional)"
        placeholder: "SN-67890"
```

### 5. Precondition Types — Detailed Specification

All preconditions follow ADR-0010 step syntax: `id` → `uses` → `name` → `with` → `returns`.

#### 5.1 `precondition/generate`

TestLab produces values dynamically at TCK start and presents them to the user.

**Step structure:**

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique precondition identifier |
| `uses` | Yes | Always `precondition/generate` |
| `name` | Yes | Human-readable title shown to user |
| `with.description` | No | Instructions for the user |
| `returns` | Yes | Map of generated output fields |

**`returns` field specification (extended from ADR-0010):**

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Data type (`string`, `integer`, `boolean`, `object`) |
| `class` | Yes | Semantic class (`url`, `bpn`, `did`, `uuid`, `enum`) |
| `generator` | Yes | Built-in generator function identifier |

**Built-in generators:**

| Generator | Class | Description |
|-----------|-------|-------------|
| `testlab_dsp_endpoint` | url | TestLab's DSP protocol endpoint for this session |
| `testlab_bpn` | bpn | TestLab's Business Partner Number |
| `testlab_did` | did | TestLab's Decentralized Identifier |
| `dataspace_version` | enum | Dataspace version from TCK manifest (`jupiter` or `saturn`) |
| `mock_discovery_endpoint` | url | Session-scoped mock Discovery Finder URL |
| `mock_dtr_endpoint` | url | Session-scoped mock DTR URL |
| `uuid` | uuid | Random UUID (generated once, frozen) |

#### 5.2 `precondition/provide`

A static configuration template that TestLab resolves and shows to the user.

**Step structure:**

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique precondition identifier |
| `uses` | Yes | Always `precondition/provide` |
| `name` | Yes | Human-readable title shown to user |
| `with.description` | No | Instructions for the user |
| `with.value` | Yes | The template content (object, string, or array) |
| `returns` | Yes | Map declaring what the template produces |

**`with.value` variable resolution:**

| Syntax | Resolved by | When | Purpose |
|--------|------------|------|---------|
| `${{ vars.step_id.returns.field }}` | TestLab | At display time | Reference other precondition returns |
| `$UUID$` | TestLab | At display time | Generate a UUID |
| `<<placeholder>>` | **User manually** | On their SUT | Values TestLab cannot know (e.g., SUT base URLs) |

The `<<placeholder>>` syntax is intentionally different from `${{ }}` to make it visually clear which values the user must fill in versus which TestLab resolves.

**`returns` field specification:**

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Data type (`object`, `string`, `array`) |
| `class` | Yes | Semantic class (`policy`, `aas_descriptor`, `asset_spec`) |

The `returns` of a `precondition/provide` step exposes the resolved `with.value` object for reference by other preconditions and tests.

#### 5.3 `precondition/input`

Values the user must provide before TCK execution begins.

**Step structure:**

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique precondition identifier |
| `uses` | Yes | Always `precondition/input` |
| `name` | Yes | Human-readable title shown to user |
| `with.description` | No | Help text explaining what's needed |
| `returns` | Yes | Map of input field definitions |

**`returns` field specification (extended from ADR-0010):**

| Field | Required | Description |
|-------|----------|-------------|
| `type` | Yes | Data type (`string`, `integer`, `boolean`) |
| `class` | Yes | Semantic class (`url`, `bpn`, `did`, `asset_id`, `part_id`) |
| `label` | Yes | Display label shown in input form |
| `placeholder` | No | Example value shown in empty input field |

#### 5.4 Executable Checks

Automated verification steps that run after user configuration is complete but before test execution begins. They use regular step namespaces (e.g., `connector/`, `http/`, `mock/`) — NOT the `precondition/` namespace.

**Step structure:**

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique precondition identifier |
| `uses` | Yes | Any valid step type (e.g., `connector/health_check`, `http/call`) |
| `name` | Yes | Human-readable description of what is being verified |
| `with` | Yes | Step inputs — may reference `${{ env.services.x.y }}`, `${{ env.variables }}`, or other precondition returns |
| `returns` | No | Optional typed outputs (available to subsequent preconditions and tests) |
| `validate` | No | Optional inline assertions to verify the check passed |

**Semantics:**

- Executable checks run **after** all `generate`, `provide`, and `input` preconditions are resolved
- They verify that configured infrastructure is actually reachable and correctly set up
- If a check's `validate:` block fails, the TCK execution is **aborted** with a clear error
- Checks may reference services via `${{ env.services.<name>.<return_key> }}`
- Checks may produce `returns:` values available to subsequent checks and tests

**Example:**

```yaml
preconditions:
  # ... generate, provide, input preconditions ...

  # ── Executable checks (verify infrastructure) ────────────────────
  - id: health_provider
    uses: connector/health_check
    name: Provider health check
    with:
      connector_service: ${{ env.services.provider.connector_service }}
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200

  - id: health_consumer
    uses: connector/health_check
    name: Consumer health check
    with:
      connector_service: ${{ env.services.consumer.connector_service }}
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200
```

**Failure behavior:**

| Scenario | Result |
|----------|--------|
| Check step executes successfully, all validations pass | ✓ Proceed to tests |
| Check step executes successfully, validation fails | ✗ Abort TCK — report which check failed and why |
| Check step fails to execute (e.g., network error) | ✗ Abort TCK — report connection/execution error |
| Check step has no `validate:` block | ✓ Passes if step executes without error |

### 6. Execution Lifecycle

```
┌─────────────────────────────────────────────────────┐
│  1. COMPILE TIME                                     │
│     - Validate precondition syntax                   │
│     - Verify all ${{ env.preconditions.x.y }} refs   │
│     - Verify no circular references between          │
│       preconditions                                  │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  2. TCK START (Pre-Execution Phase)                  │
│     a. Run generators → produce dynamic values       │
│     b. Resolve ${{ }} in templates using generated   │
│        values                                        │
│     c. Display ALL preconditions to user:            │
│        - Generated values: "Copy these to your SUT" │
│        - Templates: "Register this in your SUT"     │
│        - Inputs: "Please provide these values"      │
│     d. Wait for user confirmation:                   │
│        - All inputs filled                           │
│        - User clicks "I have configured my SUT"     │
│     e. Freeze precondition returns (immutable)       │
│     f. Execute checks → verify infrastructure        │
│        - Run all executable check preconditions      │
│        - Abort if any check fails                    │
│        - Store check returns (immutable)             │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│  3. TEST EXECUTION                                   │
│     - Tests reference ${{ env.preconditions.x.y }}   │
│     - Values are immutable (read-only)               │
│     - setup → steps → teardown (per ADR-0010)        │
└─────────────────────────────────────────────────────┘
```

### 7. Precondition Resolution Order

Preconditions may reference other preconditions' outputs. The compiler validates the dependency graph:

```yaml
# access_policy references testlab_connector.returns.bpn → valid (generate before provide)
- id: testlab_connector
  uses: precondition/generate
  ...

- id: access_policy
  uses: precondition/provide
  with:
    value:
      constraints:
        - right_operand: "${{ vars.testlab_connector.returns.bpn }}"
```

**Resolution order:**

1. `generate` preconditions execute first (produce dynamic values)
2. `provide` templates are resolved (may reference generated values and inputs)
3. `input` fields are collected from the user (may have defaults from generated values)
4. `check` preconditions execute last (may reference generated values, inputs, and services)

**Compiler validations:**

| Rule | Error |
|------|-------|
| Circular reference | `Circular precondition reference: {a} → {b} → {a}` |
| Forward reference from generate to input | `Generator '{id}' cannot reference input '{ref}' — inputs are collected after generation` |
| Unknown precondition reference | `Unknown precondition reference 'preconditions.{id}.{field}' — no precondition with id '{id}'` |
| Unknown field reference | `Precondition '{id}' does not define output '{field}'` |

### 8. Referencing Preconditions in Tests

Tests access precondition values through the standard expression syntax:

```yaml
steps:
  - id: pull_ccmapi_data
    uses: connector/patterns/pull_data_by_policy
    name: Pull CCMAPI data using preconditioned policy
    with:
      connector_service: ${{ env.services.consumer_edc.connector_service }}
      counter_party_address: ${{ preconditions.counter_party_connector.dsp_url }}
      counter_party_id: ${{ preconditions.counter_party_connector.id }}
      policy: ${{ preconditions.usage_policy.policy }}
      filters:
        - operand_left: "https://w3id.org/edc/v0.0.1/ns/type"
          operator: "="
          operand_right: "https://w3id.org/catenax/taxonomy#CCMAPI"
```

### 9. Operator Presentation

Each category implies how a client presents it to the operator:

| Category | Presentation |
|----------|-------------|
| `generate` | Read-only cards with "Copy" buttons — user copies values to configure SUT |
| `provide` | Expandable template cards with syntax highlighting — user copies entire object |
| `input` | Form fields with labels, placeholders, and validation — user fills before running |
| `check` (executable) | Status indicators with pass/fail badges — auto-run after user confirms configuration |

The run does not start until every precondition in the checklist is satisfied.

### 10. Variable Seeding (`seed`)

Preconditions can **seed** environment variables with their output values. This bridges the gap between precondition-generated values and `env.variables` that services and steps reference.

#### 10.1 YAML Syntax

```yaml
preconditions:
  - id: testlab_connector
    uses: precondition/inject/connector
    with:
      type: connector
      name: "TestLab Connector"
    returns:
      dsp_url: { type: "string", class: "Url" }
      management_url: { type: "string", class: "Url" }
      bpn: { type: "string", class: "Bpn" }
    seed:
      testlab_dsp_url: dsp_url
      testlab_management_url: management_url
      consumer_bpn: bpn
```

**`seed` field:**

| Key | Value | Meaning |
|-----|-------|---------|
| env variable name | `returns` field name | After precondition executes, write `returns.<value>` into `env.variables.<key>` |

#### 10.2 `uses` Path Convention

| `uses:` pattern | Category | Purpose |
|-----------------|----------|---------|
| `precondition/inject/{target}` | Inject | Retrieves/injects from environment (e.g., `connector`, `participant`) |
| `precondition/generate/{target}` | Generate | Creates a new value (e.g., `uuid`, `ed25519`, `timestamp`, `bpn`) |
| `precondition/provide` | Provide | Provides a static value (e.g., a policy object) |
| `precondition/input` | Input | Requests user input at runtime |

#### 10.3 Seeding Priority Rules

```
--env explicit override  >  seed from precondition  >  default value
```

If the user provides `--env testlab_dsp_url=https://...`, the seed is skipped for that variable. Seeds only write to variables that have not been explicitly overridden.

#### 10.4 Compiled Representation

In `tck-execution.json`, the `seed` mapping is preserved verbatim:

```json
{
  "preconditions": [{
    "id": "testlab_connector",
    "uses": "precondition/inject/connector",
    "name": "TestLab Connector Configuration",
    "with": { "type": "connector", "name": "TestLab Connector" },
    "returns": {
      "dsp_url": { "type": "string", "class": "Url" },
      "management_url": { "type": "string", "class": "Url" },
      "bpn": { "type": "string", "class": "Bpn" }
    },
    "seed": {
      "testlab_dsp_url": "dsp_url",
      "testlab_management_url": "management_url",
      "consumer_bpn": "bpn"
    }
  }]
}
```

In `global_symbols`, seeded variables include a `seeded_by` field:

```json
{
  "env.testlab_dsp_url": {
    "source": "env.variables",
    "type": "string",
    "default": "",
    "seeded_by": "testlab_connector.dsp_url"
  }
}
```

#### 10.5 Compiler Validation Rules

| Rule | Error |
|------|-------|
| `seed` value must exist in `returns` keys | `Seed target 'x' not found in returns of precondition '{id}'` |
| `seed` key must be declared in `env.variables` | `Seed variable 'x' not declared in env.variables` |
| Same env variable cannot be seeded by multiple preconditions | `Variable 'x' seeded by both '{id1}' and '{id2}'` |

#### 10.6 Player Boot Sequence (Updated)

```
1. Load global_symbols → apply defaults + --env overrides
2. Load assets (schemas, testdata) + overrides
3. Execute preconditions IN ORDER:
   a. Run precondition step → get output dict
   b. Validate output matches `returns` contract
   c. For each `seed` entry: if env var NOT already set by --env → write output value
4. Re-resolve services that depend on seeded variables (lazy init)
5. Run tests
```

---

## Consequences

### Positive

- **Clear separation** between "what TestLab controls" and "what the user must configure"
- **Immutable contract** — precondition values cannot be accidentally modified during execution
- **Self-documenting** — the TCK YAML itself describes exactly what the user needs to do
- **Client-friendly** — the structured format maps directly to a configuration form
- **Compiler-verifiable** — all precondition references are validated at compile time
- **No magic** — every value the test uses has a declared source (generated, provided, or input)

### Negative

- **User friction** — operators must complete precondition configuration before running tests
- **Complexity** — four precondition types add cognitive load for TCK authors
- **Template maintenance** — static templates must be updated when standards change
- **Partial verification only** — executable checks verify connectivity but cannot fully validate SUT configuration
