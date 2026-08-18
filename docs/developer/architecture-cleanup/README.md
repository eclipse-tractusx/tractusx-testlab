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
| **P1** | Deletion pass | **done** — 1,060 lines removed, 152 added |
| **P2** | Close the false-positive class | **done** |
| **P3** | Rewrite compiler + collapse to one `.tck`, executed from the IR | in-progress — IR made lossless; player wiring next |
| **P4** | Rewrite execution engine + type the seams | **done** |
| **P5** | Rename, reshape, add invariants | not started |

### P0 outcome

Three gates now run in CI (`.github/workflows/test.yml`) and all pass:

| Gate | State |
| --- | --- |
| `ruff check src tests tools` | clean — 880 violations fixed, no rule deferred |
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
| F-A01 | Critical | Authoring models accept and drop unknown keys (`extra="ignore"`) | P2 | **done** — all 14 authoring models strict; error names the full path |
| F-A02 | Critical | Unresolved `${{ }}` reference becomes its own literal text | P2 | **done** — raises `UnresolvedReferenceError`, naming what is in scope |
| F-A03 | Critical | Steps fabricate `HttpResponse(500)` and still report PASSED (15 sites) | P2 | **done** — 15 sites raise `StepExecutionError`; no step invents a status the SUT never sent |
| F-A04 | Critical | `run_step` catches 5 exception types; the rest abort the whole job | P2 | **done** — catches broadly, classifies engine fault vs SUT failure |
| F-A05 | Critical | Assertion with no `operator` silently becomes `not_null`, ignoring `value` | P2 | **done** — operands checked against the operator's declared arity |
| F-A06 | Critical | Zero executed assertions is a passing result | P2 | **done** — `declared` vs `total` recorded; a run that verified nothing says so |
| F-A07 | High | Polling treats timeout as a normal outcome | P2 | **done** — raises unless the step asks for `allow_timeout` |
| F-A08 | High | Unknown keys also accepted by JSON Schemas and the config loader | P2/P3 | **done** — config in P2; the generated schemas carry `additionalProperties: false` |
| F-A09 | Critical | Package integrity check does not cover the executed test files | P3 | **done** — one digest over every archive entry; seal and verify share one function |
| F-A10 | Critical | `metadata.dataspace_version` was never read — a jupiter TCK ran as saturn, silently | P0 | **done** |
| F-A11 | High | `expects: fail` silently dropped by the model | P2 | **done** — declared; the validations carry the expectation |

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
| F-B01 | High | JSON Schema and Pydantic model disagree on 6 required fields | P3 | **done** — schemas generated from the models; `testlab schema --check` in CI |
| F-B02 | High | `validate/*` registered as steps but forbidden by the validator | P1 | **done** — module deleted; its stronger schema check ported into the reachable path |
| F-B03 | High | Three variable syntaxes live against a rule permitting one | P1 | **done** — `${var}`, `@var`, `source: VARIABLE` all removed |
| F-B04 | Medium | Undeclared-variable check greps a syntax no script uses | P2 | **done** — scope-aware, now an error; 23 spurious warnings → 0 |
| F-B05 | Medium | Two accepted shapes for `env.schemas` / `env.testdata` | P3 | **done** — the generated schema describes the list form the models declare |
| F-B06 | Medium | Three version numbers for one artefact; `v1-alpha2` is not PEP 440 | P3 | **done** — `1.0.0a2`, read from package metadata everywhere |
| F-B07 | Low | Docstrings promise `.tck`, code writes `.stck`; "inlining" does not inline | P3 | **done** — `.stck` deleted; `.tck` is the one format, plain or encrypted |
| F-B08 | High | Compiler and runtime parse `${{ }}` with different regexes | P3 | **done in P1** — one grammar in `syntax/patterns.py`, five definitions gone |

## Theme C — Subsystems wired to fields that no longer exist

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-C01 | High | 4 execution subsystems are permanent no-ops (`depends_on`, `outputs`, `services`, `variables`) | P1 | **done** — `ordering.py`, `_helpers.py`, `resolve_service_def`, 4 phantom properties deleted |
| F-C02 | Medium | CLI progress bar reads 3 keys no event carries → always renders FAIL | P4 | **done (reading bug)** — typed-event contract stays in P4 |
| F-C03 | Medium | `server/routes/jobs.py` defines the same 2 symbols twice | P0 | **done** |
| F-C04 | Medium | 8 stale xfail markers; 4 duplicate test files | P0 | **done** — `xfail_strict` now prevents recurrence |
| F-C05 | Low | Unused assignment/param, duplicated imports, wrong docstring | P0 | **done** — plus a dead helper calling an undefined name |

## Theme D — Layering and structure

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-D01 | High | Folder layout does not predict step identity | P5 | **done** — every step's path mirrors its id; enforced |
| F-D02 | High | Import cycle player ↔ steps, held open by deferred imports | P4 | **done** — `contracts.StepInvoker`; the edge is one-way |
| F-D03 | High | `StepContext` is a god object; reaches into `ServiceManager._definitions` | P4 | **done** — `DataspaceAccess` split out; 222 → 151 lines |
| F-D04 | Medium | Alias shims renaming functions for no behavioural reason | P1 | **done** — 6 files → `phase.py` |
| F-D05 | Medium | 13 files over 300 lines; 5 folders over 5 files | P5 | **done** — 16 → 13 over 300, largest 638 → 422; ratcheted, may only shrink |
| F-D06 | Medium | No test package for `config`, `logging`, `security`, `syntax`, `schemas` | P3 | **done** — `tests/unit/security/`, 15 tests over encryption, signing and sealing |

