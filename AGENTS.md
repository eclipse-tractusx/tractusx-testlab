# AGENTS.md — Tractus-X TestLab AI Agent Instructions

> **Compatibility**: This file consolidates all agent definitions and coding instructions for use with
> OpenAI Codex, GitHub Copilot, and any AI tool that reads `AGENTS.md` from the repository root.
> The canonical source remains `.github/agents/*.agent.md` and `.github/instructions/*.instructions.md`.

---

## Project Overview

**tractusx-testlab** is the Python backend library for authoring and running Eclipse Tractus-X dataspace tests, plus the shared authoring contract (YAML format, variable syntax, block/step catalog).

| Codebase | Stack | Location |
|----------|-------|----------|
| Python library | Python 3.12+, Pydantic v2, async, pytest, tractusx-sdk | `src/tractusx_testlab/` |

Tests: `tests/` at repo root. Docs: `docs/` with MkDocs Material. Config: `mkdocs.yml`.

---

## Agent Roles

### `testlab-architect` — Software Architect & Project Manager

**Scope**: Planning, impact analysis, work package design, architectural decisions.

- Analyzes requirements and breaks them into scoped work packages
- Identifies which agent should handle each package and why
- Evaluates trade-offs, risks, and dependencies before code is written
- Read-only — **NEVER writes code** — plans and advises only
- Hands approved work packages directly to the specialist agents

### `testlab-master` — Backend Developer

**Scope**: Everything in `src/tractusx_testlab/` — Python modules, CLI, models, steps, services.

- Expert in Python 3.12+, Pydantic v2, async, pytest, tractusx-sdk
- The testlab is a thin orchestration layer on top of `tractusx-sdk>=0.7.0`
- CLI: Typer-based — `testlab run`, `testlab compile`, `testlab validate`
- SDK modules: `tractusx_sdk.dataspace` (connectors, DSP, discovery), `tractusx_sdk.industry` (AAS/DTR)

### `testlab-test-master` — Test Engineer

**Scope**: Everything in `tests/` — unit tests, integration tests, fixtures, factories.

- Expert in pytest, pytest-asyncio, mocking, test architecture
- Arrange-Act-Assert structure, one concept per test
- Descriptive names: `test_compiler_rejects_unknown_step_type`
- Mock at boundaries, prefer dependency injection over monkey-patching

### `testlab-docs-master` — Technical Writer

**Scope**: Everything in `docs/` and `mkdocs.yml` — documentation pages, tutorials, API reference.

- Expert in MkDocs Material, Mermaid diagrams, developer guides
- Verify all documentation claims against actual code before writing
- Every code example must be copy-paste-ready and correct

---

## Design Principles

1. **One way to do things.** Never offer two approaches to the same result.
2. **Steps are functions.** Every step has typed inputs and typed outputs.
3. **Auto-generate IDs.** asset_id, policy_id, contract_id = auto-generated UUIDs. Never ask the user.
4. **Hide plumbing.** Connector addresses come from test_root config, not per-step fields.
5. **Defaults everywhere.** Steps work with minimal input.

---

## Hard Rules

| Rule | Enforcement |
|------|-------------|
| No source-code file exceeds 300 lines (docs exempt) | `find <dir> -name '*.py' \| xargs wc -l \| awk '$1 > 300'` |
| Max 5 files per folder, excluding the barrel (`__init__.py`); docs exempt | Reorganize into responsibility-grouped sub-folders, each with a barrel the parent forwards through |
| Code is modular by design — single-responsibility units, reusable helpers, no duplication | Split along responsibility seams; extract shared logic into importable modules |
| Apache-2.0 license header on all source files | Required |
| AI-generated code subtitle after license header | See below |
| Variable syntax in YAML: `${{ ... }}` (e.g. `${{ env.X }}`, `${{ steps.<id>.<out> }}`) per ADR-0010 | Never `@variable_name` or `${var}` |

### AI-Generated Code Subtitle

All AI-generated or AI-modified files must include this subtitle immediately after the license header:

**Python / Shell / YAML** (`##`):
```python
## This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: o3).
## It was reviewed and tested by a human committer.
```

**HTML / XML** (`<!-- -->`):
```html
<!-- This code was partially generated using artificial intelligence (AI) (Tool: Codex, Model: o3). -->
<!-- It was reviewed and tested by a human committer. -->
```

Replace `Codex` and `o3` with the actual tool and model name being used.

---

## Python Conventions (`src/tractusx_testlab/`)

