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

Agreed

## Date

2026-05-28 (proposed) - 2026-08-18 (agreed, with the amendments below)

## Context

The TestLab player emits execution traces for:

- **Observability**: streaming progress to the IDE via SSE
- **Debugging**: inspecting step-level inputs, outputs, and validation results
- **Audit**: immutable record of what ran, what passed, and what failed
- **Tooling**: log aggregator ingestion (ELK, Loki, Datadog) without custom transformers

Traces are delivered to the IDE frontend over Server-Sent Events (SSE) and persisted as JSONL files. The format must be self-contained, streamable, and interoperable with existing observability infrastructure.

The previous v2 format (flat JSONL with a header line) coupled trace identity to file-level context, making it unsuitable for single-stream TCK runs where multiple tests and lifecycle phases interleave. A CloudEvents-based envelope provides per-event identity, standard typing, and ecosystem compatibility.

### Two records, two audiences

A run leaves **two** artifacts, and they are not two formats of one thing:

| Artifact | Location | Format | Audience |
|----------|----------|--------|----------|
| **Transcript** | `logs_dir` - `<date>/<time>_<job_id>.log` | Plain text, identical to the console | A person watching or reviewing the run |
| **Trace** | `data_dir` - `<date>/<time>_<job_id>.jsonl` | CloudEvents JSONL (this ADR) | The IDE, the report, log aggregators, anyone debugging the wire |

They are configured separately (`TESTLAB_LOGS_DIR` / `TESTLAB_DATA_DIR`, or `--logs-dir` / `--data-dir`) because they are read for different reasons. The engine previously wrote JSONL to `logs_dir` and text only to the console, which produced a log file that was neither: too verbose to read, and not the trace either.

**The transcript is taken at the console, not at a logger.** A per-logger file handler only ever sees what was written through *that* logger, which left the file holding the execution events and nothing else - not the compile narration, not the run header, not the result banner, and not the tracebacks, because `logger.exception` goes to the root logger and `typer.echo` never touches `logging` at all. A transcript missing the traceback is missing the one thing the reader opened it for. So `sys.stdout` and `sys.stderr` are copied for the duration of the run: whatever a run prints, by any route, is what the file gets, and "the same as the console" becomes a property of the mechanism instead of a list of call sites somebody has to keep complete. ANSI colour is stripped and a progress bar's redraws collapse to their final state, since the file is read in an editor.

The transcript opens **before compilation** so the compiler's output is in it, which is why the run id is committed to up front and then used for the job and the trace as well. All three name the same run.

**Two records, one lookup apart.** Each transition is traced before it is logged, and the `id` of the event written is printed at the end of the line the transcript gets — `… step.call [dtr-filterability] pull_dtr #3 CatalogController.get_catalog → POST …/catalog/request ← 200 in 1373ms id=ic-tck/dtr-filterability/execution/pull_dtr/calls/3/tck.test.step.call/2229712…`. The line stays what a person can read going past — which step, which call of it, who made it, and what came back — and the id is the key to the event that holds the headers and the bodies. Without it a step that is fourteen calls printed fourteen identical lines. Nothing is added to the payload a consumer receives over SSE; the id belongs to the envelope, which the transcript is now quoting.

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
| Test step | `<tckid>/<testid>/<phase>/<stepid>/<type>/<hash>` | `cert-mgmt-tck/catalog-policy-validation/execution/pull_data_1/tck.test.step.passed/b48f2a165d39` |

`<phase>` is `setup`, `execution`, or `teardown`. It is part of the path because a step id is only unique **within** a phase - a `cleanup_asset` in teardown and one in setup are different steps, and without the segment their events share a path and are told apart only by the payload hash. It also lets a reader drop a whole phase from a trace with a prefix match, which is the usual first move when a teardown is noisy and the failure is in execution.

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
| `tck.test.step.start` | `{attempt, index, phase, inputs?}` | Step execution begins; `inputs` is the `with:` block **resolved** |
| `tck.test.step.call` | `{index, context, started_at, request, response?, errors?}` | One call the step made, published when its answer came back |
| `tck.test.step.update` | `{attempt, state, ...context}` | Progress (long-running) |
| `tck.test.step.passed` | `{attempt, duration_ms, inputs?, outputs, validations}` | Step succeeded (terminal) |
| `tck.test.step.failed` | `{attempt, duration_ms, inputs?, outputs?, validations, errors}` | Step failed (terminal) |
| `tck.test.step.skipped` | `{attempt, reason}` | Step skipped |
| `tck.test.step.timeout` | `{attempt, duration_ms, timeout_ms}` | Step timed out |
| `tck.test.step.retry` | `{attempt, previous_attempt, reason}` | Retry initiated |

