<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2025 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# ADR-0010: YAML Syntax v2 (GHA-Inspired)

## Status

Accepted

## Date

2026-05-20

## Context

TestLab YAML v1 used a custom syntax (`type:`, `params:`, `@variable_name`, `store_in_memory:`) that was unfamiliar to most developers. This created a learning curve and made the format feel proprietary. After evaluating four alternatives — GitHub Actions (GHA), GitLab CI, Azure Pipelines, and keeping v1 — we chose the GHA-inspired syntax for the following reasons:

| Criterion | GHA | GitLab CI | Azure Pipelines | v0 (current) |
|-----------|-----|-----------|-----------------|--------------|
| Developer familiarity | Very high | High | Medium | None |
| Step-as-function model | Native (`uses`/`with`) | Partial | Partial | Custom |
| Variable interpolation | `${{ }}` (expressive) | `$VARIABLE` (flat) | `$(var)` (flat) | `@var` (custom) |
| Typed outputs | `outputs` concept exists | No | No | `store_in_memory` |
| Ecosystem tooling | Broad | Narrow | Narrow | None |
| Inline assertions | No (we extend with `validate:`) | No | No | Custom |

### Forces

- Primary users are certification testers — syntax must be learnable in minutes.
- The IDE auto-generates YAML from blocks — human authoring is secondary but must be pleasant.
- The compiler must validate structural correctness and variable resolution at compile time.
- Steps produce typed outputs (ADR-0009) — the syntax must express return types and classes.
- TCK manifests define shared environment (services, schemas, variables) inherited by all tests.
- Migration from v1 must be automatable with a CLI command.

## Decision

We adopt a GHA-inspired YAML syntax with the following specification.

---

### 1. Keywords

| Keyword | Purpose | Required | Scope |
|---------|---------|----------|-------|
| `id` | Stable identifier | Yes (IDE auto-generates) | Step, Document root |
| `uses` | Step type (replaces v1 `type:`) | Yes | Step |
| `name` | Human-readable label | Yes | Step, `metadata` block |
| `with` | Input parameters (replaces v1 `params:`) | No | Step |
| `returns` | Typed output declarations | No | Step |
| `validate` | Inline assertions | No | Step |
| `kind` | Document type (`tck`, `test`) | Yes | Document root |
| `env` | Environment block (variables, services, schemas) | No | TCK manifest |
| `setup` | Pre-test steps | No | Test file |
| `steps` | Main test steps | Yes | Test file |
| `teardown` | Post-test cleanup steps | No | Test file |
| `namespace` | Machine identifier for TCK linkage | Yes | Document root |
| `testlab` | TestLab syntax version (e.g. `v1-alpha`) | Yes | Document root |
| `preconditions` | TCK-level precondition steps | No | TCK manifest |
| `tests` | List of test file references | Yes | TCK manifest |

### 2. Step Field Ordering

Fields within a step MUST appear in this canonical order:

```yaml
- id: create_asset_1
  uses: connector/create_asset
  name: Create the test asset
  with:
    asset_id: ${{ steps.generated_id }}
    description: "Test asset for negotiation"
  returns:
    asset_id:
      type: string
      class: AssetId
  validate:
    - uses: validate/assert
      with:
        input: status_code
        operator: equals
        value: 200
    - uses: validate/field
      with:
        input: response_body
        path: "id"
        operator: not_null
```

> **Note:** The `input` field in assertions always references a variable declared in a step's `returns:` block. At runtime it resolves to `${{ steps.step_name.field }}`.

Order: **id → uses → name → with → returns → validate**

The compiler MUST reject steps where `id` does not appear first or `uses` does not appear second. Remaining fields may appear in any order but the canonical order is enforced by IDE serialization.

### 3. Variable Interpolation

#### 3.1 Syntax

All variable references use the `${{ }}` expression syntax:

| Pattern | Scope | Source | Example |
|---------|-------|--------|---------|
| `${{ steps.x }}` | Test-local | Step `returns` values | `${{ steps.asset_id }}` |
| `${{ steps.step_id.x }}` | Test-local (qualified) | Specific step's return | `${{ steps.create_asset_1.asset_id }}` |
| `${{ env.x }}` | TCK-global | TCK manifest `env.variables` | `${{ env.provider_url }}` |
| `${{ env.schemas.name }}` | TCK-global | TCK manifest `env.schemas` | `${{ env.schemas.asset_schema }}` |
| `${{ metadata.x }}` | TCK-global | TCK manifest `metadata` fields | `${{ metadata.dataspace_version }}` |
| `${{ execution.x }}` | Runtime | Player-injected execution context | `${{ execution.id }}` |

#### 3.2 Resolution Rules

1. **Flat `${{ steps.x }}`** resolves by searching all preceding steps' `returns` for key `x`.
2. If exactly one match exists → resolved.
3. If zero matches → **compiler error**: `Unresolved variable: steps.x — no preceding step returns 'x'`.
4. If multiple matches → **compiler error**: `Ambiguous variable: steps.x — returned by steps [step_a, step_b]. Use qualified form: ${{ steps.step_a.x }}`.
5. **Qualified `${{ steps.step_id.x }}`** always resolves to exactly that step's return. If the step or return does not exist → compiler error.
6. **`${{ env.x }}`** resolves from the TCK manifest `env.variables` block. If not defined → compiler error.
7. **`${{ env.schemas.name }}`** resolves to the schema file path declared in `env.schemas`. If not defined → compiler error.
8. **`${{ metadata.x }}`** resolves from the TCK manifest `metadata` block fields. Supports dot-notation for nested fields (e.g., `metadata.dataspace_version`). If the field does not exist → compiler error.
9. **`${{ execution.x }}`** resolves from the runtime execution context. Four keys are always available (`id`, `tck_id`, `timestamp`, `runner`). Additional keys may be injected via CLI `--set`, SDK `execution_context`, or `TESTLAB_EXEC_*` environment variables. Built-in keys are validated at compile time; custom keys produce a warning: `execution.{x} is not a built-in key — ensure it is injected at runtime`.
10. Variables are resolved **top-to-bottom** — a step can only reference returns from steps above it (including setup steps when referenced from main steps).

#### 3.3 Variable Lifecycle

| Phase | Visibility |
|-------|-----------|
| `setup` steps | Visible to `steps` and `teardown` |
| `steps` | Visible to subsequent `steps` and `teardown` |
| `teardown` | Can reference all preceding variables |
| `preconditions` (TCK-level) | Visible to all tests in the TCK |
| `env` variables | Visible everywhere (TCK-global) |

#### 3.4 Execution Context

The `execution` scope provides runtime context injected by the Player before execution begins. It is read-only — steps cannot modify execution variables.

**Built-in keys (always available):**

| Key | Type | Description | Example |
|-----|------|-------------|--------|
| `execution.id` | string | UUID v4, unique per run | `"a1b2c3d4-e5f6-..."` |
| `execution.tck_id` | string | Fully qualified TCK ID (`{namespace}/{id}`) | `"ccm-v0.0.1/certificate-management-tck"` |
| `execution.timestamp` | string | ISO 8601 UTC start time | `"2026-05-21T14:30:00Z"` |
| `execution.runner` | string | Runner identifier | `"local"`, `"ci"`, `"embedded"` |

**Custom keys (user-injected):**

Any additional `execution.*` key can be provided at runtime through three injection mechanisms:

| Mechanism | Example | Use case |
|-----------|---------|----------|
| CLI `--set` | `testlab run tck.yaml --set execution.tenant_id=acme` | CI pipelines, manual runs |
| SDK `execution_context` | `player.run("tck.yaml", execution_context={"tenant_id": "acme"})` | Embedded in application code |
| Environment variables | `TESTLAB_EXEC_TENANT_ID=acme` → `execution.tenant_id` | Container/cloud environments |

**Resolution priority** (highest wins):

1. CLI `--set` flag
2. SDK `execution_context` dict
3. `TESTLAB_EXEC_*` environment variables (prefix stripped, lowercased)
4. Built-in values

**Environment variable mapping:** `TESTLAB_EXEC_` prefix is stripped and the remainder is lowercased with underscores preserved. Example: `TESTLAB_EXEC_CI_PIPELINE_ID` → `execution.ci_pipeline_id`.

**Compiler behavior:**

