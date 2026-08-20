<!--

Eclipse Tractus-X - Software Development KIT

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

This section shows how to run compiled `.tck` packages (or raw TCKs) against live dataspace connectors and interpret results.

## Prerequisites

You've completed [Compiling Packages](compiling-packages.md) and have:

- A compiled package: `connector_e2e-1.0.tck`
- Running connector instances (provider + consumer) with known URLs
- Valid OAuth2 client credentials for each connector

---

## Step 1 — Run a Compiled Package

### Basic Execution

Pass runtime variables with `--var`:

```bash
testlab run connector_e2e-1.0.tck \
  --var provider_url=https://provider.example.com \
  --var consumer_url=https://consumer.example.com \
  --var token_url=https://auth.example.com/token \
  --var provider_client_id=prov-client \
  --var provider_client_secret=prov-secret \
  --var consumer_client_id=cons-client \
  --var consumer_client_secret=cons-secret \
  --var provider_bpn=BPNL000000000001
```

**Expected output:**

```
Loading connector_e2e-1.0.tck
   Test case: connector_e2e v1.0
   SDK: 0.5.0 (compiled 2026-03-30T14:22:00Z)
   Checksum: valid

Job created: a1b2c3d4-e5f6-7890-abcd-1234567890ab
Running TCK "connector_e2e" (2 tests, 9 steps)

── provision_and_consume ────────────────────────────────────────

  [1/6] create_asset
        POST https://provider.example.com/management/v3/assets
        PASS  status=200 (320ms)

  [2/6] create_policy
        POST https://provider.example.com/management/v3/policydefinitions
        PASS  status=200 (180ms)

  [3/6] create_contract_definition
        POST https://provider.example.com/management/v3/contractdefinitions
        PASS  status=200 (150ms)

  [4/6] query_catalog
        POST https://consumer.example.com/management/v3/catalog/request
        PASS  status=200, offers ≥ 1 (420ms)

  [5/6] negotiate_contract
        POST https://consumer.example.com/management/v3/contractnegotiations
        PASS  status=200, state="FINALIZED" (8.2s, polled 4×)

  [6/6] transfer_data
        POST https://consumer.example.com/management/v3/transferprocesses
        PASS  status=200, state="COMPLETED" (12.4s, polled 6×)

  [cleanup] delete_asset
        DELETE https://provider.example.com/management/v3/assets/...
        DONE  status=204 (110ms)

── submodel_validation ──────────────────────────────────────────

  [1/3] fetch_submodel_data
        GET https://consumer.example.com/management/v3/submodel/...
        PASS  status=200 (250ms)

  [2/3] validate_schema
        Validating response against schemas/serial-part-3.0.json
        PASS  schema valid (12ms)

  [3/3] check_fields
        Assert catenaXId matches ^urn:uuid:[0-9a-f-]{36}$
        Assert manufacturerPartId is not empty
        PASS  2/2 assertions (5ms)

─────────────────────────────────────────────────────────────────

Test case PASSED — 9/9 steps passed (22.1s total)
```

### Using a Variables File

For repeatable runs, define variables in a YAML file:

```yaml
# vars.yaml
provider_url: "https://provider.example.com"
consumer_url: "https://consumer.example.com"
token_url: "https://auth.example.com/token"
provider_client_id: "prov-client"
provider_client_secret: "prov-secret"
consumer_client_id: "cons-client"
consumer_client_secret: "cons-secret"
provider_bpn: "BPNL000000000001"
```

```bash
testlab run connector_e2e-1.0.tck --vars-file vars.yaml
```

Variables from `--var` flags override `--vars-file` values:

```bash
# Override provider_url while using vars.yaml for everything else
testlab run connector_e2e-1.0.tck \
  --vars-file vars.yaml \
  --var provider_url=https://staging-provider.example.com
```

---

## Step 2 — Run from Raw YAML (Without Compiling)

During development, you can run a TCK directly without compiling:

```bash
testlab run tck.yaml \
  --var provider_url=https://provider.example.com \
  --var consumer_url=https://consumer.example.com \
  --var token_url=https://auth.example.com/token \
  --var provider_client_id=prov-client \
  --var provider_client_secret=prov-secret \
  --var consumer_client_id=cons-client \
  --var consumer_client_secret=cons-secret \
  --var provider_bpn=BPNL000000000001
```

This performs validate → compile-in-memory → execute in one step. Useful for local development; for CI/CD or distribution, always use compiled `.tck` packages.