### Package Structure
```
src/tractusx_testlab/
├── cli/          ← Typer CLI commands
├── compiler/     ← YAML compiler + validator + packager
├── config/       ← Configuration loading
├── logging/      ← Structured logging
├── models/       ← Pydantic models
├── player/       ← Test execution engine
├── scripting/    ← YAML parser + builders
├── security/     ← Crypto key generation
├── server/       ← Mock server (FastAPI)
├── services/     ← Service manager
├── steps/        ← Step executors
└── syntax/       ← Default syntax constants
```

### Code Quality
- All public functions have type annotations
- Private helpers prefixed with `_`
- Protocols and ABCs for all extension points
- `@dataclass(frozen=True)` or Pydantic `ConfigDict(frozen=True)` for value objects
- Context managers for resource lifecycle
- Structured logging via `logging.getLogger(__name__)` — never `print()`
- Async code uses `asyncio.TaskGroup` over bare `create_task`
- No wildcard imports — explicit imports only
- No bare `except Exception:` or `except:` — catch the narrowest type
- No `: Any` unless unavoidable — use specific types or generics

### Error Handling
- Domain hierarchy: `TestLabError → CompilationError | ExecutionError | MockServerError`
- Context in errors: what failed, what was expected, what was received
- Validate at boundaries, raise typed exceptions, never swallow errors

### Naming
- Booleans: `is_*`, `has_*`, `should_*`
- Factory functions: `create_*`
- Converters: `to_*`, `from_*`
- Collections: plural nouns (`steps`, `assertions`, not `step_list`)

### Quality Gates
```bash
find src -name '*.py' | xargs wc -l | awk '$1 > 300 && !/total/'   # Must be empty
grep -rn "except Exception:" src/ --include="*.py"                   # Must be empty
grep -rn "print(" src/ --include="*.py" | grep -v "_fingerprint"     # Must be empty
python -m pytest tests/ -x -q                                        # Must pass
```
- **SonarQube**: Run `mcp_sonarqube_analyze_file_list` on all created/modified files. Fix CRITICAL/BLOCKER findings before delivering.

### Splitting Oversized Files
Modularity is the goal; the line limit is just the trigger. Extract **reusable** units along responsibility seams — never cut a file arbitrarily. Shared logic becomes an importable helper; never duplicate it.
- **Steps**: one step class per file, extract `_helpers.py` and `_constants.py`
- **CLI**: one command group per file, main app wires with `app.add_typer()`
- **Models**: one concern per file, `__init__.py` as barrel re-export only

### Tractus-X SDK Reference

The testlab delegates to SDK classes — never reimplement protocol logic.

**Dataspace** (`tractusx_sdk.dataspace`):
- `services.connector.ServiceFactory` — `get_connector_consumer_service()`, `get_connector_provider_service()`
- `services.connector.BaseConnectorService` — `do_get()`, `do_dsp()`, `create_asset()`, `get_catalog_by_dct_type()`
- `services.discovery.DiscoveryFinderService`, `ConnectorDiscoveryService`
- `managers.connection` — `MemoryConnectionManager`, `FileSystemConnectionManager`
- `managers.OAuth2Manager` — OAuth2 token management

**Industry** (`tractusx_sdk.industry`):
- `services.AasService` — DTR operations
- `models.aas.v3` — `ShellDescriptor`, `SpecificAssetId`, `AssetKind`

**Dataspace versions**: `"jupiter"` (EDC v0.8–0.10) and `"saturn"` (EDC v0.11+, DSP 2025-1)

---

## Testing Conventions (`tests/`)

### Framework
- pytest + pytest-asyncio
- Run: `python -m pytest tests/ -x -q`
- Config lives **only** in `pyproject.toml` `[tool.pytest.ini_options]`

### Layout — see [tests/README.md](tests/README.md)
```
tests/
├── unit/          ← mirrors src/tractusx_testlab/ package for package
├── combinations/  ← step-to-step wiring against in-process doubles
├── examples/      ← the shipped docs/examples/ TCKs, read from disk
├── integration/   ← CLI → compiler → player, end to end
├── e2e/           ← TCK YAML run against a real dataspace (CI, not pytest)
├── fixtures/      ← static YAML/JSON inputs
└── paths.py       ← REPO_ROOT / SRC_DIR / DOCS_DIR / FIXTURES_DIR / CCM_RAW_DIR
```
- A test for `tractusx_testlab.<a>.<b>` goes in `tests/unit/<a>/<b>/`. No exceptions
  except cross-package contracts, which sit at the parent level.