- Built-in keys (`id`, `tck_id`, `timestamp`, `runner`): always valid, no warning
- Any other `execution.*` key: compile-time warning (may not be available at runtime)
- At runtime: missing custom key → execution error with context message

#### 3.5 User Mental Model: Two Variable Concepts Only

The `${{ steps.x }}` / `${{ env.x }}` interpolation syntax is an **implementation detail** that TCK authors should never need to think about. From the user's perspective, there are exactly **two concepts**:

| User Concept | Label in IDE | Actual Syntax | Semantics |
|--------------|-------------|---------------|-----------|
| **Local variable** | "Step output" / "Local" | `${{ steps.x }}` | Private to the current test — produced by a step's `returns` and consumed by subsequent steps within the same test file. Not visible to other tests. |
| **Environment variable** | "Environment" / "Public" | `${{ env.x }}` | Shared across the entire TCK — defined once in the TCK manifest and inherited by all test files. Can be overwritten if needed, globally visible. |

**Design rules:**

1. **The IDE hides interpolation syntax entirely.** Users pick variables from dropdowns or drag output tokens — they never type `${{ }}` manually.
2. **Variable labels use domain language.** The IDE shows "Asset ID (from Create Asset step)" not `${{ steps.create_asset_1.asset_id }}`.
3. **Color-coding distinguishes scope.** Local variables and environment variables use distinct visual indicators so users always know the scope at a glance.
4. **No third category.** There is no "global mutable", no "shared between tests", no "session" scope. Two concepts only — local outputs and public environment. If a value must be shared, it belongs in `env`.
5. **Qualification is automatic.** When ambiguity arises (two steps return the same variable name), the IDE silently switches to the qualified form — the user sees a disambiguation prompt ("Which step's output?"), never raw syntax.
6. **Environment overwrite is explicit.** To update an environment variable mid-test, the user uses a dedicated "Set Environment Variable" block (`util/set_env`). This keeps mutations visible and auditable — the block clearly shows which variable is being changed and to what value.

**Rationale:** TCK authors are certification testers, not developers. Forcing them to understand expression interpolation, scoping rules, or qualified references adds cognitive load that produces zero value. The IDE and compiler handle the plumbing; the user thinks in "my step's output" and "the test environment".

#### 3.5.1 Overwriting Environment Variables (`util/set_env`)

When a test needs to change an environment variable (e.g., switch a URL, update a token after rotation), the user uses the **"Set Environment Variable"** block:

```yaml
- id: update_provider_url
  uses: util/set_env
  name: Update provider URL for failover
  with:
    variable: provider_url
    value: "https://provider-failover.local/management"
```

**Semantics:**

- **Modifies the environment variable directly.** After execution, `${{ env.provider_url }}` resolves to the new value for all subsequent steps.
- **The `env` config reflects the change.** If the user inspects the environment variables panel in the IDE, the modified variable shows its updated value (marked as "modified" to distinguish from the original TCK manifest default).
- The override is visible to all subsequent steps, including `teardown`.
- **Persistence follows normal save behavior.** The change is in-memory until the user explicitly saves the file — just like any other edit. Saving writes the updated value to the TCK manifest on disk.
- The compiler validates that `variable` references an existing key in `env.variables`.

**IDE presentation:** The block shows as "Set Environment Variable" with a dropdown of available environment variable names and a value input. No `${{ }}` syntax is exposed.

### 4. Step IDs

| Rule | Specification |
|------|---------------|
| Pattern | `[a-z][a-z0-9_]{0,49}` |
| Max length | 50 characters |
| Uniqueness | Unique within a test file (across setup + steps + teardown) |
| Stability | IDs do not change when steps are reordered |
| Generation | IDE auto-generates from step type (e.g., `create_asset_1`, `negotiate_2`) |
| User override | Users may set custom IDs via the IDE or YAML |

**Compiler rules:**

- Reject duplicate IDs within a test file.
- Reject IDs that do not match the pattern.
- Reject IDs that collide with reserved words: `env`, `steps`, `returns`, `steps`, `setup`, `teardown`.

### 5. Returns (Step Outputs)

Every step MAY declare `returns:`. Each return is a named output with metadata:

```yaml
returns:
  agreement_id:
    type: string
    class: AgreementId
  negotiation_id:
    type: string
    class: NegotiationId
```

| Field | Required | Description |
|-------|----------|-------------|
| key (name) | Yes | Output variable name — must be unique within the step |
| `type` | Yes | Data type: `string`, `integer`, `boolean`, `object`, `array` |
| `class` | Yes | Semantic class from ADR-0009 class registry |

**Rules:**

- ALL `returns` values are auto-persisted in test memory at runtime. No opt-in flag.
- The runtime populates return values after step execution completes successfully.
- If a step fails, its returns are NOT populated (downstream references will be `null`).
- A step with no `returns:` block produces no variables.
- Return names must match `[a-z][a-z0-9_]{0,49}`.

### 6. Validate (Assertions)

Assertions use the **same `uses:` / `with:` pattern as steps**. The `validate/` namespace contains all assertion types — just like `connector/`, `mock/`, or `util/` are step namespaces.

```yaml
validate:
  - uses: validate/assert
    with:
      input: status_code
      operator: equals
      value: 200
  - uses: validate/field
    with:
      input: response_body
      path: "header.messageId"
      operator: matches_regex
      value: "^urn:uuid:[0-9a-f-]{36}$"
  - uses: validate/field
    with:
      input: response_body
      path: "content.requestStatus"
      operator: one_of
      value: ["IN_PROGRESS", "COMPLETED", "REJECTED"]
  - uses: validate/field
    with:
      input: response_body
      path: "content.certificate"
      operator: not_null
  - uses: validate/object
    with:
      input: response_body
      operator: equals
      value:
        status: "COMPLETED"
        type: "ISO9001"
  - uses: validate/schema
    with:
      input: response_body
      schema: "${{ env.schemas.certificate_response }}"
```

**Why `validate:` not `assert:`:** The keyword is domain-specific to certification testing. "Validate" communicates intent to non-technical users more naturally than "assert" (which implies unit testing). No CI system uses `validate:`, avoiding confusion.

**Why `uses:` / `with:`:** Assertions are conceptually the same as steps — they have a type (`uses:`) and parameters (`with:`). Using the same structural pattern means one mental model for the entire YAML file: every operation is `uses:` + `with:`.

#### 6.1 Assertion Types (`validate/` namespace)

The `input` field **always** references a variable declared in a step's `returns:` block. At runtime it resolves to `${{ steps.step_name.field }}`.

| `uses:` value | Purpose | Required `with:` fields |
|---|---|---|
| `validate/assert` | Compare a direct return variable against scalar/array | `input`, `operator`, `value` |
| `validate/field` | Compare a nested field within a return variable | `input`, `path`, `operator`, `value` (optional for `not_null`) |
| `validate/query_param` | Validate a specific query parameter from a `query_params` return | `input`, `param`, `operator`, `value` (not available for `not_null` or `is_null`) |
| `validate/object` | Deep-compare return variable against JSON object | `input`, `operator`, `value` (object) |
| `validate/schema` | Validate return variable against JSON schema | `input`, `schema` |

#### 6.2 Operators

**Operators for `validate/assert` and `validate/field`:**

| Operator | Meaning | Example |
|----------|---------|---------|
| `equals` | Equals | `operator: equals, value: 200` |
| `not_equals` | Not equals | `operator: not_equals, value: "ERROR"` |
| `not_null` | Value exists | `operator: not_null` (no `value` needed) |
| `is_null` | Value does not exist / is absent | `operator: is_null` (no `value` needed) |
| `is_base64` | Value is valid base64-encoded string | `operator: is_base64` (no `value` needed) |
| `matches_regex` | Regex match | `operator: matches_regex, value: "^[0-9a-f-]{36}$"` |
| `one_of` | One of listed options | `operator: one_of, value: ["A", "B"]` |
| `contains` | Contains value | `operator: contains, value: "Asset"` |
| `gt` | Greater than | `operator: gt, value: 0` |
| `gte` | Greater than or equal | `operator: gte, value: 1` |
| `lt` | Less than | `operator: lt, value: 500` |
| `lte` | Less than or equal | `operator: lte, value: 100` |

**Operators for `validate/object`:** `equals`, `contains`

#### 6.2.1 Implementation Architecture: Accessor + Operator Engine

