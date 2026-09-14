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
<!-- This documentation was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and tested by a human committer. -->

# Certificate Management — Developer Guide

This guide covers running the Certificate Management TCK against a provider: configuring the run, reading the results, and fixing what fails. For how the suite is built, see the [Architecture Guide](ccm-architecture-guide.md). For what each check asserts, see [CCM Conformity Testing](ccm-conformity-testing.md).

## Prerequisites

- **Python 3.12+** and the CLI: `pip install --pre tractusx-testlab`. In a checkout of this repository, run `poetry install` and put `poetry run` in front of every `testlab` command below.
- **An engine-side connector** that TestLab drives through its management API. TestLab uses it to negotiate with the provider.
- **The provider under test**: its connector's DSP endpoint and participant id, a CCMAPI offer under the CX-0135 usage policy, and the CCMAPI behind it. The [Business Guide](ccm-business-guide.md#what-the-provider-must-have-in-place) has the full list.
- **Inbound reach.** During a run, TestLab serves mock endpoints on port `8100` (the engine setting `server_port`). *Send Feedback Notification* waits for the provider to call one of them, so the provider must be able to reach this host on that port.

## 1. Check the suite

```bash
testlab validate docs/examples/certificate-management-v2/raw/index.yaml
```

`validate` takes the manifest (`index.yaml`), never a single test file. It checks the manifest and all four tests against the `v1-alpha` syntax and the registered steps.

To see what a run will ask for, compile the suite and inspect the package:

```bash
testlab compile docs/examples/certificate-management-v2/raw/index.yaml --output ccm.tck
testlab inspect ccm.tck --variables --infrastructure
```

```text
  VARIABLES
  ID                             Source       Scope      Type
  sut_counter_party_id           input        sut        string
  sut_counter_party_address      input        sut        string
  ccm_usage_policy               value        —          object

  INFRASTRUCTURE
  Capability                Required   Standard
  engine.connector          True       CX-0018
  sut.connector             True       CX-0018
```

Add `--manifest` for the package identity and checksum, or `--json` for machine-readable output.

## 2. Supply what the run needs

A run needs three groups of values. You can put all of them in one run config:

| Group | Keys | Where the need comes from |
| --- | --- | --- |
| Infrastructure bindings | `infrastructure.engine.connector.management_url`, `infrastructure.engine.connector.participant_id` (plus `api_key` if the management API needs one), `infrastructure.sut.connector.dsp_url`, `infrastructure.sut.connector.participant_id` | `infrastructure:` in the manifest: both connectors are required |
| Declared inputs | `sut_counter_party_id`, `sut_counter_party_address` | `env.variables` with `source: input` |
| Test data values | `consumer_bpn`, `provider_bpn`, `certificate_type`, `location_bpns`, `testlab_dsp_url`, `request_id`, `document_id` | `${{ env.… }}` references inside the three JSON files in `raw/testdata/` |

```yaml
# run-config.yaml
variables:
  # Engine side: the connector TestLab operates (management_url includes the management path)
  infrastructure.engine.connector.management_url: https://testlab-edc.example.com/management
  infrastructure.engine.connector.api_key: <engine-api-key>
  infrastructure.engine.connector.participant_id: BPNL000000000TLB

  # SUT side: the provider's connector
  infrastructure.sut.connector.dsp_url: https://provider-edc.example.com/api/v1/dsp
  infrastructure.sut.connector.participant_id: BPNL000000000001

  # Declared inputs: give the same connector as the SUT binding
  sut_counter_party_id: BPNL000000000001
  sut_counter_party_address: https://provider-edc.example.com/api/v1/dsp

  # Values the request and notification bodies read
  consumer_bpn: BPNL000000000TLB
  provider_bpn: BPNL000000000001
  certificate_type: iso9001
  location_bpns: BPNS000000000001
  testlab_dsp_url: https://testlab-edc.example.com/api/v1/dsp
  request_id: 0b133a08-b03a-4f4f-b0f4-55bbbcf088f9
  document_id: <documentId of an existing certificate at the provider>
```

