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
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6). -->
<!-- It was reviewed and tested by a human committer. -->

# How to Run the Full Development Workflow

The IDE frontend is developed in the separate [cx-test-suite](https://github.com/eclipse-tractusx/cx-test-suite) repository; this repository is the Python engine and CLI.

## Python development

The project is managed with Poetry (>= 2.0) and requires Python 3.12+:

```bash
# Install all dependency groups (test, docs)
poetry install

# Run tests
poetry run pytest -v

# Run the CLI
poetry run testlab validate tests/e2e/connector-dtr-smoke/tests/dtr_roundtrip.yaml
poetry run testlab compile tests/e2e/connector-dtr-smoke/index.yaml --plain
poetry run testlab run tests/e2e/connector-dtr-smoke/index.yaml
```

Before opening a PR, check that the generated step reference is still in sync:

```bash
poetry run testlab docs --check
```

## Documentation

The docs dependencies are in the `docs` Poetry group (installed by `poetry install`):

```bash
poetry run mkdocs serve   # http://localhost:8000
poetry run mkdocs build   # Build static site
```