All `validate/*` types share a **single operator engine**. Each assertion type only differs in how it **accesses** the value to compare — the comparison logic itself is never duplicated:

```
┌─────────────────────┐      ┌──────────────────┐
│  validate/assert    │─────▶│                  │
├─────────────────────┤      │                  │
│  validate/field     │─────▶│  Operator Engine │──▶ pass / fail
├─────────────────────┤      │  (shared, single │
│  validate/query_param│─────▶│   implementation)│
├─────────────────────┤      │                  │
│  validate/object    │─────▶│                  │
└─────────────────────┘      └──────────────────┘
        Accessors                  Operators
   (extract the value)         (compare the value)
```

**Accessor responsibilities** (one per assertion type):

| Assertion type | Accessor logic |
|----------------|----------------|
| `validate/assert` | Return the raw value from `returns[input]` |
| `validate/field` | Resolve dot-path (`path`) into the object from `returns[input]` |
| `validate/query_param` | Look up `param` key in the query_params map, optionally base64-decode |
| `validate/object` | Return the full object from `returns[input]` |
| `validate/schema` | Separate path — delegates to JSON Schema validator, not the operator engine |

**Operator engine** — single function signature:

```
evaluate(resolved_value, operator, expected_value) → { pass: bool, message: string }
```

All operators (`equals`, `not_null`, `is_null`, `matches_regex`, `one_of`, `contains`, `gt`, `gte`, `lt`, `lte`, `is_base64`, `not_equals`) are implemented **once** in the operator engine and reused by every accessor.

**Adding a new assertion type** (e.g., `validate/header`) requires:
1. Write a new accessor (how to extract the value) — ~10 lines
2. Register it in the accessor map
3. All existing operators work automatically — zero duplication

**Adding a new operator** (e.g., `starts_with`) requires:
1. Add it to the operator engine — ~5 lines
2. All existing assertion types gain the new operator automatically

> **Design rule**: Never implement operator logic inside an accessor. The accessor's only job is to resolve `input` + accessor-specific fields (`path`, `param`, `base64`) into a concrete value, then hand it to the operator engine.

#### 6.3 Query Parameter Validation and Extraction

**Assertion (`validate/query_param`):**

Validates a specific query parameter from a `query_params` return. Uses `param` instead of `path`:

```yaml
validate:
  - uses: validate/query_param
    with:
      input: query_params
      param: "certificateType"
      operator: equals
      value: "ISO9001"
  - uses: validate/query_param
    with:
      input: query_params
      param: "bpn"
      operator: matches_regex
      value: "^BPNL[0-9A-Z]{12}$"
  - uses: validate/query_param
    with:
      input: query_params
      param: "page"
      operator: not_null
  - uses: validate/query_param
    with:
      input: query_params
      param: "fragment"
      operator: is_null
  - uses: validate/assert
    with:
      input: query_params
      operator: is_null
```

> **`is_null` on the full `query_params` object** asserts that no query parameters were sent at all (clean URL, no `?` params). Use `is_null` on a specific `param` to assert that particular parameter was not included.

**Encoding & Decoding:**

Query parameters often contain encoded values. Two encoding layers exist:

| Encoding | Description | Handling |
|----------|-------------|----------|
| URL (percent-encoding) | `%20`, `%3D`, `+` etc. | **Automatic** — runtime always decodes. Users never see `%20`. |
| Base64 | Complex payloads encoded as `eyJicG4iOi...` | **Explicit** — set `base64: true` to decode before validation. |

Use `base64: true` to decode the parameter value before the operator is applied:

```yaml
# Validate a base64-encoded filter parameter contains expected JSON
- uses: validate/query_param
  with:
    input: query_params
    param: "filter"
    base64: true
    operator: equals
    value:
      bpn: "BPNL00000000001"
      type: "ISO9001"

# Assert the value is valid base64 (without decoding the content)
- uses: validate/query_param
  with:
    input: query_params
    param: "filter"
    operator: is_base64
```

The `value` field supports both scalars and objects. When `base64: true` is set and the decoded content is valid JSON, it is parsed as an object before the operator runs — enabling deep equality and field-level checks.

| Operator | With `base64: true` |
|----------|---------------------|
| `equals` | Compares decoded value (string or parsed object) |
| `contains` | Checks substring in decoded string, or key presence in decoded object |
| `is_base64` | Asserts the raw (pre-decode) value is valid base64 — `base64: true` is ignored |

> **Design rule**: URL decoding is always automatic. Base64 decoding is always explicit (`base64: true`). No other encoding schemes are supported — if needed in the future, add new boolean flags following the same pattern.

**Extraction (`util/extract_query_param`):**

Extracts a single query parameter value into a local variable for reuse in subsequent steps:

```yaml
# Simple extraction (string value)
- id: extract_cert_type
  uses: util/extract_query_param
  name: Extract certificate type from SUT request
  with:
    source: ${{ steps.wait_for_pull.query_params }}
    param: "certificateType"
  returns:
    value:
      type: any

# Base64-encoded JSON extraction (decoded to object)
- id: extract_filter
  uses: util/extract_query_param
  name: Extract decoded filter object
  with:
    source: ${{ steps.wait_for_pull.query_params }}
    param: "filter"
    base64: true
  returns:
    value:
      type: any
```

**Return type inference (`type: any`):**

`type: any` is a **deferred type** — it tells the compiler "the concrete type is unknown at compile time and will be resolved at runtime." This is necessary for steps whose output depends on the actual data received (e.g., a query parameter might be a plain string or a base64-encoded JSON object).

**When to use `type: any`:**

| Scenario | Why `any` is needed |
|----------|---------------------|
| `util/extract_query_param` with `base64: true` | Output could be `string`, `object`, or `array` depending on content |
| Steps that parse dynamic external input | The SUT sends unpredictable structures |
| Utility steps with polymorphic output | Same step, different output shapes |

**How `type: any` works:**

1. **Compile time**: The compiler skips type-compatibility checks on downstream references to this variable. No error if a `validate/field` (expects object) or `validate/assert` (expects scalar) references it.
2. **Runtime**: After the step executes, the runtime inspects the actual value and assigns a concrete type (`string`, `integer`, `object`, `array`, `boolean`). This resolved type is stored in test memory alongside the value.
3. **Validation**: If a downstream operator is incompatible with the resolved type (e.g., `gt` on an object), it fails with a clear runtime error: `"Operator 'gt' requires a numeric value, got 'object' from step 'extract_filter'"`.

**Contrast with fixed types:**

| Declaration | Compile-time check | Runtime behavior |
|-------------|-------------------|------------------|
| `type: string` | Compiler rejects `validate/field` (needs object) | Runtime asserts value IS a string, fails otherwise |
| `type: object` | Compiler rejects `operator: gt` (needs numeric) | Runtime asserts value IS an object, fails otherwise |
| `type: any` | Compiler allows all downstream uses | Runtime resolves type, then validates operator compatibility |

> **Design rule**: Use `type: any` only when the output type genuinely depends on runtime data. Prefer concrete types (`string`, `object`) for steps with predictable outputs — this catches errors at compile time instead of runtime.

| `base64` | Decoded content | Resolved `type` at runtime |
|----------|----------------|---------------------------|
| `false` (default) | Raw param value | `string` |
| `true` | Valid JSON object/array | `object` or `array` |
| `true` | Non-JSON content | `string` |

After this step, `${{ steps.extract_cert_type.value }}` (or short form `${{ steps.value }}` if unambiguous) is available as a local variable.

#### 6.4 Input variable resolution

The `input` field references a variable name from the current step's `returns:` declaration:

- `status_code` — HTTP response status (integer)
- `response_body` — Parsed JSON response (object, used with `validate/field` for dot-path access)
- `response_headers` — Response headers (object)

The `input` value is always a return variable name. It resolves at runtime to the actual value stored in `${{ steps.step_name.field }}`.

### 7. Document Kinds

#### 7.1 TCK Manifest (`kind: tck`)

##### Source Folder Structure

A TCK project on disk follows this layout:

```
certificate-management-tck/
├── index.yaml                                  # TCK manifest (kind: tck)
├── schemas/
│   ├── business_partner_certificate.json       # CX-0135 BPC response schema
│   └── notification_header.json                # CX-0135 notification envelope schema
├── testdata/
│   ├── available_notification.json             # JSON payload (most common format)
│   └── sample_certificate.pdf                  # Binary attachment example
└── tests/
    ├── request-certificate.yaml                # Test files (kind: test)
    ├── validate-payload.yaml
    └── available-notification.yaml
```

