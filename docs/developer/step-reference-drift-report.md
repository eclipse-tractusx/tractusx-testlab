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

# Step Reference vs. Implementation — Drift Report

> Date: 2026-08-07 | Branch: `feat/run_security_consitency`
> Scope: [`docs/specification/reference/steps.md`](../specification/reference/steps.md)
> compared against the live step registry it is generated from.
> Status: **analysis** — one incidental fix applied (D0), the rest is unimplemented.

## Summary

The page claims it "cannot drift from the implementation" because it is generated
from the steps' Pydantic models. That claim holds for **step inventory** — every
registered step is documented, with matching parameters, defaults, aliases, outputs,
and published variables. It does **not** hold for the file on disk, which is
**7 lines stale** and would fail `testlab docs --check` today.

Two of the three findings are about the guard rails around the generator rather than
the generator itself: the header tells a reader to run a command that does not exist,
and nothing in CI ever runs the check that would have caught the stale lines.

| ID | Area | Severity | Status |
| --- | --- | --- | --- |
| D0 | Broken SDK import blocked the generator entirely | blocker | **fixed** |
| D1 | 7 stale output-type lines; `--check` fails | medium | open |
| D2 | Header cites a command that does not exist | low | open |
| D3 | No CI gate runs `testlab docs --check` | medium | open |

---

## Method

Three independent enumerations of "what steps exist", cross-checked against each
other and against the committed page:

| Source | Count |
| --- | --- |
| Registry, via `testlab docs -o -` | 44 |
| `@step("…")` decorators under [`src/tractusx_testlab/steps/`](../../src/tractusx_testlab/steps/) | 42 |
| Registered programmatically in [`pull_data/__init__.py:42-43`](../../src/tractusx_testlab/steps/pull_data/__init__.py) | 2 |
| Documented in `steps.md` | 44 |

42 + 2 = 44, and the sorted name lists are identical. `connector/consumer/pull_data_filtered`
and `connector/consumer/pull_data_filtered_by_policy` are the two that carry no
decorator — they call `step(...)` as a plain function on an already-defined class, so
a decorator-only grep under-reports by exactly those two. Worth knowing before anyone
audits step coverage with `grep` again.

Byte diff of the committed page against a fresh generation isolates the drift to the
`Type:` line of seven steps. Nothing else differs.

---

## D0 — Broken SDK import blocked the generator (fixed)

An uncommitted edit to [`catalog_query.py`](../../src/tractusx_testlab/steps/connector/catalog_query.py)
imported `DspTools` from a module that does not exist in the installed SDK:

```python
from tractusx_sdk.utils import DspTools          # ModuleNotFoundError
from tractusx_sdk.dataspace.tools import DspTools  # actual location
```

`tractusx_sdk` exposes only `dataspace`, `extensions`, and `industry` at the top
level. The blast radius was wider than the docs command: `catalog_query` is imported
by `consume.py`, so **every** `connector/consumer/*` step failed to import, and
`testlab docs` exited 1 before emitting a single line.

