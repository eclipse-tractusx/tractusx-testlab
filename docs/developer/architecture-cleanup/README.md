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
<!-- This document was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and validated by a human committer. -->

# Architecture Cleanup — Finding Ledger

> Started 2026-08-17 on `feat/architecture_refactoring`.
> Source review: 49 findings, two reproduced failures.

**This effort changes behaviour.** It is deliberately distinct from
[`refactor-plan/`](../refactor-plan/README.md), which is structural-only and
promises no contract changes. This one rejects input that used to be accepted,
deletes code that is reachable-but-inert, and replaces the package format.

## Why this ledger exists

The work spans five phases over several weeks. Every finding below carries an ID
used in commit messages, test `reason=` strings, and code comments, so a change
can always be traced back to the reason it was made — and so a finding cannot be
quietly dropped between sessions.

**Status values:** `open` · `in-progress` · `done` · `blocked` · `dropped`
(with a reason).

---

## Gate questions — answered 2026-08-17

| # | Question | Answer |
| --- | --- | --- |
| Q1 | Are inter-script `depends_on` dependencies a v1 feature? | **No — delete the machinery.** |
| Q2 | Is an unsigned `.tck` a supported distribution format? | **`.tck` is the one distribution *and* execution format.** The separate package format is wrong and goes. |
| Q3 | Does the IDE consume `tck-execution.json`? | **No — and that is not what it is for.** It is the compiled, machine-readable form *the player is meant to execute*. The IDE only authors declarative YAML and, at run time, renders the trace by parsing CloudEvents. |
| Q4 | Is the AI-provenance subtitle a compliance artefact? | **No.** Keep it in file headers; do not enforce it in CI. |

### Q3 inverts the largest planned change

The review recorded `compiler/ir/` (866 LOC) as the single biggest deletion,
on the evidence that nothing executes `tck-execution.json` — it is written,
fingerprinted, and read back only to verify its own digest.

That evidence was right; the conclusion was wrong. **The IR is not dead code,
it is unwired code.** The intended pipeline is:

```text
YAML (authored in the IDE)  →  compile  →  tck-execution.json  →  player executes
```

What actually ships today executes the raw YAML carried alongside the IR, and
fingerprints the IR nobody runs. So the correct move is the opposite of
deletion:

- **Keep** `compiler/ir/` and make the player execute the IR.
- **Delete the second representation instead** — `tck-bundle.yaml` and the
  `tests/*.yaml` copies inside the archive, plus the player's YAML-from-package
  load path.
- A `.tck` then carries `manifest.yaml` + `tck-execution.json` + `assets/`, and
  nothing else that could be mistaken for the thing that runs.

This is a better outcome than the deletion it replaces: **F-A09 closes
structurally rather than by patching the digest.** Once the fingerprinted
artefact and the executed artefact are the same file, there is no gap left to
verify the wrong side of. Combined with Q2 collapsing two package formats into
one, P3 gets simpler than estimated, not harder.

Net effect on the deletion budget: −866 (IR retained) +~400 (bundle/YAML paths
removed), so roughly 1,300 LOC rather than 1,750. Revised in the phase notes
below.

---

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| **P0** | Enforcement layer — ruff, mypy, CI gates | **done** |
| **P1** | Deletion pass (~1,300 LOC after the Q3 revision) | not started |
| **P2** | Close the false-positive class | not started |
| **P3** | Rewrite compiler + collapse to one `.tck`, executed from the IR | not started |
| **P4** | Rewrite execution engine + type the seams | not started |
| **P5** | Rename, reshape, add invariants | not started |

### P0 outcome

Three gates now run in CI (`.github/workflows/test.yml`) and all pass:

| Gate | State |
| --- | --- |
| `ruff check src tests tools` | clean — 880 violations fixed, the rest deferred with a named finding and phase |
| `mypy` | clean — 135 errors → 0 gated; 72 remain behind per-module ratchet entries |
| `pytest tests/` | 1,310 pass, 0 fail — integration suite no longer excluded |
| `testlab docs --check` | added; step reference must match the models |
| wheel installs + every module imports | added; catches undeclared dependencies |

Fully type-clean and gated: `infrastructure`, `logging`, `security`, `services`,
`syntax`. Every other package has a `[[tool.mypy.overrides]]` entry naming the
finding that clears it — removing the entry is how a package graduates.

**Not done in P0, deliberately:** `ruff format` would rewrite 151 files. That
belongs in one isolated commit with a `.git-blame-ignore-revs`, not mixed into
behavioural work where it would make every other diff unreviewable. Deferred to
P5.

---