## Theme E — The same job, done several ways

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-E01 | High | Blocking `requests` inside `async def`, alongside `httpx` | P4 | **done (our half)** — one async client; SDK half is F-E07 |
| F-E02 | High | 4 undeclared runtime deps: `requests`, `rich`, `cryptography`, `starlette` | P0 | **done** — declared; `starlette` reached via `fastapi`. `requests` goes in P4 |
| F-E03 | Medium | 16 of 56 steps overlap another step | **P5** | deferred — see note |
| F-E04 | Medium | Two dot-path extractors with different semantics | P1 | **done** — `_get_nested` deleted with its module |
| F-E05 | Medium | Hidden camelCase fallback in path lookup | P4 | **done** — a path names the key the document has |
| F-E06 | Low | Two lockfiles, one tracked | P0 | **done** — `uv.lock` removed; poetry is what CI uses |
| F-E07 | High | The SDK is synchronous, so ~22 SDK calls block the loop too | P4 | **done** — 18 network calls offloaded via `sdk_call.run` |

## Theme F — Error model and typing floor

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-F01 | High | Documented `TestLabError` hierarchy does not exist | P2 | **done** — `TestLabError` → Authoring/Execution/Engine; all 12 reparented |
| F-F02 | High | Service layer typed `object`; 56 defensive `getattr` sites follow | P4 | **done** — `contracts/services.py`; mypy in `steps` 59 → 17 |
| F-F03 | Medium | `UserWarning` on every import and CLI invocation | P4 | **done** — field renamed `assertions`, YAML key unchanged |
| F-F04 | Medium | Two typing dialects (`Optional[X]` 62 files, `X \| None` 12) | P4 | **done** — `Optional`/`Union` gone; rules enforced |

## Theme G — Nothing is enforced

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-G01 | Critical | No linter, type checker or formatter anywhere | P0 | **done** — ruff check, ruff format and mypy all gated in CI, no exemptions |
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
| F-H01 | High | Hand-written env mapping, already drifted (`logs_dir` has no var) | P5 | **done** — pydantic-settings derives every name |
| F-H02 | Medium | No sample config; surface documented across 5 pages | P5 | **done** — `testlab.config.example.yaml` + `testlab config` |
| F-H03 | Medium | One prefix, two unrelated naming schemes | P5 | **done** — both derived from their models |

## Theme I — CLI behaviour and record-keeping

| ID | Sev | Finding | Phase | Status |
| --- | --- | --- | --- | --- |
| F-I01 | Medium | `run` compiles as a side effect, writing into the source tree | P5 | **done** — builds to a temp dir |
| F-I02 | Medium | Three overlapping package-inspection commands | P5 | **done** — `info`/`decompile` folded into `inspect --manifest` / `--extract` |
| F-I03 | Low | `util/log` uses `print()`, bypassing structured logging | P5 | **done** |
| F-I04 | Low | 150 files carry another project's copyright header | P5 | **done** — 217 files corrected |
| F-I05 | Low | Stray tracked files; inaccurate AI-provenance record | P5 | **done** — stray files removed; subtitle kept per Q4 |

---

## Invariants

The five tests that keep the cleanup from regressing. Each fails the build when
a second way of doing something reappears.

| # | Invariant | Test | Status |
| --- | --- | --- | --- |
| I1 | Every step's module path is derivable from its id | `tests/unit/steps/test_step_registration.py` | **done** |
| I2 | Every registered step is reachable by the validator | `tests/unit/steps/test_step_registration.py` | **done** |
| I3 | Generated step reference and JSON Schemas equal the committed ones | `testlab docs --check`, `testlab schema --check` | **done** |
| I6 | Compiling a TCK loses nothing the models declare | `tests/unit/compiler/test_ir_is_lossless.py` | **done** |
| I4 | A TCK with unknown keys, unresolvable refs, or zero assertions is rejected | `tests/unit/test_no_false_positives.py` | **written — 7 tests, all `xfail(strict)` against P2/P3** |
| I5 | No duplicate basenames, no file over 300 lines, no banned module names | `tests/unit/structure/test_module_layout.py` | **done** — with a shrinking allowlist |

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

---

## P1 note — why F-E03 moved to P5

The other P1 items delete code no TCK can reach. Collapsing the 16 overlapping
steps is different in kind: it changes the **authoring surface**, and it is a
merge rather than a deletion.

Two findings from checking before cutting:

- Nine of the ten candidates have **zero uses** across `docs/examples` and
  `tests` — only `pull_data_filtered` is used (5 times).
- But the wizard family exists *specifically* for IDE form-based authoring, and
  the IDE is a separate repository. A TCK authored there could use them and
  would not appear in this search.

