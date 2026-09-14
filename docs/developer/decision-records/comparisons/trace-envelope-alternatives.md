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

<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.7). -->
<!-- It was reviewed and tested by a human committer.  -->

# Trace Envelope Alternatives — Side-by-Side Comparison

> Companion analysis to [ADR-0016](../backend/ADR-0016-execution-trace-format.md). Compares five (plus one bonus) envelope formats for the TestLab execution trace stream, using the same failed CCM validation event (`tck.test.completed` / `validate/assert` on `ccm-present-vc`, expected `status_code=200`, got `403`).

## The Reference Event

All examples below encode **the same step-level event**: the failing `assert_status_200` validation on test `ccm-present-vc` from run `5b1a8e3c-9d2f-4a11-8f7d-1c0b6e2a9d44` under TCK `tractusx-ccm-v2` v`2.0.0`. The original ADR-0016 v2 form is reproduced under Option 4.

---

## Option 1 — CloudEvents 1.0

### What it is
[CloudEvents 1.0](https://cloudevents.io) is a CNCF specification for describing event data in a transport-agnostic way. Events carry mandatory context attributes (`id`, `source`, `specversion`, `type`) plus arbitrary `data`. Extensions (e.g. `sequence`, `traceparent`, `partitionkey`) layer on top. Maps cleanly to HTTP, Kafka, NATS, AMQP and SSE bindings.

### Same CCM event in this format
```json
{
  "specversion": "1.0",
  "id": "5b1a8e3c-...-seq-2",
  "source": "/tractusx-testlab/runs/5b1a8e3c-9d2f-4a11-8f7d-1c0b6e2a9d44/tests/ccm-present-vc",
  "type": "org.eclipse.tractusx.testlab.test.validation.end.v2",
  "time": "2026-05-28T14:31:19.502Z",
  "datacontenttype": "application/json",
  "subject": "ccm-present-vc/assert_status_200",
  "sequence": "2",
  "sequencetype": "Integer",
  "tckid": "tractusx-ccm-v2",
  "runid": "5b1a8e3c-9d2f-4a11-8f7d-1c0b6e2a9d44",
  "data": {
    "phase": "steps",
    "uses": "validate/assert",
    "ref": "present_vc_1",
    "status": "failed",
    "duration_ms": 1,
    "inputs": {"assertion": "equals", "field": "status_code", "expected": 200},
    "outputs": {"actual": 403, "passed": false},
    "errors": [{
      "code": "ASSERTION_FAILED",
      "message": "Expected status_code=200, got 403",
      "retryable": false
    }]
  }
}
```

### Strengths
- Industry-standard envelope, CNCF-graduated, vendor-neutral.
- First-class SSE binding ([CE HTTP binding](https://github.com/cloudevents/spec/blob/main/cloudevents/bindings/http-protocol-binding.md) maps cleanly to SSE frames).
- Reverse-DNS `type` namespacing handles long-term evolution and multi-source ecosystems.
- Extensions (`sequence`, `partitionkey`, `traceparent`) cover ordering, sharding and W3C trace correlation.
- Strong tooling: SDKs in Python (`cloudevents`), TypeScript (`cloudevents`), and dozens of broker integrations.

### Weaknesses
- Verbose: ~9 envelope fields per event before the payload — meaningful overhead on a high-frequency stream.
- Attribute name constraints (lowercase, alphanumeric, ≤20 chars) force ugly extension names (`tckid`, `runid`).
- The `id` field is per-event, not per-run — correlation requires reading an extension.
- Header-once optimisation from ADR-0016 is **not idiomatic** — every event carries `source`, `type`, `specversion`.
- Two-level envelope (`data` vs top-level) complicates JSONL grep/jq queries the team already uses.

### Fit for TestLab
**Mid.** Great if we expect external consumers (third-party dashboards, brokers) to consume TestLab events. Overkill for the current "a client reads the server's SSE stream" use case, where every byte of envelope overhead is paid on every step event and the client never federates with another event source.

---

## Option 2 — OpenTelemetry Logs Data Model

### What it is
The [OTel Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/) defines `LogRecord` with `time_unix_nano`, `observed_time_unix_nano`, `severity_number`/`severity_text`, `body` (any), `attributes` (k/v map), and `resource`/`scope`. Carries `trace_id` and `span_id` for span correlation. Designed for ingestion by Loki, Tempo, Jaeger, Grafana Cloud, Datadog, etc., via OTLP (gRPC/HTTP).

### Same CCM event in this format
```json
{
  "resource": {
    "attributes": {
      "service.name": "tractusx-testlab",
      "service.version": "2.0.0",
      "deployment.environment": "local"
    }
  },
  "scope": {"name": "tractusx.testlab.player"},
  "logRecords": [{
    "timeUnixNano": "1779892279502000000",
    "observedTimeUnixNano": "1779892279502000000",
    "severityNumber": 17,
    "severityText": "ERROR",
    "body": {"stringValue": "Expected status_code=200, got 403"},
    "traceId": "5b1a8e3c9d2f4a118f7d1c0b6e2a9d44",
    "spanId": "0000000000000002",
    "attributes": {
      "testlab.tck_id": "tractusx-ccm-v2",
      "testlab.test_id": "ccm-present-vc",
      "testlab.run_id": "5b1a8e3c-9d2f-4a11-8f7d-1c0b6e2a9d44",
      "testlab.phase": "steps",
      "testlab.step.id": "assert_status_200",
      "testlab.step.uses": "validate/assert",
      "testlab.step.ref": "present_vc_1",
      "testlab.step.status": "failed",
      "testlab.assertion.type": "equals",
      "testlab.assertion.field": "status_code",
      "testlab.assertion.expected": 200,
      "testlab.assertion.actual": 403,
      "testlab.error.code": "ASSERTION_FAILED",
      "event.name": "tck.test.validation.end"
    }
  }]
}
```

### Strengths
- Native consumption by every modern observability backend (Loki, Tempo, Grafana, Datadog, Honeycomb, Jaeger).
- `trace_id`/`span_id` provide free distributed-trace correlation across player, mock server, and SUT calls.
- Severity is built in — no `status`-to-severity mapper needed in log shippers.
- OTLP gRPC + HTTP collectors are mature; Python SDK (`opentelemetry-sdk`) and TS SDK both first-class.
- `resource` block is the natural home for header-once metadata.

### Weaknesses
- Flat `attributes` map loses the typed `inputs`/`outputs` structure — assertion semantics get smeared into a dotted bag.
- Designed for **logs**, not for **structured domain events**: the `body` is opaque, every client has to learn the attribute schema.
- `time_unix_nano` strings are unfriendly for jq and client consumers — humans want ISO 8601.
- Heavy SDK footprint (OTel collector, exporters) if we want end-to-end OTLP — the testlab today writes JSONL files.
- Streaming via SSE is non-standard for OTel — OTLP wants gRPC or HTTP push.

### Fit for TestLab
**Mid-low.** Excellent destination format (we should probably **export to** OTel from our envelope), but a poor primary envelope. Forces clients to navigate a flat attribute bag instead of a typed domain object, and the JSONL ergonomics are worse than what we have today.

---

## Option 3 — Elastic Common Schema (ECS)

### What it is
[ECS](https://www.elastic.co/guide/en/ecs/current/index.html) is Elastic's flat dotted-field schema for any document indexed into Elasticsearch. Defines standard field families: `event.*`, `service.*`, `trace.*`, `error.*`, `user.*`, etc. Designed for uniform querying across heterogeneous sources in Kibana.

### Same CCM event in this format
```json
{
  "@timestamp": "2026-05-28T14:31:19.502Z",
  "ecs.version": "8.11.0",
  "event.kind": "event",
  "event.category": ["process"],
  "event.action": "validation.end",
  "event.outcome": "failure",
  "event.dataset": "testlab.trace",
  "event.sequence": 2,
  "event.duration": 1000000,
  "service.name": "tractusx-testlab",
  "service.version": "2.0.0",
  "service.environment": "local",
  "trace.id": "5b1a8e3c9d2f4a118f7d1c0b6e2a9d44",
  "labels": {
    "tck_id": "tractusx-ccm-v2",
    "test_id": "ccm-present-vc",
    "run_id": "5b1a8e3c-9d2f-4a11-8f7d-1c0b6e2a9d44",
    "phase": "steps",
    "step_id": "assert_status_200",
    "step_uses": "validate/assert",
    "step_ref": "present_vc_1",
    "assertion_type": "equals",
    "assertion_field": "status_code",
    "assertion_expected": "200",
    "assertion_actual": "403"
  },
  "error.code": "ASSERTION_FAILED",
  "error.message": "Expected status_code=200, got 403",
  "message": "Expected status_code=200, got 403"
}
```

### Strengths
- Beautiful Kibana out of the box — every field is queryable, faceted, and chartable with zero custom dashboards.
- `event.outcome` + `event.action` is exactly the `status` + `event` split we already designed.
- Flat field names make grep/jq trivial (`. | select(.["event.outcome"]=="failure")`).
- Mature, stable spec maintained by Elastic; widely adopted in security and SRE tooling.
- `trace.id` interoperates with OTel — same correlation story for free.

### Weaknesses
- Optimised for Elasticsearch indexing, not for structured domain events — nested `inputs`/`outputs` get flattened into `labels` and lose their typing.
- ECS `labels` values must be **scalar strings**, so numeric `expected`/`actual` must be stringified, breaking type fidelity.
- Verbose field names (`event.dataset`, `service.environment`, `event.duration`) bloat every event.
- Tightly couples us to Elastic mental model — non-ELK consumers (SSE clients) gain nothing.
- No native SSE binding — ECS is a document shape, not a transport.

### Fit for TestLab
**Low.** Right destination format if we ship to ELK in the future, wrong primary envelope. The lossy `inputs`/`outputs` flattening hurts clients far more than ELK helps anyone today.

---

## Option 4 — JSONL + Plain Domain Schema (ADR-0016 v2)

### What it is
Our own header-once JSONL envelope. First line is `type: "header"` with run-scoped fields. Subsequent lines carry `sequence`, `type`, `event`, `status`, `timestamp`, plus domain-specific payload. No nested `data` block — domain fields are top-level. One JSONL file per scope (`tck-trace.jsonl`, `tests/<test_id>.jsonl`).

### Same CCM event in this format
```json
{
  "sequence": 2,
  "index": 1,
  "phase": "steps",
  "id": "assert_status_200",
  "uses": "validate/assert",
  "ref": "present_vc_1",
  "status": "failed",
  "started_at": "2026-05-28T14:31:19.501Z",
  "finished_at": "2026-05-28T14:31:19.502Z",
  "duration_ms": 1,
  "inputs": {"assertion": "equals", "field": "status_code", "expected": 200},
  "outputs": {"actual": 403, "passed": false},
  "errors": [{
    "code": "ASSERTION_FAILED",
    "message": "Expected status_code=200, got 403",
    "retryable": false,
    "recommendations": [
      {"id": "check-sut-response", "message": "Inspect the actual response from the SUT for unexpected values"},
      {"id": "inspect-actual-vs-expected", "message": "Open the per-test trace and compare outputs.actual against inputs.expected"}
    ]
  }]
}
```

### Strengths
- Minimal overhead — no nested `data` block, no `specversion`, no `attributes` map.
- Header-once design saves ~80 bytes per event at scale; matches the existing implementation.
- Domain-typed: `inputs`/`outputs` preserve full structure including numeric `expected`/`actual`.
- Plain JSONL maps one-line-one-event to SSE frames without translation; existing client handlers stay simple.
- Fully under our control — no upstream spec to track, no breaking changes from third parties.

### Weaknesses
- No standard tooling — every consumer (log shipper, dashboard) needs a custom adapter.
- Schema evolution discipline is on us; no validators in the wild.
- No built-in distributed-trace correlation (`trace_id`/`span_id`).
- Anyone reading the trace must learn TestLab-specific field names before they can grep.
- Header-once means a line read in isolation is missing context — consumers must replay from the header.

### Fit for TestLab
**High.** This is the status quo, and the design directly mirrors what SSE clients and the CLI need today. The cost is lifetime ownership of the schema; the win is zero envelope tax and perfect domain fit.

---

## Option 5 — AsyncAPI 3.0 + Custom Message Schema

### What it is
[AsyncAPI 3.0](https://www.asyncapi.com/docs/reference/specification/v3.0.0) describes message-driven APIs: channels, operations, messages, and payload schemas. It is a **contract specification**, not an envelope — the on-the-wire message shape is whatever we define in the `payload` schema (usually JSON Schema). Provides codegen (Python, TS), validators, and docs generation. Comparable to OpenAPI but for SSE/WebSocket/Kafka/MQTT.

### Same CCM event in this format
The message payload is *whatever we want*. AsyncAPI just documents and validates it. Below: the ADR-0016 v2 line as the documented payload of a `trace.events` channel SSE message.

`asyncapi.yaml` (excerpt):
```yaml
asyncapi: 3.0.0
channels:
  testTrace:
    address: /runs/{runId}/tests/{testId}/trace
    messages:
      validationEnd:
        $ref: '#/components/messages/ValidationEnd'
components:
  messages:
    ValidationEnd:
      name: tck.test.validation.end
      contentType: application/json
      payload:
        $ref: '#/components/schemas/StepEvent'
```

On-the-wire SSE frame (the payload itself):
```json
{
  "sequence": 2,
  "type": "tck.test.validation.end",
  "phase": "steps",
  "id": "assert_status_200",
  "uses": "validate/assert",
  "ref": "present_vc_1",
  "status": "failed",
  "started_at": "2026-05-28T14:31:19.501Z",
  "finished_at": "2026-05-28T14:31:19.502Z",
  "duration_ms": 1,
  "inputs": {"assertion": "equals", "field": "status_code", "expected": 200},
  "outputs": {"actual": 403, "passed": false},
  "errors": [{"code": "ASSERTION_FAILED", "message": "Expected status_code=200, got 403", "retryable": false}]
}
```

### Strengths
- Provides a **contract layer** ADR-0016 currently lacks — channels, operations, message catalog, version negotiation.
- Codegen for Python (`asyncapi-python`) and TypeScript (`@asyncapi/modelina`) — type-safe clients on both sides for free. `[verify]` exact generator names.
- Generates browsable HTML docs (AsyncAPI Studio) — onboarding new TCK authors gets easier.
- SSE binding is part of the spec — channels can be SSE-typed natively.
- Layers cleanly on top of Option 4 — AsyncAPI describes the messages, Option 4 *is* the message.

### Weaknesses
- Not an envelope — solves a different problem (contract & docs), so it does not displace Options 1–4.
- Toolchain weight: spec authoring, codegen pipelines, CI validation steps.
- AsyncAPI 3.0 is relatively young; some generators lag the spec.
- Risk of double-maintenance: the YAML spec and the actual Pydantic/TS models can drift.
- Adds zero value if we never publish the trace stream to external consumers.

### Fit for TestLab
**Complement, not replacement.** AsyncAPI is the right answer to "how do we document and version the trace channel" — but the on-the-wire shape is still Option 4. Adopt later if/when we expose the stream to third parties; not needed for the ADR-0016 decision today.

---

## Option 6 (Bonus) — W3C Server-Sent Events Native + Typed `event:` Names

### What it is
SSE itself defines three frame fields: `event`, `id`, `data`. ADR-0016 already maps to these. The "bonus" option is to commit harder: treat the `event:` SSE field as the **discriminator** (`tck.test.validation.end`) and make `data:` a domain-only payload with no embedded `type`. The envelope **is** the SSE frame.

### Same CCM event in this format
```
event: tck.test.validation.end
id: 2
data: {"phase":"steps","id":"assert_status_200","uses":"validate/assert","ref":"present_vc_1","status":"failed","started_at":"2026-05-28T14:31:19.501Z","finished_at":"2026-05-28T14:31:19.502Z","duration_ms":1,"inputs":{"assertion":"equals","field":"status_code","expected":200},"outputs":{"actual":403,"passed":false},"errors":[{"code":"ASSERTION_FAILED","message":"Expected status_code=200, got 403","retryable":false}]}
```

### Strengths
- Smallest possible payload — `type` and `sequence` live in SSE metadata.
- The browser `EventSource` API routes by `event` natively — `source.addEventListener("tck.test.validation.end", ...)`.
- Reconnection via `Last-Event-ID` is the spec's built-in primitive.

### Weaknesses
- **Loses the JSONL story.** Once persisted to disk we have to re-embed `type` and `sequence` — two formats to maintain.
- Non-SSE consumers (Kafka, file replay) need a different parser.
- Discoverability suffers — `event:` lines are not standard fields in most log tooling.

### Fit for TestLab
**Low.** Optimises the byte count on the wire at the cost of asymmetry between in-flight and on-disk forms. ADR-0016's "one JSONL line = one SSE frame" is a stronger invariant.

---

## Comparison Matrix

| Criterion | Option 1 — CloudEvents | Option 2 — OTel Logs | Option 3 — ECS | Option 4 — JSONL (ADR-0016) | Option 5 — AsyncAPI | Option 6 — SSE Native |
|---|---|---|---|---|---|---|
| Self-contained events | ⚠️ Yes per event, but verbose | ⚠️ Yes, attribute bag loses typing | ⚠️ Flat fields, lossy nesting | ⚠️ Header-once needed for full context | ✅ Whatever payload we design | ❌ Needs SSE metadata to be complete |
| `status`-where-meaningful principle | ⚠️ `data.status`, fights with `type` taxonomy | ⚠️ Forced into `severityText` | ✅ `event.outcome` matches exactly | ✅ Native top-level `status` | ✅ Whatever we design | ✅ Whatever we design |
| Client consumer simplicity | ⚠️ Two-level envelope (`data` + top) | ❌ Flat attribute bag, opaque body | ⚠️ Stringified scalars in `labels` | ✅ Domain-typed top-level fields | ✅ Codegen TS types | ✅ `EventSource` events |
| SSE binding maturity | ✅ Spec-defined HTTP binding | ❌ Non-standard for OTLP | ❌ Document shape, no transport | ✅ Trivial line-to-frame | ✅ SSE in spec | ✅ This IS SSE |
| Ecosystem tooling | ✅ CNCF SDKs, broker integrations | ✅ Loki, Tempo, Grafana, Datadog | ✅ Kibana, Elastic stack | ❌ TestLab-only | ⚠️ Codegen tools young | ⚠️ Browser-only first-class |
| Schema evolution | ✅ Reverse-DNS `type` + `dataschema` | ✅ Attribute namespaces | ⚠️ Tied to ECS major version | ⚠️ Manual `schema_version` discipline | ✅ Versioned message contracts | ❌ No versioning primitive |
| Bytes/event overhead | ❌ ~9 envelope fields | ❌ Resource + scope + nano timestamps | ⚠️ Long dotted field names | ✅ Minimal | ✅ Whatever we design | ✅ Minimal |
| Cross-codebase clients (Py + TS) | ✅ `cloudevents` in both | ✅ OTel SDK in both | ⚠️ ECS libs, not idiomatic | ⚠️ Hand-rolled (Pydantic + TS interface) | ✅ Codegen for both | ✅ `EventSource` + Pydantic |
| Risk of over-engineering | ❌ High — spec ceremony, extension naming | ❌ High — collector pipeline pressure | ⚠️ Mid — pulls us toward ELK | ✅ Low — already built | ⚠️ Mid — second spec to maintain | ⚠️ Mid — dual on-disk/on-wire forms |

---

## Final Recommendation

**Keep Option 4 (ADR-0016 v2 JSONL) as the primary envelope. Add Option 5 (AsyncAPI 3.0) as the contract layer when the trace stream is exposed beyond its current clients. Treat Option 2 (OTel Logs) as an export destination, not a replacement.**

The reference event makes the verdict clear: every standardised envelope (CloudEvents, OTel, ECS) either bloats the line, flattens the typed `inputs`/`outputs` we depend on, or both — and none of them solve a problem we have today. A client reads a single server's SSE stream; there are no third-party consumers, no broker federation, and no observability backend pinning our format choice. Option 4 minimises envelope overhead, preserves domain typing end-to-end, and maps one-to-one to SSE frames. The genuine gap it has — a contract/version story — is precisely what AsyncAPI fills additively without changing a single byte on the wire. Adopting CloudEvents or OTel now would be standards-cargo-culting; adopt them later as **gateway translations** if and when an external consumer actually appears.

---

**File**: `docs/developer/decision-records/comparisons/trace-envelope-alternatives.md`
**Companion to**: [ADR-0016](../backend/ADR-0016-execution-trace-format.md)
