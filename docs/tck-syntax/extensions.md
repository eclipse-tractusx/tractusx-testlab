# 9. Proposed Extensions (unratified)

These correspond to ADR-0001 §2 D10 (P1–P7). They are written as they would appear once ratified.

## 9.1 CAC traceability — `cac:` (P1)

```yaml
- id: send_status_notification
  uses: connector/dataplane/http_request
  cac: ["CX-0135:v3.1.0:CAC-014"]
  validate:
    - uses: validate/field
      cac: ["CX-0135:v3.1.0:CAC-014"]
      with: { input: status_code, operator: equals, value: 200 }
```

- Format: `<standard-id>:<standard-version>:<cac-id>`.
- Valid on steps and on individual validations. A validation's `cac` overrides the step's for reporting.
- Every referenced standard must appear in `metadata.standards`. Compiler-enforced.
- Copied into event `data.cac` and into the conformity report, producing the CAC coverage matrix.

## 9.2 Conditionals — `if:`, `validate/any_of`, `validate/all_of` (P2)

Needed because the CAC model has `IF` plus `MUST … OR/AND … MUST`, and nothing in the step syntax expresses it.

```yaml
validate:
  - uses: validate/any_of                                  # OR
    if: "${{ execution.<step>.response_body.status == 'failed' }}"
    with:
      validations:
        - uses: validate/field
          with: { input: status_code, operator: equals, value: 503 }
        - uses: validate/field
          with: { input: response_body, path: "error.code",
                  operator: equals, value: "SERVICE_UNAVAILABLE" }

  - uses: validate/all_of                                  # explicit AND (sibling entries are already AND)
    with:
      validations: [ … ]
```

- `if:` evaluates to a boolean over `${{ }}`-resolvable values. If false, the step or validation is **skipped**,
  not failed, and emits a `skipped` result in the log.
- `any_of` passes if at least one nested validation passes; `all_of` if all do.
- Nesting depth limit: 2.

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