### Wire Exchanges

Per [C40](../../contract-conflict-decisions.md), **every request a step sends and every answer it gets is recorded**, whether or not a script reads them. They are siblings of `outputs`, never folded into it: `outputs` is the addressable surface a `returns:` block may name, and the wire is evidence rather than a step output.

**Each call is its own event.** `tck.test.step.call` is emitted the moment a call comes back, between the step's `start` and its terminal event, in the order the calls completed:

| Field | Shape | Meaning |
|-------|-------|---------|
| `index` | integer | Position of the call within the step, from 1. |
| `context` | string | Who sent it — the SDK method for a call `tractusx-sdk` made on the engine's behalf (`CatalogController.get_catalog`), `testlab/http_client` for one the engine made itself. |
| `started_at` | string | When it went out. |
| `request` | `HttpRequest` | `method`, `url`, `headers`, `params` (query parameters sent alongside the URL rather than inside it), `body`. |
| `response` | `HttpResponse` | `status_code`, `headers`, `body`, `duration_ms`. Absent when the transport raised. |
| `errors[]` | `[{code, message, retryable}]` | Present instead of `response` when the call never got one: `TRANSPORT_FAILED`, carrying the exception. |

A step is often several calls: `connector/consumer/pull_data_filtered` runs a catalog query, a negotiation, a poll loop and a transfer before it returns anything. Publishing them **as they happen** rather than in one terminal event is what makes a minute-long step watchable, and it keeps the trace from carrying the same 1.6 kB catalog answer twice — the terminal event carries the verdict, not a transcript of what the step had been doing.

**Inputs and outputs.** `tck.test.step.start` carries `inputs`, the `with:` block with every `${{ … }}` reference **already substituted** — the values the step is about to be given. It used to carry the template text, so a trace of a step reading `expected_policies: ${{ env.usage_policy }}` repeated the name of the variable and never said what the run seeded it with, which is the one thing the reader opened the trace for. A reference that names nothing in scope is the exception: the block is published as written and the terminal event reports the unresolved reference as the step's failure. The terminal event carries `inputs` too, as the step received them, next to the `outputs` it published.

**What the trace shows is what was sent.** A step *also* names a subject exchange, and a step driving the SDK writes that summary itself - the URL its client would have used, its own parameters as the body, a `200` inferred from not having raised. That account is what the run **keeps**: it is the surface a `returns:` block names (`response_headers`, `status_code`, `body`) and what assertions read, so it stays exactly as the step declared it. It is not what the run **writes**. What the trace, the transcript and the SSE stream carry are the calls the tracer recorded - the DSP `CatalogRequest` the SDK actually posted, the headers it actually sent, the body the SUT actually answered. A trace read to debug a SUT is worth nothing while it describes a request nobody sent. (`logging.wire.as_recorded` performs the substitution for the one `request`/`response` pair the SSE `StepResult` still carries as its headline.)

**`context` says who sent it.** A call the SDK made on the engine's behalf is attributed to the SDK method that made it (`CatalogController.get_catalog`, `ConnectorConsumerService.do_get`); a call the engine made itself is attributed to `testlab/http_client`. A step spans two transports and several SDK layers, and "which layer sent this" is the first question asked of a failing call - answered by a field rather than by the reader inferring it from the URL.

