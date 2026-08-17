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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and tested by a human committer. -->

# Test suite layout

Five top-level buckets, split by *what a failure tells you* — not by how fast
the test runs.

| Directory | Answers | Doubles |
|-----------|---------|---------|
| `unit/` | Does one module honour its contract? | Everything outside the module |
| `combinations/` | Do steps compose — outputs of one wiring into the next? | Only the network edge |
| `examples/` | Does the shipped example TCK still parse, compile and run? | Connectors and registries |
| `integration/` | Does the CLI → compiler → player chain hold end to end? | The SDK layer |
| `e2e/` | Does testlab drive a **real** dataspace? (CI only, not pytest) | Nothing |

## `unit/` — mirrors `src/tractusx_testlab/`

One package per source package, same name, same nesting:

```
unit/cli/          ← src/tractusx_testlab/cli/
unit/compiler/     ← src/tractusx_testlab/compiler/
unit/models/       ← src/tractusx_testlab/models/
unit/player/       ← src/tractusx_testlab/player/
unit/player/loading/
unit/scripting/    ← src/tractusx_testlab/scripting/
unit/server/       ← src/tractusx_testlab/server/
unit/services/     ← src/tractusx_testlab/services/
unit/steps/        ← src/tractusx_testlab/steps/
unit/steps/{assertions,connector,flow,industry,pull_data,security,server,utility}/
```

The rule is mechanical: a test for `tractusx_testlab.steps.connector.negotiate`
belongs in `unit/steps/connector/`. Files directly under `unit/steps/` test
contracts that span several step packages (registry wiring, executor
protocols), which is the only reason a test sits above its module.

## `combinations/` — step-to-step wiring

Journeys built from real step classes against in-process doubles
(`connector_double.py`, `http_double.py`, `mock_server_double.py`) driven
through `harness.py`. These catch the seams unit tests cannot see: a step
publishing an output under a name the next step does not read.

## `examples/` — the published examples are the fixture

`examples/ccm/` exercises the `certificate-management-v2` example under
`docs/examples/`. It exists so a change to the engine that silently breaks
the documentation fails CI. The example is read from disk rather than
duplicated here — a copied fixture drifts, the shipped example cannot.

## `e2e/` — not collected by pytest

`e2e/connector-dtr-smoke/` is a TCK written in testlab's own YAML, run by
`.github/workflows/e2e-umbrella.yml` against a kind cluster. See
[e2e/README.md](e2e/README.md).

## Paths — never count `..` from `__file__`

Test modules sit at varying depths, so `Path(__file__).parent.parent` silently
repoints when a file moves between packages. Import the anchored constants
instead:

```python
from tests.paths import CCM_RAW_DIR, DOCS_DIR, FIXTURES_DIR, REPO_ROOT, SRC_DIR
```

## Packages, not loose files

Every directory here carries an `__init__.py`. pytest's default `prepend`
import mode uses the first ancestor *without* one to root `sys.path`, so the
`__init__.py` chain is what makes modules import as `tests.unit.steps.…` and
keeps same-named test files in different packages from colliding. A new
subdirectory without one will break collection.

## Running

```bash
python -m pytest tests/ -x -q                    # everything
python -m pytest tests/unit -q                   # unit only
python -m pytest tests/unit/steps/connector -q   # one source package
python -m pytest tests/ -q --ignore=tests/integration   # what CI runs
```

`asyncio_mode = "auto"`, `testpaths` and `pythonpath` live in
`pyproject.toml` under `[tool.pytest.ini_options]` — the single source of
pytest configuration.
