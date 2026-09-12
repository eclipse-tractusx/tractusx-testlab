# Execution events

<!-- markdownlint-disable MD013 -->

Everything the execution engine does is reported as an event: a job starting, a
test finishing, a step passing, an assertion failing. Those events are what a
live view of a run is built from — the IDE's execution panel, the CLI's progress
output, a log sink.

This page is the contract between the engine and whatever consumes those events.
It is what the IDE implements against.

## The one rule

**Every event carries a `kind`, and `kind` is the only thing a consumer reads to
decide what happened.**

Nothing else in the payload is a discriminator. In particular, `step_type` names
which step ran (`connector/consumer/negotiate`) and never implies an outcome —
a consumer that decides "this was an assertion" by looking for the substring
`assert` in `step_type` is reading a name for a meaning it does not carry, and
will be wrong the first time a step is renamed. Assertions have their own kind
(`assertion_result`); step outcomes have theirs.

The kinds are declared once, in
[`EventKind`](https://github.com/eclipse-tractusx/tractusx-testlab/blob/main/src/tractusx_testlab/models/primitives/enums.py),
and every payload is a pydantic model in
[`models/runtime/events.py`](https://github.com/eclipse-tractusx/tractusx-testlab/blob/main/src/tractusx_testlab/models/runtime/events.py).
The engine publishes them through one place, `ExecutionMonitor`, so there is no
second path that could emit a differently-shaped event.

## Transport

Events reach a consumer over Server-Sent Events:

```text
GET /tck-execution/{job_id}/stream
```

Each event is one SSE frame:

```text
id: 42
event: step.completed
data: {"kind":"step_completed","job_id":"…","test_id":"…","step_id":"…","result":{…}}
```

- **`event:`** is the wire name — the `kind` with its first underscore turned
  into a dot (`step_completed` → `step.completed`). It exists so a consumer can
  subscribe per event type with `EventSource.addEventListener`; the
  authoritative value is still `data.kind`.
- **`id:`** is a monotonic sequence number from the engine's event buffer, not a
  timestamp. Reconnecting with `Last-Event-ID` replays everything after it, so a
  dropped connection does not lose events.
- The stream closes after a terminal event: `job.completed`, `job.failed`, or
  `job.cancelled`.
- A `:keepalive` comment is sent every 15 seconds while idle.

### The CloudEvents envelope

A service that persists or forwards these events wraps each one in a CloudEvents
1.0 envelope — `cx-test-suite-engine` does, for its trace file and its own SSE
stream. The envelope adds an identity and a position; it does **not** rename
anything, and `data` is the event verbatim, `kind` included.

Its `id` is a **path to where in the run the event happened**, so it is
deterministic and readable rather than an opaque hash:

```text
<tck-id>/<test>/<phase>/<step-id>/<nested…>/<event-name>
```

```text
ccm-tck/catalog-policy-validation/execution/negotiate_offer/step.failed
ccm-tck/catalog-policy-validation/execution/negotiate_offer/0/assertion.result
ccm-tck/job.started
```

Every segment is omitted when the event has no such context — a job event is
just `<tck-id>/<event-name>` — so the id says exactly as much as is true. The
segments between the step and the event name are the nesting inside it: an
assertion's `index` within the step's `validate:` block, and, for a step that
runs steps of its own (`flow/if`, `flow/retry`), each nested step id in turn.

Two events therefore share an id only if they are the same event, which is what
makes the id usable as a key: a consumer can address a step's outcome without
having tracked the stream from the beginning, and re-running the same TCK
produces the same ids for the same steps.

## Event kinds

### Job lifecycle

#### `job_started`

The job began executing.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_started"` | |
| `job_id` | string | The run this event belongs to. |
| `tck_id` | string | The TCK being executed. |

```json
{"kind": "job_started", "job_id": "3f1c…", "tck_id": "certificate-management-tck"}
```

#### `job_paused` / `job_resumed`

The operator paused a running job, or resumed a paused one. Both carry only
`kind` and `job_id`.

```json
{"kind": "job_paused", "job_id": "3f1c…"}
```

#### `job_completed`

**Terminal.** Every test completed or was intentionally skipped.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_completed"` | |
| `job_id` | string | |
| `status` | `"COMPLETED"` | Always this value; present so job events share a shape. |

#### `job_failed`

**Terminal.** At least one test failed, or the run raised.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_failed"` | |
| `job_id` | string | |
| `status` | `"FAILED"` | |
| `error` | string \| null | Why it failed, when the engine has a reason to give. |

```json
{"kind": "job_failed", "job_id": "3f1c…", "status": "FAILED", "error": "One or more tests failed"}
```

#### `job_cancelled`

**Terminal.** The operator cancelled the job before it reached an outcome of its
own.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_cancelled"` | |
| `job_id` | string | |
| `status` | `"CANCELLED"` | |

### Test lifecycle

#### `test_started`

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"test_started"` | |
| `job_id` | string | |
| `test_id` | string | The test's id. |
| `index` | integer | Its position in the run, from 0. |

```json
{"kind": "test_started", "job_id": "3f1c…", "test_id": "catalog-policy-validation", "index": 2}
```

#### `test_completed`

Sent whatever the outcome — the outcome is `result.status`, one of `COMPLETED`,
`FAILED`, `SKIPPED`. There is no separate `test_failed` kind, because a test
result already carries its status and its steps.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"test_completed"` | |
| `job_id` | string | |
| `result` | `TestResult` | Status, every step result, timing, assertion summary. |

```json
{
  "kind": "test_completed",
  "job_id": "3f1c…",
  "result": {
    "test_name": "catalog-policy-validation",
    "status": "COMPLETED",
    "execution": [{"step_name": "…", "status": "PASSED", "…": "…"}],
    "total_duration_s": 4.12,
    "assertion_summary": {"total": 6, "passed": 6, "failed_hard": 0, "failed_soft": 0}
  }
}
```

### Step lifecycle

#### `step_started`

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_started"` | |
| `job_id` | string | |
| `test_id` | string | The test the step belongs to. |
| `step_id` | string \| null | The step's own `id:`, when the test gave it one. |
| `step_index` | integer | Its position in the phase, from 0. |
| `step_type` | string | What the step *is* — `connector/consumer/negotiate`. Never an outcome. |
| `step_name` | string | Display name the engine composed for it. |
| `phase` | string | `setup`, `execution` or `teardown` — the test's own three keys. |
| `inputs` | object \| null | The step's `with:` block **resolved** — every `${{ … }}` reference substituted for the value the run seeded or produced. A reference that names nothing in scope leaves the block as written, and the terminal event reports it as the step's failure. |

```json
{
  "kind": "step_started",
  "job_id": "3f1c…",
  "test_id": "catalog-policy-validation",
  "step_id": "negotiate_offer",
  "step_index": 1,
  "step_type": "connector/consumer/negotiate",
  "step_name": "[2/6] negotiate_offer",
  "phase": "execution",
  "inputs": {"dataset_id": "urn:uuid:9b7c…"}
}
```

#### `step_call`

One call the step made, published **as soon as its answer came back** — while the
step is still running. A step is not one call, and the long ones are long because
they are many: a DSP pull is a catalog query, a negotiation and a poll loop that
can run for a minute. A consumer that waited for `step_completed` to learn what
the step had been doing would show a spinner for that minute, and the step's
terminal event would have to carry the whole conversation a second time.

Zero or more of these arrive between a step's `step_started` and its terminal
event, in the order the calls completed. A step that makes no HTTP call publishes
none.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_call"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `step_type` | string | The step's `uses:` value. |
| `index` | integer | Position of the call within the step, from 1. |
| `call` | `HttpExchange` | `request`, `response` (absent when the transport raised), `error`, `context` and `started_at`. |

`call.context` names who sent it: the SDK method for a call `tractusx-sdk` made on
the engine's behalf (`CatalogController.get_catalog`), `testlab/http_client` for
one the engine made itself. Credential-bearing headers are masked, per
[ADR-0016](decision-records/backend/ADR-0016-execution-trace-format.md).

```json
{
  "kind": "step_call",
  "job_id": "3f1c…",
  "test_id": "pull-ccmapi",
  "step_id": "pull_ccmapi_endpoint",
  "step_type": "connector/consumer/pull_data_filtered",
  "index": 3,
  "call": {
    "context": "ContractNegotiationController.get_by_id",
    "request": {"method": "GET", "url": "https://connector.example.com/management/v3/contractnegotiations/9d6c…", "headers": {"x-api-key": "***"}, "params": null, "body": null},
    "response": {"status_code": 404, "headers": {"content-type": "application/json"}, "body": {"detail": "Not Found"}, "duration_ms": 4.0},
    "error": null,
    "started_at": "2026-08-19T06:24:53.437Z"
  }
}
```

#### `step_completed` / `step_failed` / `step_skipped`

Exactly one of the three follows every `step_started`. Which one is decided by
the step's `result.status` at the single place that status is known — a consumer
never re-derives it.

| Kind | Emitted when |
|------|--------------|
| `step_completed` | The step ran and no hard assertion failed. |
| `step_failed` | A hard assertion failed, or the step raised. |
| `step_skipped` | The step's `if:` condition was false, or no implementation is registered for its `uses:`. |

All three share a shape:

| Field | Type | Description |
|-------|------|-------------|
| `kind` | one of the three | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `result` | `StepResult` | Status, timing, output, request/response, assertion results. |

```json
{
  "kind": "step_failed",
  "job_id": "3f1c…",
  "test_id": "catalog-policy-validation",
  "step_id": "negotiate_offer",
  "result": {
    "step_name": "[2/6] negotiate_offer",
    "step_type": "connector/consumer/negotiate",
    "status": "FAILED",
    "duration_s": 30.2,
    "error": "Expected status_code=200, got 502",
    "request": {"method": "POST", "url": "https://…/v3/edrs"},
    "response": {"status_code": 502}
  }
}
```

A failure that can say more than a sentence also carries `result.error_code` —
the machine-readable name the trace publishes as `errors[].code` — and
`result.error_context`, the evidence behind the message, published as
`errors[].context` (ADR-0016). `connector/consumer/pull_data_filtered` failing on
the policy sets `POLICY_MISMATCH` and a context holding every offer it compared
and how each differed, so a consumer renders the comparison instead of parsing
it back out of `error`. Both are absent when the error has only its sentence.

#### `step_listening`

`mock/api` has registered an endpoint: from now on the system under test may
call it. Everything else in a run is testlab calling out; this is the first of
the three moments the run depends on a call coming *in*, so the event says where
that call has to go. A call that arrives before the test reaches its wait step
is held for it.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_listening"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `step_type` | string | `mock/api`. |
| `listener` | `Listener` | `method`, `url` and `path` — where to call. `url` is the address as the engine knows it. |

```json
{
  "kind": "step_listening",
  "job_id": "3f1c…",
  "test_id": "external-callback",
  "step_id": "open_callback",
  "step_type": "mock/api",
  "listener": {"method": "POST", "url": "http://localhost:8100/testlab-e2e/callback", "path": "/testlab-e2e/callback"}
}
```

On the console: `step.listening [external-callback] open_callback mock/api — call POST http://localhost:8100/testlab-e2e/callback`.
In the trace it is a `tck.test.step.listening`.

#### `step_waiting`

`mock/wait/http_request` is now blocked on the endpoint, for at most
`timeout_s`. The run has nothing left to do but wait: if the SUT will not make
the call, a person has to, and this is the line that tells them what to type.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_waiting"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `step_type` | string | `mock/wait/http_request`. |
| `listener` | `Listener` | The address the step is blocked on. |
| `timeout_s` | number | How long the step waits before failing. |

```json
{
  "kind": "step_waiting",
  "job_id": "3f1c…",
  "test_id": "external-callback",
  "step_id": "await_call",
  "step_type": "mock/wait/http_request",
  "listener": {"method": "POST", "url": "http://localhost:8100/testlab-e2e/callback", "path": "/testlab-e2e/callback"},
  "timeout_s": 30.0
}
```

On the console: `step.waiting [external-callback] await_call mock/wait/http_request — call POST http://localhost:8100/testlab-e2e/callback (up to 30s)`.
In the trace it is a `tck.test.step.waiting`.

#### `step_received`

The call arrived. Published by `mock/wait/http_request` the moment it has the
request, before its assertions run, so a consumer sees the inbound traffic the
same way `step_call` shows the outbound.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_received"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `step_type` | string | `mock/wait/http_request`. |
| `listener` | `Listener` | The address that was called. |
| `request` | `CallbackResult` | The inbound request: `method`, `path`, `headers`, `query_params`, `payload`, `received_at`. |
| `waited_ms` | integer | How long the wait step was blocked. `0` when the call had arrived before the step got there. |

```json
{
  "kind": "step_received",
  "job_id": "3f1c…",
  "test_id": "external-callback",
  "step_id": "await_call",
  "step_type": "mock/wait/http_request",
  "listener": {"method": "POST", "url": "http://localhost:8100/testlab-e2e/callback", "path": "/testlab-e2e/callback"},
  "request": {"listener_name": "POST:/testlab-e2e/callback", "path": "/testlab-e2e/callback", "method": "POST",
              "headers": {"content-type": "application/json"}, "query_params": {},
              "payload": {"from": "stub-sut"}, "received_at": "2026-09-10T12:00:03.412Z", "timed_out": false},
  "waited_ms": 3012
}
```

On the console: `step.received [external-callback] await_call mock/wait/http_request ← POST /testlab-e2e/callback after 3012ms body={"from": "stub-sut"}`.
In the trace it is a `tck.test.step.received`.

### Assertions

#### `assertion_result`

One event per assertion in a step's `validate:` block, published **before** that
step's own outcome event.

This is the kind that exists so nobody has to guess. A consumer that wants to
show assertions separately from steps reads these; it does not look for
assertion-shaped step types.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"assertion_result"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | The step the assertion was evaluated on. |
| `step_name` | string | |
| `index` | integer | Position in the step's `validate:` block, from 0. |
| `assertion` | `AssertionResult` | `passed`, `expected`, `actual`, `message`, `severity`. |

```json
{
  "kind": "assertion_result",
  "job_id": "3f1c…",
  "test_id": "catalog-policy-validation",
  "step_id": "negotiate_offer",
  "step_name": "[2/6] negotiate_offer",
  "index": 0,
  "assertion": {
    "passed": false,
    "expected": 200,
    "actual": 502,
    "message": "Expected 200, got 502",
    "severity": "HARD"
  }
}
```

A `SOFT` failure is reported here and does not fail the step; a `HARD` one is
followed by `step_failed`.

## Ordering

Within a job, events arrive in execution order, and the `id:` sequence is
monotonic. The nesting is:

```text
job_started
  test_started
    step_started
      assertion_result        (zero or more)
    step_completed | step_failed | step_skipped
  test_completed
job_completed | job_failed | job_cancelled
```

`job_paused` and `job_resumed` can appear between any two step events.
`job_cancelled` can end the stream at any point.

## Adding a kind

1. Add the value to `EventKind`.
2. Add its payload model to `models/runtime/events.py` and to the
   `ExecutionEvent` union.
3. Add the `on_*` method to `ExecutionMonitor` — the publisher is the only place
   that builds an event, so a new kind cannot be emitted from anywhere else. A
   step-level kind goes on its `StepEvents` half (`_monitor_steps.py`).
4. Document it here, with a field table and an example.

Step 4 is not optional: this page is the contract, and a kind that is emitted but
undocumented is a kind consumers will handle by guessing.
