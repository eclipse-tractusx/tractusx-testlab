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

# Debugging

Problems show up at three moments. **Validation** means the TCK itself is wrong. **Run start** means something the TCK needs wasn't supplied. **During the run** means a step or a check failed. Each section below starts from the message you actually see.

## Validation: `testlab validate` reports errors

`testlab validate <index.yaml>` checks the whole TCK and lists every finding at once. `testlab compile` and `testlab run` run the same checks first.

| Message (abridged) | Cause and fix |
|---|---|
| `Unknown step type 'digital-twin/provider/create_shell_descriptor'` | The id doesn't exist. Ids are renamed without aliases, so an older TCK may name one that has moved (here, to `digital-twin-registry/provider/create_shell_descriptor`). Look it up in the [step reference](../api-reference/steps/index.md) or with `testlab docs --step <id> --json`. |
| `'${{ steps.fetch.status_code }}' in param 'url' names nothing this TCK supplies. Available: …` | The reference's root is unknown. Step outputs are addressed by phase, `${{ execution.<step-id>.<output> }}` or `${{ setup.<step-id>.<output> }}`, never `steps.`. Variables are `${{ env.<id> }}` and must be declared under `env.variables`. Bindings are `${{ infrastructure.<side>.<capability>.<field> }}`. The message lists what is available. |
| `'returns' name 'x' is not produced by step '…'. It publishes: …` | `returns:` may only name the step's declared outputs or the universal fields (`status_code`, `headers`, `body`, `response_body`, `response_headers`, `duration_ms`, `value`, `request`, `response`). Fix the name; the message lists the valid ones. |
| `Operator 'not_null' does not read 'value'` | The operand doesn't belong to that operator. Unary operators take none; `between` takes `min` and `max`. See [Validations](../api-reference/steps/validations.md). |
| `'validate/assert' cannot be used as a standalone step` | Assertions go in the `validate:` block of the step whose output they check. |
| `Variable 'x' has source: input but no scope declared` | Say who supplies the input: `scope: engine` (whoever runs TestLab) or `scope: sut` (the party under test). |
| `Variable 'x' is scoped to 'sut', but the infrastructure block requires no sut capability` | Declare what the run needs, for example `infrastructure.sut.connector.required: true`, or drop the variable. |
| `namespace '…' must match the TCK id '…'` | Every test's `namespace:` is the manifest's `id:`. |

For version-specific steps, pass the dataspace generation: `testlab validate index.yaml --version saturn`.

## Run start: `Cannot run index.yaml`

The run refuses to start when something the TCK declares as required wasn't supplied. The message names every missing item and where to set it:

```text
Cannot run index.yaml:
  This TCK requires infrastructure that is not fully bound: sut.connector
  sut.connector — set:
      infrastructure.sut.connector.participant_id   (or TESTLAB_SUT_CONNECTOR_PARTICIPANT_ID)
      infrastructure.sut.connector.dsp_url   (or TESTLAB_SUT_CONNECTOR_DSP_URL)
```

```text
Cannot run index.yaml:
  This TCK needs 4 input variable(s) that were not supplied:
      token_url
      ...
  Set them under 'variables:' in the run config, or pass --var name=value.
```

Bindings go in `testlab.config.yaml`, in `TESTLAB_*` environment variables, or in `--var` for one run ([Infrastructure Bindings](../developer/infrastructure-bindings.md)). To see what the engine actually resolved, and from which source, run `testlab config`. To see what a compiled package requires, run `testlab inspect <package.tck> --variables --infrastructure`.

## During the run: a step or a check failed

### Read the two records

Every `testlab run` leaves two files:

- **The transcript**, `./logs/<date>/<time>_<job>.log` (`--logs-dir`). It is byte-for-byte what the console showed.
- **The execution trace**, `./data/<date>/<time>_<job>.jsonl` (`--data-dir`). It is CloudEvents, one per line, holding every step's inputs, outputs, checks and HTTP exchanges. That includes the calls the SDK made on the engine's behalf, which is where a 403 three calls into a DSP negotiation becomes visible ([ADR-0016](../developer/decision-records/backend/ADR-0016-execution-trace-format.md)).

