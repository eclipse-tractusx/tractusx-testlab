<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5). -->
<!-- It was reviewed and tested by a human committer. -->

# Execution events

<!-- markdownlint-disable MD013 -->

Everything the execution engine does is reported as an event: a job starting, a
test finishing, a step passing, an assertion failing. Those events are what a
live view of a run is built from — a client following the server's event stream,
the CLI's progress output, a log sink.

This page is the contract between the engine and whatever consumes those events.

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
GET /testlab/tck-execution/{job_id}/stream
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
1.0 envelope. The envelope adds an identity and a position; it does **not** rename
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

#### `job_held` / `job_restored`

A paused run has stopped and is on hold, or has left it and goes on
(ADR-0026). On hold, every contract definition the run created is deleted
from its connector and its mocks answer 404; on leaving it, the definitions are
created again. `job_held` follows `job_paused` once the step in flight has
ended, or stopped for the pause (`step_suspended`). `job_restored` follows the
resume, and also a cancellation of the paused run, so that its teardown finds
what it created.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_held"` / `"job_restored"` | |
| `job_id` | string | |
| `withdrawn` | string[] | `job_held`: the contract definitions deleted, in the order they were created. |
| `kept` | object | `job_held`: definition id → why the connector would not delete it. Empty when all were. |
| `restored` | string[] | `job_restored`: the contract definitions created again. |
| `lost` | object | `job_restored`: definition id → why the connector would not take it back. |

```json
{"kind": "job_held", "job_id": "3f1c…", "withdrawn": ["testlab-ccmapi-cd-3f1c"], "kept": {}}
```

In the trace they are a `tck.held` and a `tck.restored`.

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
| `attempt` | integer | Which run of this test within the job, from 1. Above 1 only in a session, for an `async: true` test run again. |

```json
{"kind": "test_started", "job_id": "3f1c…", "test_id": "catalog-policy-validation", "index": 2, "attempt": 1}
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

#### `test_awaiting`

**Labs.** Only a `TckSession` sends it (see [Sessions](#sessions)). An
`async: true` test is ready and waits for someone to run it; nothing is running.
Sent once per such test, after the tests that run on their own are done.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"test_awaiting"` | |
| `job_id` | string | |
| `test_id` | string | The test's id. |
| `index` | integer | Its position in the manifest, from 0. |

```json
{"kind": "test_awaiting", "job_id": "3f1c…", "test_id": "push-notification", "index": 3}
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

`result.error_origin` says who the failure belongs to, published as
`errors[].origin`: `sut` for a verdict, `authoring` for a TCK or run
configuration that is wrong (`AUTHORING_ERROR` — a mock asset id the TCK reused
across runs, a reference to a name nothing publishes), `infrastructure` and
`connector` for the deployment and the dataspace exchange, `engine` for TestLab
itself (ADR-0016).

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
| `listener` | `Listener` | The address the step is blocked on. `via` says how the call has to arrive: `direct` (`mock/wait/http_request` — the SUT calls `url`) or `dataplane` (`mock/wait/dataplane/http_request` — the SUT finds the offer on the engine connector at `offer.dsp_url` / `offer.participant_id` with `offer.catalog_filters`, built from the asset's public `offer.properties` when the step names the asset (`with.asset`), else from `offer.asset_id`; it negotiates the offer and calls through its data plane, so `url` is only the data plane's target). `action`, when the wait step declares one, is what the test asks of the SUT: `label`, `description`, `recommendation` (the steps, in order) and `fields` (`label`, `value`) to copy; a viewer shows it in place of what it would derive from the rest. |
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

On the console: `step.waiting [external-callback] await_call mock/wait/http_request — call POST http://localhost:8100/testlab-e2e/callback (up to 30s)`,
and under it a framed block for the person who may have to act (a data-plane wait names the
connector and the catalog filter instead of the mock URL):

```
==============================================================================
  ACTION REQUIRED                                              waits up to 30s
  [external-callback] await_call
------------------------------------------------------------------------------
  What to do:
    1. Send POST http://localhost:8100/testlab-e2e/callback.
==============================================================================
```
In the trace it is a `tck.test.step.waiting`.

#### `step_suspended`

The run was paused while `mock/wait/*` was blocked: the listener has closed
and the timeout has stopped (ADR-0026). When the run resumes, the step opens
the listener again and publishes a fresh `step_waiting` whose `timeout_s` is
this event's `remaining_s`. A consumer counting down re-reads its deadline
from that event.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_suspended"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `step_type` | string | `mock/wait/http_request` or `mock/wait/dataplane/http_request`. |
| `listener` | `Listener` | The address the step was blocked on, as in `step_waiting`. |
| `remaining_s` | number | What is left of the timeout: what the step waits for once the run resumes. |
| `waited_ms` | integer | How long the step has waited so far, pauses excluded. |

