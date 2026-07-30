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

# ADR-0016: Execution Trace Format — CloudEvents Hybrid Envelope

## Status

Proposed

## Date

2026-05-28

## Context

The TestLab player emits execution traces for:

- **Observability**: streaming progress to the IDE via SSE
- **Debugging**: inspecting step-level inputs, outputs, and validation results
- **Audit**: immutable record of what ran, what passed, and what failed
- **Tooling**: log aggregator ingestion (ELK, Loki, Datadog) without custom transformers

Traces are delivered to the IDE frontend over Server-Sent Events (SSE) and persisted as JSONL files. The format must be self-contained, streamable, and interoperable with existing observability infrastructure.

The previous v2 format (flat JSONL with a header line) coupled trace identity to file-level context, making it unsuitable for single-stream TCK runs where multiple tests and lifecycle phases interleave. A CloudEvents-based envelope provides per-event identity, standard typing, and ecosystem compatibility.

!!! note "Prerequisites are Variables, not Preconditions"
    Everything a test needs before its steps run is a **Variable** (see
    [ADR-0018](../shared/ADR-0018-unified-variables-model.md) and
    [ADR-0021](../shared/ADR-0021-remove-precondition-concept.md)). The separate precondition
    concept was removed. The trace therefore emits `tck.variable.*` resolution events
    (not `tck.precondition.*`), and infrastructure that the engine or SUT must provide is
    validated as a **binding** at boot (`tck.boot.binding.*`, see
    [ADR-0019](ADR-0019-service-requirements-and-engine-bindings.md)).

## Decision

Every trace line is a **CloudEvents v1.0** JSON object with domain-specific extensions (`sequence`, nested `data`). The format is a hybrid: CloudEvents envelope for interoperability, domain `data` for TestLab semantics.

### Envelope Fields

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `specversion` | `"1.0"` | Fixed | CloudEvents spec version |
| `id` | `string` | Computed | Structured path ID (see below) |
| `source` | `string` | Step `uses` | Emitting component (step type or lifecycle source) |
| `type` | `string` | Event verb | Lifecycle event type from the taxonomy |
| `time` | `string (ISO 8601)` | Clock | Event emission timestamp |
| `sequence` | `integer` | Counter | Global monotonic counter (1-based across the entire TCK run) |
| `data` | `object` | Domain | Event-specific payload |

### The `id` Convention

Event IDs encode structural context as path segments:

| Scope | Format | Example |
|-------|--------|---------|
| TCK lifecycle | `<tckid>/<type>/<hash>` | `cert-mgmt-tck/tck.start/a3f8c1d27e4b` |
| Boot binding | `<tckid>/infrastructure/<side>.<capability>/<type>/<hash>` | `cert-mgmt-tck/infrastructure/engine.connector/tck.boot.binding.passed/c5f0b3d42e8a` |
| Boot service | `<tckid>/infrastructure/<side>.<capability>/<type>/<hash>` | `cert-mgmt-tck/infrastructure/engine.connector/tck.boot.service.ready/d6a1c4e53f9b` |
| Variable | `<tckid>/env/variables/<varname>/<type>/<hash>` | `cert-mgmt-tck/env/variables/sut_connector/tck.variable.resolved/6f3ad5c128e4` |
| Test lifecycle | `<tckid>/<testid>/<type>/<hash>` | `cert-mgmt-tck/catalog-policy-validation/tck.test.passed/c59034276e4a` |
| Test step | `<tckid>/<testid>/<stepid>/<type>/<hash>` | `cert-mgmt-tck/catalog-policy-validation/pull_data_1/tck.test.step.passed/b48f2a165d39` |

The trailing `<hash>` is a 12-character hex string (blake2b of `data`) that disambiguates emissions with otherwise identical paths.

### The `source` Convention

| Context | Source value | Example |
|---------|-------------|---------|
| Step execution | Step's `uses` value | `connector/pull_data_filtered`, `validate/assert` |
| Variable resolution | Variable's `uses` value, or `testlab/player/variables` | `config/connector/policy`, `testlab/player/variables` |
| TCK lifecycle | `testlab/player/lifecycle` | — |
| Boot / binding | `testlab/player/boot` | — |

### Type Taxonomy

#### TCK Lifecycle Events

