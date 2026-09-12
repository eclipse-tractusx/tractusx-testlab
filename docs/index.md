<div align="center" markdown>

![Eclipse Tractus-X SDK TestLab](media/test-lab-app-logo-white-claim.png#only-light){ width="260" }
![Eclipse Tractus-X SDK TestLab](media/test-lab-app-logo-black-claim.png#only-dark){ width="260" }

</div>

# Welcome to Tractus-X TestLab

**TestLab** is the test authoring and execution engine for Eclipse Tractus-X dataspaces.
You describe a test scenario in declarative YAML — the calls to make, the values to
check, the cleanup to perform — and TestLab validates it, packages it, runs it against
real connectors and services, and reports exactly what happened. No Python required.

<div class="grid cards" markdown>

-   :material-file-document-edit-outline: **Write**

    ---

    Compose tests from a catalogue of predefined steps: HTTP calls, connector
    negotiations, Digital Twin Registry lookups, assertions.

-   :material-shield-check-outline: **Validate & compile**

    ---

    Every test is checked before anything executes, then sealed into a portable
    `.tck` package — optionally signed and encrypted.

-   :material-play-circle-outline: **Run**

    ---

    Execute a TCK from the `testlab` CLI or embed the player in your own
    application, with a full execution trace of every step.

</div>

## Quick start

This walkthrough takes about five minutes: install the CLI, write a one-test TCK,
and run it.

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

A **TCK** (Test Case Kit) is a directory holding an `index.yaml` manifest and the
tests it lists. Create this layout:

```text
hello-tck/
├── index.yaml
└── tests/
    └── health_check.yaml
```

```yaml title="hello-tck/index.yaml"
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

```yaml title="hello-tck/tests/health_check.yaml"
kind: test
syntax: v1-alpha

namespace: hello-tck
id: health-check

metadata:
  name: Health check
  version: "1.0"

execution:
  - id: health_check
    uses: http/http_request          # (1)!
    name: Call the service
    with:
      method: GET
      url: https://eclipse-tractusx.github.io/
    returns:
      status_code:
        type: integer
    validate:
      - uses: validate/assert        # (2)!
        with: { input: status_code, operator: equals, value: 200 }
```

1. `uses` picks a step from the [Step Reference](api-reference/steps/index.md).
2. Checks read the values the step declares under `returns`.

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

The console transcript is written to `./logs` and the full execution trace — every
step's outputs, checks and request/response — to `./data`.

### 5. Package and share it

Compile the TCK into a single `.tck` package that anyone can run:

```bash
testlab compile index.yaml -o hello.tck
testlab run hello.tck
```

!!! tip "Where to go next"
    - `testlab <command> --help` lists every option, for example `--var KEY=VALUE`
      to override a variable at run time.
    - To sign and encrypt packages for a specific player, see
      [Compiling Packages](specification/walkthrough/compiling-packages.md).

## Explore the documentation

The most common starting points are below. For every page, grouped by what you want
to do, see the [Documentation Map](home/documentation-map.md).

| If you want to…                              | Read                                                          |
|----------------------------------------------|---------------------------------------------------------------|
| Understand what TestLab is and how it works  | [Overview](home/overview.md)                                  |
| Learn the YAML test format                   | [TCK Syntax](tck-syntax/index.md)                             |
| Read the requirements specification          | [Specification](specification/index.md)                       |
| Look up a step and its inputs and outputs    | [Step Reference](api-reference/steps/index.md)                      |
| Follow a guided scenario                     | [Tutorials](tutorials/index.md)                               |
| Use TestLab as a Python library              | [API Reference](api-reference/index.md)                       |
| Extend the engine or contribute              | [Developer](developer/index.md) · [Contributing](contributing/index.md) |
