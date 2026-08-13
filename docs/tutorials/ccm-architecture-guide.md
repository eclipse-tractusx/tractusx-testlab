<!--
 Eclipse Tractus-X - Tractus-X TestLab

 Copyright (c) 2026 Contributors to the Eclipse Foundation

 See the NOTICE file(s) distributed with this work for additional
 information regarding copyright ownership.

 This program and the accompanying materials are made available under the
 terms of the Apache License, Version 2.0 which is available at
 https://www.apache.org/licenses/LICENSE-2.0.

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 License for the specific language governing permissions and limitations
 under the License.

 SPDX-License-Identifier: Apache-2.0
-->
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# Company Certificate Management — Architecture Guide

This guide explains the system architecture, execution design, and extension points of the CX-0135 conformity test suite.

## System Architecture

Four components collaborate during a test run:

```mermaid
flowchart LR
    IDE[IDE<br/>React / Blockly] <--> Backend[Backend<br/>Python / FastAPI]
    Backend <--> Mock[Mock Server<br/>FastAPI]
    Backend <--> SUT[SUT<br/>CCMAPI Implementation]
    SUT --> Mock

    style IDE fill:#1565c0,stroke:#333,color:#fff
    style Backend fill:#2e7d32,stroke:#333,color:#fff
    style Mock fill:#6a1b9a,stroke:#333,color:#fff
    style SUT fill:#e65100,stroke:#333,color:#fff
```

| Component | Technology | Role |
|-----------|-----------|------|
| **IDE** | React 19, Blockly 12, TypeScript (separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository) | Visual test authoring and real-time execution monitoring |
| **Backend** | Python 3.12, FastAPI | YAML parsing, test orchestration, step execution |
| **Mock Server** | Embedded FastAPI | Callback endpoints, canned responses for inbound SUT calls |
| **SUT** | Any CX-0135 implementation | The system being validated |

## Execution Architecture

When a user clicks Execute in the IDE (or runs `testlab run` from the CLI), this sequence runs:

```mermaid
sequenceDiagram
    participant IDE as IDE
    participant API as Backend API
    participant Parser as YamlParser
    participant Player as Player
    participant Step as StepRunner
    participant SUT as SUT
    participant Mock as Mock Server

    IDE->>API: POST /run/yaml (YAML body)
    API-->>IDE: 202 (job_id)
    IDE->>API: GET /stream/{job_id} (SSE)
    API->>Parser: parse(yaml) → Tck
    Parser->>Player: run_test_case(tck)
    Player->>Player: topological_sort(scripts)
    loop Each script in order
        Player->>Step: execute(step, context)
        Step->>SUT: DSP / HTTP call
        SUT-->>Step: Response
        SUT->>Mock: Async callback
        Mock-->>Step: Resolve future
        Step-->>Player: StepResult
        Player-->>IDE: SSE event
    end
```

### IDE → Backend handoff

The IDE frontend lives in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository; this engine repository exposes the HTTP API it talks to.

1. `ExecuteButton.handleExecute()` converts the Blockly workspace to YAML via `modelToYaml()`
2. `useExecutionStore.execute(yaml)` sends `POST /testlab/test-execution/run`
3. The backend returns HTTP 202 with a `job_id`
4. The IDE opens an SSE stream at `GET /testlab/test-execution/{job_id}/stream`
5. The backend emits `step.started`, `step.completed`, and `step.failed` events
6. The `ExecutionPanel` renders results as they arrive

### Backend orchestration

1. `YamlParser` deserializes the YAML into a `Tck` model (metadata + variables + test references)
2. Each test reference resolves to a `Script` (setup steps + main steps + teardown steps)
3. The `Player` calls `topological_sort(scripts)` to order scripts by `depends_on` edges
4. For each script: run setup → run main steps → run teardown (even if main steps fail)
5. Per step: resolve `${{ }}` references → execute the step → evaluate `validate:` assertions → publish the step's declared `returns:` outputs into the run context

## Test Orchestration Design

### Why topological sorting?

Tests declare dependencies via `depends_on`. For example, `validate_payload` depends on `request_certificate` and reads the `document_id` output it publishes. The player builds a dependency graph and runs scripts in an order that satisfies all dependencies.

```mermaid
flowchart TD
    REQ[request_certificate] --> VAL[validate_payload]
    REQ --> AWAIT[await_feedback_callback]
    REQ --> SEND[send_feedback]
    VAL --> SEND
    AWAIT --> SEND
    PUSH[push_certificate]
    AVAIL[available_notification]
    EXPOSE[expose_testlab_asset]
    ERR[error_handling]
```

Independent scripts (no inbound edges) can run in any order. The player preserves declaration order for independent scripts.

### Variable flow

