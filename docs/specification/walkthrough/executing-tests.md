<!--

Eclipse Tractus-X - Tractus-X TestLab

Copyright (c) 2026 Catena-X Automotive Network e.V.
Copyright (c) 2026 Contributors to the Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

This work is made available under the terms of the
Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
which is available at
https://creativecommons.org/licenses/by/4.0/legalcode.

SPDX-License-Identifier: CC-BY-4.0

-->

# Executing Tests

This section shows how to run a TCK against live dataspace connectors and read the results.

## Prerequisites

You've completed [Compiling Packages](compiling-packages.md) and have:

- The TCK `my-certificate-tck/index.yaml`, or its compiled package `dist/my-certificate-tck.tck`
- A connector TestLab drives (the *engine* side) and the connector of the system under test (the *SUT* side), with
  their management URL, API key, DSP endpoint and participant ID

`testlab run` accepts either target. Given a manifest, it compiles it to a temporary package first; a `.tck` runs as is.

---

## Step 1 — Bind the Infrastructure

A TCK never names the connectors it talks to. Its `infrastructure` block only says which capabilities each side must
have — here `engine.connector` and `sut.connector` — and the operator binds them. Unbound, the run stops before the first step and names every key it needs:

```text
Cannot run my-certificate-tck.tck:
  This TCK requires infrastructure that is not fully bound: engine.connector, sut.connector
  engine.connector — set:
      infrastructure.engine.connector.management_url   (or TESTLAB_ENGINE_CONNECTOR_MANAGEMENT_URL)
      infrastructure.engine.connector.participant_id   (or TESTLAB_ENGINE_CONNECTOR_PARTICIPANT_ID)
  sut.connector — set:
      infrastructure.sut.connector.participant_id   (or TESTLAB_SUT_CONNECTOR_PARTICIPANT_ID)
      infrastructure.sut.connector.dsp_url   (or TESTLAB_SUT_CONNECTOR_DSP_URL)
```

Bind them in `testlab.config.yaml` — in the working directory or `~/.testlab/` — (copy `testlab.config.example.yaml`
from the repository):

```yaml title="testlab.config.yaml"
infrastructure:
  engine:
    connector:
      management_url: https://engine.example.com/management
      api_key: "<engine management API key>"
      participant_id: BPNL000000000TLB
  sut:
    connector:
      management_url: https://sut.example.com/management
      dsp_url: https://sut.example.com/api/v1/dsp
      participant_id: BPNL000000000001
    dtr:
      base_url: https://sut.example.com/semantics/registry
```

or through the environment, which overrides the file:

```bash
export TESTLAB_SUT_CONNECTOR_DSP_URL=https://sut.example.com/api/v1/dsp
export TESTLAB_SUT_CONNECTOR_PARTICIPANT_ID=BPNL000000000001
```

`testlab config` prints the settings and bindings that resolved, and which came from the environment. Connector
steps address the bound SUT connector by default; `counter_party_address` and `counter_party_id` are only passed to
address somebody else.

---

## Step 2 — Supply Input Variables

Variables declared with `source: input` are values the operator provides. A run that lacks one stops before it starts:

```text
Cannot run my-certificate-tck.tck:
  This TCK needs 1 input variable(s) that were not supplied:
      callback_timeout_s
  Set them under 'variables:' in the run config, or pass --var name=value.
```

Pass them with `--var`:

```bash
testlab run dist/my-certificate-tck.tck --var callback_timeout_s=60
```

or collect them in a run config file under `variables:` and pass it with `--config`. `--var` overrides the file:

```yaml title="run.yaml"
variables:
  callback_timeout_s: 60
```

```bash
testlab run dist/my-certificate-tck.tck --config run.yaml
```

`testlab inspect <package> --variables` lists which variables a TCK asks for, with their scope (`engine` or `sut`).

---

## Step 3 — Run

```bash
testlab run dist/my-certificate-tck.tck --config run.yaml
```

The console shows each step as it runs, then one result table per test and a run summary. Every box is 80 columns
wide unless a step label needs more, in which case all of them widen:

```text
╔===========================================================================================╗
║                                     Test: Ping Catalog                                    ║
╠===========================================================================================╣
║  STEP                                                                     RESULT      TIME║
║  ---------------------------------------------------------------------------------------  ║
║  ✓ ping-catalog[query_catalog]:connector/consumer/query_catalog             PASS      0.4s║
╠===========================================================================================╣
║  RESULT: PASS  |  1 passed  0 failed  0 skipped  |  Total: 0.4s                           ║
╚===========================================================================================╝

  Assertions: 1 total, 1 passed, 0 hard-failed, 0 soft-failed

…

╔===========================================================================================╗
║                                      TCK RUN SUMMARY                                      ║
╠===========================================================================================╣
║  TEST                                                                     RESULT      TIME║
║  ---------------------------------------------------------------------------------------  ║
║  ✓ Ping Catalog                                                             PASS      0.4s║
║  ✓ Request Certificate                                                      PASS      9.8s║
╠===========================================================================================╣
║  RESULT: PASS  |  2 passed  0 failed  0 skipped  |  Total: 10.2s                          ║
╚===========================================================================================╝
```

Setup steps are labelled `test[setup:<id>]`. A failed step lists why under its table — the failed checks by their
`name`, or the error and whether it came from the SUT or the engine — and `testlab run` exits non-zero when any test fails.

---

## Step 4 — Skip Optional Tests

A test the author marked `skippable: true` in the manifest may be left out at run time with the `skip_tests`
variable — without modifying the package.

### Discover which tests are skippable

```bash
testlab inspect dist/my-certificate-tck.tck
```

```text
  Test: Ping Catalog  |  ID: ping_catalog.yaml  |  Skippable: Yes
  Test: Request Certificate  |  ID: request_certificate.yaml  |  Skippable: No
```