And the catalog variants are not duplicates in the deletion sense: they call
three different SDK methods (`get_catalog_with_filter`, `get_catalog_by_asset_id`,
`get_catalog_with_bpnl`). Folding them into one step with optional parameters is
a real API design decision, not a cut.

Both belong with the naming and step-path work in P5, where authoring-surface
changes are made deliberately and can be coordinated with the IDE.

---

## F-A11 — found in P2, in a shipped TCK

`extra="forbid"` (F-A01) immediately rejected a key in the certificate-management
example: `expects: fail`.

It is documented syntax — [syntax spec §9.3](../../specification/syntax/tck-syntax.md),
marked *(P3)* as planned — and `StepDefinition` had no such field, so Pydantic
dropped it. The example's `send_unknown_cert_type` step declares that the SUT
**must reject** an unknown certificate type. It ran as an ordinary step, so a SUT
that happily *accepted* the request was recorded as PASSED. The negative test
asserted nothing.

Implemented rather than rejected, because the syntax is specified and already in
use: `expects: fail` now inverts the step's outcome in `_finish()`. An engine
fault is never inverted — TestLab breaking is not the SUT correctly refusing.

This is the second finding (with F-A10) that only surfaced because a silent
tolerance was removed. Both were invisible while the engine accepted anything.

## P2 in progress