Each transcript line ends in `id=…`, the id of the event it reports. Use it to pull the whole event from the trace:

```bash
jq -c 'select(.id == "<id from the transcript>")' data/*/*.jsonl
```

### A check failed

A failed assertion is a result, not an error. The trace records it under the step's `validations`:

```bash
jq -c 'select(.type == "tck.test.step.failed") | .data.validations[] | select(.outputs.passed == false)' data/*/*.jsonl
```

```json
{"source":"validate/assert/equals","field":"status_code","inputs":{"assertion":"equals","expected":201},"outputs":{"actual":202,"passed":false},"errors":[{"code":"ASSERTION_FAILED","message":"Expected 201, got 202","severity":"HARD"}]}
```

`SOFT` checks are reported as warnings and don't fail the step.

### A step raised

When a step fails rather than a check, the failure is in `data.errors`. `origin` says whose fault it was: `sut` when the system under test answered wrongly, `engine` when TestLab itself broke.

```bash
jq -c 'select(.type == "tck.test.step.failed") | .data.errors[]?' data/*/*.jsonl
```

### No offer is made under a policy the step accepts

Consumer-side DSP steps accept an offer only when its policy matches one of the `expected_policies` **exactly**. That applies to `connector/consumer/pull_data_filtered`, `connector/consumer/pull_data_filtered_by_policy`, `connector/consumer/do_dsp`, `connector/consumer/do_dsp_with_bpnl` and `connector/discover/digital-twin-registry/auth`. When none matches, the step reports the comparison:

```text
Error: no offer from https://sut.example/api/v1/dsp/2025-1 is made under a policy this step accepts
         2 offers compared, none matched:
           offer 'aWNodWI6Y29udHJhY3Q6T0Js…' on asset 'ichub:asset:dtr:9foUM7pm…':
             the provider also requires: 'Membership eq active'
         expected: 'FrameworkAgreement eq DataExchangeGovernance:1.0', 'UsagePurpose isAnyOf cx.core.digitalTwinRegistry:1'
```

- **"the provider also requires"**: the offer carries a condition you didn't expect. An extra condition refuses the offer just as a missing one does.
- **"the provider does not offer"**: you require a condition the offers don't carry.
- **"the same conditions on both sides"**: the conditions agree, but the policy documents still differ (an action, a rule kind, a prefixed operand). Compare the two documents in the trace.
- **`'expected_policies' is an empty list`**: an empty list accepts nothing. Name the policies, or omit the key to take any offer.

The full comparison, with offer and asset ids, is in the trace:

```bash
jq -c '.data.errors[]? | select(.code == "POLICY_MISMATCH") | .context.offers[]' data/*/*.jsonl
```

### A mock endpoint is never called

1. Hand the system under test `full_mock_url` from `mock/api`. `base_mock_url` is only the server root.
2. `mock/wait/http_request` takes the `mock` output of the step that registered it (`${{ setup.<id>.mock }}`), and fails after `timeout_s` (default 30 seconds).
3. The mock server listens on the engine's host. A system under test running elsewhere must be able to reach that address. `localhost` from inside another container is not the engine.

## Working on a step: it isn't found or behaves oddly

- **`Unknown step type` for a step you just wrote.** Check that `@step("…")` matches the id exactly and that the module is imported from its category's `__init__.py`. `tests/unit/steps/test_step_registration.py` catches both. See [Create a Step](create-a-step.md).
- **A published output is missing.** An output field left at its default is not serialised. Pass every field you mean to publish explicitly, and a `None` value leaves the context variable unset.
- **An SDK call hangs the run or fails without saying which service.** Call the SDK through `sdk_call.run` and HTTP through `steps.http_client.request`. A blocking call made directly inside `execute` also stalls the mock server.
