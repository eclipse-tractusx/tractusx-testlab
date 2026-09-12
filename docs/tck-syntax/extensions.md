# 9. Proposed Extensions (unratified)

These correspond to ADR-0001 §2 D10 (P1–P7). They are written as they would appear once ratified.

## 9.1 CAC traceability — `cac:` (P1)

**Implemented in the engine.**

```yaml
- id: send_status_notification
  uses: connector/dataplane/http_request
  cac: ["CX-0135:v3.1.0:CAC-014"]
  returns:
    status_code: { type: integer, class: StatusCode }
    value: { type: object, class: ResponseBody }
  validate:
    - uses: validate/assert
      with: { input: status_code, operator: equals, value: 200 }       # reports under CAC-014
    - uses: validate/schema
      cac: ["CX-0135:v3.1.0:CAC-016"]                                # reports under CAC-016 only
      with: { input: value, schema: "${{ env.schemas.certificate_schema }}" }
```

- Format: `<standard-id>:<standard-version>:<cac-id>`. A step or validation can list several. The model rejects
  any entry that is not three colon-separated segments.
- `cac` can be set on a step and on individual validations. A validation's `cac` replaces the step's for
  reporting. A validation without one reports under the step's.
- Every referenced standard, with that exact version, must appear in `metadata.standards`. The compiler enforces
  this, including for steps nested in `flow/if` and `flow/retry`.
- Carried into the compiled IR (on the instruction and on each `validate` entry). It is also copied into the
  terminal step event: `data.cac` for the step, and `cac` on each entry of `data.validations`, with the
  step's value filled in where the validation has none. A skipped step still names its CACs.
- Traceability only: `cac` never changes a verdict.
- **Not yet built:** the conformity report's CAC coverage matrix, which would compare the CACs a standard
  declares against the CACs a TCK references.

## 9.2 Conditionals — `flow/if` (P2)

**Implemented in the engine.** The CAC model has `IF` plus `MUST … OR/AND … MUST`. The engine expresses both with
the `flow/if` step, not with keys on validations:

```yaml
- id: check_request_outcome
  uses: flow/if
  name: Branch on whether the provider reported a failure             # IF
  with:
    conditions:
      - input: "${{ execution.send_status_notification.value }}"
        path: status
        operator: equals
        value: failed
    then:
      - id: failure_is_signalled
        uses: flow/if
        name: The failure is signalled by status code or error code
        with:
          match: any                                                  # OR
          conditions:
            - input: "${{ execution.send_status_notification.status_code }}"
              operator: equals
              value: 503
            - input: "${{ execution.send_status_notification.value }}"
              path: error.code
              operator: equals
              value: SERVICE_UNAVAILABLE
          then:
            - uses: util/log
              name: Record that the failure was signalled
              with: { message: "failure signalled" }
        returns:
          condition_result: { type: boolean }
        validate:
          - uses: validate/assert
            with: { input: condition_result, operator: equals, value: true }
    else: [ … ]                                                       # the checks for the other case
```

- `conditions` use the same `input` / `path` / `operator` / `value` shape as a `validate:` entry. `match: all`
  (default) ANDs them, and `match: any` ORs them.
- The conditions are evaluated once, before either branch runs. `then:` and `else:` are ordinary step lists.
  A failing step or check in the branch that ran fails the `flow/if` step. `condition_result` and
  `branch_taken` are published so a check can show which way the run went.
- `MUST … AND MUST …` needs no construct: sibling `validate:` entries are always ANDed.
- A step's own `if:` is a different thing. It reads run state only (`success()`, `failure()`, `always()`,
  `steps.<id>.outcome`, `vars.<name>`), never a value a step returned. When false, it skips the step.
- Validations take no `if:`. The syntax has no `validate/any_of` or `validate/all_of`.

See [§6.3](authoring/cac-mapping.md#63-worked-example) for a full CAC translated this way.

## 9.3 Negative tests — `expects:` and `validate/error` (P3)

```yaml
- id: request_unknown_cert_type
  uses: connector/dataplane/http_request
  name: Request a certificate of an unknown type (negative test)
  expects: fail
  with:
    body: "${{ env.testdata.error_unknown_cert_type_body }}"
  returns:
    status_code: { type: integer, class: StatusCode }
    response_body: { type: object, class: ResponseBody }
  validate:
    - uses: validate/error
      with:
        input: response_body
        status_code: 400
        error_code: "UNKNOWN_CERTIFICATE_TYPE"
```

- `expects: fail` inverts the step's own success criterion: a transport-level or application-level failure is
  the expected outcome, and a success is a test failure.
- `validate:` entries still apply and still must all pass.

## 9.4 Integrity digests (P7)

```yaml
schemas:
  - id: certificate_schema
    source: business_partner_certificate_schema-v3.0.1.json
    digest: "sha256:9f2c…"
```

Recorded by the compiler in the `.tck` package; verified at load. Prevents a schema or fixture being swapped
between authoring and execution.
