<!--

Eclipse Tractus-X - Tractus-X TestLab

Copyright (c) 2026 Contributors to the Eclipse Foundation

See the NOTICE file(s) distributed with this work for additional
information regarding copyright ownership.

This work is made available under the terms of the
Creative Commons Attribution 4.0 International (CC-BY-4.0) license,
which is available at
https://creativecommons.org/licenses/by/4.0/legalcode.

SPDX-License-Identifier: CC-BY-4.0

-->

# Installation Guide

This guide covers installing the `tractusx-testlab` package and its `testlab` CLI.

---

## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| Python      | 3.12+           |
| pip         | latest          |
| OS          | Linux, macOS, Windows |

---

## Quick Install (PyPI)

TestLab is published on PyPI as pre-releases, so pip needs `--pre`:

```bash
pip install --pre tractusx-testlab
```

This installs the library **and** the `testlab` CLI. The [Tractus-X SDK](https://github.com/eclipse-tractusx/tractusx-sdk)
comes with it as a dependency.

To install one specific release:

```bash
pip install tractusx-testlab==1.0.0a3
```

---

## Development Install (from source)

The project is managed with [Poetry](https://python-poetry.org/) (>= 2.0):

```bash
git clone https://github.com/eclipse-tractusx/tractusx-testlab.git
cd tractusx-testlab
poetry install
poetry run testlab --help
```

`poetry install` installs the `dev`, `test` and `docs` dependency groups as well.
See [Development Workflow](../tutorials/development-workflow.md) for running the tests and the docs site.

---

## Virtual Environment

It is recommended to use a virtual environment to avoid conflicts with other Python packages.

### Create and Activate

=== "Linux / macOS"

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

=== "Windows"

    ```powershell
    python -m venv .venv
    .venv\Scripts\activate
    ```

### Deactivate

```bash
deactivate
```

---

## Verify Installation

After installation, confirm everything is working:

```bash
# Check the installed version
python -c "import importlib.metadata as m; print(m.version('tractusx-testlab'))"

# Check the testlab CLI
testlab --help
```

`testlab --help` lists these commands:

| Command | Purpose |
|---------|---------|
| `compile` | Compile a TCK manifest into a `.tck` package |
| `config` | Show the settings this engine resolved, and which of them came from the environment |
| `docs` | Generate the step reference from the steps' declared input/output models |
| `inspect` | Report what a `.tck` package contains, without executing it |
| `keygen` | Generate RSA (encryption) + Ed25519 (signing) key pairs for a player identity |
| `run` | Load and execute a TCK, printing results to stdout |
| `schema` | Generate the TCK JSON Schemas from the authoring models |
| `serve` | Start the TestLab FastAPI server via uvicorn |
| `validate` | Validate a TCK manifest and its tests without compiling |

---

## Configuration

Every setting has a default, so no configuration file is needed to validate or compile.
To *run* a TCK against a dataspace, bind the connectors and registries it requires —
see `testlab.config.example.yaml` in the repository and
[Executing Tests](../specification/walkthrough/executing-tests.md#step-1--bind-the-infrastructure).
`testlab config` prints what resolved and where each value came from.

---

## Upgrade

```bash
pip install --upgrade --pre tractusx-testlab
```

---

## Uninstall

```bash
pip uninstall tractusx-testlab
```

---

## Troubleshooting

### `testlab` command not found

If `testlab` is not found after installation, ensure:

1. The virtual environment is activated (if using one)
2. The install location is on your `PATH`
3. From a source checkout, run it through Poetry: `poetry run testlab --help`

### `No matching distribution found for tractusx-testlab`

Only pre-releases are published so far. Add `--pre`, or pin a version such as `tractusx-testlab==1.0.0a3`.

### Python version too old

TestLab requires Python 3.12+. Check your version:

```bash
python3 --version
```

If you need to install a newer version, use [pyenv](https://github.com/pyenv/pyenv) or your system package manager.
