# 5.4 Validation Functions

**[OBS]** Observed in the worked example:

| `uses` | `with` | Checks |
|---|---|---|
| `validate/assert` | `input`, `operator` | Simple assertion on a returned value. Example: `{ input: edr_token, operator: not_null }`. |
| `validate/field` | `input`, `path` (O), `operator`, `value` | Field-level check, optionally at a JSON path within the returned object. |
| `validate/schema` | `input`, `schema` | Validates a returned object against a declared JSON Schema. |

```yaml
validate:
  - uses: validate/assert
    name: "an EDR token is issued for the offer"      # optional, report-only
    with: { input: edr_token, operator: not_null }

  - uses: validate/field
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

  - uses: validate/field
    with:
      input: request_body
      path: "content.certificateStatus"
      operator: one_of
      value: ["RECEIVED", "ACCEPTED", "REJECTED"]
```

**Operator vocabulary [PROP]** — ratifying this closes ADR gap P4:

| Operator | Applies to | Meaning |
|---|---|---|
| `equals` / `not_equals` | any | Exact comparison |
| `not_null` / `is_null` | any | Presence |
| `contains` / `not_contains` | string, array | Containment |
| `one_of` / `none_of` | any | Membership in `value` (a list) |
| `matches_regex` | string | Regular expression match |
| `gt` / `gte` / `lt` / `lte` | number | Numeric comparison |
| `has_key` / `not_has_key` | object | Key presence at `path` |
| `length_equals` / `length_gt` / `length_lt` | string, array | Size |

The operators the engine implements, with the operands each one reads, are generated into the [Step Reference](../../api-reference/steps/validations.md).