**Rules:**

- The manifest file must be named `index.yaml` and live at the project root.
- No symlinks or references outside the project directory are allowed.
- Directory nesting is permitted (e.g. `tests/notifications/available.yaml`).
- `schemas/` contains JSON Schema files (`.json`) for validation assertions.
- `testdata/` contains static data files referenced by tests via `env.testdata` (optional).
- `tests/` contains all test files (`kind: test`) belonging to the TCK.

##### Implicit Folder Resolution

All file references use **bare filenames** — the parent folder is implied by the section that declares them:

| Section | Implied folder | Example entry | Resolved path |
|---------|---------------|---------------|---------------|
| `tests:` | `tests/` | `request-certificate.yaml` | `tests/request-certificate.yaml` |
| `env.schemas:` | `schemas/` | `file: business_partner_certificate.json` | `schemas/business_partner_certificate.json` |
| `env.testdata:` | `testdata/` | `file: available_notification.json` | `testdata/available_notification.json` |

**Rationale:**

1. **No redundancy.** Writing `schemas/business_partner_certificate.json` under a key called `schemas:` repeats information the compiler already knows. Bare filenames eliminate this stutter.
2. **Safer refactoring.** If a folder is ever renamed (e.g., `payloads/` → `testdata/`), only the compiler's resolution logic changes — zero YAML files need updating.
3. **Consistent convention.** All three resource sections (`tests`, `schemas`, `testdata`) follow the same pattern: declare the logical name, the compiler resolves the physical path.
4. **Reduced user error.** Users cannot accidentally point a schema entry at a file outside `schemas/` or a testdata entry at a file in `tests/`. The folder boundary is enforced structurally.

> **Compiler rule:** If a referenced file does not exist at the resolved path, the compiler emits an error: `"File 'notification_header.json' not found in schemas/ folder"`.
>
> **Nesting:** Subdirectories within the implied folder are supported — use relative paths like `notifications/available.yaml` (still resolved within `tests/`).

**Supported file types for `testdata/`:**

| Extension | MIME Type (`type`) | Notes |
|-----------|-----------|-------|
| `.json` | `application/json` | Primary format — most blocks support this |
| `.xml` | `application/xml` | For XML-based payloads |
| `.pdf` | `application/pdf` | Binary attachments (e.g., certificate documents) |
| `.txt` | `text/plain` | Plain text payloads |
| `.csv` | `text/csv` | Tabular data |

**`env.schemas` entry specification:**

| Field | Required | Description |
|-------|----------|-------------|
| key | Yes | Logical variable name — referenced in tests as `${{ env.schemas.key }}` |
| `file` | Yes | Filename relative to the `schemas/` folder (must be `.json`) |

> **Note:** The JSON Schema draft version is read from the `$schema` field inside the file itself — no need to declare it in the manifest.

**`env.testdata` entry specification:**

| Field | Required | Description |
|-------|----------|-------------|
| key | Yes | Logical variable name — referenced in tests as `${{ env.testdata.key }}` |
| `file` | Yes | Filename relative to the `testdata/` folder |
| `type` | Yes | MIME type — must be one of the supported types in the table above |

The `type` field declares the MIME type explicitly. The compiler validates that the file extension matches the declared type and rejects mismatches.

> **Note:** Not every block supports every file type. Each block's `with:` field documentation declares which types it accepts. JSON is the default and most widely supported format. The compiler validates type compatibility between testdata references and the blocks that consume them.

##### Using `env.testdata` in Steps

Testdata entries declared in `env.testdata` are referenced in step fields using the `${{ env.testdata.<key> }}` expression. The compiler resolves the reference to the file content at compile time, inlining the payload where the block expects it.

**Mock step — serving a JSON testdata file as the response body:**

```yaml
- id: mock_available_endpoint
  uses: mock/api
  name: Mock the available notification endpoint
  with:
    method: POST
    path: /api/v1/companycertificate/available
    response_status: 200
    response_body: ${{ env.testdata.available_notification }}
  returns:
    callback_id:
      type: string
      class: CallbackId
    base_mock_url:
      type: string
```

Instead of inlining a large JSON object in the YAML, the `response_body` resolves to the contents of `testdata/available_notification.json` at compile time. This keeps test files concise and testdata reusable across steps.

**Validation step — validating a response against a schema from `env.schemas`:**

```yaml
- id: validate_certificate_response
  uses: validate/schema
  name: Validate certificate payload matches CX-0135 schema
  with:
    input: ${{ steps.request_certificate.response.body }}
    schema: ${{ env.schemas.certificate_schema }}
```

The `input` field references a previous step's output, while `schema` resolves to a JSON Schema file declared in `env.schemas`. The validator loads both at runtime and reports field-level mismatches.

##### TCK Manifest Example

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

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
    - name: Mathias Moser
      email: mathias.moser@catena-x.net
      company: Catena-X Automotive Network e.V.
  copyright_holders:
    - "2026 Catena-X Automotive Network e.V."
  license: LicenseRef-Proprietary # Example only
  standards:
    - id: CX-0135
      organization: "Catena-X Automotive Network e.V." # optional
      version: v3.1.0
  tags:
    - CCM
  dataspace_version: saturn

env:
  variables: 
    provider_url: "https://provider.local" # Placeholders 
    consumer_url: "https://consumer.local" # Dummy Variables
    provider_bpn: "BPNL000000000001"
    consumer_bpn: "BPNL000000000002"
  services:
    - name: provider
      uses: service/connector_service
      with:
        base_url: ${{ env.provider_url }}
        management_path: /management/v3
        dsp_path: /api/v1/dsp
        auth:
          type: oauth2
          token_url: "https://auth.local/token"
      returns:
        service:
          type: class
          class: ConnectorService
    - name: consumer
      uses: service/connector_service
      with:
        base_url: ${{ env.consumer_url }}
        management_path: /management/v3
        dsp_path: /api/v1/dsp
        auth:
          type: oauth2
          token_url: "https://auth.local/token"
      returns:
        service:
          type: class
          class: ConnectorService
  schemas:
    certificate_schema:
      file: business_partner_certificate_schema.json
    notification_header_schema:
      file: notification_header.json
  testdata:
    available_notification:
      file: available_notification.json
      type: application/json
    sample_certificate:
      file: sample_certificate.pdf
      type: application/pdf

# Preconditions specification: see ADR-0012
preconditions: []

tests:
  - request-certificate.yaml
  - validate-payload.yaml
  - available-notification.yaml