- Every test directory needs an `__init__.py` — pytest's `prepend` import mode
  relies on the chain to root `sys.path` and to keep same-named files apart.
- Never write `Path(__file__).parent.parent` — import from `tests.paths`.

### Principles
- Arrange-Act-Assert structure
- One assertion concept per test
- Descriptive names: `test_compiler_rejects_yaml_with_unknown_step_type`
- Independent, deterministic — no randomness, no network calls in unit tests
- Fixtures and factories — never copy-paste setup
- Mock at boundaries — mock external services, not internal functions
- Use `AsyncMock` for async code

### What to Test
| Priority | What |
|----------|------|
| High | Public API contracts, error paths, edge cases |
| Medium | Integration points (CLI → compiler → runner), model validation |
| Low | Happy paths (usually covered by integration tests) |
| Never | Implementation details, third-party library behavior |

### Quality Gates
```bash
python -m pytest tests/ -x -q                                              # Must pass
find tests -name '*.py' | xargs wc -l | awk '$1 > 300 && !/total/'        # Must be empty
grep -rn "time.sleep\|asyncio.sleep" tests/ --include="*.py"               # Should be empty
```
- **SonarQube**: Run `mcp_sonarqube_analyze_file_list` on all created/modified files. Fix CRITICAL/BLOCKER findings before delivering.

---

## Documentation Conventions (`docs/`)

### Build Tool
- MkDocs Material — config in `mkdocs.yml`
- Run: `mkdocs build` (must produce zero errors)

### Structure
- `docs/home/` — Landing pages
- `docs/specification/` — YAML format specification
- `docs/tutorials/` — Step-by-step guides
- `docs/developer/` — Architecture and internals
- `docs/api-reference/` — Python API reference

### Principles
- Verify all claims against actual code before writing
- Code examples must be copy-paste-ready and correct
- Use Mermaid for all diagrams (max 10-12 nodes)
- Active voice, second person, present tense, short sentences (max 25 words)
- No placeholders (`TODO`, `TBD`, `Coming soon`)
- Documentation is exempt from the 300-line source rule — split long pages into sub-pages for readability, but a cohesive reference (ADR, spec, API page) may exceed 300 lines when splitting would harm comprehension

---

## Review Checklist (Applied to All Deliveries)

```
□ File under 300 lines? (source code only — docs exempt)
□ Functions under 30 lines?
□ Single responsibility per module?
□ No magic strings or hardcoded values?
□ Type annotations on all public functions?
□ Error messages include context (what failed, expected, received)?
□ Tests follow Arrange-Act-Assert?
□ No duplicated logic across files?
□ Naming follows conventions (is_*, create_*, to_*, plural collections)?
□ No unnecessary abstractions or wrapper layers?
□ Could a new developer understand this without explanation?
```

---

## AI Output Validation — Common LLM Failure Modes

Watch for and fix these in all AI-generated code:

- **Hallucinated APIs**: calls to functions that don't exist in the SDK or codebase
- **Plausible but wrong**: code that looks correct but has subtle logic errors
- **Copy-paste bloat**: duplicated logic that should be extracted
- **Over-abstraction**: unnecessary layers, factories-of-factories
- **Missing edge cases**: happy-path-only implementations
- **Inconsistent patterns**: mixing styles within the same codebase
- **Ignored instructions**: doing something different from what was asked

---

## Token Economy — Reducing Waste

All agents must follow these rules to minimize token consumption:

### Response Rules
- **Never echo back the task description** — start working immediately
- **Never explain what you're about to do** — just do it
- **Response format**: changed files list + diffs only (no full file dumps)
- **Max response length**: 200 lines for specialist agents, 300 lines for architect
- **Do NOT restate constraints** from the delegation prompt — acknowledge with one line, then work

### Reading Rules
- **Read only what you need**: if a file is over 100 lines, read only the target function/section
- **One read pass**: do not re-read files you already read in this session
- **One exploration per area**: after the first exploration of a codebase area, store findings — never re-explore

### Delegation Rules (for orchestrator)
- **Store shared context in session memory** — write once, reference by path in all delegations
- **Batch independent WPs** to the same agent when they touch different files
- **Line-targeted reads** in prompts: say "read lines 30-60" not "read the whole file"
- **Skip the architect for small scope** — if < 3 agents and no cross-codebase impact, plan directly
