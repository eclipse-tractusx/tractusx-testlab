# 6. Mapping CACs to Syntax

This is the core translation TCK authors perform. **[SPEC]** for the CAC model; **[PROP]** for the `cac:` key
and for expressing `IF`/`OR` with `flow/if`. Both are implemented in the engine and awaiting ratification.

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
| `IF` | A `flow/if` step: its `conditions:` read what an earlier step returned, `then:` holds the steps for when the condition holds, `else:` the ones for when it does not **[PROP [§9.2](../extensions.md#92-conditionals-flowif-p2)]** |
| `MUST` | One `validate:` entry |
| `MUST … AND MUST …` | Several `validate:` entries on one step. They are always ANDed |
| `MUST … OR MUST …` | A `flow/if` with `match: any` whose conditions are the alternatives, and a `validate:` entry requiring `condition_result == true` **[PROP [§9.2](../extensions.md#92-conditionals-flowif-p2)]** |
| CAC identity | `cac:` on the step or on one validation **[PROP [§9.1](../extensions.md#91-cac-traceability-cac-p1)]** |
| JSON Schema as MUST | `validate/schema` |

A step's own `if:` is not the way to write a CAC `IF`. It only reads the run's state (`success()`,
`failure()`, `always()`, `steps.<id>.outcome`, `vars.<name>`), never a value a step returned, and it skips
the step rather than choosing between two sets of checks. Validations take no `if:`, and there is no
`validate/any_of` or `validate/all_of`.

## 6.3 Worked example

CAC as written by the Expert Group:

> **CAC CCM-014** — *WHEN* the consumer issues an HTTP request to `/certificatemanagement/request` via the
> dataplane *WITH* a valid certificate request body, the response *MUST* have status `200` *AND* the body
> *MUST* conform to the Business Partner Certificate schema v3.0.1. *IF* the provider reports `failed`, the
> status *MUST* be `503` *OR* the body *MUST* contain an error code of `SERVICE_UNAVAILABLE`.

As YAML. The manifest's `metadata.standards` must list `CX-0135` `v3.1.0`, or the compiler rejects the `cac:`
entries:

```yaml
# WHEN … WITH …
- id: send_status_notification
  uses: connector/dataplane/http_request
  name: Call CX-0135 request api on the provider via dataplane
  cac: ["CX-0135:v3.1.0:CAC-014"]
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
    value:                  # the parsed JSON response; `body` is the raw text
      type: object
      class: ResponseBody
  validate:
    # Only what holds on both paths. Checking for 200 here would fail the
    # run whenever the provider reports `failed`.
    - uses: validate/assert
      with: { input: status_code, operator: not_null }

# IF the provider reports `failed` … otherwise …
- id: check_request_outcome
  uses: flow/if
  name: Branch on whether the provider reported a failure
  cac: ["CX-0135:v3.1.0:CAC-014", "CX-0135:v3.1.0:CAC-015"]
  with:
    conditions:
      - input: "${{ execution.send_status_notification.value }}"
        path: status
        operator: equals
        value: failed
    then:
      # … the status MUST be 503 OR the body MUST carry SERVICE_UNAVAILABLE
      - id: failure_is_signalled
        uses: flow/if
        name: The failure is signalled by status code or error code
        with:
          match: any
          conditions:
            - input: "${{ execution.send_status_notification.status_code }}"
              operator: equals
              value: 503
            - input: "${{ execution.send_status_notification.value }}"
              path: error.code
              operator: equals
              value: SERVICE_UNAVAILABLE
          then:
            - id: failure_signalled_note
              uses: util/log
              name: Record that the failure was signalled
              with: { message: "Provider signalled the failure as CX-0135 requires" }
        returns:
          condition_result:
            type: boolean
        validate:
          - uses: validate/assert
            name: status is 503 OR error.code is SERVICE_UNAVAILABLE
            with: { input: condition_result, operator: equals, value: true }
    else:
      # … otherwise the status MUST be 200 AND the body MUST conform to the schema
      - id: request_is_accepted
        uses: util/log
        name: The accepted request answers 200 with a conforming certificate
        with:
          message: "Accepted certificate request"
          value:
            status_code: "${{ execution.send_status_notification.status_code }}"
            body: "${{ execution.send_status_notification.value }}"
        returns:
          value:
            type: object
        validate:
          - uses: validate/assert
            with: { input: value.status_code, operator: equals, value: 200 }
          - uses: validate/schema
            with:
              input: value.body
              schema: "${{ env.schemas.certificate_schema }}"
```

A failing check inside a branch fails the `flow/if` step that holds it. That makes `flow/if` the step whose
verdict shows up in the log, so the `cac:` belongs on it. `cac:` on a step nested inside a branch is accepted,
and the compiler checks its standard, but the terminal event is published for the outer `flow/if` step only.

## 6.4 Two views, one CAC set **[SPEC]**

The same CACs must be reachable from both directions:

- **TCK-oriented view:** `STANDARD → TCK → TEST CASE → CAC → (WHEN/WITH/IF/MUST)`
- **Standard-oriented view:** `STANDARD → USE CASE + SEQUENCE DIAGRAM → CAC → (WHEN/WITH/IF/MUST)`

A TCK is *compliant* when every CAC derived from the standard's use cases and sequence diagrams is covered by
at least one test case, and every test case's assertions trace back to a CAC. With `cac:` in place, every
terminal step event names the CACs its verdict covers (`data.cac`, and `cac` on each validation). **[PROP]**
The compiler does not yet build a coverage matrix (CACs declared by the standard vs. CACs referenced by the
TCK) or warn on gaps.