| Done | Still open |
| --- | --- |
| F-A01 – F-A08, F-A10, F-A11, F-B04, F-C02, F-F01 | — (F-A08's schema half moved to P3) |

The original reproduction from the review now fails as it should:

```text
$ testlab validate probe/index.yaml
  [ERROR] tests/t1.yaml: parse error —
      execution.0.validte: Extra inputs are not permitted;
      execution.1.whit: Extra inputs are not permitted;
      execution.1.unknown_key_here: Extra inputs are not permitted
Invalid — 1 error(s)
```

Every offending key is named with its full path. The validator previously
printed only `loc[0]`, which for this file would have said `execution:` and left
the author to find which step and which key in a file of dozens.

---

## F-B04 — the check that had never fired

Fixing the regex (P1) made this check run for the first time, and it immediately
produced **23 warnings against the shipped example** — every one spurious. It
compared references against `getattr(script, "variables", {})`, one of the
phantom properties deleted in P1, so the set it checked against was always empty
and the message said so:

> *"may be provided via shared_variables, runtime_vars, or output propagation"*

That was true of every reference in every TCK, so the warning carried no
information and was correctly ignored by everyone.

It now resolves against the namespace the run will actually have — the manifest's
`env` variables, testdata and schemas, the script's own step ids per phase, and
the generated infrastructure binding keys — and is an **error**, because at run
time an unresolved reference is now fatal (F-A02).

The shipped example went from 23 warnings to `OK — no issues`. A typo is caught
with the available names listed beside it:

```text
[ERROR] (step 1) tests/t.yaml: '${{ env.sut_bnp.value }}' in param 'message'
        names nothing this TCK supplies. Available: env.sut_bpn, execution.ok, …
```

Only the *root* of a reference is checked — `env.sut_bpn` out of
`env.sut_bpn.value`. How deep a declared output can be walked is the step's
business, not the manifest's, and checking further would reject valid scripts.

---

## P2 complete

### F-A06 — what the finding actually turned out to be

`extra="forbid"` closed the reproduction's path: a dropped `validate:` block is
now a compile error, so assertions cannot go missing that way. But the finding
underneath survived it — **a run that checked nothing was indistinguishable from
a run that checked everything and passed.** Both printed `RESULT: PASS`.

Making a zero-assertion run a hard error is wrong: a provisioning-only TCK
legitimately asserts nothing. So the fix is to make the difference *visible* and
to measure the case that would be a defect:

- `AssertionSummary.declared` records what the executed steps asked for, beside
  `total` for what ran. Steps skipped by `if:` are excluded — a check never
  reached was not dropped.
- `unevaluated` (declared − total) fails the script. It should be unreachable,
  which is why it is measured rather than trusted: assertions going missing
  between the script and the result is the defect this review began with.
- A run that evaluated nothing now says so in the report instead of printing an
  unqualified PASS.

### F-A08 — the schema half is blocked, not skipped

`TestlabConfig` is now `extra="forbid"`. The JSON Schemas are **not** set to
`additionalProperties: false`, deliberately: they are stale (F-B01) and list
`testlab`/`steps` where the models declare `syntax`/`execution`. Turning off
extra properties against a stale schema would reject `syntax:` — which every TCK
has.

This is safe to defer because ordering makes it redundant rather than dangerous:
`Compiler.validate` binds the Pydantic models *before* it runs the JSON Schema,
and those are now strict. The schema half lands in P3 with schema generation,
which removes the drift rather than papering over it.

### F-A07 — a timeout is not a result

`poll_until_terminal` returned the last observed state on timeout and logged a
warning, so a negotiation that never reached FINALIZED and one that reached it in
200 ms produced the same shape. It now raises, naming the id, the last state seen
and the states it was waiting for. `allow_timeout=True` is the escape hatch, and
it has to be asked for.

Two tests had encoded the old behaviour. One was titled *"An unreadable
negotiation must not burn the whole wait window"* and asserted the step
**passed** with `state: None`. Its stated intent — fail fast — is preserved; it
now asserts the failure it always described.

---

## P3, part 1 — the IR was not executable

Q3 settled that `tck-execution.json` is the form the player is *meant* to run.
Before wiring the player to it, the obvious question: **is it lossless?**

It was not. Compiled against the models, the IR dropped seven declarations:

| Dropped | What the run would have done instead |
| --- | --- |
| `infrastructure` | demanded no capabilities — `MissingBindingError` never raised |
| `dataspace` / `dataspace_version` | defaulted the ecosystem release, so the SDK builds the wrong connector dialect (the same failure as F-A10) |
| `namespace` | lost the tie back to its TCK |
| `if` | conditional steps run unconditionally |
| `expects` | negative tests run as positive ones (F-A11, in a shipped TCK) |
| `timeout_s` | timeouts never applied |

Wiring the player to the IR in that state would have introduced five regressions
at once, each silent. **The IR is now lossless**, and
`tests/unit/compiler/test_ir_is_lossless.py` compares the compiled output against
`ScriptDefinition` and `StepDefinition` themselves — so a field added to a model
without the builder learning to carry it fails the build rather than going
missing at run time.

The test also guards its own fixture: one case asserts the fixture TCK exercises
every model field, because a losslessness test is only as good as the document it
compiles.

### Two further defects found on the way

**The symbol table named assets by their Python repr.** `_collect_simple_symbols`
iterated `env.schemas` and `env.testdata` as mappings; they are lists of
`{id, source}`. Iterating a list yields the entry dicts, so the symbols came out
as:

```text
"env.schemas.{'id': 'certificate_schema', 'source': 'business_partner_…json'}"
```

`env.schemas.certificate_schema` was absent from the table entirely.

**The compiled namespace was one nothing else used.** Main-phase outputs were
filed under `steps.<id>.<field>` while the runtime publishes `execution.<id>.…`,
the syntax reference documents `execution.`, and all six references in the
shipped TCK are written `execution.`. The runtime side of this mismatch carries a
comment saying it was fixed; the compiler side never was.

### Still to do in P3

Wire the player to execute the IR, delete the second representation
(`tck-bundle.yaml` and the `tests/*.yaml` copies), digest the executed bytes
(**F-A09**), generate the JSON Schemas from the models (**F-B01**, **F-B05**,
F-A08's remainder), and settle the version and extension (**F-B06**, **F-B07**).

---

## Corrections from review — 2026-08-17

Three points raised against the P2/P3 work. Two were mistakes on my part.

### `expects:` — I implemented it wrongly

I read syntax spec §9.3 ("`expects: fail` inverts the step's own success
criterion") as a runtime outcome inversion and implemented it in the runner.
**That was wrong, and it would have failed the shipped TCK on a correct run.**

The shipped negative test asks the SUT to reject an unknown certificate type,
and then asserts:

```yaml
expects: fail
validate:
  - uses: validate/field
    with: { input: status_code, operator: equals, value: 200 }
```

The refusal is an *application-level* answer — HTTP 200 carrying a rejection
body. The validations are the expectation. Inverting the step outcome turns
exactly the correct runs into failures; verified directly against `_finish()`
before removing it.

`expects` stays **declared** — it is documented syntax, it is in use, and
`extra="forbid"` would otherwise reject the shipped TCK — but it is descriptive.
It reaches the compiled IR so the IDE and reporting can see which steps are
negative tests. The inversion is gone.

### `dataspace_version` is deprecated

Removed from `ScriptDefinition` and `TckMetadataDefinition`. The `dataspace:`
block is now the only place a release is stated.

This supersedes part of the F-A10 fix: that fix corrected the player to read the
flat field from `metadata` (where it lived) instead of from the definition (where
it never did). With the field gone, `_target_release` reads `dataspace.version`
or the default, and there is no second source to disagree with.

Also removed from the IR carry-list, and from the server's compile route — which
**required** a `dataspace` block on any `kind: test` document. No shipped test
file has one; only the manifest does. The route had been rejecting
correctly-authored test files.

### `namespace` is the TCK id at test level

Not carried in the compiled test. It is required to equal the TCK id, which the
manifest already states, so it is derivable rather than lost — recorded in the
losslessness test's `_DOCUMENT_FIELDS` alongside `kind` and `syntax`.

### Already fixed: the symbol-table repr keys

`env.schemas.{'id': …}` was corrected earlier in P3 — `_collect_simple_symbols`
was iterating a list of `{id, source}` as if it were a mapping. Symbols now read
`env.schemas.certificate_schema`.

---

## F-A09 closed — the digest now covers what executes

The digest was computed in the IR builder over `manifest.yaml + tck-execution.json
+ asset digests`, and the archive was assembled *afterwards* by the CLI, which
copied in the test files the player actually runs. The seal was therefore
computed before the thing it was sealing existed.

`compiler/package_digest.py` is now the one place a package is sealed and the one
place it is verified — `seal()` and `verify()` over the same bytes. Every archive
entry is covered, name included, so a test cannot be swapped for another under a
name the manifest already trusts.

Three silent-pass conditions removed with it:

- `_verify_tck_integrity` returned early when `tck-execution.json` was absent.
  **Deleting one file from a `.tck` skipped verification entirely.** A missing
  manifest, a missing digest and a mismatch are now all refusals.
- Verification ran *after* extraction. It now runs on the archive's bytes, so a
  package that fails never reaches a path something else might read.
- Signature checking was guarded by `if compiler_public_key and sig_raw:`, and
  `testlab run` only demanded a key for `.stck` — so an encrypted `.tck` loaded
  without one decrypted and ran **with its signature unexamined**. A signed
  package is now verified or refused; there is no third outcome.

The test fixtures build their archives through the same `seal()`, so a fixture is
by construction a package the loader accepts — a test cannot pass against a
sealing rule that exists only in the test.

### Verified end to end

```text
$ testlab run tamper/out/tamper-tck.tck        # untouched
  RESULT: PASS  |  1 passed  0 failed

$ testlab run tamper/tampered.tck              # one step appended to tests/t.yaml
Refused to run tampered.tck:
  Package checksum mismatch — the contents are not the ones this package was sealed with.
  expected blake2b:e5c91eabf654bc2467ccf45112950b667006238a44ed2d08b4466342a926bdb1
  actual   blake2b:c10ac7a323aeadc179c658012a35116affe757467fab85a4c9166b42bdc61c18
```

**Both reproductions from the architecture review are now closed.** Of the seven
regression tests written at the start, six pass with their markers removed; the
seventh (F-A06's) stays armed by choice, documenting an invariant whose original
route is now unreachable.

---

## P3, part 3 — the schemas are generated

`compiler/schema_export.py` renders `tck_index.schema.json` and
`tck_test.schema.json` from `TckDefinition` and `ScriptDefinition`.
`testlab schema` writes them, `testlab schema --check` fails the build when the
committed files no longer match, and CI runs it beside `testlab docs --check`.

What the hand-written schemas had drifted into:

| | Hand-written | The models |
| --- | --- | --- |
| discriminator | `testlab` | `syntax` |
| main phase | `steps` | `execution` |
| required | +`description`, `authors`, `license`, `standards`, step `name` | not required |
| absent | `syntax`, `dataspace`, `infrastructure`, `expects`, `if`, `timeout_s` | declared |
| unknown keys | `additionalProperties: true` | `false` |

`by_alias=True` matters in the renderer: scripts write `with:` and `if:` while
the fields are `with_` and `if_condition`, because those spellings are not legal
Python. The schema has to describe the YAML, not the Python.

### It immediately exposed a test that passed for the wrong reason

`test_validate_bad_step` asserted exit code 1 against a fixture named
`_BAD_STEP_YAML` that **contained no bad step** — just a manifest with an empty
`tests:` list. It failed only because the stale schema demanded `description` and
`standards`, which the models make optional. Once the schema matched the models
the document was valid, which it always had been, and the test had nothing left
to fail on. The fixture now names a step the registry does not have, and the test
asserts the step name appears in the output.

### F-B06 — one version

`v1-alpha2` is not PEP 440; the wheel built as `tractusx_testlab-1a2`, so the
repository and the artefact disagreed about what version this was. Now `1.0.0a2`,
and the OpenAPI document reads it from package metadata rather than hardcoding
`0.7.1` — the health endpoint, the API docs and the wheel finally agree.

---

## P4, part 1 — the seams are typed

### F-F03 — the warning on every invocation

`StepDefinition.validate` shadowed `BaseModel.validate`, so Pydantic warned on
every import of the library — including every `testlab` command — and mypy
reported the override as a type error. The field is now `assertions`, with
`validation_alias` and `serialization_alias` both `validate`: scripts, the IR and
the published JSON Schema are unchanged, and the shadowing is gone.

Renaming it immediately found a reader I had missed. `validator.py` still said
`step_def.validate`, which no longer resolved to the field — it resolved to
`BaseModel.validate`, the deprecated method — and failed with
`TypeError: 'method' object is not iterable`. That is precisely the hazard the
shadowing created, made visible by removing it.

Test warnings: 28 → 6.

### F-F02 — what the engine requires, stated as types

`contracts/services.py` declares `ConnectorConsumer`, `ConnectorProvider`,
`RegistryService`, `NotificationService` and `Controller` as Protocols. They are
deliberately **not** a mirror of the SDK: they are the ~25 members the steps
actually call, which makes the engine's requirement of a connector readable in
one place.

The SDK stays untyped at its own boundary, so an SDK object satisfies a Protocol
structurally and what gets checked is the half we own.

| | Before | After |
| --- | --- | --- |
| mypy errors in `steps` | 59 | 17 |
| `getattr` probes in steps + context | 56 | 22 |
| ratcheted modules | `steps.*` (whole package) | 10, listed individually |

The remaining 17 are ordinary step-level typing — `Any` flowing out of the SDK
into a declared payload — not the `object` seam. They are listed module by module
in `pyproject.toml` so the debt shrinks one file at a time.

### Two defects the Protocols surfaced

**`mock/api` still resolved `@name`.** The last surviving legacy-syntax resolver,
kept alive by one test. It was also actively wrong: it treated *any* string
beginning with `@` as a variable reference, so a JSON-LD value like `"@id"` in a
mock response body was mangled on its way past. The body is a step parameter —
`${{ ... }}` in it is resolved before the step runs, like every other parameter —
so the second pass was removed.

**`flow/if` annotated a result `StepResult | None`** when `run_step` never
returns `None`, which mypy read as a possible `AttributeError` on the next line.

### Still open in P4

F-D02 (the player↔steps import cycle — `contracts/` is now the leaf package that
can hold the invoker Protocol), F-D03 (`StepContext` still carries the
connector-shaped accessors), F-E01 (blocking `requests` inside `async def`),
F-E05 (the camelCase fallback in path extraction), F-F04 (the typing dialect).

### F-D02 — the cycle is one-way now

`flow/if` and `flow/retry` run the steps nested inside them, which means a step
calling the runner — while the player imports the steps package to register
them. The edge went both ways, held open by importing `run_step` from inside the
`execute` bodies. That is legal Python, and it hides a cycle rather than removing
one.

`contracts.StepInvoker` states the shape of the runner; `StepContext` carries
one; `run_step` binds itself as it starts. A flow step now asks the context to
run a nested step and never names the player.

Verified statically, module-level imports outside `TYPE_CHECKING`:

```text
steps → player : none — the cycle is broken
player → steps : player/execution/phase.py, player/execution/step_runner.py
```

The invoker is bound in `run_step` rather than at the composition root, so every
context that reaches a step can run a nested one — including the ones tests build
directly. The two flow-step unit tests now hand their mock context the real
runner, which is honest about what they exercise: a step that contains steps
needs something that can run one.

`contracts/` is a leaf package — it imports nothing from the rest of testlab — so
anything may depend on it. That is what makes it the right home for this, and for
the service Protocols beside it.

---

## F-E01 — one HTTP client, and a bigger problem underneath

`steps/http_client.py` is now the only way a step makes an HTTP call. All eight
`requests` call sites are converted; `requests` no longer appears anywhere under
`steps/`.

The harm was concrete: the event loop those calls blocked is the same one running
the in-process callback server. A step waiting on a slow registry stopped the
SUT's callbacks from being answered — with a 600-second step timeout, the server
could be unreachable for ten minutes while the script sat waiting for a callback
that could not arrive.

### Two behaviours that had to be preserved deliberately

**Header casing.** `dict(httpx_response.headers)` lower-cases every name, because
httpx's own lookups are case-insensitive and it normalises for them. A script
gets no such courtesy: a TCK reading `response_headers.X-Next-Cursor` finds
nothing once the key is `x-next-cursor`. `requests` preserved the wire casing, so
`headers_of()` rebuilds from the raw pairs. Caught by an existing combination
test — without it this would have shipped as a silent break in any TCK that reads
a header.

**`resp.ok`.** A `requests` attribute httpx does not have. On a `MagicMock` it
read as truthy, so the OAuth2 refusal path stopped refusing. Now reads
`status_code >= 400`, which is transport-independent.

### The test doubles moved too

`tests/conftest.py::http_response` builds a response shaped like the one a step
now receives — content type for `body_of`, raw pairs for `headers_of`. It is
shared rather than repeated per file, because getting either half wrong makes a
test pass while the step misreads real responses. One local double had
`{"Content-Type": ...}` as a plain dict, whose case-sensitive `.get("content-type")`
returns `None`.

Unifying the client also **merged patch targets**: the DTR lookup tests patched
`requests.post` and `requests.get` separately, and now one mock answers both
calls in order.

### F-E07 — the SDK is synchronous (new)

Measured while doing this: `tractusx_sdk`'s adapters import `requests`, and no
service method is a coroutine. So roughly **22 SDK call sites also block the
loop** — catalog queries, negotiations, transfers, data pulls: exactly the long
ones.

Converting our eight calls fixes the code we own and is worth having, but it is
about a quarter of the problem. The rest needs `asyncio.to_thread` at the SDK
boundary. Recorded as its own finding rather than folded into F-E01, because the
review measured only our own calls and the scale of the remainder was not known
until now.

---

## P4 complete

### F-E07 — the SDK calls are off the loop

`steps/sdk_call.py` runs a blocking SDK operation on a worker thread. Eighteen
network-reaching calls go through it; `get_filter_expression` and
`_prepare_headers` stay inline because they only build a request, and a thread
hop costs more than the work.

Three helpers had to become `async` and their callers `await` them —
`fetch_data_address`, `_register_shell`, `_register_submodel` — which is the
honest consequence: a function that reaches the network in an async engine
should say so in its signature.

### F-E05 — a path names the key the document has

`_dict_get` tried the written key and then silently retried its camelCase form,
so `header.message_id` found `messageId`. A second spelling for one field,
undocumented and unbounded, and no way to say from a script why a path resolved.

Nothing real depended on it: every path in the shipped TCKs, and every other path
in the extraction tests, already writes the actual key. One test read
`submodel_descriptors` and existed to exercise the fallback itself. Where a
document genuinely carries two spellings the payload model declares the alias —
`authCode` and `@id` already do — and that is visible.

### F-F04 — one typing dialect

`Optional[...]` and `Union[...]` are gone from `src/` (62 files and 0 remaining
respectively). `UP007`, `UP045` and `UP046` came off the ratchet and are enforced.

### F-D03 — the context is about a run again

`DataspaceAccess` now owns the eight connector-shaped accessors and the SDK
controller URL builder. `StepContext` is 222 → 151 lines and carries variables,
job, config, infrastructure and the step invoker — nothing that knows what a
catalog is.

Call sites read `context.dataspace.consumer()` rather than
`context.get_consumer_service()`, which also says where the thing comes from.

`ServiceManager` gained a public `definition_of_type`, so nothing reaches into
`_definitions` from another module any more.

### F-A03 — a step that could not produce its output now fails

Fifteen sites built an `HttpResponse` with a fabricated status — usually `500`,
sometimes `200 if x else 500` — when the operation they were meant to perform
had produced nothing. A step fails on a raise or a hard assertion, so a
fabricated status is a value that flows into the next step's `${{ }}` and into
the assertions as if the SUT had sent it. A negotiation with no EDR reported
PASSED.

All fifteen raise `StepExecutionError` naming what was missing. No step invents
a status code, so a status in a result came off a wire.

### F-D06 — the code that decides authenticity is tested

`security/` generates the keys, encrypts the payload and verifies the signature
that say a `.tck` is the one its compiler built, and it had no unit tests. Fifteen
now cover the round trip, a flipped ciphertext bit, the wrong recipient, the
multi-recipient unwrap, a signing key handed where an encryption key was meant,
three signature cases, and the six sealing outcomes — edited entry, renamed
entry, removed entry, no manifest, no recorded digest, and the good one.

### F-B07 and F-I02 — one format, one command

`.stck` is deleted. It was a second archive format for the same job as an
encrypted `.tck`, and a strictly weaker one: it carried the authoring YAML
rather than the compiled package, skipped the package-digest check that
`_verify_tck_integrity` runs, and resolved `env.schemas` and `env.testdata` from
whatever sat next to the file on disk — assets outside the sealed envelope, read
by a package that presents itself as sealed.

With it go `Packager`, `Compiler.compile`, `Compiler.compile_tck`,
`Loader._load_package`, and the `--encrypt` flag, which had been a third way to
say what supplying keys already said — and said it by producing a *different
format*. `compile` now has two independent choices and no third spelling of
either: `--plain` writes loose files instead of an archive, and supplying both
`--compiler-keys` and `--player-pub` signs and encrypts. Supplying one without
the other is an error naming the one that is missing.

`testlab info` and `testlab decompile` are gone into `testlab inspect`. Three
verbs asked one question — what is in this package? — and each carried its own
copy of the decrypt-and-verify dance, with `info` and `decompile` reading the
archive directly rather than through the loader. `inspect` verifies once and
every section reads the verified bytes, so there is no longer a command that
reports a tampered package's own account of itself. `--manifest` is what `info`
printed; `--extract` is what `decompile` did, for every entry rather than one
YAML, and for plain packages too. `--json` emits one object keyed by section
whatever the flags — it used to emit a bare result with no flags and an envelope
with them, so a consumer had to know the argv to know the shape.

One thing found while wiring the smoke test: `compile` echoed the checksum the
IR builder computed, which is taken *before* the archive is sealed, so the number
printed by the compile was not the number in the package it had just written.
`_create_tck_archive` returns the sealed digest and that is what is reported.

### F-F02 remainder — no module is exempt from the type checker

The mypy ratchet is empty and its override blocks are deleted. It held fourteen
modules and 72 errors when the gate went in; F-F02's Protocols cleared 59, and
the last 24 came off one file at a time.

Two of them were live defects the exemption was hiding:

* `step_docs.render_shared_models` decided whether to print "Additional keys
  sent by the counterpart are passed through unchanged" by reading `model` — a
  variable left over from the *outer* loop, holding the last step's output
  model rather than the nested model being documented. The note was printed,
  or not, for the wrong object.
* `_sized` handed `int()` an unnarrowed `object` under a `type: ignore` that
  did not even cover the error code being raised.

The rest were narrowing, and most of them came from one place: `get_variable`
returns `object`, honestly, because a variable holds whatever a step published
— and every caller that wanted a URL or a token either narrowed it or, more
often, passed `object` into `.rstrip()` or an HTTP header. `StepContext.get_str`
narrows once, and the sites that read text now say so. The one site where
absence is meaningful to the SDK — `negotiate`'s `target` — deliberately still
reads `get_variable`, because `""` would say a target was named.

Also typed properly rather than ignored: `StepPayload.of` returns `Self`, so
`DataAddressPayload.of(...)` is a data address and not a bare payload; the
`Controller` Protocol declares `create`, which half its callers use; and
`_parse_script` returns the definition it parses instead of `object`.

### F-D05 — the file-size ratchet, tightened

Sixteen files were over 300 lines; thirteen are, and the largest is 422 rather
than 638. `cli/compile.py` 457 → 175 and `cli/run.py` 326 → 190 dropped off the
list entirely.

Three splits, each on a seam the code already had:

* `steps/connector/provision.py` (561) → a package with one module per resource
  family — `asset`, `policy`, `contract_definition` — plus `_shared` for the
  read-an-id and create-or-409 helpers. That is how the connector's management
  API is divided and how a script uses them.
* `steps/digital_twin/provider.py` (638) → `provider/shell.py` and
  `provider/submodel_descriptor.py`. A submodel descriptor is addressed through
  the shell that holds it, which is the one import between them.
* `cli/run.py` and `cli/inspect.py` → `_run_report.py` and `_inspect_report.py`,
  the same seam in both: the command decides what to do, the report module
  decides what the terminal shows.

And one deduplication, which is why the split was worth doing at all: the two
DTR step families each declared `DtrParams`, `DescriptorPayload`,
`SpecificAssetId`, `ShellLookupOutput` and two helpers — 85 lines, verbatim, in
both. They describe the Asset Administration Shell, not a side of it: the
provider registers a descriptor and the consumer reads the same one back. They
live in `steps/registry_models.py` now, beside the readers in
`registry_reading.py`.

The duplication was visible in the shipped documentation the whole time —
`docs/specification/reference/steps.md` documented `SpecificAssetId` twice,
because it existed twice. Deduplicating the code removed the doubled entry.

## Pipeline verification — 2026-08-18

Built a TCK that uses the whole chain and ran it, rather than reasoning about
it. Five defects, each of which had shipped.

### The verdict was a step tally

`TckResult.passed` counts steps with `PASSED`. `finalize_job` asked
`if result.passed:` — and a non-zero count is truthy. **Any run where at least
one step passed published `job_completed`**, while the CLI printed FAIL from
`status`. The event stream is what the IDE reads, so a failed TCK showed as a
green job; only a run where *every* step failed reported failure.

`steps_passed` / `steps_total` are named for what they are and the verdict is
`status`. Pinned in `tests/unit/player/test_run_verdict.py`, including the
four-of-five reproduction.

### The console trace threw away everything it was given

`_build_inline_message` looked for flat `status` / `duration_s` / `request` /
`response` keys. The typed events carry a nested `result` and a nested
`assertion`, so none of those keys were ever present and every line printed as
its event name and its script: `assertion.result [wiring]`. The JSONL had the
whole story the entire time.

`logging/console.py` renders the real shapes — which check ran, what it asked
and saw, which step finished, how long it took, and the request and response
when the step made one. Thirteen tests in `tests/unit/logging/`.

### The validator never walked `teardown`

`validate()` iterated `setup` and `execution`. A teardown step could name a
step type that does not exist, assert with an operand its operator never reads,
or declare a `returns:` the step does not publish, and `testlab validate`
answered OK.

**The shipped e2e TCK was in exactly that state** — `dtr_roundtrip.yaml`'s
teardown asserted with `expected:`, which the engine refuses. The e2e job's
first step is `testlab validate`, so the CI signal was red-on-arrival and the
validator was hiding one of the four errors. Fixed both.

Errors also name the phase now: a setup step 0, an execution step 0 and a
teardown step 0 all printed as `(step 0)`. And the main phase is labelled
`execution` — the word authors write in `${{ execution.<id> }}` — rather than
`main`, which appears nowhere in the syntax.

### `Steps: N` counted one phase of three

`TestScript.step_count` returned `len(definition.execution)`. `testlab run`
announced "Steps: 2" for a run that executed five, and gave the progress bar a
total it went past. `testlab inspect` had always counted all three, so the two
commands disagreed about the same package.

### A reference that reaches into a document said nothing useful

`${{ execution.call.body.kind }}` against a step that declared `body` failed
with a list of everything in scope. The rule is that a reference is a *name*
and the walk happens once, in `returns:` — `returns: { body.kind: ... }` — but
nothing said so at the point of failure.

I first "fixed" this by making the resolver descend, which was wrong: the walk
already had one spelling, and a second one is the alias this project does not
allow. Reverted. `UnresolvedReferenceError` now detects that a prefix is in
scope and names the remedy.

### E2E — combinations against the live dataspace

Two scenarios added to `tests/e2e/connector-dtr-smoke/`:

* `dsp_step_by_step.yaml` — the journey `connector_negotiation.yaml` runs as
  one `pull_data_filtered` step, driven as six wired steps instead: catalog →
  dataset → negotiation → transfer → EDR → data-plane fetch. Each step reads
  what the one before published, so this is what fails if the runtime stops
  carrying a real value across a phase boundary. The last step spends the EDR,
  which a token assembled from unresolved references cannot do.
* `negative_paths.yaml` — asks the live dataspace for things that are not
  there and asserts the answers say so. A green run means absence is reported
  as absence.

The manifest marks every test `skippable: true`, so the workflow runs **one
compiled package as several combinations** (`--var skip_tests=…`): full,
wiring-only, registry-only, plus an unknown id that must be refused. It also
runs `testlab inspect --json` and asserts the package carries every test the
manifest declared, so a test lost between manifest and archive is caught before
anything executes.

`tests/combinations/test_tck_pipeline.py` is the same journey without a
cluster: author three test files, compile, inspect, run, and run combinations —
18 tests covering the wiring on the wire (the ticket a setup step published
arrives in the execution step's header, and the state from *that* step's
response body arrives in teardown's), assertion recording, soft-failure
semantics, and selection refusal.