```

#### 7.2 Test File (`kind: test`)

##### `namespace` and `id` Fields

Both `kind: tck` and `kind: test` documents declare `namespace` and `id`:

| Field | TCK manifest | Test file |
|-------|-------------|-----------|
| `namespace` | **Defines** the namespace (machine identifier) | **Declares membership** in a TCK's namespace |
| `id` | Short machine identifier for the TCK | Machine-readable test identifier, unique within the namespace |

The fully qualified document identifier is `{namespace}/{id}`, e.g. `ccm-v0.0.1/certificate-management-tck` (TCK) or `ccm-v0.0.1/available-notification` (test).

The human-readable display label (`name`) lives inside `metadata` — it is not a root-level field on documents.

**`namespace` specification:**

| Property | Value |
|----------|-------|
| **Type** | String |
| **Required** | Yes (on both TCK and test) |
| **Pattern** | `^[a-z][a-z0-9-]*$` (lowercase kebab-case) |
| **Semantics** | On TCK: defines the namespace. On test: must exactly match the `namespace` of the parent TCK. |

The `namespace` field is the shared machine identifier that links TCKs and tests. The `name` field inside `metadata` is the human-readable label for display in the IDE and reports.

**`id` specification:**

| Property | Value |
|----------|-------|
| **Type** | String |
| **Required** | Yes (on both TCK and test) |
| **Pattern** | `^[a-z][a-z0-9-]*$` (lowercase kebab-case) |
| **Uniqueness** | Unique within the namespace |
| **Semantics** | Short machine identifier for the document. Combined with `namespace` forms the fully qualified ID. |

**`authors` specification:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Author's display name |
| `email` | No | Contact email address |
| `company` | No | Organization or company name |

**`copyright_holders` specification:**

| Property | Value |
|----------|-------|
| **Type** | List of strings |
| **Required** | Yes |
| **Format** | `SPDX-FileCopyrightText` value (without the key prefix): `"<year> <holder>"` |
| **Example** | `"2026 Contributors to the Eclipse Foundation"` |

Each entry corresponds to one `SPDX-FileCopyrightText:` line in traditional SPDX headers.

**`license` specification:**

| Property | Value |
|----------|-------|
| **Type** | String |
| **Required** | Yes |
| **Format** | Valid [SPDX License Identifier](https://spdx.org/licenses/) |
| **Example** | `Apache-2.0`, `MIT`, `CC-BY-4.0` |

The value maps directly to `SPDX-License-Identifier:`. Common values:

| License | SPDX Identifier |
|---------|----------------|
| Apache License 2.0 | `Apache-2.0` |
| MIT License | `MIT` |
| Creative Commons Attribution 4.0 | `CC-BY-4.0` |
| Proprietary / All Rights Reserved | `LicenseRef-Proprietary` |
| No license declared | `NONE` |

For proprietary TCKs where all rights are reserved, use `LicenseRef-Proprietary` (the SPDX convention for non-standard licenses is the `LicenseRef-` prefix).

**`standards` specification:**

A list of industry standards that the TCK validates against.

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Standard identifier (e.g. `CX-0135`, `ISO-27001`) |
| `organization` | No | Publishing organization (e.g. `"Catena-X Automotive Network e.V."`, `"Eclipse Dataspace Working Group"`. `"International Standarization Organization"`, `"Manufacturing-X"`) |
| `version` | No | Standard version (e.g. `v3.1.0`) |

Standards entries link a TCK to the formal specifications it certifies. The `id` is the canonical reference used in reports, IDE labels, and compliance matrices. When `organization` is omitted, the standard is assumed to belong to the ecosystem's default standards body. When `version` is omitted, the TCK applies to all versions of the standard.

**`tags` specification:**

| Property | Value |
|----------|-------|
| **Type** | List of strings |
| **Required** | No |
| **Pattern** | Uppercase or lowercase alphanumeric, no spaces (e.g. `CCM`, `DTR`, `Notifications`) |
| **Semantics** | Free-form labels for filtering and grouping in the IDE and reports |

Tags are display-only metadata — they have no effect on compilation or execution. Use them to categorize TCKs by domain area (e.g. `CCM` for Certificate Management, `DTR` for Digital Twin Registry).

**`dataspace_version` specification:**

| Property | Value |
|----------|-------|
| **Type** | String |
| **Required** | Yes (on TCK manifests) |
| **Allowed values** | `jupiter`, `saturn` |
| **Semantics** | Selects the dataspace protocol version and connector API compatibility level |

The `dataspace_version` determines which SDK service implementations and protocol behaviors are used at runtime:

| Value | connector Version | Protocol |
|-------|-------------|----------|
| `jupiter` | v0.8 – v0.10 | DSP 2024-1 |
| `saturn` | v0.11+ | DSP 2025-1 |

The compiler validates that all steps in the TCK are compatible with the declared `dataspace_version`. Steps that require a newer protocol version than declared will produce a compile-time error.

**`testlab` specification:**

| Property | Value |
|----------|-------|
| **Type** | String |
| **Required** | Yes (on all documents: TCK and test) |
| **Format** | `v<major>[-<qualifier>]` (e.g. `v1-alpha`, `v1`, `v2`) |
| **Semantics** | Declares the TestLab syntax version the document was authored for |
| **Placement** | Root-level field, immediately after `kind:` |

The `testlab` field is required on **every** YAML document (both `kind: tck` and `kind: test`). It pins the document to a specific version of the TestLab syntax and toolchain. The compiler and Player use this to:

- **Reject** if the running TestLab version does not support the declared syntax version (e.g. document declares `testlab: v2` but runner only supports `v1`)
- **Select behavior** — future versions may change step signatures, variable resolution rules, or package format. The `testlab` field ensures deterministic interpretation.
- **Validate consistency** — all documents in a TCK must declare the same `testlab` version. Mismatches produce a compile-time error.
- **Record** in the compiled `.tckpkg` manifest for traceability

| Check | When | Behavior |
|-------|------|----------|
| Unsupported version | Compile or run | Error: `Document requires testlab v2, running testlab v1 — upgrade required` |
| Matching version | Compile or run | Proceed normally |
| Newer runner, older document | Compile or run | Warning: `Document authored for testlab v1-alpha, running v2 — verify compatibility` |
| Version mismatch within TCK | Compile | Error: `Test '{id}' declares testlab v1 but TCK manifest declares v1-alpha` |

**Rules:**

1. **Must match a TCK namespace** — a test's `namespace` must exactly equal the `namespace:` field of a `kind: tck` manifest.
2. **Kebab-case only** — lowercase letters, digits, and hyphens. No slashes, dots, or underscores.
3. **Required on all documents** — both TCK manifests and test files must declare `namespace`.
4. **One namespace per file** — a test file belongs to exactly one TCK. No multi-namespace tests.

**Compiler behavior:**

| Check | When | Error |
|-------|------|-------|
| Syntax validation | Always | `namespace must match pattern ^[a-z][a-z0-9-]*$` |
| Membership validation | When compiling a TCK manifest | `test "{file}" declares namespace "{ns}" but is included in TCK with namespace "{tck_ns}"` |
| Orphan detection | When compiling a standalone test | Warning: `test declares namespace "{ns}" — ensure matching TCK manifest exists` |
| Environment resolution | Always | The compiler uses `namespace` to locate the parent TCK and inherit its `env:` block |

**Rationale:**

- **Explicit ownership**: A test file is self-describing — you can read its namespace and know which TCK it belongs to without checking directory structure or manifest listings.
- **Standalone loading**: Tools (IDE, CLI) can load a single test file and resolve its environment by looking up the TCK with the matching `namespace`.
- **Compiler safety**: Prevents accidental inclusion of a test in the wrong TCK manifest — the namespace mismatch is caught at compile time.

```yaml
kind: test
testlab: v1-alpha

id: available-notification
namespace: ccm-v0.0.1

metadata:
  name: "Available Notification"
  version: "1.0"
  description: >
    Test CX-0135 AVAILABLE notification: send availability notification to SUT
    and verify SUT subsequently pulls the certificate from TestLab.

setup:
  - id: gen_id
    uses: util/generate_uuid
    name: Generate asset ID
    returns:
      generated_id:
        type: string
        class: Uuid4
  - id: certificate_callback
    name: Expose Certificate Management API
    uses: mock/api
    with:
      method: GET
      path: /api/v1/companycertificate/available
      response_status: 200
      response_body: 
        businessPartnerNumber: "@provider_bpn"
        certificateType: "@certificate_type"
        registrationNumber: "CERT-AVAIL-001"
        enclosedSites:
          - enclosedSiteBpn: "@location_bpns"
        validFrom: "2026-01-01"
        validUntil: "2028-12-31"
        trustLevel: "none"
        document:
          documentID: "cert-asset-001"
          creationDate: "2026-01-01T00:00:00Z"
          contentType: "application/pdf"
          contentBase64: "iVBORw0KGgoAAAANSUhEUgA="
        validator:
          validatorName: "TÜV SÜD"
          validatorBpn: "BPNL133631123120"
        type:
          certificateVersion: "2015"
          certificateType: "@certificate_type"
        areaOfApplication: "Quality Management"
        issuer:
          issuerName: "TÜV SÜD"
          issuerBpn: "BPNL133631123120"
    returns:
      mock:
        type: class
        class: MockInstance
      base_mock_url:
        type: string
      full_mock_url:
        type: string