Variables propagate through three mechanisms:

| Mechanism | Scope | Example |
|-----------|-------|---------|
| Declared `returns:` outputs | Published automatically to the run context after each step | `connector/dataplane/http_request` publishes `status_code` and `response_body`; later steps read `${{ execution.<step_id>.<output> }}` |
| `store_in_variable` parameter | Explicit capture into a named context variable (on util steps such as `util/json_path_extract`, `util/base64`, `util/parse_kv`) | `util/json_path_extract` stores `ccmapi_asset_id` |
| Script output promotion | Across scripts | When a script completes, the player promotes its declared output variables into the shared run context for downstream scripts (`depends_on` ordering guarantees they exist) |

Steps reference variables with `${{ }}` interpolation (e.g. `${{ env.sut_counter_party_address.value }}` or `${{ execution.pull_ccmapi_endpoint.edr_token }}`). The step runner resolves them from the execution context before calling the step executor.

### Callback handling

The CCM suite uses asynchronous callbacks: the SUT processes a request and later POSTs a status update to a TestLab endpoint. The `CallbackManager` handles this:

```mermaid
sequenceDiagram
    participant Step as mock/api step
    participant CM as CallbackManager
    participant Mock as Mock Server
    participant SUT as SUT

    Step->>CM: register_future("/companycertificate/status")
    Step->>CM: register_mock(path, canned_response)
    Note right of Step: Step blocks on future.await()
    SUT->>Mock: POST /companycertificate/status
    Mock->>CM: resolve_future(path, body)
    Mock-->>SUT: canned_response
    CM-->>Step: callback body (future resolved)
```

1. `mock/api` registers an `asyncio.Future` for a specific HTTP path
2. A subsequent `mock/wait/http_request` step blocks waiting for the future to resolve
3. When the SUT sends an HTTP request to the mock server at that path, the mock server resolves the future
4. The mock server also returns a canned response to the SUT
5. The original step unblocks with the received callback body

## CX-0135 Compliance Mapping

Each CX-0135 requirement maps to a specific test and step type:

| CX-0135 Requirement | Test | Step Type | What Is Validated |
|---------------------|------|-----------|-------------------|
| §2.1.1.1 REQUEST mechanism | `request_certificate` | `connector/dataplane/http_request` | POST with header+content envelope returns 200 |
| §3.1 Semantic model | `validate_payload` | `validate/schema` | Payload matches BusinessPartnerCertificate v3.1.0 |
| §2.1.1.3 FEEDBACK inbound | `await_feedback_callback` | `mock/wait/http_request` | SUT sends callback to `/companycertificate/status` |
| §2.1.1.3 FEEDBACK outbound | `send_feedback` | `connector/dataplane/http_request` | Feedback notification via EDC data plane |
| §2.1.1.2 PUSH mechanism | `push_certificate` | `connector/dataplane/http_request` | Push via data plane to `/companycertificate/push` |
| §2.1.1.4 AVAILABLE notification | `available_notification` | `connector/dataplane/http_request` | Notification to `/companycertificate/available` |
| §2.1.4.1 Provider asset exposure | `expose_testlab_asset` | `connector/provider/create_asset` + `mock/wait/http_request` | SUT discovers and pulls from TestLab EDC |
| §2.1.1.1.4 Error handling | `error_handling` | `connector/dataplane/http_request` | REJECTED status in response envelope |

### Dataspace protocol mapping

Every test that communicates with the SUT follows the standard EDC flow:

| DSP Phase | TestLab Step Type | Purpose |
|-----------|-------------------|---------|
| Catalog discovery | `connector/consumer/query_catalog` | Find the CCMAPI asset in the provider's catalog |
| Contract negotiation | `connector/consumer/negotiate` | Agree on usage policies (e.g., `cx.ccm.base:1`) |
| Transfer initiation | `connector/consumer/initiate_transfer` | Get an EDR with data plane auth credentials |
| Data plane call | `connector/dataplane/http_request` | Send the actual CCMAPI message via the EDR |

The `connector/consumer/pull_data_filtered` step bundles the first three phases (filtered catalog query, policy check, negotiation, and EDR retrieval) into a single step — the shipped CCM suite uses it.

## Mock Server Architecture

The embedded mock server serves two purposes: it provides canned responses to the SUT and it captures inbound requests for assertion.

### Registration flow

The `mock/api` step type registers both a canned response and a callback future:

```python
# Simplified — actual implementation in step executors
mock_server.register_mock(path="/companycertificate/status", response=canned_body)
future = callback_manager.register_future(path="/companycertificate/status")
```

When the SUT hits the mock path, the server:

1. Returns the canned response to the SUT (so the SUT sees a valid response)
2. Resolves the future with the request body (so the test step can assert on it)