**How both transports are recorded.** `tractusx-sdk` traces its own traffic: every call it makes passes through `Adapter.request()` or `HttpTools`, both of which record into whichever tracer is active for the current execution context (the SDK's *Request Tracing* page documents the tracer, its filters and its options). The engine activates one tracer per step, as a named *operation*, and its own `httpx` calls record through the same `trace_call` seam - so one ordered list holds both transports under one redaction and truncation policy, and an SDK-mediated failure is as visible as a direct one. Nothing is wired into the services for this and nothing is patched: activation is a `contextvars.ContextVar`, which is also why a step on the event loop and the SDK call it dispatched to a worker thread record into the same operation (`asyncio.to_thread` copies the context).

Every entry is stamped with the innermost active operation, so a **flow step reports what it sent and its nested steps report theirs** - the parent does not claim its children's traffic a second time.

Two kinds of traffic stay out of the trace, by the SDK's design: the OAuth2 token requests of `OAuth2Manager` (credentials, and never the subject of a verdict) and the non-HTTP submodel adapters (file system, S3), which are not wire calls at all.

An exchange whose transport raised (refused connection, timeout, TLS failure) carries `request` and `error` (`"ConnectTimeout: ..."`, the exception type and its message) with no `response`. That case is why recording is not left to the steps: a step that raises never reaches the line that would have described its request.

**Header redaction.** Credential-bearing headers (`authorization`, `proxy-authorization`, `x-api-key`, `x-api-secret`, `x-auth-token`, `apikey`, `api-key`, `cookie`, `set-cookie`) are replaced with `***` in every `tck.test.step.call` **and** in the step-named subject the SSE result carries. Two records, one list: the tracer masks what it records, and a step's own summary — which never went through the tracer and is built from what the step was handed, the EDR token included — is masked on the way out, so the transcript, the SSE stream and the trace all carry the same masked value. What the run *keeps* is not masked: a script may write `returns: {response_headers: ...}` and read the headers the SUT actually sent. Redaction is by header **name**, not by value pattern: a header called `Authorization` is a secret whatever it happens to contain, and guessing at shapes is how a token ends up in a file. Bodies are recorded as JSON when they are JSON - a payload the SDK serialised before sending it is parsed back, so the trace can be queried instead of holding an escaped string - and clipped at 20 000 characters with the cut made visible: the body keeps its structure and the parts that did not fit become a `...[truncated N items]` / `...[truncated N keys]` marker. A binary body (a PDF or ZIP from a submodel server) is recorded base64 encoded. A step's recording is bounded at 1 000 calls, past which the oldest are dropped — for a poll loop that keeps the end, which is where the failure is.

#### `data.outputs` is keyed by output name

`outputs` is a mapping of the step's output names to their values — the same
names the script reads in `returns:` and in `${{ execution.<step>.<name> }}`.
A step with several outputs was always a mapping; a step whose whole output is
one value (`util/base64`, `util/json_path_extract`) published it naked, so the
trace held a bare string with nothing saying which output it was. That value is
published under `value`, which is the name it already has everywhere else (it is
in `UNIVERSAL_RETURNS`), so one reader handles every step:

```json
"outputs": {"value": "W3sibmFtZSI6ImRpZ2l0YWxUd2luVHlwZSJ9"}
"outputs": {"dataplane_url": "https://…/api/public", "edr_token": "eyJ…"}
```

A step that produced nothing keeps `"outputs": null`: naming an output it never
published would be a claim, not a shape.

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

#### Codes the engine emits today

| `code` | Where | `origin` | `context` |
|--------|-------|----------|-----------|
| `STEP_FAILED` | `data.errors[]` | `sut` | — |
| `ENGINE_FAULT` | `data.errors[]` | `engine` | — |
| `POLICY_MISMATCH` | `data.errors[]` | `sut` | the offer comparison (below) |
| `ASSERTION_FAILED` | `data.validations[].errors[]` | — | — |
| `TRANSPORT_FAILED` | `tck.test.step.call` `errors[]` | — | — |

`STEP_FAILED` and `ENGINE_FAULT` are the classification every failure gets. A
failure that can say more names itself and carries the evidence under `context`,
which is what separates *a verdict* from *a verdict a reader can act on*: an
error the engine can only classify says who to go to, and one that named itself
says what to change.

`POLICY_MISMATCH` is the first of them. The SDK reports a catalog whose offers
were all refused as "no valid policy was found", which names neither the offers
nor the condition that refused them; the engine reads both sides down to their
atomic ODRL conditions and publishes the difference as a set, so the IDE renders
the comparison instead of parsing it back out of a sentence:

```json
{"code":"POLICY_MISMATCH","origin":"sut","retryable":false,
 "message":"no offer from https://provider.example/dsp is made under a policy this step accepts\n  2 offers compared, none matched:\n    offer 'aWNodWI6Y29udHJhY3Q6T0Js…' on asset 'ichub:asset:dtr:9foUM7pm…':\n      the provider also requires: 'Membership eq active'\n  expected: 'FrameworkAgreement eq DataExchangeGovernance:1.0', 'UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1'",
 "context":{"counter_party_address":"https://provider.example/dsp","offers_compared":2,
  "expected_policies":[["FrameworkAgreement eq DataExchangeGovernance:1.0",
                        "UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1"]],
  "offers":[{"asset_id":"ichub:asset:dtr:9foUM7pmSTrr5LZnx0NqiQ",
             "offer_id":"aWNodWI6Y29udHJhY3Q6T0Js…",
             "constraints":["FrameworkAgreement eq DataExchangeGovernance:1.0",
                            "Membership eq active",
                            "UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1"],
             "closest_expected_policy":0,
             "offered_not_expected":["Membership eq active"],
             "expected_not_offered":[]}]}}
```

An offer is accepted only when its policy matches an expected one in full, so
`offered_not_expected` — a condition the **provider** adds — rejects the offer
just as `expected_not_offered` does. It is the half a flat "not found" hides,
and the usual cause of a red DSP step against a healthy deployment.

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

A run writes its own trace to `<data_dir>/<date>/<time>_<job_id>.jsonl`; the excerpts below are the shapes to expect there.

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

**Step passed with nested validations** (sequence 16). Note the `execution` segment before the step id:
```json
{"specversion":"1.0","id":"...catalog-policy-validation/execution/pull_data_1/tck.test.step.passed/b48f2a165d39",
 "source":"connector/pull_data_filtered","type":"tck.test.step.passed",
 "time":"2026-05-28T18:30:47.738Z","sequence":16,
 "data":{"attempt":1,"duration_ms":2538,
  "inputs": {...},
  "outputs":{"asset_id":"urn:asset:ccm-api-3.0",
   "edr_token":{"$jwe":"eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIiwia2lkIjoibG9jYWwtMjAyNi0wNS0yOCJ9..<iv>.<ct>.<tag>"}},
  "request:" {},
  "response": {}, 
  "validations":[
   {"source":"validate/assert","field":"edr_token",
    "inputs":{"assertion":"not_null"},"outputs":{"passed":true}},
   {"source":"validate/assert","field":"dataplane_url",
    "inputs":{"assertion":"not_null"},"outputs":{"passed":true}}]}}
```

**Failed step with recommendations** (sequence 20):
```json
{"specversion":"1.0","id":"...catalog-policy-validation/execution/send_request_1/tck.test.step.failed/f8c367508a7d",
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

**A failing step, end to end** — captured verbatim from a run of
`connector/consumer/pull_data_filtered` against a stub connector (bodies elided
with `...`, nothing else edited). Four event shapes, in the order they were
written: what the step was asked to do, the calls as they came back, and the
verdict. The step made 64 calls over a minute — one catalog query, one EDR
negotiation, and 62 polls of a negotiation the SUT never acknowledged — each
published while the step was still running:

```json
{"specversion":"1.0","id":"wire-trace-demo-v0.0.1/pull-ccmapi/execution/pull_ccmapi_endpoint/tck.test.step.start/3360cfa181e7",
 "source":"connector/consumer/pull_data_filtered","type":"tck.test.step.start",
 "time":"2026-08-19T07:01:38.280641Z","sequence":11,
 "data":{"attempt":1,"index":0,"phase":"execution",
  "inputs":{"filters":[{"operand_left":"https://w3id.org/edc/v0.0.1/ns/type","operator":"=",
                        "operand_right":"https://w3id.org/catenax/taxonomy#CCMAPI"}]}}}

{"specversion":"1.0","id":"wire-trace-demo-v0.0.1/pull-ccmapi/execution/pull_ccmapi_endpoint/calls/1/tck.test.step.call/d139f29478c8",
 "source":"connector/consumer/pull_data_filtered","type":"tck.test.step.call",
 "time":"2026-08-19T07:01:38.281975Z","sequence":12,
 "data":{"index":1,"context":"CatalogController.get_catalog",
  "started_at":"2026-08-19T07:01:38.281055Z",
  "request":{"method":"POST","url":"http://localhost:8090/api/v1/dsp/management/v3/catalog/request",
   "headers":{"Content-Type":"application/json","x-api-key":"***"},"params":null,
   "body":{"@type":"CatalogRequest","counterPartyId":"BPNL000000000001",
           "protocol":"dataspace-protocol-http:2025-1","querySpec":{"...":"..."}}},
  "response":{"status_code":200,"headers":{"content-type":"application/json"},
   "body":{"@type":"dcat:Catalog","dcat:dataset":["..."]},"duration_ms":0.83}}}

{"specversion":"1.0","id":"wire-trace-demo-v0.0.1/pull-ccmapi/execution/pull_ccmapi_endpoint/calls/64/tck.test.step.call/bbad330cd436",
 "source":"connector/consumer/pull_data_filtered","type":"tck.test.step.call",
 "time":"2026-08-19T07:02:37.781049Z","sequence":75,
 "data":{"index":64,"context":"ContractNegotiationController.get_by_id",
  "started_at":"2026-08-19T07:02:37.776734Z",
  "request":{"method":"GET",
   "url":"http://localhost:8090/api/v1/dsp/management/v3/contractnegotiations/495c78f6-4731-4667-a235-a1d76c1cc8c0",
   "headers":{"Content-Type":"application/json","x-api-key":"***"},"params":null,"body":null},
  "response":{"status_code":404,"headers":{"content-type":"application/json"},
   "body":{"detail":"Not Found"},"duration_ms":4.14}}}

{"specversion":"1.0","id":"wire-trace-demo-v0.0.1/pull-ccmapi/execution/pull_ccmapi_endpoint/tck.test.step.failed/42179abe7d50",
 "source":"connector/consumer/pull_data_filtered","type":"tck.test.step.failed",
 "time":"2026-08-19T07:02:38.790788Z","sequence":76,
 "data":{"attempt":1,"duration_ms":60501.176,"validations":[],
  "inputs":{"filters":[{"operand_left":"https://w3id.org/edc/v0.0.1/ns/type","operator":"=",
                        "operand_right":"https://w3id.org/catenax/taxonomy#CCMAPI"}]},
  "errors":[{"code":"ENGINE_FAULT","origin":"engine","retryable":false,
   "message":"[Connector Service]: The EDR Negotiation [495c78f6-...] did not reach FINALIZED state after 60.0s (last state: None)!"}]}}
```

The calls say what one error message could not: the catalog came back, the
negotiation was accepted, and the SUT then answered `404` to every poll of the
negotiation it had just handed out. `context` names which SDK method was holding
the phone each time, `origin: "engine"` says the engine gave up rather than the
SUT failing a check, and the sequence numbers say the polls were readable as they
happened rather than a minute later.

The `errors[].origin` field separates an engine fault from a SUT verdict: a
reader triaging a red run needs to know whether to fix the SUT or file a bug
against TestLab, and one `FAILED` cannot say which.

## Implementation Status

The envelope, the id convention, the sequence counter, the TCK/test/step taxonomy,
nested validations, and the wire exchanges are **implemented**:

| Piece | Where |
|-------|-------|
| CloudEvents envelope, ids, sequence | `logging/trace.py` |
| Engine events -> trace vocabulary | `player/execution/_trace_events.py` |
| Emission points | `player/execution/monitor.py` |
| Request/response capture (httpx + SDK `requests`, via the SDK tracer) | `logging/wire/`, `steps/http_client.py` |
| Transcript / trace split | `logging/structured.py`, `config/settings.py` |

Specified here and **not yet emitted** - the engine has no events for them today,
so they are the next increments rather than silent omissions:

- `tck.boot.*` - requirements, binding, and service events (ADR-0019)
- `tck.variable.*` - resolution and operator-input events (ADR-0018, ADR-0017)
- `tck.test.step.retry` / `tck.test.step.timeout`
- `$jwe` secret encryption; sensitive **headers** are redacted today, sensitive
  **outputs** are not yet encrypted
- `recommendations.yaml` resolution on `errors[]`
- SSE `Last-Event-ID` resumption (the `sequence` it needs is emitted; the
  server-side resume is not wired)

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
