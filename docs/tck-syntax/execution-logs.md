# 8. Execution Logs — CloudEvents / JSONL

## 8.1 Purpose **[SPEC]**

One syntax, two purposes:

- **Live Execution Tracking** — streaming events from Backend to Frontend during execution, over **SSE**
  (Server-Sent Events, normal HTTP/1.1, fragmented/chunked response). The Frontend opens the connection by
  calling `/tck/execute` and can call another API to close it (stop/pause). On error, events may carry
  recommendations, error traces and information about what was tested.
- **Execution Tracing & Debug** — the same structure, stored, containing the HTTP requests and responses sent
  and received, so incompatibilities can be diagnosed precisely after the fact and a CAB can verify the report.

## 8.2 Envelope **[SPEC]**

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

## 8.3 Event type registry **[OBS + PROP]**

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

## 8.4 `data` payload **[PROP]**

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