steps:
  - id: create_asset_1
    uses: connector/provider/create_asset
    name: Create the test asset
    with:
      asset_id: ${{ setup.gen_id.generated_id }}
      description: "Test asset"
      connector_service: ${{ env.services.provider.connector_service}}
    returns:
      asset_id:
        type: string
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200
      - uses: validate/field
        with:
          input: response_body
          path: "id"
          operator: equals
          value: ${{ setup.gen_id.generated_id }}

  - id: get_asset_1
    uses: connector/provider/get_asset
    name: Retrieve the created asset
    with:
      asset_id: ${{ steps.create_asset_1.asset_id }}
      connector_service: ${{ env.services.provider.connector_service}}
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200
      - uses: validate/field
        with:
          input: response_body
          path: "id"
          operator: equals
          value: ${{ steps.asset_id }}

  - id: wait_for_call
    uses: mock/wait/http_request
    name: Wait for provider RECEIVE acknowledgment
    with:
      mock: ${{ steps.certificate_callback.mock }}
      timeout_s: 60
    returns:
      request_method:
        type: string
      request_headers:
        type: object
      request_body:
        type: object
      query_params:
        type: object
      elapsed_ms:
        type: integer
      
    validate:
      - uses: validate/assert
        with:
          input: request_method
          operator: equals
          value: "POST"
      - uses: validate/field
        with:
          input: request_body
          path: "header.messageId"
          operator: matches_regex
          value: "^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
      - uses: validate/field
        with:
          input: request_body
          path: "header.context"
          operator: equals
          value: "CompanyCertificateManagement-CCMAPI-Status:1.0.0"
      - uses: validate/field
        with:
          input: request_body
          path: "header.sentDateTime"
          operator: not_null
      - uses: validate/field
        with:
          input: request_body
          path: "header.senderBpn"
          operator: matches_regex
          value: "^BPNL[0-9A-Z]{12}$"
      - uses: validate/field
        with:
          input: request_body
          path: "header.receiverBpn"
          operator: equals
          value: ${{ env.consumer_bpn }}
      - uses: validate/field
        with:
          input: request_body
          path: "header.version"
          operator: equals
          value: "3.1.0"
      - uses: validate/field
        with:
          input: request_body
          path: "content.certificateStatus"
          operator: one_of
          value:
            - "RECEIVED"
            - "ACCEPTED"
            - "REJECTED"

teardown:
  - id: export_asset_id
    uses: util/export_env
    name: Export asset ID to TCK environment
    with:
      variable: last_asset_id
      value: ${{ steps.create_asset_1.asset_id }}
  - id: delete_asset_1
    uses: connector/delete_asset
    name: Clean up test asset
    with:
      asset_id: ${{ steps.create_asset_1.asset_id }}
      service: ${{ env.services.provider }}
```

##### Test Document Structure

A `kind: test` document has the following root-level fields:

| Field | Required | Description |
|-------|----------|-------------|
| `kind` | Yes | Always `test` |
| `namespace` | Yes | Must match the `namespace` of the parent TCK manifest |
| `id` | Yes | Machine-readable identifier, unique within the namespace |
| `metadata` | Yes | Document metadata (see below) |
| `setup` | No | Steps executed before the test (preparation phase) |
| `steps` | Yes | The main test steps (execution phase) |
| `teardown` | No | Steps executed after the test (cleanup phase, runs even on failure) |

##### Test `metadata` Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Human-readable test display name |
| `version` | No | Test version (informational, not used by compiler) |
| `description` | No | Multi-line description of what the test validates |
| `tags` | No | Free-form labels for filtering (same rules as TCK `tags`) |

Tests do **not** declare `authors`, `copyright_holders`, `license`, `standards`, or `dataspace_version` — these are inherited from the parent TCK manifest via `namespace` resolution. However, tests **must** declare `testlab` at the root level (same value as the parent TCK).

##### Test Lifecycle Phases

| Phase | Field | Execution | On failure |
|-------|-------|-----------|------------|
| Setup | `setup:` | Runs first, in order | Test is skipped, teardown still runs |
| Execution | `steps:` | Runs after setup, in order | Test fails, teardown still runs |
| Teardown | `teardown:` | Runs last, always | Failures are reported but don't mask step failures |

Each phase contains a list of steps following the same step syntax (see Section 5).

##### `util/export_env` — Exporting Variables to TCK Environment

The `util/export_env` step writes a value back to the TCK's `env.variables` block, making it available to subsequent tests in the same TCK run. This is primarily used in `teardown:` to propagate state (e.g., IDs created during the test) to later tests that depend on it.

```yaml
- id: export_asset_id
  uses: util/export_env
  name: Export asset ID to TCK environment
  with:
    variable: last_asset_id
    value: ${{ steps.create_asset.asset_id }}
```

| Field | Required | Description |
|-------|----------|-------------|
| `variable` | Yes | Target key in `env.variables` (created if not present) |
| `value` | Yes | The value to export (string, resolved from `${{ }}` expressions) |

**Rules:**

- The exported variable becomes available as `${{ env.variable_name }}` in all subsequent tests.
- If the variable already exists in `env.variables`, it is overwritten.
- Export only runs if the teardown step executes — if the test is skipped entirely (setup failure), no export occurs.
- The compiler validates that `variable` is a valid identifier (`^[a-z][a-z0-9_]*$`).

**Use cases:**

| Scenario | Example |
|----------|--------|
| Pass created resource IDs to later tests | `variable: contract_id, value: ${{ steps.negotiate.contract_id }}` |
| Record test outcomes for conditional logic | `variable: asset_exists, value: "true"` |
| Chain cleanup across tests | `variable: cleanup_asset_id, value: ${{ steps.asset_id }}` |

#### 7.3 Schema File (Standard JSON Schema)

Schema files are **standard JSON Schema** documents (not YAML, not a custom format). They are referenced by name in the TCK manifest's `env.schemas` block and used by `validate/schema` assertions.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "asset_schema",
  "description": "JSON Schema for connector asset response",
  "type": "object",
  "required": ["@id", "@type"],
  "properties": {
    "@id": {
      "type": "string",
      "pattern": "^[0-9a-f-]{36}$"
    },
    "@type": {
      "type": "string",
      "enum": ["connector:Asset"]
    }
  }
}
```

**Rules:**

- Schema files use `.json` extension and standard JSON Schema syntax.
- No `kind:` field — these are plain JSON Schema documents, not TestLab YAML.
- Referenced in TCK manifest as: `asset_schema: schemas/asset.json`
- The compiler validates that referenced schema files exist and are valid JSON Schema.

### 8. Import Rule

Tests inherit **ALL** environment from the TCK manifest identified by their `namespace` field:

- All `env.variables` — available as `${{ env.x }}`
- All `env.services` — referenceable by name in `with:` blocks or via `${{ env.services.name }}`
- All `env.schemas` — available as `${{ env.schemas.name }}`

**Service implicit returns:** Each service defined in `env.services` implicitly generates a return variable with `type: object` and `class` derived from the `uses` action name. For example, a service with `uses: service/connector_service` produces a typed variable with `class: ConnectorService`. This makes the service selectable as a typed input in step `with:` blocks (e.g., `connector_service: ${{ env.services.provider.connector_service}}` or `service: ${{ env.services.provider }}`).

The `namespace` field is the key the compiler uses to resolve which TCK provides the inherited `env:` block. A test's `namespace` must match the `namespace` of exactly one TCK manifest. Both documents use the same keyword — symmetric and unambiguous.

There is no cherry-picking or partial import. A test file does not declare its own `env:` — it inherits from the TCK.

**Rationale:** Cherry-picking creates divergence. If a test needs a variable, it belongs in the TCK manifest. This keeps the environment centralized and auditable. The `namespace` makes this relationship explicit and machine-verifiable.

### 9. `uses:` Namespace Registry

Step types follow a hierarchical namespace pattern: `namespace/[sub-namespace/]action`.

**Naming conventions:**

- Namespaces use lowercase path segments separated by `/`
- Actions use `snake_case`
- Sub-namespaces group related operations within a domain (e.g., `connector/provider/` vs `connector/consumer/`)
- The full `uses:` value is the canonical step type identifier

#### 9.1 Namespace Table

| Namespace | Purpose | Actions |
|-----------|---------|--------|
| `connector/provider/` | Provider-side connector connector operations | `create_asset`, `create_policy`, `create_contract_definition` |
| `connector/consumer/` | Consumer-side connector connector operations | `negotiate`, `initiate_transfer`, `get_catalog` |
| `connector/http/` | Dataplane HTTP operations | `call_via_dataplane` |
| `http/` | Generic HTTP calls | `call` |
| `mock/` | Mock server operations | `endpoint`, `wait/request`, `dtr`, `discovery` |
| `service/` | Service definitions | `connector_service`, `mock_server`, `discovery_service` |
| `util/` | Utility operations | `generate_uuid`, `wait`, `set_env`, `export_env`, `extract_query_param` |
| `validate/` | Validation/assertion operations | `assert`, `field`, `query_param`, `object`, `schema` |
| `notification/` | Notification operations | `send`, `receive` |
| `flow/` | Flow control | `if`, `loop`, `parallel` |

