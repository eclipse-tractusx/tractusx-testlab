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

# Developer Handover — TestLab Engine

This documentation is a technical handover guide for the **TestLab engine**, the Python compiler, runner, and mock server that executes certification test scripts for Eclipse Tractus-X dataspaces. It covers architecture, data flow, and the patterns used throughout the codebase so that a new developer can orient quickly and contribute confidently.

The **IDE frontend** — the browser-based visual authoring tool built on React and Blockly — lives in the separate **cx-test-suite** repository. It talks to this engine through the server API and the block catalog generated from the engine's step registry; nothing in this repository renders UI.

## Repository layout

```
tractusx-testlab/
├── src/tractusx_testlab/         ← The engine: CLI, compiler, player, server, steps
├── tests/                        ← Pytest suite (incl. e2e/ smoke scripts)
├── stubs/                        ← Type stubs for untyped dependencies
├── tools/                        ← Maintenance tooling (e.g. IDE parity checker)
├── docs/                         ← This documentation (MkDocs)
│   └── developer/                ← You are here
├── mkdocs.yml
└── pyproject.toml                ← Poetry project definition
```

See [Architecture](architecture.md) for the layer-by-layer breakdown of `src/tractusx_testlab/`.

## Quick start

```bash
poetry install
poetry run testlab --help        # the CLI entry point
poetry run pytest                # run the test suite
poetry run mkdocs serve          # preview this documentation
```

## Documentation structure

| Page | What it covers |
|------|----------------|
| [Product Scope](product-scope.md) | Mission, MVP scope boundaries, lifecycle, execution ordering, versioning, and validation model |
| [Architecture](architecture.md) | High-level architecture, layering, module organization |
| [Step Contracts](step-contracts.md) | The single-source-of-truth contract architecture: one id, one shape per step, enforcement and anti-drift tooling |
| [Data Models](data-models.md) | The engine's Pydantic models and the YAML document structure |
| [Block Lifecycle](block-lifecycle.md) | How a step maps from YAML → registry → Python executor → SDK call |
| [Creating a Step](creating-a-step.md) | Reference for writing a new step executor and its contract |
| [Tutorials](../tutorials/index.md) | How-to guides: step executors, service types, assertions, debugging |

## Tech stack

| Technology | Purpose |
|-----------|---------|
| Python 3 + Poetry | Language and dependency management |
| Pydantic v2 | Data models, step contracts, validation |
| Typer | CLI command groups |
| FastAPI | Mock server, callbacks, SSE streaming |
| tractusx-sdk | Dataspace protocol communication (connector, DTR, discovery) |
| pytest | Test suite |
| MkDocs (Material) | This documentation |

The IDE frontend's stack (React, Blockly, Zustand, Monaco, …) is documented in the cx-test-suite repository.

## Key design principles

1. **One canonical contract per step.** One id, one set of parameter names, one output shape — declared in Pydantic next to the executor, with no aliases and no backward-compat shims. See [Step Contracts](step-contracts.md).
2. **The YAML is the interface.** Scripts use `uses:` / `with:` / `returns:`; whatever authored them — the cx-test-suite IDE or a text editor — the engine compiles and runs the same document.
3. **Steps are functions.** Every step has typed inputs and typed outputs, and publishes all of its return outputs — each top-level output field becomes a context variable of the same name.
4. **Delegate the protocol.** Steps call tractusx-sdk services rather than re-implementing dataspace protocols.
5. **Hide plumbing.** Connector services are seeded into the run context at runtime — no step names its service.
6. **Generated reference, enforced parity.** The step reference page is generated from the registry, and CI fails when it drifts (`testlab docs --check`).