The bindings do not have to live in the run config. `testlab.config.yaml` and `TESTLAB_*` environment variables (for example `TESTLAB_SUT_CONNECTOR_DSP_URL`) are also read; see [Infrastructure Bindings](../developer/infrastructure-bindings.md). A `--var KEY=VALUE` flag overrides the file for one value.

!!! note "Two things the run does not check up front"
    - `sut_counter_party_*` repeats the SUT binding. The connector steps would fall back to `infrastructure.sut.connector.*` without it, but the suite passes it explicitly. Keep the two in agreement.
    - The test data keys are not declared in the manifest. The run does not ask for them before it starts. If one is missing, the step that reads the body fails with `'env.<key>' resolves to nothing`.

## 3. Run it

```bash
testlab run docs/examples/certificate-management-v2/raw/index.yaml --config run-config.yaml
```

`run` compiles the manifest into a temporary package and validates it. Before the first step, it refuses to start if any declared input or required binding is missing, and it lists everything that is missing at once. It then starts the mock server and runs the four tests in manifest order. No test is `skippable`, so every test runs.

## 4. Read the results

| Output | Where | What it holds |
| --- | --- | --- |
| Console | stdout | One box per test with each step's `PASS`/`FAIL` and duration, failed checks with expected against actual, then a TCK run summary |
| Exit code | shell | `0` when every test passed, `1` otherwise, including a run refused before it started |
| Transcript | `./logs/<date>/<time>_<run-id>.log` (`--logs-dir`) | The console output of the run, kept verbatim |
| Execution trace | `./data/<date>/<time>_<run-id>.jsonl` (`--data-dir`) | CloudEvents, one per line: every step's outputs, checks, and the HTTP requests and responses the run made. See [Execution Logs](../tck-syntax/execution-logs.md) |

Failing lines name the test id, the phase and step id, and the step: `send-feedback-notification[setup:mock_receive_ack]:mock/api`. A test whose checks never ran is reported as `WARNING: N declared assertion(s) were never evaluated`. It is not a pass.

## 5. Fix what fails

| Message | Cause | Fix |
| --- | --- | --- |
| `This TCK needs 2 input variable(s) that were not supplied` | `sut_counter_party_id` / `sut_counter_party_address` missing | Add them under `variables:` or pass `--var` |
| `This TCK requires infrastructure that is not fully bound: engine.connector, sut.connector` | A binding key is missing; the message lists each key and its `TESTLAB_*` name | Set the listed keys |
| `'env.consumer_bpn' resolves to nothing` | A test data value is missing | Add every key from the test data row in step 2 |
| `It was not possible to get the catalog from the EDC provider! Response code: [404]` | The engine connector's `management_url` is wrong. It must include the management path. | Correct `infrastructure.engine.connector.management_url` |
| `no offer from <dsp_url> is made under a policy this step accepts` | The provider has no CCMAPI offer matching the filters, or the offer's policy is not exactly the CX-0135 usage policy. The message lists the constraints that differ. | Fix the provider's asset or policy. A subset or superset of the policy does not match. |
| `Expected 200, got …` on `request_certificate`, `send_status_notification` or `send_unknown_cert_type` | The data-plane call reached the provider's CCMAPI and was refused | Check the provider logs. The request body is in the execution trace. |
| `Expected 'REJECTED', got …` on `send_unknown_cert_type` | The provider accepted an unknown certificate type | Validate `certificateType` and answer with `requestStatus: REJECTED` |
| `Timed out after 60.0s waiting for POST /companycertificate/notification/receive` | The provider never sent the acknowledgement, or cannot reach this host on port 8100 | Check the provider's outbound call and the network path to the engine |

Check wording comes from the [validation operators](../api-reference/steps/validations.md). For problems that are not specific to this suite (unknown step ids, empty `returns:`, mocks never hit), see [Debugging](debugging.md).

## The local SUT stub

`stubs/ccm-sut/` holds a FastAPI stub that imitates a connector and a CCMAPI service. **It does not satisfy the current suite.** Its catalog answers when `infrastructure.engine.connector.management_url` is `http://localhost:8090/api/v1/dsp/management`. However, it offers no CCMAPI asset under the CX-0135 usage policy, so all four tests stop at their first step. Its own `run-config.yaml` also uses variable names that the suite no longer declares. Use the stub to check your wiring, not as a conformant provider.
