<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/media/test-lab-app-logo-black-claim.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/media/test-lab-app-logo-white-claim.png">
    <img alt="Eclipse Tractus-X SDK TestLab" src="docs/media/test-lab-app-logo-white-claim.png" width="200">
  </picture>
</p>

# Eclipse Tractus-X Test Lab

**TestLab** is the test authoring and execution engine for Eclipse Tractus-X dataspaces. It lets you author, compile, distribute, and execute conformity tests against dataspace connectors and industry services — without writing any Python code.

Test authors write **declarative YAML tests** describing the steps to execute, the values to check, and the cleanup to perform. TestLab validates them, packages them, runs them against real connectors and services, and records a full execution trace. It builds on the [Tractus-X SDK](https://github.com/eclipse-tractusx/tractusx-sdk) for its dataspace calls.

## Key Components

- **TCK** — a Test Case Kit: an `index.yaml` manifest plus the tests it lists, written in the `v1-alpha` syntax
- **Compiler** — validates a TCK before anything runs and seals it into a portable `.tck` package, optionally signed and encrypted for specific players
- **Player** — executes a TCK from the `testlab` CLI or embedded in your own application (`TestlabPlayer`), and writes a CloudEvents execution trace
- **Infrastructure bindings** — the connectors and registries a run drives are bound by the operator (`testlab.config.yaml` or `TESTLAB_*` variables), never named inside a test
- **Server** — a FastAPI app (`testlab serve`) that runs TCKs, streams live execution events over SSE, and serves the callback and mock endpoints tests listen on

## How It Works

A test is a sequence of steps from a predefined catalogue — for example `connector/provider/create_asset`, `connector/consumer/pull_data_filtered`, `digital-twin-registry/consumer/dataplane/lookup_shell` — each declaring its inputs under `with:`, the outputs it publishes under `returns:`, and the checks on those outputs under `validate:`. See the [Step Reference](docs/api-reference/steps/index.md) for every step and the [TCK Syntax](docs/tck-syntax/index.md) for the format.

## Quick Start

This walkthrough takes about five minutes: install the CLI, write a one-test TCK, and run it. For other installation options, see [INSTALL.md](INSTALL.md).

### 1. Install the CLI

TestLab needs **Python 3.12 or newer**. Install it into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install --pre tractusx-testlab
```

This puts the `testlab` command on your path. Check it works:

```bash
testlab --help
```

### 2. Write a TCK

A **TCK** (Test Case Kit) is a directory holding an `index.yaml` manifest and the tests it lists. Create this layout:

```text
hello-tck/
├── index.yaml
└── tests/
    └── health_check.yaml
```

`hello-tck/index.yaml`:

```yaml
syntax: v1-alpha
kind: tck
id: hello-tck
metadata:
  name: Hello TCK
  version: "1.0"
  description: My first TestLab TCK

tests:
  - id: health_check.yaml
    name: Health check
```

`hello-tck/tests/health_check.yaml`:

```yaml
kind: test
syntax: v1-alpha

namespace: hello-tck
id: health-check

metadata:
  name: Health check
  version: "1.0"

execution:
  - id: health_check
    uses: http/http_request          # a step from the Step Reference
    name: Call the service
    with:
      method: GET
      url: https://eclipse-tractusx.github.io/
    returns:
      status_code:
        type: integer
    validate:
      - uses: validate/assert        # checks read the values declared under returns
        with: { input: status_code, operator: equals, value: 200 }
```

### 3. Validate it

```bash
cd hello-tck
testlab validate index.yaml
```

```text
OK — index.yaml is valid (no issues)
```

A mistake in the YAML is reported here, with the file and line, before anything runs.

### 4. Run it

```bash
testlab run index.yaml
```

TestLab executes each step, logs every call it makes, and ends with a summary:

```text
╔==============================================================================╗
║                                TCK RUN SUMMARY                               ║
╠==============================================================================╣
║  TEST                                           RESULT      TIME             ║
║  --------------------------------------------------------------------------  ║
║  ✓ Health check                                   PASS      3.5s             ║
╠==============================================================================╣
║  RESULT: PASS  |  1 passed  0 failed  0 skipped  |  Total: 3.5s              ║
╚==============================================================================╝
```

The console transcript is written to `./logs` and the full execution trace — every step's outputs, checks and request/response — to `./data`.

### 5. Package and share it

Compile the TCK into a single `.tck` package that anyone can run:

```bash
testlab compile index.yaml -o hello.tck
testlab run hello.tck
```

> [!TIP]
>
> - `testlab <command> --help` lists every option, for example `--var KEY=VALUE` to override a variable at run time.
> - To sign and encrypt packages for a specific player, see [Compiling Packages](docs/specification/walkthrough/compiling-packages.md).

## Documentation

The full documentation is published at **[eclipse-tractusx.github.io/tractusx-testlab](https://eclipse-tractusx.github.io/tractusx-testlab/)**. Its sources live in the [docs](docs/) directory.

## Contributing

Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) file for information on how to contribute to this project.

## License

Distributed under the Apache License 2.0. See [LICENSE](LICENSE) for code and [LICENSE_non-code](LICENSE_non-code) for non-code content.

## NOTICE

This work is licensed under the [Apache-2.0](https://www.apache.org/licenses/LICENSE-2.0).

- SPDX-License-Identifier: Apache-2.0
- SPDX-FileCopyrightText: 2026 Contributors to the Eclipse Foundation
- SPDX-FileCopyrightText: 2026 Catena-X Automotive Network e.V.
- Source URL: https://github.com/eclipse-tractusx/tractusx-testlab
