# TCK Syntax Reference — `v1-alpha`

**Companion to [ADR-0001](./ADR-0001-tck-declarative-syntax.md).**
Audience: TCK authors (Expert Groups, TCK Developers) and Engine implementers.

## Notation used in this document

| Marker | Meaning |
|---|---|
| **[SPEC]** | Specified in the Test Suite Development presentation (2026-07-26). Normative. |
| **[OBS]** | Observed in the worked `certificate-management-tck` example in the deck, but not written out in the field-by-field slides. Treated as normative; flagged so it can be confirmed. |
| **[PROP]** | Proposed here to close a gap. **Not yet ratified** — see ADR-0001 §2 D10 and §6. |

Field tables use: `R` = required, `O` = optional.

## Sections

| Section | Covers |
|---|---|
| [1. Package Layout](package/layout.md) · [2. Common Header](package/common-header.md) | The TCK directory, file naming and the header every file starts with |
| [3. `index.yaml` — the TCK Manifest](manifest/index.md) | Manifest header and `metadata`, [`dataspace` and `infrastructure`](manifest/dataspace-infrastructure.md), [`env`](manifest/env.md) and [`tests`](manifest/tests.md) |
| [4. Test File Syntax](tests/test-files.md) | Test file header, metadata and phases |
| [5. Step / Building Block Syntax](steps/index.md) | Step anatomy, [expressions](steps/expressions.md), [capability naming](steps/capabilities.md) and [validation functions](steps/validations.md) |
| [6. Mapping CACs to Syntax](authoring/cac-mapping.md) · [7. Worked Example](authoring/worked-example.md) · [10. Checklist](authoring/checklist.md) | Turning conformity assessment criteria into a TCK |
| [8. Execution Logs](execution-logs.md) | The CloudEvents / JSONL log a run produces |
| [9. Proposed Extensions](extensions.md) | Unratified additions: `cac:`, conditionals, negative tests, digests |

Every step a test can name in `uses:`, with its inputs and outputs, is listed in the [Step Reference](../api-reference/steps.md).

## Source

*Test Suite Development — Achieving a "sustainable" certification environment*, Catena-X e.V., 2026-07-26.
Slides 8–12 (CAC structure and mapping), 14–15 (package structure), 17–21 (`index.yaml`), 23–32 (test, phase,
step and capability syntax), 36–39 (execution logs and SSE).

The slides are available as [PDF](syntax-presentation.pdf).