### mock/wait/http_request

The `mock/wait/http_request` step blocks on the registered future with a configurable timeout. If the SUT never calls back, the step fails with a timeout error.

## SUT Stub Architecture

The stub at `stubs/ccm-sut/` replaces a real EDC connector and CCMAPI service for local testing.

### What the stub replaces

```mermaid
flowchart LR
    TL[TestLab] <--> Stub[SUT Stub :8090]
    Stub --> Mock[Mock Server :8100]

    subgraph Stub
        DSP[DSP Endpoints]
        MGMT[Management API]
        CCMAPI[CCMAPI Endpoints]
    end

    style TL fill:#2e7d32,stroke:#333,color:#fff
    style Stub fill:#e65100,stroke:#333,color:#fff
    style Mock fill:#6a1b9a,stroke:#333,color:#fff
```

### Endpoint behavior

| Endpoint | Behavior |
|----------|----------|
| `POST /api/v1/dsp/catalog/request` | Returns catalog with 2 datasets: CCMAPI (`ccm-offer-001`) and Submodel (`cert-asset-001`) |
| `POST /api/v1/dsp/negotiations/initial` | Auto-finalizes, returns agreement ID |
| `POST /management/v3/transferprocesses` | Returns static transfer ID |
| `GET /management/v3/edrs/{id}/dataaddress` | Returns EDR: `endpoint=localhost:8090`, `authCode=edr-token-xxx` |
| `POST /companycertificate/request` | Returns `{requestStatus: COMPLETED}` + schedules 10s callback |
| `POST /companycertificate/push` | Returns OK + schedules 1s feedback callback |
| `POST /companycertificate/available` | Returns OK (no callback) |
| `POST /companycertificate/notification/receive` | Returns OK + schedules 1s ack callback |

### Callback mechanism

The stub sends three types of async callbacks to the TestLab mock server:

| Trigger | Callback URL | Delay | Payload |
|---------|-------------|-------|---------|
| `/companycertificate/request` | `/companycertificate/status` | 10s | `{certificateStatus: RECEIVED, documentId}` |
| `/companycertificate/push` | `/companycertificate/status` | 1s | `{certificateStatus: RECEIVED}` |
| `/companycertificate/notification/receive` | `/companycertificate/notification/receive` | 1s | Notification ack |

### Startup consumer simulation

On startup, the stub waits 20s then GETs `{TESTLAB_CALLBACK_URL}/api/v1/companycertificate` to simulate a real SUT pulling TestLab's exposed asset (for `expose_testlab_asset`).

### Extending the stub

Add routes in `app.py`, response builders in `responses.py`. See `stubs/ccm-sut/README.md` for details.

## Extension Points

### Adding a new standard's test suite

1. Create a directory for the suite — the shipped reference lives at `docs/examples/certificate-management-v2/raw/` in this repository
2. Write an `index.yaml` with `kind: tck`, metadata, variables, and test references
3. Write individual test YAML files with `kind: test`
4. To surface it in the visual IDE, add it to the example project list in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository

### Creating custom step executors

Implement a new step executor in `src/tractusx_testlab/steps/` and register it with the `@step()` decorator under a unique id following the `<category>/<module>/<function>` scheme. See [Create a Step Executor](create-step-executor.md).

### Adding new assertion types

Assertions are validation steps (`validate/assert`, `validate/field`, `validate/schema`) that read a step's declared `returns:` outputs and evaluate an operator (e.g., `equals`, `not_null`, `matches_regex`). See [Add an Assertion Type](add-assertion-type.md) for extending them.

### CI/CD integration

Run the test suite headless via CLI:

```bash
testlab run index.yaml --config run-config.yaml
```

The command prints per-script and per-step results to stdout and exits non-zero on failure; detailed logs (including the execution trace) are written to the `--logs-dir` directory (default `./logs`). Use the exit code for pass/fail status in your CI pipeline.

## Design Decisions

| Decision | Rationale | Reference |
|----------|-----------|-----------|
| SSE over WebSocket | Simpler server push, no bidirectional channel needed | [ADR-0003](../developer/decision-records/shared/ADR-0003-sse-for-live-ide-execution.md) |
| YAML over JSON for tests | Human-readable, supports comments, familiar to DevOps | Project convention |
| Topological sort over linear | Enables parallel-safe independent tests, enforces dependencies | Player design |
| `asyncio.Future` for callbacks | Native async/await integration, no polling, timeout support | Mock server design |
| `${{ }}` interpolation | GitHub-Actions-style references, explicit about their source (`env.`, `execution.`) | [Specification](../specification/syntax/tck-syntax.md) |

## Next Steps

- **[Developer Guide](ccm-developer-guide.md)** — Setup, running, and debugging