## Theme A — Silence where there should be an error

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-A01 | Critical | Authoring models accept and drop unknown keys (`extra="ignore"`) | P2 | open |
| F-A02 | Critical | Unresolved `${{ }}` reference becomes its own literal text | P2 | open |
| F-A03 | Critical | Steps fabricate `HttpResponse(500)` and still report PASSED (15 sites) | P2 | open |
| F-A04 | Critical | `run_step` catches 5 exception types; the rest abort the whole job | P2 | open |
| F-A05 | Critical | Assertion with no `operator` silently becomes `not_null`, ignoring `value` | P2 | open |
| F-A06 | Critical | Zero executed assertions is a passing result | P2 | open |
| F-A07 | High | Polling treats timeout as a normal outcome | P2 | open |
| F-A08 | High | Unknown keys also accepted by JSON Schemas and the config loader | P2 | open |
| F-A09 | Critical | Package integrity check does not cover the executed test files | P3 | open |
| F-A10 | Critical | `metadata.dataspace_version` was never read — a jupiter TCK ran as saturn, silently | P0 | **done** |

### F-A10 — found during P0, not in the original review

`_target_release` read `definition.dataspace_version`. That field does not exist
on `TckDefinition`; the flat spelling lives on `TckMetadataDefinition`. Because
the read went through `getattr(…, "")`, the miss looked exactly like "the author
did not state a release".

Two consequences, and the second is the dangerous one:

1. A TCK declaring `metadata.dataspace_version: jupiter` with no `dataspace:`
   block resolved to the **saturn** default, so the SDK built saturn connector
   services for a jupiter deployment — the wrong DSP dialect.
2. It also returned `release_stated=False`, which is precisely the flag that
   tells `InfrastructureManager.align()` not to hold the release against the
   bound deployment. **The `StandardConflictError` guard was therefore bypassed**,
   so the mismatch raised nothing at all.

Found because mypy objected to `getattr` on a statically-known attribute, and
fixed by reading the declared field directly. Three regression tests in
`tests/unit/player/test_player_infrastructure.py::TestRelease`.

The `SimpleNamespace` test double in that file had to become a real
`TckDefinition` for the tests to keep passing — which is the point: the stub was
as silent about the missing field as the model was, so it agreed with the bug.
That is the concrete cost of F-F02's defensive `getattr` style, in one place.

## Theme B — Four descriptions of one contract

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-B01 | High | JSON Schema and Pydantic model disagree on 6 required fields | P3 | open |
| F-B02 | High | `validate/*` registered as steps but forbidden by the validator | P1 | open |
| F-B03 | High | Three variable syntaxes live against a rule permitting one | P1 | open |
| F-B04 | Medium | Undeclared-variable check greps a syntax no script uses | P2 | open |
| F-B05 | Medium | Two accepted shapes for `env.schemas` / `env.testdata` | P3 | open |
| F-B06 | Medium | Three version numbers for one artefact; `v1-alpha2` is not PEP 440 | P3 | open |
| F-B07 | Low | Docstrings promise `.tck`, code writes `.stck`; "inlining" does not inline | P3 | open |
| F-B08 | High | Compiler and runtime parse `${{ }}` with different regexes | P3 | open |

## Theme C — Subsystems wired to fields that no longer exist

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-C01 | High | 4 execution subsystems are permanent no-ops (`depends_on`, `outputs`, `services`, `variables`) | P1 | **blocked on Q1** |
| F-C02 | Medium | CLI progress bar reads 3 keys no event carries → always renders FAIL | P4 | open |
| F-C03 | Medium | `server/routes/jobs.py` defines the same 2 symbols twice | P0 | **done** |
| F-C04 | Medium | 8 stale xfail markers; 4 duplicate test files | P0 | **done** — `xfail_strict` now prevents recurrence |
| F-C05 | Low | Unused assignment/param, duplicated imports, wrong docstring | P0 | **done** — plus a dead helper calling an undefined name |

## Theme D — Layering and structure

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-D01 | High | Folder layout does not predict step identity | P5 | open |
| F-D02 | High | Import cycle player ↔ steps, held open by deferred imports | P4 | open |
| F-D03 | High | `StepContext` is a god object; reaches into `ServiceManager._definitions` | P4 | open |
| F-D04 | Medium | Alias shims renaming functions for no behavioural reason | P1 | open |
| F-D05 | Medium | 13 files over 300 lines; 5 folders over 5 files | P5 | open |
| F-D06 | Medium | No test package for `config`, `logging`, `security`, `syntax`, `schemas` | P3 | open |

