# 6. Mapping CACs to Syntax

This is the core translation TCK authors perform. **[SPEC]** for the CAC model; **[PROP]** for the `cac:` and
conditional constructs used below.

## 6.1 The CAC sentence

```
WHEN  <test step / action>        ← may come from an Enablement Service (CX-0018, CX-0002),
                                    Industry Core, or be a generic action like "http request"
WITH  <test data>
IF    <condition>                 ← supports conditionals for negative tests
MUST  <assertion>                 ← repeatable; combinable with AND / OR
```

## 6.2 Translation table

| CAC element | Syntax construct |
|---|---|
| `WHEN` | The step: `uses:` + `name:` |
| `WITH` | `with:` inputs, sourced from `${{ env.testdata.* }}` and `${{ env.* }}` |
| `IF` | `if:` on a step or validation **[PROP [§9.2](../extensions.md#92-conditionals-if-validateany_of-validateall_of-p2)]** |
| `MUST` | One `validate:` entry |
| `MUST … AND MUST …` | Multiple `validate:` entries (implicit AND), or `validate/all_of` when nested under an `IF` |
| `MUST … OR MUST …` | `validate/any_of` with a nested `validations:` list **[PROP [§9.2](../extensions.md#92-conditionals-if-validateany_of-validateall_of-p2)]** |
| CAC identity | `cac:` on the step or validation **[PROP [§9.1](../extensions.md#91-cac-traceability-cac-p1)]** |
| JSON Schema as MUST | `validate/schema` |

## 6.3 Worked example

CAC as written by the Expert Group:

> **CAC CCM-014** — *WHEN* the consumer issues an HTTP request to `/certificatemanagement/request` via the
> dataplane *WITH* a valid certificate request body, the response *MUST* have status `200` *AND* the body
> *MUST* conform to the Business Partner Certificate schema v3.0.1. *IF* the provider reports `failed`, the
> status *MUST* be `503` *OR* the body *MUST* contain an error code of `SERVICE_UNAVAILABLE`.

As YAML:

```yaml
- id: send_status_notification
  uses: connector/dataplane/http_request
  name: Call CX-0135 request api on the provider via dataplane
  cac: ["CX-0135:v3.1.0:CAC-014"]              # [PROP]
  with:
    method: POST
    dataplane_url: "${{ execution.pull_notification_endpoint.dataplane_url }}"
    path: "/companycertificate/request"
    edr_token: "${{ execution.pull_notification_endpoint.edr_token }}"
    headers:
      Content-Type: "application/json"
    body: "${{ env.testdata.send_feedback_body }}"
  returns:
    status_code:
      type: integer
      class: StatusCode
    response_body:
      type: object
      class: ResponseBody
  validate:
    # MUST … AND MUST … → two sibling validations
    - uses: validate/field
      with: { input: status_code, operator: equals, value: 200 }
    - uses: validate/schema
      with:
        input: response_body
        schema: "${{ env.schemas.certificate_schema }}"

    # IF … MUST … OR MUST …  → guarded any_of                          [PROP]
    - uses: validate/any_of
      if: "${{ execution.send_status_notification.response_body.status == 'failed' }}"
      cac: ["CX-0135:v3.1.0:CAC-015"]
      with:
        validations:
          - uses: validate/field
            with: { input: status_code, operator: equals, value: 503 }
          - uses: validate/field
            with:
              input: response_body
              path: "error.code"
              operator: equals
              value: "SERVICE_UNAVAILABLE"
```

## 6.4 Two views, one CAC set **[SPEC]**

The same CACs must be reachable from both directions:

- **TCK-oriented view:** `STANDARD → TCK → TEST CASE → CAC → (WHEN/WITH/IF/MUST)`
- **Standard-oriented view:** `STANDARD → USE CASE + SEQUENCE DIAGRAM → CAC → (WHEN/WITH/IF/MUST)`

A TCK is *compliant* when every CAC derived from the standard's use cases and sequence diagrams is covered by
at least one test case, and every test case's assertions trace back to a CAC. **[PROP]** With `cac:` in place,
the compiler can produce a coverage matrix (CACs declared by the standard vs. CACs referenced by the TCK) and
warn on gaps.
