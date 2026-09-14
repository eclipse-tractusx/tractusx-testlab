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

# Development Workflow

This repository is the TestLab engine: the `tractusx_testlab` Python package, the `testlab` CLI and the server. The project uses Poetry (2.x) and Python 3.12. See [Installation](../home/installation.md) for setting up the environment.

```bash
poetry install          # the package plus its dev, test and docs groups
```

## Before you push: what CI runs

CI runs the checks below, and a pull request is blocked until all of them pass. Run the same commands locally, in this order: the fast checks first, the full suite last.

```bash
poetry run ruff check src tests tools
poetry run ruff format --check src tests
poetry run mypy                            # every module under src/ is type-checked; there are no exemptions

poetry run testlab docs --check            # the step reference matches the step models
poetry run testlab schema --check          # the TCK JSON Schemas match the authoring models

poetry run python -m pytest tests/ -q
```

When `docs --check` or `schema --check` fails, regenerate the pages with `testlab docs` or `testlab schema` and commit the result. Those files are generated; don't edit them by hand.

The test suite includes guards that review would otherwise have to catch:

| Guard | Fails when |
|---|---|
| `tests/unit/structure/test_module_layout.py` | a source file passes 300 lines or a known oversized file grows, a module is named `utils`/`helpers`/`base`/…, or a new basename is duplicated |
| `tests/unit/steps/test_step_registration.py` | a step isn't under the package its id names, or isn't imported |
| `tests/unit/steps/test_step_contracts.py` | a step lacks a declared input/output contract or a docstring |
| `tests/combinations/test_assertion_matrix.py` | an assertion operator has no passing and failing case |

## Run a TCK while you work

```bash
poetry run testlab validate docs/examples/certificate-management-v2/raw/index.yaml
poetry run testlab compile  docs/examples/certificate-management-v2/raw/index.yaml --plain -o build/ccm
poetry run testlab run      docs/examples/certificate-management-v2/raw/index.yaml
poetry run testlab config                  # which settings were resolved, and from where
```

`testlab run` refuses to start until every capability the TCK requires is bound. Bind them in `testlab.config.yaml`, through `TESTLAB_*` environment variables, or per run with `--var infrastructure.sut.connector.dsp_url=…`; see [Infrastructure Bindings](../developer/infrastructure-bindings.md). `tests/e2e/connector-dtr-smoke/` runs against a real dataspace in CI (`.github/workflows/e2e-umbrella.yml`), not under pytest.

## Tests: where a new one goes

| Directory | For |
|---|---|
| `tests/unit/<package>/…` | one module's contract; mirrors `src/tractusx_testlab/` package for package |
| `tests/combinations/` | steps wired into each other against in-process doubles |
| `tests/examples/` | the shipped `docs/examples/` TCKs still parse, compile and run |
| `tests/integration/` | the CLI → compiler → player chain |

Every test directory needs an `__init__.py`. Import paths from `tests/paths.py` instead of building them from `Path(__file__)`. [tests/README.md](https://github.com/eclipse-tractusx/tractusx-testlab/blob/main/tests/README.md) has the details.

## Two traps that pass locally and fail in CI

- **An undeclared dependency.** The dev virtualenv holds every group and whatever the SDK pulls in, so an import that `pyproject.toml` doesn't declare still works locally. CI builds the wheel and imports every module in a clean virtualenv. To reproduce that, build with `poetry build` and install the wheel into a throwaway venv.
- **A dependency change without its IP record.** Changing `poetry.lock` means `DEPENDENCIES` must be regenerated with the Eclipse Dash tool. The `dependencies.yml` workflow fails when it is stale or names a restricted package.

## Source-file conventions

Every new source file starts with the Apache-2.0 license header. AI-assisted files also carry the two-line AI notice after it. Copy both from a neighbouring file. [AGENTS.md](https://github.com/eclipse-tractusx/tractusx-testlab/blob/main/AGENTS.md) holds the full conventions: logging through `logging.getLogger(__name__)` and never `print()`, narrow `except` clauses, one canonical name per concept.

## Documentation

```bash
poetry run mkdocs serve          # http://localhost:8000
poetry run mkdocs build --strict # also fails on broken links and pages missing from the nav
```