Fixed at [`catalog_query.py:34`](../../src/tractusx_testlab/steps/connector/catalog_query.py#L34).
The only consumer is `DspTools.filter_assets_and_policies` in `_select_offer`
([line 221](../../src/tractusx_testlab/steps/connector/catalog_query.py#L221)).

---

## D1 — Seven stale output-type lines

`testlab docs --check` exits 1. The entire delta is the declared output type of the
seven steps whose `output_model` is `NoOutput`:

| Step | Line in `steps.md` | On disk | Generator emits |
| --- | --- | --- | --- |
| `connector/provider/delete_asset` | 561 | `Type: any` | `Type: NoneType` |
| `connector/provider/delete_contract_definition` | 583 | `Type: any` | `Type: NoneType` |
| `connector/provider/delete_policy` | 603 | `Type: any` | `Type: NoneType` |
| `dtr/delete_shell_descriptor` | 677 | `Type: any` | `Type: NoneType` |
| `flow/delay` | 725 | `Type: any` | `Type: NoneType` |
| `mock/discovery` | 828 | `Type: any` | `Type: NoneType` |
| `mock/dtr` | 851 | `Type: any` | `Type: NoneType` |

### Cause

`NoOutput` is declared as `StepValue[None]` in
[`steps/_contracts.py:55`](../../src/tractusx_testlab/steps/_contracts.py#L55), so the
generic argument the renderer receives is `type(None)` — the *class* — not the literal
`None`. The guard in [`step_docs.py:83`](../../src/tractusx_testlab/scripting/step_docs.py#L83)
only catches the literal:

```python
if annotation is Any or annotation is None:
    return "any"
```

`type(None)` is neither, so it falls through to the `isinstance(annotation, type)`
branch at [line 101](../../src/tractusx_testlab/scripting/step_docs.py#L101) and is
rendered by `_PRIMITIVES.get(annotation, annotation.__name__)`. `NoneType` is absent
from `_PRIMITIVES`, so the raw Python class name leaks into the page.

Note the module already binds `_NONE_TYPE = type(None)`
([line 58](../../src/tractusx_testlab/scripting/step_docs.py#L58)) and uses it to strip
`None` out of `Optional[...]` unions — the sentinel exists, it is just not consulted
on the bare-`NoneType` path.

### Which side is right?

Neither, and that is the point.

- **`any`** (on disk) actively misleads: it reads as "any value at all", which is
  what an *undeclared* output looks like. The `NoOutput` docstring names this exact
  hazard — *"'no output' and 'output not declared yet' look the same to a script
  author unless one of them says so"* — and `any` reintroduces it.
- **`NoneType`** (generated) is correct but is Python jargon in a page written for
  script authors, who write YAML and never see a Python type.

The description line directly above already carries the meaning — *"This step
produces no value — it acts, and there is nothing to read back."* — so the `Type:`
line is redundant in this case, not merely badly worded.

### Options

| Option | Change | Effect |
| --- | --- | --- |
| **A** (recommended) | Omit the `Type:` line entirely when the output is `NoOutput` | Description alone carries it; no jargon, no ambiguity |
| B | Map `NoneType` to `none` in `type_name` | One-line fix, keeps the section shape uniform across all steps |
| C | Extend the line-83 guard to `annotation is _NONE_TYPE` | Restores `any` — **not recommended**, it re-creates the ambiguity `NoOutput` exists to remove |

Either A or B must be followed by regenerating the page, since `--check` compares
bytes.

---

## D2 — Header cites a command that does not exist

The page's second line reads:

```markdown
<!-- Generated by `testlab docs steps`. Do not edit by hand. -->
```

There is no `steps` subcommand. `testlab docs` takes options only (`--output/-o`,
`--step/-s`, `--json`, `--check`), and the extra argument is a hard error:

```console
$ testlab docs steps
Error: Got unexpected extra argument (steps)
```

The `-s/--step` option is presumably what the string was reaching for, but it is
repeatable and *filters* the output to named steps — `testlab docs` with no arguments
is what regenerates the whole page. The string is emitted from
[`step_docs.py:294`](../../src/tractusx_testlab/scripting/step_docs.py#L294) and should
read `testlab docs`.

Minor on its own; it compounds with D3, because the header is currently the only
instruction a contributor has for how to refresh the page, and following it fails.

---

## D3 — No CI gate runs the check

`--check` works correctly — it prints
`Error: docs/specification/reference/steps.md is out of date; run 'testlab docs'.`
and exits 1. Nothing under [`.github/`](../../.github/) invokes it, and there is no
`Makefile` target for it either.

So the generated page is only as fresh as the last time someone remembered to run the
command by hand — which is how D1 arose. Wiring `testlab docs --check` into the same
job that runs lint or tests turns this class of drift into a build failure at the
commit that causes it, instead of a discrepancy someone notices months later.

This also closes the loop on the page's own opening claim ("it cannot drift from the
implementation"): today that is an aspiration, and the gate is what would make it
true.

---

## Recommended order

1. Pick **D1 option A or B**, apply it in `step_docs.py`.
2. Fix the header string (**D2**) in the same change — it lives in the same module.
3. Regenerate: `poetry run testlab docs`.
4. Add `poetry run testlab docs --check` to CI (**D3**), which locks in 1–3.

Steps 1–3 are a single small commit. Step 4 is what prevents the report from being
needed again.
