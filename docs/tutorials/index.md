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

# Tutorials

Worked examples, each one run against the engine as it is today. Start with **Your first TCK** below, then pick a path:

| I want to… | Read |
|---|---|
| run and understand a real conformity suite | [Certificate Management](certificate-management.md) |
| add a step that tests can name in `uses:` | [Create a Step](create-a-step.md) |
| add a comparison the `validate:` blocks can use | [Add an Assertion Operator](add-assertion-operator.md) |
| let a TCK require a new kind of infrastructure | [Add an Infrastructure Capability](add-infrastructure-capability.md) |
| catch a TCK mistake before it runs | [Add a Validation Rule](add-validation-rule.md) |
| get a change through CI | [Development Workflow](development-workflow.md) |
| work out why a TCK doesn't validate, start or pass | [Debugging](debugging.md) |

The full YAML language is in [TCK Syntax](../tck-syntax/index.md), and every step in the [Step Reference](../api-reference/steps/index.md).

## Your first TCK

A TCK is a directory with an `index.yaml` manifest and a `tests/` folder. This one has two tests: one calls an HTTP endpoint and checks the answer, the other exposes a mock endpoint and checks the call it receives. Neither needs a dataspace.

### 1. Install

```bash
pip install --pre tractusx-testlab
```

### 2. Write the manifest

`my-first-tck/index.yaml`:

```yaml
kind: tck
syntax: v1-alpha

id: my-first-tck

metadata:
  name: My First TCK
  version: "1.0.0"
  description: Two tests that need no dataspace

tests:
  - id: health_check.yaml
    name: Health check
  - id: callback.yaml
    name: Callback
```

The manifest's `id` is the namespace of every test in it. A real TCK also declares `dataspace:`, the `infrastructure:` it requires and its `env:` variables; see [Manifest](../tck-syntax/manifest/index.md).

### 3. Call an endpoint and check the answer

`my-first-tck/tests/health_check.yaml`:

```yaml
kind: test
syntax: v1-alpha

namespace: my-first-tck
id: health-check

metadata:
  name: Health Check
  version: "1.0.0"

execution:
  - id: health_check
    uses: http/http_request
    name: Call the health endpoint
    with:
      method: GET
      url: https://httpbin.org/json
    returns:
      status_code:
        type: integer
    validate:
      - uses: validate/assert/equals
        with: { input: status_code, value: 200 }
```

Every step has the same four parts:

- `uses:` names the implementation.
- `with:` passes its parameters.
- `returns:` declares the outputs the rest of the test reads.
- `validate:` checks those outputs.

### 4. Expose a mock and check the call it receives

A conformity test often has to *receive* a call. The system under test notifies back, or asks TestLab for data. `mock/api` registers an endpoint on the engine's mock server, and `mock/wait/http_request` blocks until that endpoint is called. Here an `http/http_request` stands in for the system under test.

`my-first-tck/tests/callback.yaml`:

```yaml
kind: test
syntax: v1-alpha

namespace: my-first-tck
id: callback

metadata:
  name: Callback
  version: "1.0.0"

setup:
  - id: callback_endpoint
    uses: mock/api
    name: Expose a callback endpoint
    with:
      method: POST
      path: /notifications/receive
      response_status: 202
    returns:
      mock:
        type: object
      full_mock_url:
        type: string

execution:
  - id: send_notification
    uses: http/http_request
    name: Stand in for the system under test
    with:
      method: POST
      url: ${{ setup.callback_endpoint.full_mock_url }}
      body: { status: RECEIVED }
    validate:
      - uses: validate/assert/equals
        with: { input: status_code, value: 202 }

  - id: wait_for_callback
    uses: mock/wait/http_request
    name: Wait for the call to arrive
    with:
      mock: ${{ setup.callback_endpoint.mock }}
      timeout_s: 30
    returns:
      request_body:
        type: object
    validate:
      - uses: validate/field/equals
        with: { input: request_body, path: status, value: RECEIVED }
```

A later step reads an earlier one's output as `${{ <phase>.<step-id>.<output> }}`, here `setup.callback_endpoint.full_mock_url`. In a real test, you hand that URL to the system under test instead of calling it yourself.

### 5. Validate and run

```bash
testlab validate my-first-tck/index.yaml
testlab run my-first-tck/index.yaml
```

`validate` checks the manifest and every test without running anything:

```text
OK — index.yaml is valid (no issues)
```

`run` compiles the TCK, executes it and prints one summary per test and one for the run:

```text
║  ✓ callback[setup:callback_endpoint]:mock/api           PASS      0.0s       ║
║  ✓ callback[send_notification]:http/http_request        PASS      0.0s       ║
║  ✓ callback[wait_for_callback]:mock/wait/http_request   PASS      0.0s       ║
...
║  RESULT: PASS  |  2 passed  0 failed  0 skipped  |  Total: 0.9s              ║
```

The run also writes a transcript to `./logs/` and a CloudEvents execution trace to `./data/`. [Debugging](debugging.md) shows how to read both.

### Where to go next

- Test a real connector: add `infrastructure.sut.connector.required: true` to the manifest and use the `connector/consumer/*` steps. The connector is bound when the TCK runs, not written into it; see [Infrastructure Bindings](../developer/infrastructure-bindings.md).
- See a complete suite: [Certificate Management](certificate-management.md) walks through the shipped CX-0135 TCK in `docs/examples/certificate-management-v2/`.