#### 9.2 Examples

```yaml
uses: connector/provider/create_asset
uses: connector/consumer/negotiate
uses: connector/dataplane/http_request
uses: http/request
uses: mock/api
uses: mock/wait/http_request
uses: util/generate_uuid
uses: util/set_env
uses: util/export_env
uses: util/extract_query_param
uses: validate/field
uses: validate/assert
uses: validate/schema
uses: validate/query_param
uses: notification/send
uses: flow/if
```

#### 9.3 Extensibility

New namespaces and actions can be added without breaking existing tests. The schema enum in `docs/specification/schemas/test-file.schema.json` is the authoritative source of valid `uses:` values. The compiler rejects unknown step types at compile time.

---

## Compiler Rules

The compiler validates YAML files and rejects invalid documents with actionable error messages.

### Structural Validation

| Rule | Error Message |
|------|---------------|
| Missing `kind:` | `Missing required field 'kind' at document root` |
| Unknown `kind:` value | `Invalid kind: '{value}'. Expected: tck, test` |
| Missing `steps:` in test | `Test file must contain a 'steps' field` |
| Missing `tests:` in TCK | `TCK manifest must contain a 'tests' field` |
| Empty `steps:` array | `'steps' must contain at least one step` |
| Step missing `id:` | `Step at index {n} is missing required field 'id'` |
| Step missing `uses:` | `Step '{id}' is missing required field 'uses'` |
| Step missing `name:` | `Step '{id}' is missing required field 'name'` |

### ID Validation

| Rule | Error Message |
|------|---------------|
| Invalid ID pattern | `Step ID '{id}' does not match pattern [a-z][a-z0-9_]{0,49}` |
| Duplicate ID | `Duplicate step ID '{id}' — first defined at step index {n}` |
| Reserved word | `Step ID '{id}' is a reserved word` |

### Variable Resolution

| Rule | Error Message |
|------|---------------|
| Unresolved `steps.x` | `Unresolved variable 'steps.{x}' in step '{id}' — no preceding step returns '{x}'` |
| Ambiguous `steps.x` | `Ambiguous variable 'steps.{x}' in step '{id}' — returned by [{ids}]. Use: ${{{{ steps.{first_id}.{x} }}}}` |
| Unresolved qualified ref | `Unresolved reference 'steps.{step_id}.{x}' — step '{step_id}' does not return '{x}'` |
| Step ID not found | `Unknown step ID '{step_id}' in variable reference 'steps.{step_id}.{x}'` |
| Forward reference | `Forward reference in step '{id}' — step '{ref_id}' is defined after current step` |
| Unresolved `env.x` | `Unresolved environment variable 'env.{x}' — not defined in TCK manifest env.variables` |
| Unresolved schema | `Unresolved schema 'env.schemas.{name}' — not defined in TCK manifest env.schemas` |
| Unresolved `metadata.x` | `Unresolved metadata field 'metadata.{x}' — not defined in TCK manifest metadata block` |
| Unresolved `execution.x` (built-in) | `Unresolved execution variable 'execution.{x}' — not a recognized built-in key. Built-in keys: id, tck_id, timestamp, runner` |
| Uninjected `execution.x` (custom) | Warning: `execution.{x} is not a built-in key — ensure it is injected at runtime via --set or execution_context` |

### Returns Validation

| Rule | Error Message |
|------|---------------|
| Missing `type:` in return | `Return '{name}' in step '{id}' is missing required field 'type'` |
| Missing `class:` in return | `Return '{name}' in step '{id}' is missing required field 'class'` |
| Invalid `type:` value | `Invalid type '{value}' for return '{name}' in step '{id}'. Expected: string, integer, boolean, object, array` |
| Unknown `class:` value | `Unknown class '{value}' for return '{name}' in step '{id}'. See classes.json for valid classes` |
| Duplicate return name | `Duplicate return name '{name}' in step '{id}'` |

### Validate Block

| Rule | Error Message |
|------|---------------|
| Invalid `uses:` value | `Unknown assertion type '{value}' in validate block of step '{id}'. Expected: validate/assert, validate/field, validate/object, validate/schema` |
| Missing `with:` | `Assertion at index {n} in step '{id}' is missing required field 'with'` |
| Missing required field | `Assertion '{uses}' at index {n} in step '{id}' is missing required field '{field}' in 'with'` |
| Unknown operator | `Unknown operator '{op}' in assertion at index {n} in step '{id}'` |

---

## IDE Serialization Rules

The IDE (Blockly workspace → YAML) MUST follow these rules when serializing:

1. **Field order**: Always emit `id → uses → name → with → returns → validate`.
2. **ID generation**: auto-generate from `uses` value + incrementing suffix (e.g., `create_asset_1`).
3. **Empty blocks omitted**: Do not emit `with:`, `returns:`, or `validate:` if they have no content.
4. **String quoting**: Quote strings containing special characters (`${{ }}`, `:`, `#`, `{`, `}`). Do not quote plain strings.
5. **Indentation**: 2 spaces, no tabs.
6. **Document separator**: Each file starts with `kind:` — no `---` separator needed (single-document files).
7. **Variable serialization**: Always emit the flat form `${{ steps.x }}` unless the compiler has previously flagged ambiguity for that variable name.

---

## Runtime Execution Rules

The runtime (Python player) executes steps with these semantics:

1. **Sequential by default**: Steps execute top-to-bottom within each phase.
2. **Phase order**: `preconditions` → `setup` → `steps` → `teardown`.
3. **Returns auto-persist**: After successful step execution, all declared `returns` are stored in the test memory dict keyed by `{step_id}.{name}` and also by flat `{name}`.
4. **Failure handling**: If a step fails, its `returns` are NOT stored. Subsequent steps referencing those returns receive `null`.
5. **Teardown always runs**: Even if `steps` fail, `teardown` executes (best-effort cleanup).
6. **Validate execution**: Assertions in `validate:` run immediately after the step completes. Each assertion is resolved via its `uses:` type and executed with its `with:` parameters. A failed assertion marks the step as failed but does NOT abort the test — remaining steps still execute (fail-continue mode).
7. **Environment modifiable via `util/set_env`**: `env` variables can only be changed through the `util/set_env` step — no other step type can mutate them. The modification updates the in-memory env state and is reflected in the IDE's environment panel (marked as "modified"). Persistence to disk follows normal save semantics.

---

## Migration Guide: v1 → v2

### Keyword Mapping

| v1 Syntax | v2 Syntax | Notes |
|-----------|-----------|-------|
| `type: create_asset` | `uses: connector/create_asset` | Namespace prefix added |
| `params:` | `with:` | Direct rename |
| `@variable_name` | `${{ steps.variable_name }}` | Expression syntax |
| `store_in_memory: key` | `returns:` block | Declares type and class |
| (no equivalent) | `id:` | New required field |
| (no equivalent) | `validate:` | Replaces external assertions |

### Automated Migration

The CLI provides a migration command:

```bash
testlab migrate v1-to-v2 --input tests/ --output tests-v2/
```

Migration steps performed automatically:

1. `type: x` → `uses: {namespace}/x` (namespace inferred from step registry)
2. `params:` → `with:`
3. `@var` → `${{ steps.var }}`
4. `store_in_memory: key` → `returns:` with `type: string`, `class: String` (conservative defaults — user should refine)
5. auto-generate `id:` from step type + index
6. Wrap file in `kind: test` structure
7. Extract environment to TCK manifest `kind: tck`

### Manual Steps Required After Migration

- Review and correct `class:` values on all `returns` (migration uses `string` as default).
- Review and correct `type:` values on all `returns`.
- Verify auto-generated `id:` values are meaningful.
- Add `validate:` blocks where assertions were previously external.
- Create `schemas/` files for any JSON Schema validations.

---

## Full Example: End-to-End TCK

### `tck.yaml`

