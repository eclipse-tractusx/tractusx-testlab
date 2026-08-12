# Execution events

<!-- markdownlint-disable MD013 -->

Everything the execution engine does is reported as an event: a job starting, a
script finishing, a step passing, an assertion failing. Those events are what a
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
GET /test-execution/{job_id}/stream
```

Each event is one SSE frame:

```text
id: 42
event: step.completed
data: {"kind":"step_completed","job_id":"…","script":"…","step_id":"…","result":{…}}
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

**Terminal.** Every script completed or was intentionally skipped.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_completed"` | |
| `job_id` | string | |
| `status` | `"COMPLETED"` | Always this value; present so job events share a shape. |

#### `job_failed`

**Terminal.** At least one script failed, or the run raised.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_failed"` | |
| `job_id` | string | |
| `status` | `"FAILED"` | |
| `error` | string \| null | Why it failed, when the engine has a reason to give. |

```json
{"kind": "job_failed", "job_id": "3f1c…", "status": "FAILED", "error": "One or more scripts failed"}
```

#### `job_cancelled`

**Terminal.** The operator cancelled the job before it reached an outcome of its
own.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"job_cancelled"` | |
| `job_id` | string | |
| `status` | `"CANCELLED"` | |

### Script lifecycle

#### `script_started`

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"script_started"` | |
| `job_id` | string | |
| `script` | string | The script's id. |
| `index` | integer | Its position in the run, from 0. |

```json
{"kind": "script_started", "job_id": "3f1c…", "script": "catalog-policy-validation", "index": 2}
```

#### `script_completed`

Sent whatever the outcome — the outcome is `result.status`, one of `COMPLETED`,
`FAILED`, `SKIPPED`. There is no separate `script_failed` kind, because a script
result already carries its status and its steps.

| Field | Type | Description |
|-------|------|-------------|
| `kind` | `"script_completed"` | |
| `job_id` | string | |
| `result` | `ScriptResult` | Status, every step result, timing, assertion summary. |

```json
{
  "kind": "script_completed",
  "job_id": "3f1c…",
  "result": {
    "script_name": "catalog-policy-validation",
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
| `script` | string | The script the step belongs to. |
| `step_id` | string \| null | The step's own `id:`, when the script gave it one. |
| `step_index` | integer | Its position in the phase, from 0. |
| `step_type` | string | What the step *is* — `connector/consumer/negotiate`. Never an outcome. |
| `step_name` | string | Display name the engine composed for it. |
| `phase` | string | `setup`, `main` or `teardown`. |

```json
{
  "kind": "step_started",
  "job_id": "3f1c…",
  "script": "catalog-policy-validation",
  "step_id": "negotiate_offer",
  "step_index": 1,
  "step_type": "connector/consumer/negotiate",
  "step_name": "[2/6] negotiate_offer",
  "phase": "main"
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
| `script` | string | |
| `step_id` | string \| null | |
| `result` | `StepResult` | Status, timing, output, request/response, assertion results. |

```json
{
  "kind": "step_failed",
  "job_id": "3f1c…",
  "script": "catalog-policy-validation",
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
| `script` | string | |
| `step_id` | string \| null | The step the assertion was evaluated on. |
| `step_name` | string | |
| `assertion` | `AssertionResult` | `passed`, `expected`, `actual`, `message`, `severity`. |

```json
{
  "kind": "assertion_result",
  "job_id": "3f1c…",
  "script": "catalog-policy-validation",
  "step_id": "negotiate_offer",
  "step_name": "[2/6] negotiate_offer",
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
  script_started
    step_started
      assertion_result        (zero or more)
    step_completed | step_failed | step_skipped
  script_completed
job_completed | job_failed | job_cancelled
```

`job_paused` and `job_resumed` can appear between any two step events.
`job_cancelled` can end the stream at any point.

## Reserved

`step_waiting` is declared in `EventKind` for a step blocked on an inbound
callback, and **the engine does not currently emit it** — `mock/wait/http_request`
blocks without reporting a job-level transition. Consumers should ignore it until
this note says otherwise rather than building UI on an event that never arrives.

## Adding a kind

1. Add the value to `EventKind`.
2. Add its payload model to `models/runtime/events.py` and to the
   `ExecutionEvent` union.
3. Add the `on_*` method to `ExecutionMonitor` — the publisher is the only place
   that builds an event, so a new kind cannot be emitted from anywhere else.
4. Document it here, with a field table and an example.

Step 4 is not optional: this page is the contract, and a kind that is emitted but
undocumented is a kind consumers will handle by guessing.