| `type` | `data` shape | Description |
|--------|-------------|-------------|
| `tck.start` | `{tck_id, namespace, metadata, environment, service, run_id}` | TCK run begins |
| `tck.boot.start` | `{manifest, compiler_version}` | Boot phase begins |
| `tck.boot.requirements` | `{dataspace, infrastructure}` | Declares the required/optional capabilities per side |
| `tck.boot.binding.start` | `{side, capability}` | Binding validation begins (`side` ∈ `engine` \| `sut`) |
| `tck.boot.binding.passed` | `{side, capability, outputs, duration_ms}` | Binding reachable and valid |
| `tck.boot.binding.failed` | `{side, capability, errors, duration_ms}` | Binding missing or unreachable |
| `tck.boot.service.start` | `{side, capability}` | Engine starts the service backing a capability |
| `tck.boot.service.ready` | `{side, capability, outputs?, duration_ms}` | Service started and ready |
| `tck.boot.service.failed` | `{side, capability, errors, duration_ms}` | Service failed to start |
| `tck.boot.passed` | `{duration_ms, assets_resolved, bindings, services}` | Boot succeeded |
| `tck.boot.failed` | `{duration_ms, errors}` | Boot failed |
| `tck.tests.planned` | `{tests: [<test_id>, ...]}` | Ordered test execution plan |
| `tck.end` | `{status, total, passed, failed, skipped, duration_ms, labels}` | TCK run complete |

#### Boot Requirements Event

`tck.boot.requirements` is emitted once, right after `tck.boot.start`, before any binding or
service. It publishes the resolved topology (ADR-0019) so the operator and the IDE know up front
what each side must provide — e.g. that the SUT must expose **both** a connector and a DTR. Each
capability carries its `required` flag: `true` is **enabled** (the run needs it), `false` is
**disabled** (declared but not exercised this run). The shape mirrors the manifest `infrastructure:`
block exactly:

```json
{
  "dataspace": { "ecosystem": "Catena-X", "version": "saturn" },
  "infrastructure": {
    "engine": { "connector": { "required": true }, "dtr": { "required": false } },
    "sut":    { "connector": { "required": true }, "dtr": { "required": true } }
  }
}
```

A capability with `required: true` is then either validated as a binding (engine side) or resolved
as a variable (SUT side); a `required: false` capability emits no further boot events.

#### Boot Binding Events

Every required `infrastructure.<side>.<capability>` (ADR-0019) is validated and **injected** at
boot, one `tck.boot.binding.*` triple per capability. Engine-side bindings (the EDC connector and
the DTR) are resolved from the operator binding profile and injected into the player here — this is
the single place the concrete EDC/DTR configuration enters the run. Steps never carry it (ADR-0019
§4); they reference only variables, and the player drives the injected engine service implicitly.

`tck.boot.binding.passed.outputs` records the **resolved, non-secret** configuration so the run is
reproducible from the trace alone:

| Engine capability | Typical `outputs` (clear) | Encrypted (`$jwe`) |
|-------------------|---------------------------|--------------------|
| `connector` | `status`, `version`, `dsp_url`, `management_url`, `bpn` | `auth` (api key / client secret / token) |
| `dtr` | `status`, `version`, `base_url` | `auth` (api key / OAuth2 client secret) |