---

## Step 3 — Skip Optional Tests

Some tests in a TCK are marked `skippable: true` by the author, indicating they cover
optional capabilities that the SUT may not yet support. You can bypass them at runtime
using the `skip_tests` variable — without modifying the package itself.

### Discover which tests are skippable

```bash
testlab inspect connector_e2e-1.0.tck
```

Each test in the output shows its **ID** and whether it is skippable:

```
  Script: Validate catalog policy  |  ID: catalog_policy_validation.yaml  |  Skippable: Yes
  Script: Request certificate       |  ID: request_certificate.yaml        |  Skippable: No
```

The **ID** (e.g. `catalog_policy_validation.yaml`) is what you pass to `skip_tests`.
The display name is for humans only — it cannot be used to identify a test for skipping.

### Skip a single test

```bash
testlab run connector_e2e-1.0.tck \
  --var skip_tests=catalog_policy_validation.yaml \
  --var provider_url=https://provider.example.com \
  --var ...
```

### Skip multiple tests

Repeating `--var skip_tests=...` overwrites the previous value. Use a config YAML
to skip more than one test:

```yaml
# skip.yaml
skip_tests:
  - catalog_policy_validation.yaml
  - error_handling.yaml
```

```bash
testlab run connector_e2e-1.0.tck \
  --config skip.yaml \
  --var provider_url=https://provider.example.com \
  --var ...
```

### Result

Skipped tests appear in the output with status `SKIPPED`:

```
── catalog_policy_validation ────────────────────────────────────
  [SKIPPED] Test intentionally skipped by operator request.
─────────────────────────────────────────────────────────────────

Test case COMPLETED — 5/5 executed, 1 skipped
```

The overall TCK result is `COMPLETED` when all executed tests pass and any number
of `SKIPPED` tests are present. A single `FAILED` test makes the TCK `FAILED`.

### Error: invalid skip request

Validation runs **before any test executes**. If you request skipping a test that does
not exist or is not marked skippable, the run aborts immediately:

```
Error: Cannot skip test(s) 'request_certificate.yaml': not marked skippable.
Set skippable: true on the test entry in the TCK manifest to allow skipping.
```

!!! note
    Only the TCK author can allow skipping. Tests without `skippable: true` are
    mandatory conformance checks that cannot be bypassed by the operator.

---

## Step 5 — Run Encrypted Packages (Default)

Packages are encrypted by default. To run them, the Player must have:

1. Its private key at `~/.testlab/keys/player.pem`
2. The Compiler's verification key in `~/.testlab/trusted_compilers/`