```yaml
kind: tck
testlab: v1-alpha

id: certificate-management-tck
namespace: ccm-v0.0.1

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
    - name: Mathias Moser
      email: mathias.moser@catena-x.net
      company: Catena-X Automotive Network e.V.
  copyright_holders:
    - "2026 Catena-X Automotive Network e.V."
  license: Apache-2.0
  standards:
    - id: CX-0135
      version: v3.1.0
  tags:
    - CCM
  dataspace_version: saturn

env:
  variables:
    provider_url: "https://provider.local/management"
    consumer_url: "https://consumer.local/management"
    provider_bpn: "BPNL000000000001"
    consumer_bpn: "BPNL000000000002"
    callback_url: "https://testlab.local/callback"
  
  schemas:
    certificate_schema:
      file: business_partner_certificate_schema.json
    notification_header_schema:
      file: notification_header.json
  testdata:
    available_notification:
      file: available_notification.json
      type: application/json
    sample_certificate:
      file: sample_certificate.pdf
      type: application/pdf

# Preconditions specification: see ADR-0012
preconditions: []

tests:
  - tests/asset-crud.yaml
  - tests/contract-negotiation.yaml
```

### `tests/contract-negotiation.yaml`

```yaml
kind: test
testlab: v1-alpha

id: negotiate-contract
namespace: ccm-v0.0.1

metadata:
  name: "Contract Negotiation Happy Path"
  description: Negotiate a contract and verify agreement is created

setup:
  - id: gen_asset_id
    uses: util/generate_uuid
    name: Generate unique asset ID
    returns:
      generated_id:
        type: string
        class: Uuid

  - id: create_asset
    uses: connector/create_asset
    name: Create provider asset
    with:
      asset_id: ${{ steps.generated_id }}
      connector_service: ${{ env.services.provider.connector_service}}
    returns:
      asset_id:
        type: string
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200

  - id: create_policy
    uses: connector/create_policy
    name: Create access policy
    with:
      connector_service: ${{ env.services.provider.connector_service}}
      policy:
        type: open
    returns:
      policy_id:
        type: string
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200

  - id: create_contract_definition
    uses: connector/create_contract_definition
    name: Create contract definition
    with:
      asset_id: ${{ steps.asset_id }}
      access_policy_id: ${{ steps.policy_id }}
      contract_policy_id: ${{ steps.policy_id }}
      connector_service: ${{ env.services.provider.connector_service}}
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200

steps:
  - id: query_catalog
    uses: connector/query_catalog
    name: Query provider catalog from consumer
    with:
      provider_url: ${{ env.provider_url }}
      connector_service: ${{ env.services.consumer.connector_service}}
    returns:
      offer_id:
        type: string
        class: OfferId
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200
      - uses: validate/schema
        with:
          input: response_body
          schema: ${{ env.schemas.catalog_response }}

  - id: negotiate
    uses: connector/negotiate
    name: Initiate contract negotiation
    with:
      offer_id: ${{ steps.offer_id }}
      provider_url: ${{ env.provider_url }}
      connector_service: ${{ env.services.consumer.connector_service}}
    returns:
      negotiation_id:
        type: string
      agreement_id:
        type: string
    validate:
      - uses: validate/assert
        with:
          input: status_code
          operator: equals
          value: 200
      - uses: validate/assert
        with:
          input: agreement_id
          operator: not_null

teardown:
  - id: delete_asset
    uses: connector/delete_asset
    name: Remove test asset
    with:
      asset_id: ${{ steps.create_asset.asset_id }}
      service: ${{ env.services.provider }}
```

---

## Consequences

### Positive

- **Instant familiarity**: Developers who know GitHub Actions can read TestLab YAML without documentation.
- **Steps are functions**: `uses` + `with` + `returns` maps cleanly to function call semantics.
- **Compile-time safety**: Variable resolution is fully validated before execution — no runtime surprises.
- **IDE-friendly**: The canonical field order and auto-generated IDs make serialization deterministic.
- **Extensible**: New step namespaces and variable scopes can be added without syntax changes.
- **Typed outputs**: `returns` with `type` and `class` enable IDE filtering (ADR-0009) and documentation.

### Negative

- **Breaking change from v1**: All existing YAML files must be migrated (mitigated by CLI tool).
- **Verbosity increase**: `${{ steps.x }}` is longer than `@x` (mitigated by IDE auto-completion).
- **Learning curve for `${{ }}`**: Users unfamiliar with GHA must learn expression syntax (mitigated by IDE doing the heavy lifting).
- **Strict ordering**: Canonical field order adds one more thing the compiler must validate.

### Risks

| Risk | Mitigation |
|------|-----------|
| v1 YAML files break silently | Compiler detects `type:` and `params:` as v1 markers → emits "This appears to be v1 syntax. Run `testlab migrate v1-to-v2`." |
| Users forget `returns:` metadata | IDE blocks auto-declare returns from block JSON — user never writes them manually |
| Schema files drift from actual API | Schema validation is optional (only when `schema` operator is used in `validate:`) |
| Qualified variable syntax is verbose | IDE defaults to flat form; only switches to qualified on ambiguity |

---

## Appendix A: V2 Syntax Revisions (2026-07)

The following changes were applied to the V2 syntax after the original acceptance. Each is
traceable to a specific ADR or PR.

### A.1 Keyword Renames

| Original (§1) | Current V2 | Reason |
|----------------|------------|--------|
| `testlab:` (syntax version marker) | `syntax: v2` | Decouples the product name from the format identifier. Files declare `syntax: v2` at root. |
| `steps:` (main execution phase) | `execution:` | Avoids collision with the `${{ steps.x }}` variable scope — `steps` is a variable namespace, `execution` is the phase keyword. |
| `namespace:` (required) | `namespace:` (optional in V2) | V2 TCK manifests infer namespace from the `id` field. When present it is honoured; when absent the compiler uses `""`. |
| `preconditions:` (TCK-level) | **Removed** | See ADR-0021. Replaced by complex variables in `env.variables`. |

The compiler accepts both `steps:` (V1 compat) and `execution:` (V2) in test files.
The JSON schema (`tck_test.schema.json`) uses a `oneOf` requiring exactly one of them.

### A.2 `env.schemas` and `env.testdata` — List Format

V1 used a dict keyed by name:

```yaml
env:
  schemas:
    certificate_schema:
      file: business_partner_certificate_schema.json
```

V2 accepts a **list of `{id, source}` objects**:

```yaml
env:
  schemas:
    - id: certificate_schema
      source: business_partner_certificate_schema.json
```

The compiler and runner accept both formats (dict and list). The list format is canonical for
new V2 manifests.

### A.3 Variable Lifecycle (amends §3.3)

The `preconditions (TCK-level)` row in the Variable Lifecycle table is removed. The revised
visibility model:

| Phase | Visibility |
|-------|-----------|
| `setup` steps | Visible to `execution` and `teardown` |
| `execution` steps | Visible to subsequent `execution` steps and `teardown` |
| `teardown` | Can reference all preceding variables |
| `env` variables (TCK-global) | Visible everywhere — includes complex variables (`uses:`/`with:`/`returns:`) |

Complex variables defined in `env.variables` with a `uses:` verb (e.g. `config/connector/policy`)
are resolved at TCK load time and their `returns:` fields are accessible as
`${{ env.<variable_id>.<field> }}`. See ADR-0021 §3.

### A.4 `infrastructure.*` Variable References

Steps MAY reference infrastructure variables directly using `${{ infrastructure.<side>.<capability>.<field> }}`.
This is a convenience shorthand documented by ADR-0019 §4 amendment: the player seeds these from
the operator's binding profile before execution begins. Example:

```yaml
with:
  connector_service: ${{ infrastructure.engine.connector }}
  counter_party_address: ${{ infrastructure.sut.connector.dsp_url }}
```

### A.5 Deprecated Verb Rejection (Compiler)

The compiler rejects any step using a verb prefix listed in the deprecated verbs registry.
As of ADR-0021, `precondition/*` is the only deprecated prefix. The error message includes
the ADR reference and a migration path.

---

## References

- [ADR-0009: Typed Variable Class System](ADR-0009-typed-variable-class-system.md) — defines `class` taxonomy used in `returns:`
- [ADR-0021: Remove Precondition Concept](ADR-0021-remove-precondition-concept.md) — removes `preconditions:` and `precondition/*` verbs
- [ADR-0019: Service Requirements and Engine Bindings](../backend/ADR-0019-service-requirements-and-engine-bindings.md) — infrastructure topology
- [GitHub Actions Workflow Syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) — inspiration source
- [Product Scope](../../product-scope.md) — lifecycle: IDE → YAML → compile → execute → feedback
