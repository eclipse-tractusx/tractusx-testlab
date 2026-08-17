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
<!-- This document was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5). -->
<!-- It was reviewed and validated by a human committer. -->

# ADR-0025: Assertions Read Declared Returns

## Status

Accepted — partially implemented; see *Implementation status*

## Date

2026-08-10

## Context

A step declares what it publishes in `returns:` and what it checks in `validate:`.
The intended model is a straight line: the step executes, its return values are
stored, and each assertion picks one of those values and applies an action to it.

The implementation does not follow that line.

**`validate:` never sees the returns.** `run_step` evaluates the assertions
against the raw `StepOutput`
([`step_runner.py:69`](../../../../src/tractusx_testlab/player/execution/step_runner.py#L69)),
and `store_step_outputs` extracts the declared returns into context variables
afterwards, in a separate pass. Both call the same `extract_path`, so the common
case coincidentally agrees — but the assertion is reading the output object, not
the surface the step declared. A name that is not a declared return is extracted
just the same, and a name that resolves to nothing yields `None` with no
complaint.

**There are four spellings for "the value to check".** `output:` and `path:` are
read as synonyms (`params.get("output") or params.get("path")`), `input:` is a
third, handled by a branch that exists solely for `validate/assert` and
`validate/field`, and `source: VARIABLE` plus `value:` is a fourth route that
reaches into the context instead.

**There are three schemes for "the action".** `assert/not_null` (block form),
`NOT_NULL` (a flat spelling the map labels "legacy … for backward
compatibility"), and `validate/assert` with `operator: not_null` (parameter
form). A `uses:` matching none of them is not rejected: `_assertion_type` falls
back to `AssertionType(a.uses)` and then to `AssertionType.EXACT`, so a typo
becomes an equality comparison against `None` and frequently passes.

**The operators are implemented twice.** `_apply_inline_operator` in
[`assertions/`](../../../../src/tractusx_testlab/steps/assertions/) serves
the inline path; `_check` in
[`utility/validate.py`](../../../../src/tractusx_testlab/steps/utility/validate.py)
serves the registered `validate/*` steps. Two tables that must agree, with
nothing keeping them in agreement.

**Assertion parameters are not interpolated.** `resolve_params` runs over a
step's `with:` but not over an assertion's, which is why the `@name` prefix and
`source: VARIABLE` exist at all — they are a private, weaker substitute for
`${{ }}` inside assertion blocks.

Every script in the repository writes the same two forms —
`validate/assert` with `input:` and `operator:` (51 occurrences),
`validate/field` with the addition of `path:` (45) — and `validate/schema`
twice. Nothing uses the `assert/*` block names or the flat `NOT_NULL` spellings.
The generality above is unused; what it costs is that no spelling is wrong, so
no mistake is caught.

## Decision

`returns:` is the step's public surface, and `validate:` sees that surface and
nothing else. Concretely:

### 1. Returns are resolved before assertions run

`store_step_outputs` moves ahead of assertion evaluation. Assertions are given
the resolved return map, not the raw `StepOutput`. What a script asserts on is
therefore exactly what a later step reads from the context — one extraction, one
result, no chance of the two disagreeing.

### 2. One key names the input: `input`

`input` holds the name of a declared return — a plain name, never a path:

```yaml
returns:
  edr_token: { type: string }
  response_body: { type: object }
validate:
  - uses: validate/assert
    with: { input: edr_token, operator: not_null }
  - uses: validate/field
    with: { input: response_body, path: header.messageId, operator: equals, value: "${{ env.message_id.value }}" }
```

`output:` and `source:` are removed as spellings of the input; `path:` keeps its
meaning and gains a single owner (decision 3).

`input` wins for two reasons. It is what every assertion in the repository
already writes, so the harmonisation costs nothing at the call sites that are
already right. And `source` is not available: it already means *where a value
comes from* in three places — `source: INLINE | VARIABLE` in the expected-value
resolution being deleted here, `ValueSource` (`INLINE` / `FILE` / `VARIABLE`) in
the frontend's [`schema.ts`](../../../../ide/src/models/schema.ts), and
`source: value | input | generated` on a variable declaration
([ADR-0018](ADR-0018-unified-variables-model.md)). Using it for "the value being
checked" would make it the third meaning of one word, in a record whose purpose
is to remove exactly that.

The consequence runs the other way too: `util/json_path_extract` and
`util/validate_path` currently spell this key `source` — the deleted
`validate/semantic_schema` documented it as "name of the context variable
holding the JSON data", the right idea under the wrong name. They move to
`input`, and the
[parity analysis](../../ide-engine-contract-parity.md) records the same
direction.

**An `input` that is not a declared return is a compile error.** This is the
change that gives the rest its value — it converts the whole class of silent
`None` assertions into a message naming the step, the assertion and the
undeclared name. Asserting on something means declaring it, which is also what
lets the IDE offer the exact set of input names a validate block may use.

### 3. The `validate/*` family, one member per kind of check

The family stays, and every member is a registered step with one params model.
What separates them is the *kind* of check, not a spelling:

| Step | `with:` | Checks |
| --- | --- | --- |
| `validate/assert` | `input`, `operator`, `value` | the return value itself |
| `validate/field` | `input`, `path`, `operator`, `value` | a field inside that value |
| `validate/schema` | `input`, `schema` | the value against a JSON Schema document |

All three take `severity: hard | soft` — `hard` by default, lower-case like the
rest of the syntax.

| Key | Meaning |
| --- | --- |
| `input` | Name of a declared return. A name, never a path. |
| `path` | Dot-separated route into that value. `validate/field` only. |
| `operator` | One of the comparisons below. Required — there is no default. |
| `value` | The operand, for the comparisons that take one. |

`input` carrying a plain name and `path` carrying the route is what earns
`validate/field` its place: there is exactly one way to reach a nested field, and
the block that does it says so in its name. A dotted `input` would be a second
way to write what `path` already writes — the kind of duplicate spelling this
whole record exists to remove — and it would cost the IDE the ability to render
`input` as a dropdown of the preceding step's returns.

| `operator` | Uses `value` | Checks |
| --- | --- | --- |
| `not_null` | — | value is not `None` |
| `null` | — | value is `None` |
| `not_empty` | — | value is truthy |
| `equals` | yes | equality |
| `not_equals` | yes | inequality |
| `contains` | yes | `value` occurs in the input |
| `not_contains` | yes | `value` does not occur |
| `matches_regex` | yes | `value` is the pattern, searched in the input |
| `greater_than` | yes | ordered comparison |
| `less_than` | yes | ordered comparison |
| `greater_or_equal` | yes | ordered comparison |
| `less_or_equal` | yes | ordered comparison |
| `between` | yes | `value` is `[min, max]`, inclusive |

`operator` is a closed enum. An operator outside it is a compile error, like an
undeclared `input` — the two silent fallbacks in `_assertion_type` are what
this replaces.

The two schema steps are members of the family, not comparisons, because their
second operand is a document rather than a value the input is compared against:

```yaml
  - uses: validate/schema
    with: { input: response_body, schema: "${{ env.schemas.certificate_request }}" }
```

The operator being a parameter of `validate/assert` rather than a block of its
own (`assert/equals`, `assert/not_null`, …) is a deliberate trade. The
per-operator form would give each block exactly the fields its action needs,
which is the shape rule [the parity analysis](../../ide-engine-contract-parity.md)
argues for elsewhere. Against that: `validate/assert` is what all 98 assertion
blocks in the repository already write, the operator list is a closed enum the
IDE can render as a dropdown, and `value` is the only conditional field — shown
for the ten operators that take an operand, hidden for the three that do not.
One conditional field driven by a closed enum is a bounded cost; fourteen
near-identical toolbox entries is a permanent one.

### 4. `${{ }}` is the only interpolation

Assertion `with:` blocks pass through `resolve_params`, exactly as step `with:`
blocks do. The `@name` prefix, `source: INLINE | VARIABLE` and the `expected:`
key are removed — they are a second, weaker template mechanism for something
`${{ }}` already does. `source` therefore disappears from assertion blocks
entirely rather than changing meaning.

### 5. One operator table

`_apply_inline_operator` and `_check` collapse into a single module that the
assertion engine calls. There is one implementation of `equals`.

### 6. An assertion is a step, wherever it is written

The `validate/*` family stays in the step registry. A validation is a step like
any other: it has a params model, it is documented by `testlab docs`, it appears
in the IDE toolbox, and it can stand on its own in `execution:` when a script
needs to check something no immediately preceding step produced.

Writing one inside a step's `validate:` list runs *the same step*, with the
parent's returns in scope. Decision 1 is what makes this true rather than
merely tidy: once the returns are stored before the assertions run, the parent's
return names are ordinary context variables by then, so `input` resolves
identically in both positions. There is no inline dialect to keep in step with
the registered one.

What this deletes is the *parallel* implementation, not the steps.
`AssertionEngine._evaluate_inline_validate_assert` and the branch that routes
`validate/assert` and `validate/field` around the normal flow go away; the
engine keeps the operator table from decision 5, the severity handling and the
`AssertionResult` recording, and calls the registered steps for the checks
themselves.

The `assert/*` family and the flat `NOT_NULL` spellings are deleted outright.
They are a third naming scheme for what `validate/*` already does, and no script
has ever written one.

`validate/semantic_schema` is deleted with them. Schema validation is one kind
of check and `validate/schema` is the step that does it; the semantic variant
checks only that the payload carries a semantic model's required *top-level
keys*, which is a weaker check written in a second vocabulary — `schema_ref` and
`required_keys` instead of `schema`. Pointing `validate/schema` at the JSON
Schema derived from the same SAMM model does the job properly and with the
family's own keys. No script uses it. What goes with it: the module
[`industry/semantic.py`](../../../../src/tractusx_testlab/steps/industry/semantic.py),
the seven unit tests in `tests/test_ccm_steps.py` and
`tests/test_ccm_integration_steps.py`, its entry in the generated
`docs/specification/reference/steps.md`, and the row naming it in
`docs/tutorials/ccm-conformity-testing.md`.

### 7. The family harmonised, end to end

Four loose ends that are part of the same harmonisation and would otherwise
survive it:

- **`util/json_path_extract` and `util/validate_path` follow the family.** Their
  `source:` becomes `input:` — they read a value the same way, so they spell it
  the same way. This is the one rename that reaches outside the `validate/*`
  namespace.
- **`severity` becomes a real field.** It is read today from
  `params.get("severity")` on the inline path, but no `validate/*` params model
  declares it, so as a step it is silently swallowed by `extra="allow"`. All
  three models declare it.
- **`schema` loses its alias.** `validate/schema` accepts `schema` and
  `json_schema` today ([parity analysis](../../ide-engine-contract-parity.md#aliases-already-in-the-engine));
  `schema` is the survivor, and with `schema_ref` gone from the registry it is
  the only key in the syntax that carries a schema.
- **The frontend's operator list is rewritten to match.**
  [`AssertionOperator`](../../../../ide/src/models/schema.ts) is upper-case
  (`EQUALS`, `NOT_NULL`) where scripts write lower-case, spells the regex check
  `REGEX`, has no `null`, and carries four entries — `SCHEMA`,
  `SCHEMA_VALIDATION`, `ASSERT_FIELD`, `JSON_PATH_EXTRACT` — that are not
  operators at all under this record: two are `validate/schema`, one is
  `validate/field`, and one is a `util/` step. It becomes the thirteen
  lower-case operators from decision 3, and nothing else.
  `InlineValidation { uses, with }` needs no change — it never constrained the
  keys.

Applied to [`request_certificate.yaml`](../../../examples/certificate-management-v2/raw/tests/request_certificate.yaml),
the whole `validate:` surface of a script reads the same way in every block:

```yaml
    returns:
      status_code: { type: integer }
      response_body: { type: object, class: ResponseBody }
    validate:
      - uses: validate/assert
        with: { input: status_code, operator: equals, value: 200 }
      - uses: validate/field
        with:
          input: response_body
          path: "header.messageId"
          operator: matches_regex
          value: "^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
      - uses: validate/schema
        with:
          input: response_body
          schema: "${{ env.schemas.certificate_schema }}"
```

`input` first, always naming a declared return; then the keys that block adds.
The `status_code` check moves from `validate/field` to `validate/assert` — it
carries no `path`, so it was never a field assertion. That swap is the visible
half of decision 3: the two steps stop being interchangeable.

### Migration

| Today | Becomes |
| --- | --- |
| `with: { source: x, … }` on `util/json_path_extract`, `util/validate_path` | `with: { input: x, … }` |
| `uses: validate/semantic_schema` | `uses: validate/schema` against the model's JSON Schema |
| `with: { output: x, … }` | `with: { input: x, … }` |
| `uses: validate/field` with no `path:` | `uses: validate/assert` |
| `with: { input: x }` with no `operator` | `with: { input: x, operator: not_null }` — the default is gone |
| `with: { value: "@var" }` | `with: { value: "${{ var }}" }` |
| `with: { min: a, max: b }` on `between` | `with: { value: [a, b] }` |
| `uses: NOT_NULL` and the other flat spellings | `uses: validate/assert`, `with: { operator: not_null, … }` |
| `uses: assert/exact`, `assert/assert_field`, `assert/schema_validation` | `operator: equals`, `uses: validate/field`, `uses: validate/schema` |
| `uses: assert/status_code` | `operator: equals` on a declared `status_code` return |
| `uses: assert/json_path_extract` | a `util/json_path_extract` step, then a plain assertion on its return |

Almost nothing in an existing assertion moves. `input:` stays `input:`, no
`uses:` value disappears, and `validate/field` keeps its `path:`. The only
`uses:` that change are the `validate/field` blocks written without a path —
two of the forty-five — and the only
`with:` key that changes is `source:` on the two `util/` steps that spell it
that way. The remaining rows have no occurrences in any script; the last two are
the only entries that change a script's shape rather than its spelling.

What actually tightens is not the spelling but the rules behind it: `input` must
name a declared return, `operator` must be present and in the enum, and the
assertion reads the stored returns rather than the raw output.

Any step that asserts on a value it does not declare gains the `returns:` entry
for it in the same commit.

## Consequences

### Positive

- A typo in an assertion fails at compile time with the name in the message,
  instead of passing an equality check against `None`.
- What a script asserts on and what a later step consumes are the same resolved
  value, produced once.
- `returns:` becomes a real interface: the IDE can populate a validate block's
  input list from the preceding step instead of asking the author to type a
  name that nothing checks.
- One operator implementation, so `equals` cannot mean two things — and one
  implementation of each check, whether it is written inline or as a step.
- The assertion catalog is describable in two tables — the `_USES_TO_TYPE` map,
  its legacy half and both silent fallbacks are deleted.
- The blocks a script already writes stay the blocks a script writes. The syntax
  gets stricter without getting less familiar, and every `uses:` in the
  repository survives the change.
- A validation is documented, listed and offered like any other step, because it
  is one.

### Negative

- Every assertion in the repository is touched: 98 blocks across the examples,
  plus the TCK and the fixtures. Close to a search-and-replace, but not zero.
- Asserting on a value now requires declaring it in `returns:`. That is one more
  line in the cases where a script wants a single ad-hoc check on, say,
  `status_code`.
- `value` is a conditional field: meaningful for ten operators, meaningless for
  three. The IDE has to drive its visibility from the operator dropdown, and a
  hand-written script can still set it where it is ignored. This is the price of
  an operator parameter instead of fourteen blocks, and it is accepted
  knowingly.
- Reaching a nested field costs two keys (`input` plus `path`) where a dotted
  `input` would have cost one. In exchange `input` stays a name the IDE can
  offer from a list and the compiler can check.

### Neutral

- Nothing is aliased and nothing is kept for compatibility, per the rule the
  [parity analysis](../../ide-engine-contract-parity.md) sets out. At
  `0.0.6-alpha` there is no published contract to hold to.
- `severity` keeps both its levels and its default (`hard`); only its casing
  changes.

## Implementation status

Landed 2026-08-13, alongside the IDE-side decisions recorded in
`ide-backend-drift-decisions.md`. What this record specified and what shipped
differ in three places, all deliberate.

### What landed

- **Decision 3 — the `validate/*` family.** `validate/assert`, `validate/field`
  and `validate/schema` are the whole assertion vocabulary. `validate/field`
  now descends `path` inside `input` instead of ignoring it, and
  `validate/schema` is recognised inline instead of falling through to an exact
  comparison against `None`.
- **Decision 5 — one operator table.**
  [`steps/assertions/operators.py`](../../../../src/tractusx_testlab/steps/assertions/operators.py)
  is the single implementation. `validate/*` assertions, the registered
  `validate/*` steps and `flow/if` conditions all resolve through it; the
  duplicate table in `steps/utility/validate.py` is gone.
- **The `assert/*` family and the flat `NOT_NULL` spellings are deleted**, along
  with the `AssertionType` enum and the `_ASSERTION_CHECKS` dispatch that
  existed only to serve them.
- **Both silent fallbacks are gone.** An unresolvable `uses:` or an operator
  outside the vocabulary is a compile error naming the vocabulary, and at run
  time a failed assertion carrying the same message — never a quiet `EXACT`
  comparison that passes.
- **`returns:` names are checked against the step's declared outputs**
  (`ScriptValidator._validate_returns`). This is decision 2's rule applied to
  `returns:` as well as to `input:`; it is what makes an output a step never
  publishes a compile error rather than an empty variable several steps later.

### Where the implementation diverges from this record

1. **The operator names are the ratified §5.4 set, not the list in decision 3.**
   `is_null` rather than `null`, and `gt`/`gte`/`lt`/`lte` rather than
   `greater_than`/`less_than`/`greater_or_equal`/`less_or_equal`. The IDE had
   already ratified those spellings and its blocks emit them; matching the
   engine to the authoring tool was the cheaper correction. The set is also
   wider than the thirteen listed here — it adds `one_of`, `none_of`,
   `has_key`, `not_has_key`, `length_equals`, `length_gt` and `length_lt`,
   which the engine already implemented and the IDE already offered.

2. **`validate/assert/<operator>` is accepted as well as
   `validate/assert` + `operator:`.** Decision 3 argues against per-operator
   blocks and that argument still holds for the *toolbox* — the IDE emits the
   parameter form and only the parameter form. The suffix form exists so that
   the deleted `assert/<operator>` names have a home in the surviving namespace
   for hand-written scripts; both spellings resolve through the same table to
   the same check, so there is one implementation, not two.

3. **`@name` and `source: VARIABLE` still resolve.** Decision 4 removes them in
   favour of `${{ }}`, which needs assertion `with:` blocks to pass through
   `resolve_params` — a change to the compiler's expression pass rather than to
   the assertion engine. It is not done.

### Not yet implemented

Decision 1 (returns resolved before assertions run), decision 4 (`${{ }}` as the
only interpolation), decision 6 (inline assertions routed through the registered
steps) and decision 7's loose ends — the `source:` → `input:` rename on
`util/json_path_extract` and `util/validate_path`, `severity` as a declared
field, and lower-case severity values.