See [Compiling Packages - Step 2](compiling-packages.md#step-2-generate-keys-one-time-setup) for key setup.

```bash
testlab run connector_e2e-1.0.tck \
  --vars-file vars.yaml
```

The Player automatically:

1. Verifies the `signature.sig` using the trusted Compiler key
2. Finds its own entry in `authorized_players` by fingerprint
3. Unwraps the AES key using its RSA private key
4. Decrypts `payload.enc` to recover scripts and assets
5. Executes in-memory (decrypted content is never written to disk)

**Expected output:**

```
Loading connector_e2e-1.0.tck
   Test case: connector_e2e v1.0
   Encrypted package detected
   Signature verified (compiler:sha256:a1b2c3d4...)
   Player authorized (player:sha256:d4e5f6a1...)
   Payload decrypted (AES-256-GCM)
```

Plain packages (compiled with `--plain`) skip the decryption steps and load directly.

**Error: unauthorized Player:**

```
Loading connector_e2e-1.0.tck
   Encrypted package detected
   Player fingerprint player:sha256:99aabb... not found in authorized_players
   Error: This Player is not authorized to execute this package.
```

**Error: untrusted Compiler:**

```
Loading connector_e2e-1.0.tck
   Encrypted package detected
   Compiler compiler:sha256:a1b2c3d4... not in trust store
   Error: Package was signed by an untrusted Compiler.
         Add the compiler's public key to ~/.testlab/trusted_compilers/
```

---

## Step 6 — Result Logs and Reports

### The Two Records a Run Leaves

Every run writes two files, and they are not two formats of the same thing.

| | Transcript | Execution trace |
|---|---|---|
| **Where** | `./logs/<date>/<time>_<job_id>.log` | `./data/<date>/<time>_<job_id>.jsonl` |
| **Override** | `--logs-dir` (or `TESTLAB_LOGS_DIR`) | `--data-dir` (or `TESTLAB_DATA_DIR`) |
| **Format** | Plain text, identical to what scrolled past on the console | CloudEvents v1.0 JSON-lines ([ADR-0016](../../developer/decision-records/backend/ADR-0016-execution-trace-format.md)) |
| **Read it when** | You want to see what happened | You want to know exactly what went over the wire, or you are feeding a tool |

```bash
testlab run connector_e2e-1.0.tck \
  --vars-file vars.yaml \
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
  RESULT: FAIL  |  1 passed  1 failed  |  Duration: 1205ms
```

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

**A step that failed on the policy** — a DSP step turns down every offer whose policy is not one the script named, and says which condition turned them down. `context` carries the same comparison structurally, so the IDE renders it:

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

Read it as a set difference. `offered_not_expected` is what the provider requires and your `expected_policies` does not carry — the offer is refused for it just as surely as for something missing, so a deployment that added `Membership` to its policy fails a TCK that never listed it. `expected_not_offered` is the other direction: what the script requires and the provider does not offer.

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


### JUnit XML Report

For CI/CD integration, generate a JUnit XML report:

```bash
testlab run connector_e2e-1.0.tck \
  --vars-file vars.yaml \
  --junit results.xml
```

### Summary Report

Use `--report` to generate a Markdown summary:

```bash
testlab run connector_e2e-1.0.tck \
  --vars-file vars.yaml \
  --report report.md
```

**Example summary (all passed):**

```markdown
# Test Report — connector_e2e v1.0

| Metric | Value |
|--------|-------|
| Started | 2026-03-30T14:30:00Z |
| Duration | 22.1s |
| Scripts | 2 |
| Steps | 9 passed, 0 failed, 0 skipped |
| Assertions | 9 passed, 0 failed |
| Result | PASSED |

## provision_and_consume

| # | Step | Status | Duration |
|---|------|--------|----------|
| 1 | create_asset | PASS | 320ms |
| 2 | create_policy | PASS | 180ms |
| 3 | create_contract_definition | PASS | 150ms |
| 4 | query_catalog | PASS | 420ms |
| 5 | negotiate_contract | PASS | 8.2s |
| 6 | transfer_data | PASS | 12.4s |

## submodel_validation

| # | Step | Status | Duration |
|---|------|--------|----------|
| 1 | fetch_submodel_data | PASS | 250ms |
| 2 | validate_schema | PASS | 12ms |
| 3 | check_fields | PASS | 5ms |
```

**Example summary (with failures):**

```markdown
# Test Report — connector_e2e v1.0

| Metric | Value |
|--------|-------|
| Started | 2026-03-30T14:30:00Z |
| Duration | 38.5s |
| Scripts | 2 |
| Steps | 4 passed, 1 failed, 1 stopped |
| Assertions | 5 passed, 1 failed |
| Result | FAILED |

## provision_and_consume

| # | Step | Status | HTTP | Duration | Error |
|---|------|--------|------|----------|-------|
| 1 | create_asset | PASS | 200 | 320ms | — |
| 2 | create_policy | PASS | 200 | 180ms | — |
| 3 | create_contract_definition | PASS | 200 | 150ms | — |
| 4 | query_catalog | PASS | 200 | 420ms | — |
| 5 | negotiate_contract | FAIL | 502 | 30.2s | Expected status_code=200, got 502 |
| 6 | transfer_data | STOP | — | 60.0s | Timed out after 60s |
```

---

## Step 7 — Programmatic Execution (Python API)

You can run packages from Python code:

```python
from tractusx_sdk.extensions.testlab import Player

async def run_tests():
    player = Player()

    result = await player.run(
        "connector_e2e-1.0.tck",
        runtime_vars={
            "provider_url": "https://provider.example.com",
            "consumer_url": "https://consumer.example.com",
            "token_url": "https://auth.example.com/token",
            "provider_client_id": "prov-client",
            "provider_client_secret": "prov-secret",
            "consumer_client_id": "cons-client",
            "consumer_client_secret": "cons-secret",
            "provider_bpn": "BPNL000000000001",
        },
    )

    # Every run creates a Job with a unique ID
    print(f"Job ID: {result.job_id}")
    print(f"Test case: {result.tck_name}")
    print(f"Status: {result.status}")           # COMPLETED | FAILED | WAITING
    print(f"Duration: {result.duration_ms}ms")
    print(f"Steps: {result.passed}/{result.total}")

    for script_result in result.scripts:
        for step in script_result.steps:
            print(f"  [{step.status}] {step.name} ({step.duration_ms}ms)")

            # Access the full HTTP request/response
            if step.request:
                print(f"    -> {step.request.method} {step.request.url}")
                print(f"    -> Headers: {step.request.headers}")
                print(f"    -> Body: {step.request.body}")

            if step.response:
                print(f"    <- HTTP {step.response.status_code}")
                print(f"    <- Headers: {step.response.headers}")
                print(f"    <- Body: {step.response.body}")
                print(f"    <- Duration: {step.response.duration_ms}ms")

            # Access error details for failed/stopped steps
            if step.error:
                print(f"    !! Error: {step.error}")
            if step.error_traceback:
                print(f"    !! Traceback: {step.error_traceback}")

    # Access job memory (persisted across all steps and wait/resume cycles)
    print(f"Job memory: {result.job.memory}")

    # Access job events (lifecycle audit trail)
    for event in result.job.events:
        print(f"  [{event.timestamp}] {event.event_type}: {event.description}")
```

For tests that enter `WAITING` state (e.g., awaiting an external callback), you can poll or subscribe to the job:

```python
    # If the job is waiting for an external response, poll until done
    if result.status == "WAITING":
        print(f"Job waiting for: {result.job.waiting_for}")
        final = await player.wait_for_job(result.job_id, timeout=300)
        print(f"Final status: {final.status}")
```

### Server Mode

Run the Player as an HTTP server for remote triggering:

```bash
testlab serve --port 8100
```

#### Upload a Package

Upload a `.tck` file to the server so it can be executed later by name. Both encrypted and plain packages are accepted:

```bash
# Upload an encrypted package
curl -X POST http://localhost:8100/api/v1/packages \
  -F "file=@connector_e2e-1.0.tck"
```

**Response:**

```json
{
  "package_id": "connector_e2e-1.0",
  "name": "connector_e2e",
  "version": "1.0",
  "format": "ENCRYPTED",
  "size_bytes": 14100,
  "uploaded_at": "2026-03-30T14:28:00Z",
  "checksum": "sha256:e3b0c44298fc1c149afbf4c8996fb924..."
}
```

Upload a plain package:

```bash
# Upload a plain (development) package
curl -X POST http://localhost:8100/api/v1/packages \
  -F "file=@connector_e2e-1.0.tck"
```

```json
{
  "package_id": "connector_e2e-1.0",
  "name": "connector_e2e",
  "version": "1.0",
  "format": "PLAIN",
  "size_bytes": 5423,
  "uploaded_at": "2026-03-30T14:28:00Z",
  "checksum": "sha256:a1b2c3d4e5f6..."
}
```

List uploaded packages:

```bash
curl http://localhost:8100/api/v1/packages
```

```json
{
  "packages": [
    {
      "package_id": "connector_e2e-1.0",
      "name": "connector_e2e",
      "version": "1.0",
      "format": "ENCRYPTED",
      "uploaded_at": "2026-03-30T14:28:00Z"
    }
  ]
}
```

Delete an uploaded package:

```bash
curl -X DELETE http://localhost:8100/api/v1/packages/connector_e2e-1.0
```

#### Run a Test

Trigger a test run via HTTP. Every run creates a **Job** — a stateful entity that tracks the full execution lifecycle. You can reference an uploaded package by `package_id` or provide a filesystem path:

```bash
curl -X POST http://localhost:8100/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "package": "connector_e2e-1.0",
    "runtime_vars": {
      "provider_url": "https://provider.example.com",
      "consumer_url": "https://consumer.example.com",
      "token_url": "https://auth.example.com/token",
      "provider_client_id": "prov-client",
      "provider_client_secret": "prov-secret",
      "consumer_client_id": "cons-client",
      "consumer_client_secret": "cons-secret",
      "provider_bpn": "BPNL000000000001"
    }
  }'
```

**Response (completed job):**

```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
  "status": "COMPLETED",
  "tck": "connector_e2e",
  "created_at": "2026-03-30T14:30:00Z",
  "started_at": "2026-03-30T14:30:00Z",
  "finished_at": "2026-03-30T14:30:22Z",
  "duration_ms": 22100,
  "current_step": null,
  "waiting_for": null,
  "scripts": [
    {
      "name": "provision_and_consume",
      "status": "PASSED",
      "steps": [
        {
          "step": "create_asset",
          "status": "PASS",
          "duration_ms": 320,
          "request": {
            "method": "POST",
            "url": "https://provider.example.com/management/v3/assets",
            "headers": {"Content-Type": "application/json", "Authorization": "Bearer ***"},
            "body": {"@context": {}, "asset": {"@id": "asset-001"}}
          },
          "response": {
            "status_code": 200,
            "headers": {"Content-Type": "application/json"},
            "body": {"@id": "asset-001", "createdAt": "2026-03-30T14:30:01Z"},
            "duration_ms": 315
          },
          "error": null
        },
        {
          "step": "create_policy",
          "status": "PASS",
          "duration_ms": 180,
          "request": {
            "method": "POST",
            "url": "https://provider.example.com/management/v3/policydefinitions"
          },
          "response": {"status_code": 200, "duration_ms": 175},
          "error": null
        },
        {
          "step": "create_contract_definition",
          "status": "PASS",
          "duration_ms": 150,
          "request": {
            "method": "POST",
            "url": "https://provider.example.com/management/v3/contractdefinitions"
          },
          "response": {"status_code": 200, "duration_ms": 145},
          "error": null
        },
        {
          "step": "query_catalog",
          "status": "PASS",
          "duration_ms": 420,
          "request": {
            "method": "POST",
            "url": "https://consumer.example.com/management/v3/catalog/request"
          },
          "response": {"status_code": 200, "duration_ms": 415},
          "error": null
        },
        {
          "step": "negotiate_contract",
          "status": "PASS",
          "duration_ms": 8200,
          "request": {
            "method": "POST",
            "url": "https://consumer.example.com/management/v3/contractnegotiations"
          },
          "response": {"status_code": 200, "duration_ms": 8150},
          "error": null
        },
        {
          "step": "transfer_data",
          "status": "PASS",
          "duration_ms": 12400,
          "request": {
            "method": "POST",
            "url": "https://consumer.example.com/management/v3/transferprocesses"
          },
          "response": {"status_code": 200, "duration_ms": 12350},
          "error": null
        }
      ]
    },
    {
      "name": "submodel_validation",
      "status": "PASSED",
      "steps": [
        {
          "step": "fetch_submodel_data",
          "status": "PASS",
          "duration_ms": 250,
          "request": {
            "method": "GET",
            "url": "https://consumer.example.com/management/v3/submodel/..."
          },
          "response": {"status_code": 200, "duration_ms": 245},
          "error": null
        },
        {
          "step": "validate_schema",
          "status": "PASS",
          "duration_ms": 12,
          "request": null,
          "response": null,
          "error": null
        },
        {
          "step": "check_fields",
          "status": "PASS",
          "duration_ms": 5,
          "request": null,
          "response": null,
          "error": null
        }
      ]
    }
  ]
}
```

The response includes every step with its full request/response detail and error state. Non-HTTP steps (like `validate_schema` and `check_fields`) have `null` request/response fields. Sensitive headers are redacted automatically.

#### Job in WAITING State

When a test includes an `await_callback` step, the `/run` endpoint returns immediately with the job in `WAITING` state. The job resumes automatically when the callback arrives:

```bash
# Start a test that waits for a notification acknowledgment
curl -X POST http://localhost:8100/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{
    "package": "notification_e2e-1.0",
    "runtime_vars": { "..." }
  }'
```

**Response (job waiting):**

```json
{
  "job_id": "f9e8d7c6-b5a4-3210-fedc-ba9876543210",
  "status": "WAITING",
  "tck": "notification_e2e",
  "created_at": "2026-03-30T15:00:00Z",
  "started_at": "2026-03-30T15:00:00Z",
  "finished_at": null,
  "duration_ms": null,
  "current_script": "send_and_acknowledge",
  "current_step": "wait_for_ack",
  "waiting_for": "callback: /callbacks/notif-ack-xyz",
  "memory": {
    "notification_id": "notif-abc-123",
    "sent_at": "2026-03-30T15:00:02Z"
  }
}
```

Query the job later to check if it has completed:

```bash
curl http://localhost:8100/api/v1/jobs/f9e8d7c6-b5a4-3210-fedc-ba9876543210
```

Once the external system calls `POST /callbacks/notif-ack-xyz`, the job resumes and eventually returns `COMPLETED` or `FAILED`.

#### Query Jobs

List all jobs:

```bash
curl http://localhost:8100/api/v1/jobs
```

```json
{
  "jobs": [
    {
      "job_id": "a1b2c3d4-e5f6-7890-abcd-1234567890ab",
      "status": "COMPLETED",
      "tck": "connector_e2e",
      "created_at": "2026-03-30T14:30:00Z",
      "duration_ms": 22100
    },
    {
      "job_id": "f9e8d7c6-b5a4-3210-fedc-ba9876543210",
      "status": "WAITING",
      "tck": "notification_e2e",
      "created_at": "2026-03-30T15:00:00Z",
      "waiting_for": "callback: /callbacks/notif-ack-xyz"
    }
  ]
}
```

Filter by status:

```bash
curl http://localhost:8100/api/v1/jobs?status=WAITING
```

Get job memory:

```bash
curl http://localhost:8100/api/v1/jobs/f9e8d7c6-b5a4-3210-fedc-ba9876543210/memory
```

```json
{
  "notification_id": "notif-abc-123",
  "sent_at": "2026-03-30T15:00:02Z"
}
```

Get job event log:

```bash
curl http://localhost:8100/api/v1/jobs/f9e8d7c6-b5a4-3210-fedc-ba9876543210/events
```

```json
{
  "events": [
    {"timestamp": "2026-03-30T15:00:00Z", "event_type": "job_created", "description": "Job created for notification_e2e-1.0"},
    {"timestamp": "2026-03-30T15:00:00Z", "event_type": "job_started", "description": "Execution started"},
    {"timestamp": "2026-03-30T15:00:01Z", "event_type": "step_completed", "description": "send_notification: PASS (1.2s)"},
    {"timestamp": "2026-03-30T15:00:01Z", "event_type": "job_waiting", "description": "Waiting for callback: /callbacks/notif-ack-xyz"}
  ]
}
```

Cancel a job:

```bash
curl -X POST http://localhost:8100/api/v1/jobs/f9e8d7c6-b5a4-3210-fedc-ba9876543210/cancel
```

---

## Command Reference

| Command | Description |
|---------|-------------|
| `testlab run <file>` | Execute a `.tck` or raw `tck.yaml` |
| `testlab run <file> --var KEY=VALUE` | Pass a runtime variable |
| `testlab run <file> --vars-file <vars.yaml>` | Load variables from a file |
| `testlab run <file> --logs-dir <dir>` | Where the run transcript is written (default `./logs`) |
| `testlab run <file> --data-dir <dir>` | Where the CloudEvents execution trace is written (default `./data`) |
| `testlab run <file> --junit <file.xml>` | Write JUnit XML report |
| `testlab run <file> --report <file.md>` | Write Markdown summary report |
| `testlab run <file> --timeout 300` | Set global timeout in seconds (default: 600) |
| `testlab jobs` | List all jobs (with optional `--status` filter) |
| `testlab job <job_id>` | Show job detail (status, memory, events) |
| `testlab cancel <job_id>` | Cancel a running or waiting job |
| `testlab serve --port <port>` | Start Player in HTTP server mode |

### Server API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/packages` | Upload a `.tck` package (multipart form, field `file`) |
| `GET` | `/api/v1/packages` | List uploaded packages |
| `GET` | `/api/v1/packages/{package_id}` | Get package metadata |
| `DELETE` | `/api/v1/packages/{package_id}` | Delete an uploaded package |
| `POST` | `/api/v1/run` | Execute a package (creates a Job) |
| `GET` | `/api/v1/jobs` | List all jobs (supports `?status=` filter) |
| `GET` | `/api/v1/jobs/{job_id}` | Get job detail (status, memory, scripts, events) |
| `POST` | `/api/v1/jobs/{job_id}/cancel` | Cancel a running or waiting job |
| `GET` | `/api/v1/jobs/{job_id}/memory` | Get job memory key-value store |
| `GET` | `/api/v1/jobs/{job_id}/events` | Get job lifecycle event log |

---

## Next Steps

- Return to the [Walkthrough Overview](index.md) for a summary
- Review the [YAML Script Format](../reference/yaml-format.md) reference for all step types
- See the [Package Format](../reference/package-format.md) specification for archive internals
- Consult [Functional Requirements](../specification/functional-requirements.md) for full requirement traceability

---

## NOTICE

This work is licensed under the [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/legalcode).

- SPDX-License-Identifier: CC-BY-4.0
- SPDX-FileCopyrightText: 2025, 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2025, 2026 Catena-X Automotive Network e.V.
- Source URL: [https://github.com/eclipse-tractusx/tractusx-sdk](https://github.com/eclipse-tractusx/tractusx-sdk)