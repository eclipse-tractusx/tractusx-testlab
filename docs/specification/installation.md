<!--

Eclipse Tractus-X - Software Development KIT

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

This guide covers all the ways to install the Tractus-X SDK and the `testlab` CLI tool.

---

## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| Python      | 3.12+           |
| pip         | latest           |
| OS          | Linux, macOS, Windows |

---

## Quick Install (PyPI)

Install the latest release from PyPI:

```bash
pip install tractusx-sdk
```

This installs the SDK library **and** the `testlab` CLI tool.

Verify the installation:

```bash
testlab --help
```

---

## Install Script

The repository includes an install script that automates environment setup:

```bash
git clone https://github.com/eclipse-tractusx/tractusx-sdk.git
cd tractusx-sdk
./install.sh
```

The script will:

1. Check that Python 3.12+ is available
2. Create a virtual environment (`.venv/` by default)
3. Upgrade pip
4. Install the SDK from PyPI
5. Verify the `testlab` CLI is available

### Script Options

| Flag | Description |
|------|-------------|
| `--dev` | Install from local source in editable mode (for development) |
| `--venv DIR` | Use a custom virtual environment directory (default: `.venv`) |
| `--no-venv` | Skip virtual environment creation, install into the active environment |
| `--help` | Show usage information |

### Examples

```bash
# Standard install (PyPI + virtual environment)
./install.sh

# Development install from source
./install.sh --dev

# Custom virtual environment location
./install.sh --venv myenv

# Install into an already-active environment
./install.sh --no-venv
```

---

## Development Install (from source)

For contributors or anyone working on the SDK itself:

```bash
git clone https://github.com/eclipse-tractusx/tractusx-sdk.git
cd tractusx-sdk
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test,docs]"
```

Or use the install script shorthand:

```bash
./install.sh --dev
```

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
# Check SDK version
python -c "import tractusx_sdk; print(tractusx_sdk.__version__)"

# Check testlab CLI
testlab --help
```

Expected output from `testlab --help`:

```
Usage: testlab [OPTIONS] COMMAND [ARGS]...

  Tractus-X Testlab CLI — compile, encrypt, validate, and run TCKs.

Commands:
  compile     Compile a YAML test script into a .tck package.
  config      Show the resolved configuration.
  docs        Generate the step reference from the step catalog.
  inspect     Report what a .tck package contains, without executing it.
  keygen      Generate RSA (encryption) + Ed25519 (signing) key pairs.
  run         Load and execute a TCK, printing results to stdout.
  schema      Write the JSON Schemas for the authoring format.
  serve       Run the TestLab HTTP server.
  validate    Validate a YAML test script without compiling.
```

---

## Upgrade

To upgrade to the latest version:

```bash
pip install --upgrade tractusx-sdk
```

---

## Uninstall

```bash
pip uninstall tractusx-sdk
```

---

## Troubleshooting

### `testlab` command not found

If `testlab` is not found after installation, ensure:

1. The virtual environment is activated (if using one)
2. The install location is on your `PATH`
3. Try running via Python module: `python -m tractusx_sdk.extensions.testlab.cli`

### Python version too old

The SDK requires Python 3.12+. Check your version:

```bash
python3 --version
```

If you need to install a newer version, use [pyenv](https://github.com/pyenv/pyenv) or your system package manager.

### Permission denied on install.sh

```bash
chmod +x install.sh
./install.sh
```