The **ID** (the test's file name) is what `skip_tests` takes; the display name cannot be used.

### Skip tests

```bash
testlab run dist/my-certificate-tck.tck --config run.yaml --var skip_tests=ping_catalog.yaml
```

Several tests are separated by commas (`--var skip_tests=a.yaml,b.yaml`), or listed in the run config:

```yaml title="run.yaml"
variables:
  callback_timeout_s: 60
  skip_tests: ping_catalog.yaml,error_handling.yaml
```

A skipped test is reported as `SKIP` and does not count as a pass:

```text
║  - Ping Catalog                                                             SKIP      0.0s║
║  ✓ Request Certificate                                                      PASS      9.8s║
╠===========================================================================================╣
║  RESULT: PASS  |  1 passed  0 failed  1 skipped  |  Total: 9.8s                           ║
```

### Invalid skip requests

The request is checked **before any test executes**. Naming a test that does not exist, or is not skippable, refuses the whole run:

```text
Cannot run my-certificate-tck.tck:
  Cannot skip test(s) 'request_certificate.yaml': not marked skippable. Set skippable: true on the test entry in the TCK manifest to allow skipping.
```

!!! note
    Only the TCK author can allow skipping. Tests without `skippable: true` are mandatory conformance checks.

---

## Step 5 — Run Encrypted Packages

An encrypted package needs the Player's identity and the Compiler's public key (see
[Compiling Packages — Step 4](compiling-packages.md#step-4--sign-and-encrypt-for-a-player-optional)):

```bash
testlab run dist/my-certificate-tck-encrypted.tck \
  --player-keys .keys/player \
  --compiler-pub .keys/compiler/signing.pub \
  --config run.yaml
```

The Player first verifies the Compiler's signature over the readable manifest and the encrypted payload, then unwraps
its own copy of the content key, decrypts the payload, verifies the package checksum against the one the manifest
states, and only then loads the TCK. Without keys it refuses:

```text
Refused to run my-certificate-tck-encrypted.tck:
  Package 'my-certificate-tck-encrypted.tck' is encrypted — provide --player-keys to load it.
```

---

## Step 6 — Result Logs

### The Two Records a Run Leaves

Every run writes two files, and they are not two formats of the same thing.

| | Transcript | Execution trace |
|---|---|---|
| **Where** | `./logs/<date>/<time>_<job_id>.log` | `./data/<date>/<time>_<job_id>.jsonl` |
| **Override** | `--logs-dir` (or `TESTLAB_LOGS_DIR`) | `--data-dir` (or `TESTLAB_DATA_DIR`) |
| **Format** | Plain text, identical to what scrolled past on the console | CloudEvents v1.0 JSON-lines ([ADR-0016](../../developer/decision-records/backend/ADR-0016-execution-trace-format.md)) |
| **Read it when** | You want to see what happened | You want to know exactly what went over the wire, or you are feeding a tool |

```bash
testlab run dist/my-certificate-tck.tck \
  --config run.yaml \
  --logs-dir ./logs \
  --data-dir ./data
```

#### The transcript

Everything the console showed, in order: the compile narration, the run header, the execution events, any traceback, and the result banner. It is copied from `stdout`/`stderr` rather than from a logger, so nothing a run prints is left out. Colour is stripped and the progress bar collapses to one line.

```text
Preparing run package from index.yaml ...
Compiled → /tmp/testlab-run-50qwd21f/industry-core-part-type-tck-v2.1.1.tck
  Package checksum : blake2b:62915239b916b565…
...
2026-08-18 15:38:12 [INFO    ] [testlab.player.17bc9b69] step.started [dtr-filterability] pull_dtr connector/consumer/pull_data_filtered (execution)
2026-08-18 15:38:13 [INFO    ] [testlab.player.17bc9b69] step.failed [dtr-filterability] pull_dtr connector/consumer/pull_data_filtered FAILED 538ms — [Connector Service]: catalog request refused, 403
  → POST https://connector.example.com/api/data/v3/catalog/request body={"@type": "CatalogRequest", …}
  ← 403 in 44ms body=<html>…403 Forbidden…</html>
  (2 calls — full request/response in the execution trace)
Engine fault while running step dtr-filterability[pull_dtr]:connector/consumer/pull_data_filtered
Traceback (most recent call last):
  ...
ConnectionError: [Connector Service]: It was not possible to get the catalog…
...

╔==============================================================================╗
║                            Test: dtr-filterability                           ║
╠==============================================================================╣
║  STEP                                          RESULT      TIME              ║
║  --------------------------------------------------------------------------  ║
║  ✓ encode_filter                                 PASS      0.0s              ║
║  ✗ pull_dtr                                      FAIL      0.5s              ║
╠==============================================================================╣
║  RESULT: FAIL  |  1 passed  1 failed  0 skipped  |  Total: 0.5s              ║
╚==============================================================================╝

  ✗ pull_dtr
           Error: [Connector Service]: catalog request refused, 403

  Assertions: 1 total, 1 passed, 0 hard-failed, 0 soft-failed

╔==============================================================================╗
║                                TCK RUN SUMMARY                               ║
╠==============================================================================╣
║  TEST                                          RESULT      TIME              ║
║  --------------------------------------------------------------------------  ║
║  ✗ dtr-filterability                             FAIL      0.5s              ║
╠==============================================================================╣
║  RESULT: FAIL  |  0 passed  1 failed  0 skipped  |  Total: 1.2s              ║
╚==============================================================================╝
```

Each footer tallies the rows above it: steps under a test, tests under the run summary, so a test the operator skipped counts as one skipped test there. The boxes are 80 columns wide unless a step's name needs more, in which case every box in the report widens to show it in full.

On a terminal the icons and the RESULT column are coloured — green for a pass, red for a failure, yellow for a skip — and the transcript keeps the words without the colour. Off a terminal the colour is dropped, unless `FORCE_COLOR` is set: a CI log viewer such as GitHub Actions renders the codes, and the e2e workflow sets it. `NO_COLOR` turns colour off anywhere. The tables are the ones the Tractus-X SDK's TCK runners draw, so a report from either tool reads the same.

#### The execution trace

One CloudEvent per line. Each is self-contained: it says which TCK, which test, which phase, and which step it belongs to, so no reader has to track state across lines.

**A step that passed** — its checks are nested in `validations`, not emitted as separate events:

```json
{"specversion":"1.0",
 "id":"industry-core-tck/dtr-filterability/execution/encode_filter/tck.test.step.passed/fb82f7ea7668",
 "source":"util/base64","type":"tck.test.step.passed",
 "time":"2026-08-18T13:38:12.992Z","sequence":4,
 "data":{"attempt":1,"duration_ms":0.085,
  "outputs":{"value":"W3sibmFtZSI6ImRpZ2l0YWxUd2luVHlwZSIsInZhbHVlIjoiUGFydFR5cGUifV0="},
  "validations":[{"source":"validate/assert","field":"value",
   "inputs":{"assertion":"not_null"},
   "outputs":{"actual":"W3sibmFtZSI6…","passed":true}}]}}
```

**A step that failed** — with the request that failed and the answer it got. Credential headers are replaced with `***`; `exchanges[]` appears when the step made more than one call:

```json
{"specversion":"1.0",
 "id":"industry-core-tck/dtr-filterability/execution/pull_dtr/tck.test.step.failed/fa97a93c0fef",
 "source":"connector/consumer/pull_data_filtered","type":"tck.test.step.failed",
 "time":"2026-08-18T13:38:13.536Z","sequence":6,
 "data":{"attempt":1,"duration_ms":538.4,"validations":[],
  "request":{"method":"POST",
   "url":"https://connector.example.com/api/data/v3/catalog/request",
   "headers":{"Content-Type":"application/json","x-api-key":"***"},
   "body":{"@type":"CatalogRequest","counterPartyAddress":"https://sut.example.com/api/v1/dsp/2025-1"}},
  "response":{"status_code":403,
   "headers":{"Server":"awselb/2.0","Content-Type":"text/html"},
   "body":"<html>…403 Forbidden…</html>","duration_ms":43.7},
  "exchanges":[{"request":{"…":"…"},"response":{"status_code":403}},
               {"request":{"…":"…"},"response":{"status_code":403}}],
  "errors":[{"code":"ENGINE_FAULT","origin":"engine","retryable":false,
   "message":"[Connector Service]: catalog request refused, 403"}]}}
```

`errors[].origin` tells you who to go to: `sut` means the system under test answered wrongly, `engine` means TestLab itself broke and the run says nothing about the SUT.

**A step that failed on the policy** — a DSP step turns down every offer whose policy is not one the test named, and says which condition turned them down. `context` carries the same comparison structurally, so a client can render it:

```json
{"specversion":"1.0",
 "id":"industry-core-tck/dtr-filterability/execution/pull_dtr/tck.test.step.failed/84b7ffbb879d",
 "source":"connector/consumer/pull_data_filtered","type":"tck.test.step.failed",
 "time":"2026-08-19T10:14:14.391Z","sequence":8,
 "data":{"attempt":1,"duration_ms":2363.3,"validations":[],
  "errors":[{"code":"POLICY_MISMATCH","origin":"sut","retryable":false,
   "message":"no offer from https://sut.example.com/api/v1/dsp/2025-1 is made under a policy this step accepts…",
   "context":{"offers_compared":2,
    "expected_policies":[["FrameworkAgreement eq DataExchangeGovernance:1.0",
                          "UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1"]],
    "offers":[{"asset_id":"ichub:asset:dtr:9foUM7pmSTrr5LZnx0NqiQ",
               "offer_id":"aWNodWI6Y29udHJhY3Q6T0Js…",
               "offered_not_expected":["Membership eq active"],
               "expected_not_offered":[]}]}}]}}
```

Read it as a set difference. `offered_not_expected` is what the provider requires and your `expected_policies` does not carry — the offer is refused for it just as surely as for something missing, so a deployment that added `Membership` to its policy fails a TCK that never listed it. `expected_not_offered` is the other direction: what the test requires and the provider does not offer.

#### Reading a trace

```bash
# Every step that failed, and why
jq -c 'select(.type == "tck.test.step.failed") | {id, err: .data.errors[0].message}' data/*/*.jsonl

# Which condition refused every offer, for a step that failed on the policy
jq -c '.data.errors[]? | select(.code == "POLICY_MISMATCH") | .context.offers[]
       | {asset_id, offered_not_expected, expected_not_offered}' data/*/*.jsonl

# Every call one step made
jq 'select(.id | contains("/pull_dtr/")) | .data.exchanges[]?' data/*/*.jsonl

# Drop a noisy teardown and look only at execution
jq 'select(.id | contains("/execution/"))' data/*/*.jsonl
```

---

## Step 7 — Programmatic Execution (Python API)

`TestlabPlayer` runs a compiled `.tck` from Python:

```python
import asyncio

from tractusx_testlab.config.loader import ConfigLoader
from tractusx_testlab.player import TestlabPlayer


async def main() -> None:
    # Settings resolve as the CLI's do: defaults, testlab.config.yaml, then
    # TESTLAB_* environment variables, then these overrides.
    config = ConfigLoader.load(cli_overrides={"logs_dir": "./logs", "data_dir": "./data"})
    player = TestlabPlayer(config=config)

    result = await player.run(
        "dist/my-certificate-tck.tck",
        runtime_vars={"callback_timeout_s": "60"},
    )

    print(f"TCK {result.tck_id}: {result.status.value}")
    for test in result.tests:
        print(f"  {test.test_name}: {test.status.value}")
        for step in test.execution:
            print(f"    [{step.status.value}] {step.phase.value}:{step.step_name} ({step.duration_s:.2f}s)")
            if step.error:
                print(f"      {step.error_origin}: {step.error}")


asyncio.run(main())
```

- `player.run(path, runtime_vars=…)` takes packages only; `player.run_tck(tck, runtime_vars=…)` runs a TCK already
  loaded with `tractusx_testlab.player.Loader().load(path)`. An encrypted package cannot be run through `run()`.
- `result` is a `TckResult` (`tck_id`, `status`, `tests`, `started_at`, `finished_at`). Each `TestResult` carries
  `test_id`, `test_name`, `status`, `execution` (every step of every phase, in order), `assertion_summary` and `error`.
- Each `StepResult` carries `step_name`, `step_type`, `phase` (`SETUP`, `EXECUTION`, `TEARDOWN`), `status`
  (`PASSED`, `FAILED`, `SKIPPED`, …), `duration_s`, `inputs`, `output`, `request`, `response`, `exchanges`,
  `assertions`, and on failure `error`, `error_code`, `error_origin` and `error_traceback`.

See also `docs/examples/run_tck_as_backend.py`, which loads a package, lists the variables it requires, and runs it.

---

## Step 8 — Server Mode

`testlab serve` starts the TestLab FastAPI app. It runs TCKs, streams live execution events to its clients over SSE, and serves the mock and
callback endpoints tests register — so a TCK whose tests use `mock/api` expects the SUT to reach this server.

```bash
testlab serve --port 8100
```

The interactive API documentation is served at `/docs`.

### Upload and run a package

```bash
curl -X POST http://localhost:8100/testlab/packages -F "file=@dist/my-certificate-tck-1.0.tck"
```

```json
{
  "package_id": "6a8a4fc04cf9",
  "name": "my-certificate-tck",
  "version": "1.0",
  "format": "ENCRYPTED",
  "size_bytes": 15651,
  "uploaded_at": "2026-09-12T22:01:37.812944Z",
  "checksum": "97e363efb569752a7166d6c52c42a3033970e4bae411e9afabd20cdc89e996c4",
  "file_path": "…/packages/6a8a4fc04cf9/my-certificate-tck-1.0.tck"
}
```

The name and version are read from the file name, split at its last `-` (`<name>-<version>.tck`), so upload a
package under a versioned file name. Upload is limited to `max_upload_bytes` (50 MB by default).

!!! note "Known limitations in 1.0.0a3"
    `format` is reported as `ENCRYPTED` for every package, readable or not, and `GET /testlab/packages` lists each
    package with the whole file stem as its `name` and an empty `version`. Uploaded packages are stored under
    `<storage_dir>/packages/`.

```bash
curl -X POST http://localhost:8100/testlab/run/package \
  -H "Content-Type: application/json" \
  -d '{"package_id": "6a8a4fc04cf9", "runtime_vars": {"callback_timeout_s": "60"}}'
```

```json
{"job_id": "f574e1925147431a95bf52a8dae302a1", "status": "QUEUED"}
```

Instead of `package_id`, `"path"` names a `.tck` on the server's file system. The run happens in the background; follow it with the job endpoints.

An encrypted package runs with the server's own Player identity and trusted Compilers, never with keys sent in the
request — see [Keys on a Server](../specification/security.md#keys-on-a-server).

### Follow a job

```bash
curl http://localhost:8100/testlab/tck-execution/f574e1925147431a95bf52a8dae302a1
```

```json
{
  "job_id": "f574e1925147431a95bf52a8dae302a1",
  "status": "RUNNING",
  "package_name": null,
  "tck_id": "my-certificate-tck",
  "runtime_vars": {"callback_timeout_s": "60"},
  "memory": {"state": {}, "events": []},
  "created_at": "2026-09-12T22:01:37.819734Z",
  "started_at": "2026-09-12T22:01:37.901204Z",
  "finished_at": null,
  "total_duration_s": null,
  "current_test": "request-certificate",
  "current_step": "wait_callback",
  "waiting_for": null,
  "result": null,
  "error": null
}
```

A job's `status` is one of `QUEUED`, `RUNNING`, `WAITING`, `PAUSED`, `COMPLETED`, `FAILED`, `CANCELLED`, `TIMED_OUT`;
`result` holds the `TckResult` once it finishes. `GET /testlab/tck-execution/{job_id}/stream` streams the job's events
as Server-Sent Events (reconnect with `Last-Event-ID` to replay missed ones) — see
[Execution Events](../../developer/execution-events.md).

### Run YAML directly

A client can also post YAML documents rather than packages. `/testlab/compile` validates one document — a manifest or a test —
and always answers `200`:

```bash
curl -X POST http://localhost:8100/testlab/compile \
  -H "Content-Type: application/x-yaml" --data-binary @my-certificate-tck/index.yaml
```

```json
{"status": "ok", "errors": []}
```

```json
{"status": "error", "errors": [{"path": "id", "message": "required key 'id' is missing from a tck"}]}
```

`POST /testlab/tck-execution/run` takes a YAML body the same way and starts a job.

### Server API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/testlab/health` | Health and engine version |
| `POST` | `/testlab/packages` | Upload a `.tck` package (multipart form, field `file`) |
| `GET` | `/testlab/packages` | List uploaded packages |
| `DELETE` | `/testlab/packages/{package_id}` | Delete an uploaded package |
| `POST` | `/testlab/run/package` | Run an uploaded (`package_id`) or on-disk (`path`) package — returns `202` and a job |
| `POST` | `/testlab/compile` | Validate a YAML body; returns `{status, errors[]}` |
| `POST` | `/testlab/tck-execution/run` | Run a TCK posted as YAML (`/run/yaml` is an alias) — returns `202` and a job |
| `GET` | `/testlab/tck-execution` | List jobs (`?status=` filter) |
| `GET` | `/testlab/tck-execution/{job_id}` | Job detail, including the result once finished |
| `GET` | `/testlab/tck-execution/{job_id}/stream` | Live events (SSE) |
| `POST` | `/testlab/tck-execution/{job_id}/pause` | Pause a running job (`409` unless `RUNNING`) |
| `POST` | `/testlab/tck-execution/{job_id}/resume` | Resume a paused job (`409` unless `PAUSED`) |
| `POST` | `/testlab/tck-execution/{job_id}/cancel` | Cancel a job |
| `GET` `POST` `PUT` `DELETE` | `/testlab/callbacks/{path}` | Callback endpoints steps listen on; unregistered paths answer `404` |

---

## Command Reference

| Command | Description |
|---------|-------------|
| `testlab run <index.yaml or .tck>` | Execute a TCK |
| `testlab run <target> --var KEY=VALUE` | Pass a runtime variable (repeatable) |
| `testlab run <target> --config <run.yaml>` | Load runtime variables from the file's `variables:` map |
| `testlab run <target> --logs-dir <dir>` | Where the run transcript is written (default `./logs`) |
| `testlab run <target> --data-dir <dir>` | Where the CloudEvents execution trace is written (default `./data`) |
| `testlab run <pkg.tck> -k <player-dir> --compiler-pub <signing.pub>` | Run an encrypted package |
| `testlab config [--json]` | Show resolved settings and infrastructure bindings |
| `testlab serve [--host <addr>] [--port <port>] [--reload]` | Start the server (default `0.0.0.0:8000`) |

---

## Next Steps

- Return to the [Walkthrough Overview](index.md)
- Look up every step in the [Step Reference](../../api-reference/steps/index.md)
- Read the [TCK Syntax](../../tck-syntax/index.md) reference

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-testlab](https://github.com/eclipse-tractusx/tractusx-testlab)