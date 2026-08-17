# Tutorials

Step-by-step guides for common TestLab engine tasks — writing tests, Python step executors, services, validation, and debugging.

Looking for the visual IDE (Blockly blocks, React components, YAML sync)? That frontend lives in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository, together with its own tutorials.

## Getting Started

### 1. Install the Python package

```bash
pip install tractusx-testlab
```

### 2. Write your first test

Tests are packaged as a TCK: a directory with an `index.yaml` manifest and a `tests/` folder.

`my-tck/index.yaml`:

```yaml
syntax: v1-alpha
kind: tck
id: my-first-tck
metadata:
  name: My First TCK
  version: "1.0"
  description: A single health-check test

tests:
  - id: health_check.yaml
    name: Health check
```

`my-tck/tests/health_check.yaml`:

```yaml
kind: test
syntax: v1-alpha

namespace: my-first-tck
id: health-check

metadata:
  name: "Health Check"
  version: "1.0"

execution:
  - id: health_check
    uses: http/http_request
    name: Health Check
    with:
      method: GET
      url: http://localhost:8080/api/check/health
    returns:
      status_code:
        type: integer
    validate:
      - uses: validate/assert
        with: { input: status_code, operator: equals, value: 200 }
```

Each step names its implementation with `uses:`, passes parameters in `with:`, and declares its readable outputs in `returns:` — assertions in `validate:` read exactly those declared names.

### 3. Validate

```bash
testlab validate my-tck/tests/health_check.yaml
```

### 4. Run

```bash
testlab run my-tck/index.yaml
```

## Using Mock Services

Mocks let you test without real infrastructure. Register a mock endpoint in `setup:`, hand its URL to the system under test, then wait for the call:

```yaml
setup:
  - id: mock_callback
    uses: mock/api
    name: Expose a mock callback endpoint
    with:
      method: POST
      path: "/notifications/receive"
      response_status: 200
    returns:
      mock:
        type: class
        class: MockInstance
      full_mock_url:
        type: string

execution:
  - id: wait_for_callback
    uses: mock/wait/http_request
    name: Wait for the SUT to call the mock
    with:
      mock: "${{ steps.mock_callback.mock }}"
      timeout_s: 30
    returns:
      request_body:
        type: object
```

TestLab runs a local HTTP server for the mocks; `full_mock_url` is the address a script hands to the system under test. A protocol-aware Digital Twin Registry mock is available as `mock/dtr`, and twin registration against a real registry uses `digital-twin/provider/create_shell_descriptor`.

## All Tutorials

### Python (Runtime & Steps)

- [Create a New Step Executor](create-step-executor.md) — Write the Python code behind a step id
- [Add a New Assertion Type](add-assertion-type.md) — Extend the `validate/*` steps
- [Add a New Service Type](add-service-type.md) — Register a new external service integration
- [Add a New Validation Rule](add-validation-rule.md) — Add a static check to the compiler

### Workflow

- [Development Workflow](development-workflow.md) — Python and docs dev commands
- [Debugging Common Issues](debugging.md) — Troubleshoot step resolution, validation, and runtime failures

### Certificate Management

- [CCM Business Guide](ccm-business-guide.md) — What Company Certificate Management tests certify
- [CCM Architecture Guide](ccm-architecture-guide.md) — How the CCM test flows are built
- [CCM Developer Guide](ccm-developer-guide.md) — Implementing against the CCM TCK
- [CCM Conformity Testing](ccm-conformity-testing.md) — Running the conformity suite