## Theme E — The same job, done several ways

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-E01 | High | Blocking `requests` inside `async def`, alongside `httpx` | P4 | open |
| F-E02 | High | 4 undeclared runtime deps: `requests`, `rich`, `cryptography`, `starlette` | P0 | **done** — declared; `starlette` reached via `fastapi`. `requests` goes in P4 |
| F-E03 | Medium | 16 of 56 steps overlap another step | P1 | open |
| F-E04 | Medium | Two dot-path extractors with different semantics | P1 | open |
| F-E05 | Medium | Hidden camelCase fallback in path lookup | P4 | open |
| F-E06 | Low | Two lockfiles, one tracked | P0 | open |

## Theme F — Error model and typing floor

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-F01 | High | Documented `TestLabError` hierarchy does not exist | P2 | open |
| F-F02 | High | Service layer typed `object`; 56 defensive `getattr` sites follow | P4 | open |
| F-F03 | Medium | `UserWarning` on every import and CLI invocation | P4 | open |
| F-F04 | Medium | Two typing dialects (`Optional[X]` 62 files, `X \| None` 12) | P4 | open |

## Theme G — Nothing is enforced

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-G01 | Critical | No linter, type checker or formatter anywhere | P0 | **done** — formatter deferred to P5, see P0 outcome |
| F-G02 | High | CI excludes integration tests and every documented quality gate | P0 | **done** |
| F-G03 | Medium | No packaging smoke test | P0 | **done** |
| F-G04 | Medium | `__main__.py` runs the CLI on *import*, not only on `python -m` | P0 | **done** |

### F-G04 — found by the packaging smoke test on its first run

`__main__.py` called `main()` at module level with no `if __name__ ==
"__main__":` guard, so importing `tractusx_testlab.__main__` launched the CLI.
Anything that walks the package triggered it: the smoke test, documentation
generators, coverage collectors. The new gate caught this the first time it ran,
which is the argument for the gate.

Also confirmed live while building the wheel: `version = "v1-alpha2"` is not
PEP 440 and the artefact builds as `tractusx_testlab-1a2` (F-B06). The repository
and the distributed package disagree about what version this is.

## Theme H — Configuration

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-H01 | High | Hand-written env mapping, already drifted (`logs_dir` has no var) | P5 | open |
| F-H02 | Medium | No sample config; surface documented across 5 pages | P5 | open |
| F-H03 | Medium | One prefix, two unrelated naming schemes | P5 | open |

## Theme I — CLI behaviour and record-keeping

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-I01 | Medium | `run` compiles as a side effect, writing into the source tree | P5 | open |
| F-I02 | Medium | Three overlapping package-inspection commands | P5 | open |
| F-I03 | Low | `util/log` uses `print()`, bypassing structured logging | P5 | open |
| F-I04 | Low | 150 files carry another project's copyright header | P5 | open |
| F-I05 | Low | Stray tracked files; inaccurate AI-provenance record | P5 | open |

---

## Invariants

The five tests that keep the cleanup from regressing. Each fails the build when
a second way of doing something reappears.

| # | Invariant | Test | Status |
| --- | --- | --- | --- |
| I1 | Every step's module path is derivable from its id | `tests/unit/steps/test_step_registration.py` | partial — inventory covered, path mapping in P5 |
| I2 | Every registered step is reachable by the validator | — | P1, with F-B02 |
| I3 | Generated step reference equals the committed one | `testlab docs --check` in CI | **done**. JSON Schema half lands with P3 |
| I4 | A TCK with unknown keys, unresolvable refs, or zero assertions is rejected | `tests/unit/test_no_false_positives.py` | **written — 7 tests, all `xfail(strict)` against P2/P3** |
| I5 | No duplicate basenames, no file over 300 lines, no banned module names | — | P5 |

### The P2/P3 ratchet is armed

`tests/unit/test_no_false_positives.py` holds both reproductions from the review
plus five siblings, each asserting the *correct* behaviour and marked
`xfail(strict=True)` against its finding:

| Test | Finding |
| --- | --- |
| a misspelled `validte:` key is rejected | F-A01 |
| an unknown key on a step is rejected | F-A01 |
| an unresolvable `${{ }}` reference fails the run | F-A02 |
| an assertion with no `operator` is rejected | F-A05 |
| a run that executed no declared assertion fails | F-A06 |
| a tampered test file inside a `.tck` is refused | F-A09 |
| a package missing its digest target is refused | F-A09 |

With `xfail_strict = true`, the moment a fix lands the test XPASSes and the build
fails until the marker comes off. **A finding in this file cannot be closed
quietly, and cannot regress quietly either.**

One further test in that file is deliberately *not* xfail: it characterises the
three-representation archive layout as it exists today, so P3's collapse to a
single artefact shows up as a visible, intentional change rather than a silent
one.