Secret binding fields (`auth`, `api_key`, `client_secret`, credentials) are **never** emitted in
clear — they are JWE-encrypted under a `$jwe` key per [Secret Protection](#secret-protection),
exactly like sensitive step outputs. A `tck.boot.binding.failed` carries `errors` only, no config.

#### Boot Service Events

A **binding** validates and injects an *external* endpoint; a **service** is the engine-operated
component the player *starts* per run to drive that capability — for example the engine's connector
client that uses the injected EDC config. A service is addressed by the **same**
`infrastructure.<side>.<capability>` path as its binding (ADR-0019), exactly as written in the
manifest YAML: `{side, capability}` in `data`, `infrastructure/<side>.<capability>` in the `id`. The
same capability therefore appears once under `bindings` (its endpoint was validated) and once under
`services` (its client was started). A service `start` follows the binding it depends on (the client
needs its injected config first).

The **mock server is part of the testlab backend**, not a per-run service: it is already running
before any run begins, so it emits **no** `tck.boot.service.*` events and never appears in
`tck.boot.passed.services`. Its endpoints surface where they are used, not as a boot service.

| Capability | `start` data | `ready` data |
|------------|-------------|--------------|
| `engine.connector` | `{side: "engine", capability: "connector"}` | `{side, capability, outputs: {status}, duration_ms}` |

Any secret in service `outputs` follows the same `$jwe` rule. `tck.boot.passed` then lists
`bindings` (validated endpoints) and `services` (started components) separately, both addressed as
`infrastructure.<side>.<capability>`.

#### Variable Resolution Events

Prerequisites resolve in a single phase before tests, after boot. Each variable resolves to
exactly one **disposition** (`known` \| `request` \| `generate`, see
[ADR-0018](../shared/ADR-0018-unified-variables-model.md)). The `input.*` events fire only for the
`request` disposition.

| `type` | `data` shape | Description |
|--------|-------------|-------------|
| `tck.variable.resolve.start` | `{name, uses?, disposition, schema?}` | Variable resolution begins |
| `tck.variable.resolve.update` | `{name, state, ...context}` | Progress (long-running) |
| `tck.variable.resolved` | `{name, disposition, outputs, duration_ms}` | Variable resolved |
| `tck.variable.resolve.failed` | `{name, errors, duration_ms}` | Resolution failed |
| `tck.variable.resolve.skipped` | `{name, reason}` | Variable not needed |
| `tck.variable.input.required` | `{name, schema, prompt, correlation_id, input_prompts}` | Blocked on operator input |
| `tck.variable.input.received` | `{name, correlation_id, outputs}` | Operator input received |

#### Config Variable Schema

A variable bound to a **config capability** that publishes a config schema carries a `schema`
reference in its resolution events. Today this is `config/connector/policy`: the policy a test
must configure (e.g. the SUT access/usage policy) is a complex variable
([ADR-0018](../shared/ADR-0018-unified-variables-model.md)) whose value validates against the Catena-X policy
JSON Schema shipped in `ide/schemas/policies/`, selected by the run's `dataspace_version`:

| `dataspace_version` | Config schema `$id` |
|---------------------|---------------------|
| `saturn` | `https://w3id.org/catenax/2025/9/policy/schema/atomic-constraint-schemas.json` |
| `jupiter` | `urn:tractusx:testlab:policy:jupiter` |

The `schema` field is always a JSON-Schema **reference** — `{"$ref": "<config schema $id>"}` — never
an inline ad-hoc copy. Author, operator, and trace therefore validate the policy against one source
of truth (the same variables config schema the IDE authoring uses). It maps by disposition:

- `known` / `generate` — `tck.variable.resolve.start` carries `schema`, declaring the config schema
  the provided or generated `value` validates against.
- `request` — `tck.variable.input.required` carries that same config-schema `$ref` as its `schema`,
  so the operator UI renders the policy editor from the specified schema, not a hand-written one.

Variables with no published config schema (plain primitives, infrastructure-derived values) omit
`schema` entirely.


#### Test Lifecycle Events

| `type` | `data` shape | Description |
|--------|-------------|-------------|
| `tck.test.start` | `{test_id}` | Test begins |
| `tck.test.passed` | `{test_id, duration_ms, passed, failed, assertions}` | Test passed |
| `tck.test.failed` | `{test_id, duration_ms, passed, failed, assertions}` | Test failed |
| `tck.test.skipped` | `{test_id, reason}` | Test skipped |

#### Test Setup Events

| `type` | `data` shape | Description |
|--------|-------------|-------------|
| `tck.test.setup.start` | `{attempt}` | Start new setup like mock for example |

#### Test Step Events

| `type` | `data` shape | Description |
|--------|-------------|-------------|
| `tck.test.step.start` | `{attempt}` | Step execution begins |
| `tck.test.step.update` | `{attempt, state, ...context}` | Progress (long-running) |
| `tck.test.step.passed` | `{attempt, duration_ms, outputs, http?, validations}` | Step succeeded (terminal) |
| `tck.test.step.failed` | `{attempt, duration_ms, outputs?, http?, validations, errors}` | Step failed (terminal) |
| `tck.test.step.skipped` | `{attempt, reason}` | Step skipped |
| `tck.test.step.timeout` | `{attempt, duration_ms, timeout_ms}` | Step timed out |
| `tck.test.step.retry` | `{attempt, previous_attempt, reason}` | Retry initiated |

### Nested Validations

Validations are **nested inside the terminal step event** in `data.validations[]`. They are NOT separate CloudEvents. Each validation element:

```json
{
  "source": "validate/assert",
  "field": "edr_token",
  "inputs": {"assertion": "not_null", "expected": null},
  "outputs": {"actual": "...", "passed": true},
  "errors": []
}
```

| Field | Type | Description |
|-------|------|-------------|
| `source` | `string` | Validation step's `uses` value |
| `field` | `string` | Output field being validated from specific step |
| `inputs` | `object` | Assertion type + expected value |
| `outputs` | `object` | Actual value + `passed` boolean |
| `errors` | `array` | Present only on validation failure (with recommendations) |

**Rationale**: Validations are semantically part of the step result, not independent events. Nesting reduces event count and keeps the step result self-contained for IDE rendering.

### Nested HTTP Exchanges

The wire-level HTTP requests and responses a step performs are **nested inside the terminal step event** in `data.http[]`, parallel to `data.validations[]`. They are NOT separate CloudEvents. Each element captures one request/response exchange:

```json
{
  "exchange": "catalog_request",
  "request": {
    "method": "POST",
    "url": "https://testlab.local/management/v3/catalog/request",
    "headers": {"x-api-key": {"$jwe": "..."}, "content-type": "application/json"},
    "body": {"@type": "CatalogRequest", "counterPartyAddress": "..."}
  },
  "response": {
    "status": 200,
    "headers": {"content-type": "application/json"},
    "body": {"@id": "urn:catalog:sut-ccm-offers", "dcat:dataset": []},
    "duration_ms": 312
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `exchange` | `string` | Logical name of the exchange within the step (e.g. `catalog_request`, `contract_negotiation_poll`, `dataplane_pull`) |
| `request` | `object` | `{method, url, headers, body?}` of the outbound call |
| `response` | `object` | `{status, headers, body?, duration_ms}` of the inbound reply |

Sensitive header values (e.g. `x-api-key`, `authorization`) and sensitive body fields carry the JWE `$jwe` wrapper described in [Secret Protection](#secret-protection) — they are never logged in clear text. A failed exchange records the last observed `response` (e.g. a negotiation that stayed `REQUESTED` until timeout); the failure reason itself lives in `data.errors[]` / `data.validations[]`.

**Rationale**: HTTP exchanges are the evidence behind a step's `outputs`. Nesting them in the terminal event keeps the request/response trail self-contained for IDE inspection and offline audit, mirroring the `validations` nesting and avoiding a flood of separate wire-level events.

### Retry Handling

When a step is retried:

1. A `tck.test.step.retry` event fires with `{attempt: N, previous_attempt: N-1, reason: "..."}`
2. A new `tck.test.step.start` fires with `{attempt: N}`
3. The terminal event carries `{attempt: N, ...}` indicating which attempt produced the result

All attempts share the same `<tckid>/<testid>/<stepid>/` prefix — the trailing hash disambiguates.

### Secret Protection

All sensitive fields are encrypted using **standard JWE compact serialization** (RFC 7516) with `alg: "dir"` and `enc: "A256GCM"`. This is the single way secrets are protected — there is no redaction fallback.

Encryption applies to any output field marked sensitive (e.g. tokens, credentials) **and** any input field with `class: "secret"` (see [ADR-0017](ADR-0017-input-callback-endpoint.md)).

An encrypted field carries a JWE compact serialization string under a `$jwe` key. A JWE compact token is a 5-part base64url dotted string (`header.encrypted_key.iv.ciphertext.tag`; the `encrypted_key` segment is empty for `dir`):

```json
{
  "edr_token": {
    "$jwe": "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIiwia2lkIjoibG9jYWwtMjAyNi0wNS0yOCJ9..<iv>.<ciphertext>.<tag>"
  }
}
```

The `$jwe` field holds the JWE compact serialization string. Its protected header carries `alg`, `enc`, and `kid` (key id) — the `kid` enables rotation.

**Key management**: Keys are stored as a standard **JWKS** file (`~/.testlab/keys.jwks`, chmod 600) for local dev; CI provides the key via `TESTLAB_ENCRYPTION_KEY` (registered as a masked secret). The JWK `kid` enables rotation — old keys decrypt old traces.

**Library**: Python `jwcrypto` (built on `cryptography`; full JWE/JWK support).

> AES-GCM nonce uniqueness is handled by the JWE library per-encryption.

### Error Structure with Recommendations

Errors appear in two places:
- `data.errors[]` on the step event (step-level failures)
- `data.validations[].errors[]` on individual validation failures

Each error object:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | `string` | Yes | Machine-readable code (e.g. `NEGOTIATION_TIMEOUT`) |
| `message` | `string` | Yes | Human-readable: what failed, expected vs actual |
| `retryable` | `bool` | Yes | Whether the step can be retried |
| `context` | `object` | No | Diagnostic data (IDs, states, durations) |
| `recommendations` | `array` | No | Actionable suggestions from `recommendations.yaml` |

#### Recommendation Resolution Order

On failure, the player resolves recommendations by merging (deduplicated by `id`):

1. `<error.code>` — most specific (e.g. `NEGOTIATION_TIMEOUT`)
2. `validation:<type>` — validation assertion type (e.g. `validation:equals`)
3. `step:<uses>` — step type (e.g. `step:connector/pull_data_filtered`)

#### `recommendations.yaml` Configuration

```yaml
# By error code
NEGOTIATION_TIMEOUT:
  - id: check-policy-match
    message: "Verify the SUT's access policy accepts your BPN and usage purpose"
    docs: "https://eclipse-tractusx.github.io/docs/tutorials/policy-troubleshooting"
  - id: increase-timeout
    message: "Increase negotiation timeout via 'negotiation_timeout_ms' in test config"
    config: negotiation_timeout_ms

# By step type
step:connector/pull_data_filtered:
  - id: verify-dct-type
    message: "Confirm the catalog filter dct:type matches the SUT asset registration"

# By validation type
validation:equals:
  - id: inspect-actual-vs-expected
    message: "Compare outputs.actual against inputs.expected in the trace"
```

### Variable Input Flow

When a `request`-disposition variable needs operator input:

1. Player emits `tck.variable.input.required` with `correlation_id`, `schema`, `prompt`, and `input_prompts`
2. SSE stream **pauses server-side** — no further events until input arrives
3. IDE renders a form from `input_prompts`; user submits via REST endpoint (out of scope — see ADR-0017)
4. Player emits `tck.variable.input.received` echoing `correlation_id` + `outputs`
5. Player emits `tck.variable.resolved` and streaming resumes

The `correlation_id` links the request to the response, enabling the backend to match submissions to pending variables.

### SSE Transport Mapping

Each JSONL line maps to one SSE frame:

| SSE field | Source | Purpose |
|-----------|--------|---------|
| `event:` | `type` value | Routes to IDE event handler |
| `id:` | `sequence` (string) | Enables `Last-Event-ID` reconnection |
| `data:` | Full CE JSON (one line) | Self-contained event payload |

**Reconnection**: IDE sends `Last-Event-ID: <sequence>` on reconnect. Backend resumes from `sequence + 1`. The `tck.start` event is re-sent on every new connection so late joiners have run context.

## Concrete Example

See [`docs/examples/certificate-management-v2/plain/execution-trace.jsonl`](../../../examples/certificate-management-v2/plain/execution-trace.jsonl) for a full 34-event TCK trace.

**TCK start** (sequence 1):
```json
{"specversion":"1.0","id":"certificate-management-tck/tck.start/a3f8c1d27e4b",
 "source":"testlab/player/lifecycle","type":"tck.start",
 "time":"2026-05-28T18:30:00.000Z","sequence":1,
 "data":{"tck_id":"certificate-management-tck","namespace":"ccm-v0.0.1",
  "metadata":{"name":"Certificate Management TCK","version":"v0.0.1",
   "standard":"CX-0135","dataspace_version":"saturn"},
  "environment":"local","service":"tractusx-testlab",
  "run_id":"a3f8c1d2-7e4b-4a9f-b5c6-2d1e8f9a0b3c"}}
```

**Input-required pause** (sequences 9–10, ~45s gap):
```json
{"specversion":"1.0","id":"...tck.variable.input.required/4d18b3af06c2",
 "source":"testlab/player/variables","type":"tck.variable.input.required",
 "time":"2026-05-28T18:30:00.530Z","sequence":9,
 "data":{"name":"sut_connector","correlation_id":"inp-sut-conn-01",
  "prompt":"Provide SUT connector details","input_prompts":[...]}}

{"specversion":"1.0","id":"...tck.variable.input.received/5e29c4b017d3",
 "source":"testlab/player/variables","type":"tck.variable.input.received",
 "time":"2026-05-28T18:30:45.090Z","sequence":10,
 "data":{"name":"sut_connector","correlation_id":"inp-sut-conn-01",
  "outputs":{"counter_party_address":"https://sut-connector.example.com/api/v1/dsp",
   "counter_party_id":"BPNL000000000SUT"}}}
```

**Step passed with nested validations** (sequence 16):
```json
{"specversion":"1.0","id":"...pull_data_1/tck.test.step.passed/b48f2a165d39",
 "source":"connector/pull_data_filtered","type":"tck.test.step.passed",
 "time":"2026-05-28T18:30:47.738Z","sequence":16,
 "data":{"attempt":1,"duration_ms":2538,
  "outputs":{"asset_id":"urn:asset:ccm-api-3.0",
   "edr_token":{"$jwe":"eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIiwia2lkIjoibG9jYWwtMjAyNi0wNS0yOCJ9..<iv>.<ct>.<tag>"}},
  "validations":[
   {"source":"validate/assert","field":"edr_token",
    "inputs":{"assertion":"not_null"},"outputs":{"passed":true}},
   {"source":"validate/assert","field":"dataplane_url",
    "inputs":{"assertion":"not_null"},"outputs":{"passed":true}}]}}
```

**Failed step with recommendations** (sequence 20):
```json
{"specversion":"1.0","id":"...send_request_1/tck.test.step.failed/f8c367508a7d",
 "source":"connector/pull_data_filtered","type":"tck.test.step.failed",
 "time":"2026-05-28T18:31:17.801Z","sequence":20,
 "data":{"attempt":1,"duration_ms":30000,
  "validations":[{"source":"validate/assert","field":"status_code",
   "inputs":{"assertion":"equals","expected":200},
   "outputs":{"actual":null,"passed":false},
   "errors":[{"code":"NEGOTIATION_TIMEOUT",
    "message":"Contract negotiation did not reach AGREED state within 30s",
    "retryable":true,
    "recommendations":[
     {"id":"check-policy-match","message":"Verify the SUT's access policy..."},
     {"id":"increase-timeout","message":"Increase timeout...","config":"negotiation_timeout_ms"},
     {"id":"verify-dct-type","message":"Confirm catalog filter dct:type..."}]}]}],
  "errors":[{"code":"NEGOTIATION_TIMEOUT","retryable":true,
   "message":"Contract negotiation did not reach AGREED state within 30s"}]}}
```

## Alternatives Considered

| Alternative | Reason for Rejection |
|-------------|---------------------|
| Flat JSONL with header line (v2) | Header couples identity to file; doesn't support single-stream TCK runs |
| Separate validation events | Inflates event count; validations are semantically part of the step result |
| UUID v4 for `id` field | Opaque — no structural context; harder to filter/grep |
| Full-line encryption | Breaks log aggregator indexing — non-sensitive fields become unsearchable |
| Custom `$encrypted` wrapper | Reinvents JWE (RFC 7516); standard JWE compact gives library support, JWK key rotation, and interoperability |
| `[REDACTED]` redaction strategy | Irreversibly discards debug-valuable data; JWE encryption protects secrets while remaining recoverable with the key |
| OpenTelemetry spans | Requires OTel collector infrastructure; overkill for file-based traces |
| Protobuf encoding | Not human-readable; cannot `cat` or `jq` the trace |
| Two-file split (TCK + per-test) | Adds complexity; single-stream is simpler for IDE consumption and SSE delivery |

## Consequences

### Positive

- Standard CloudEvents envelope enables integration with any CE-compatible tooling
- Structured `id` enables filtering by TCK, test, step, or event type via simple string prefix
- Self-contained events — no header dependency; any line is independently meaningful
- Nested validations keep step results atomic for IDE rendering
- `sequence` provides total ordering and SSE reconnection support
- Standard JWE (RFC 7516) encryption is the single mechanism for secret protection; `kid`-based JWK rotation keeps old traces decryptable
- Recommendation resolution order provides increasingly specific fix suggestions

### Negative

- Larger per-event overhead (~100 bytes envelope) vs flat format
- Consumers must parse CloudEvents envelope before accessing domain data
- `id` path convention requires understanding the format — not standard CE

### Neutral

- No backward compatibility with v2 format — clean break (no v2 consumers exist in production)
- Performance impact negligible (~1μs envelope construction vs ms-scale step execution)