```json
{
  "kind": "step_suspended",
  "job_id": "3f1c…",
  "test_id": "external-callback",
  "step_id": "await_call",
  "step_type": "mock/wait/http_request",
  "listener": {"method": "POST", "url": "http://localhost:8100/testlab-e2e/callback", "path": "/testlab-e2e/callback"},
  "remaining_s": 21.4,
  "waited_ms": 8600
}
```

On the console: `step.suspended [external-callback] await_call mock/wait/http_request — call POST http://localhost:8100/testlab-e2e/callback (paused, 21s left)`.
In the trace it is a `tck.test.step.suspended`.

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

#### `step_selecting`

`connector/query_catalog/select_asset` read a catalog that offers more than one
asset and waits for the operator to choose one. The host answers through the
player — `player.jobs.selections.answer(job_id, asset_id, step_id)`, or
`POST /testlab/tck-execution/{job_id}/select` with `{"asset_id": …, "step_id": …}`
on the TestLab server — with one of the options' `asset_id`. A pause stops the
clock and keeps the question open; when the run resumes, a fresh
`step_selecting` carries what is left of the timeout as `timeout_s`.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_selecting"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | The id to send back with the answer. |
| `step_type` | string | `connector/query_catalog/select_asset`. |
| `selection` | `AssetSelection` | `counter_party_address`, `counter_party_id`, `options` and the test's `action`, if any. Each option is an `asset_id`, the dataset's other `properties`, and the `policies` (`odrl:hasPolicy`) it is offered under. |
| `timeout_s` | number | How long the step waits for the choice, pauses excluded. |

```json
{
  "kind": "step_selecting",
  "job_id": "3f1c…",
  "test_id": "certificate-push",
  "step_id": "select_ccmapi",
  "step_type": "connector/query_catalog/select_asset",
  "selection": {
    "counter_party_address": "https://sut.example/api/v1/dsp",
    "counter_party_id": "BPNL000000000001",
    "options": [
      {"asset_id": "ccmapi-1", "properties": {"dct:type": {"@id": "cx-taxo:CCMAPI"}},
       "policies": [{"@id": "offer-1", "odrl:permission": {"odrl:action": {"@id": "odrl:use"}}}]},
      {"asset_id": "ccmapi-2", "properties": {"dct:type": {"@id": "cx-taxo:CCMAPI"}}, "policies": []}
    ],
    "action": null
  },
  "timeout_s": 300.0
}
```

On the console: `step.selecting [certificate-push] select_ccmapi connector/query_catalog/select_asset — choose 1 of 2 (up to 300s)`, then one row per option.
In the trace it is a `tck.test.step.selecting`.

#### `step_selected`

The operator chose. Published before the step returns its output.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"step_selected"` | |
| `job_id` | string | |
| `test_id` | string | |
| `step_id` | string \| null | |
| `step_type` | string | `connector/query_catalog/select_asset`. |
| `asset_id` | string | The asset chosen. |
| `waited_ms` | integer | How long the step waited for the choice, pauses excluded. |

On the console: `step.selected [certificate-push] select_ccmapi connector/query_catalog/select_asset → ccmapi-1 after 5120ms`.
In the trace it is a `tck.test.step.selected`.

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

`job_paused` and `job_resumed` can appear between any two step events, and so
can the hold they bracket: `job_paused`, then `job_held`, then — once resumed —
`job_resumed` and `job_restored`. A wait blocked when the pause came reports
`step_suspended` before `job_held` and a fresh `step_waiting` after
`job_restored`.
`job_cancelled` can end the stream at any point.

### Sessions

A host that holds a run open between tests (`TestlabPlayer.open_session`, labs)
sends the same events, in this order:

```text
job_started
  test_started … test_completed          (every test not marked async: true)
  test_awaiting                          (each async: true test)
  test_started(attempt=n) … test_completed   (each time one is asked for)
  test_started … test_completed          (SKIPPED, for each one never asked for)
job_completed | job_failed
```

The verdict counts each test's latest attempt.

## Adding a kind

1. Add the value to `EventKind`.
2. Add its payload model to `models/runtime/events.py` (or, for the hold's,
   `hold_events.py`; for the operator's choice, `selection.py`) and to the
   `ExecutionEvent` union.
3. Add the `on_*` method to `ExecutionMonitor` — the publisher is the only place
   that builds an event, so a new kind cannot be emitted from anywhere else. A
   step-level kind goes on its `StepEvents` half (`_monitor_steps.py`), or on
   `SelectionEvents` (`_monitor_selection.py`) for the operator's choice.
4. Document it here, with a field table and an example.

Step 4 is not optional: this page is the contract, and a kind that is emitted but
undocumented is a kind consumers will handle by guessing.
