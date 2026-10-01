# 5.2 Expression / Reference Syntax **[OBS]**

Values are interpolated with `${{ … }}`.

| Form | Resolves to | Example |
|---|---|---|
| `${{ env.<var-id> }}` | A manifest variable's value, whatever its type | `${{ env.ccm_usage_policy }}` |
| `${{ env.schemas.<schema-id> }}` | A declared JSON Schema | `${{ env.schemas.certificate_schema }}` |
| `${{ env.testdata.<testdata-id> }}` | A declared test data file's content | `${{ env.testdata.send_feedback_body }}` |
| `${{ execution.<step-id>.<return-key> }}` | A prior step's declared return | `${{ execution.pull_notification_endpoint.edr_token }}` |
| `${{ setup.<step-id>.<return-key> }}` **[PROP]** | A setup step's return | `${{ setup.create_asset.asset_id }}` |
| `${{ infrastructure.<engine\|sut>.<capability>.<field> }}` | A field of the bound deployment. A credential field (`api_key`) is a handle, not text — see [Credential references](#credential-references) | `${{ infrastructure.sut.connector.dsp_url }}` |
| `${{ execution.id }}` | The id of this run — the job id an engine hands the player. Unique per run (no execution step may be called `id`), so a test can name what it leaves in a shared system apart from another run's | `"testlab-ccmapi-${{ execution.id }}"` |

> **Resolved.** Slide 29 referenced a compound `sut_connector` variable with `counter_party_*` return keys,
> while slide 20 declared one variable per value. One value per variable is normative, and a variable is
> referenced by its id alone — `${{ env.sut_counter_party_address }}`. A variable that published several
> named artifacts was the reason a reference had to name one, and the reason the same value had two
> spellings; there is now nothing to name. Counter-party address and id are not variables at all: they come
> from the SUT's infrastructure binding ([§3.4 `infrastructure`](../manifest/dataspace-infrastructure.md#34-infrastructure-spec)).

Rules **[PROP]**:

- A reference is resolved once. What it stands for is resolved again only when it is part of the TCK package — a test data file or a static `env` value, whose `${{ }}` the author wrote. A step output, an operator input or a binding is data: a `${{ }}` inside it is handed on as text, never resolved. Authored content may nest references 16 deep.

- References resolve **only backwards** within the same test, plus `env` / `testdata` globally.
- Referencing a step in a later phase, a later step, or another test is a compile error.
- Whole-value references may be unquoted; embedded references must be quoted:
  `path: "/companycertificate/request"` vs `dataplane_url: "${{ execution.x.dataplane_url }}"`.

## Credential references

**[PROP]** A binding field that holds a credential — today `infrastructure.engine.connector.api_key` and
`infrastructure.sut.connector.api_key` — does not resolve to its value. It resolves to a *handle* that a
test may use in exactly one way: as the **whole value of a header** of `http/http_request`.

```yaml
- id: create_asset
  uses: http/http_request
  with:
    method: POST
    url: "${{ infrastructure.engine.connector.management_url }}/v3/assets"
    headers:
      x-api-key: "${{ infrastructure.engine.connector.api_key }}"
```

Rules:

- The request must go to the binding's own origin — the scheme, host and port of its `management_url`. Any
  other origin (a different host, a look-alike such as `https://connector.example.com.evil.io`, another port,
  `http` instead of `https`) fails the step with `CREDENTIAL_ORIGIN_MISMATCH`, before anything is sent. A
  request carrying a credential does not follow redirects.
- Anywhere else — interpolated into a longer string (`"Bearer ${{ … }}"`), in a URL, a body, a query, another
  step's input, a check, a `returns:` or an `env` value — the reference is a compile error, and fails the step
  with `CREDENTIAL_MISUSE` if it reaches the run.
- A host may withhold a side's credentials from raw requests altogether (`credential_release`, see
  [Infrastructure bindings](../../developer/infrastructure-bindings.md#credentials)). A test that sends one
  then fails with `CREDENTIAL_NOT_RELEASED`. The `connector/*` and `digital-twin-registry/*` steps are
  unaffected: they are handed the credential by the binding, never by the test.
- Every record of the run — the trace, the live events, the console transcript, the step's recorded request —
  shows the value as `***`.

## Call-scoped references (`labs`)

**[PROP]** Inside [`labs/mock/api/dynamic`](../../api-reference/steps/labs/mock-api.md) a reference may start
with `*.`. It names something that exists only while the mock answers one call, and it is read when
that call arrives — once per call — rather than when the step runs.

| Form | Resolves to | Example |
|---|---|---|
| `${{ *.request.body }}` | The JSON body of the call being answered: `{}` for a POST or PUT whose body is not JSON, `null` for any other method | `${{ *.request.body }}` |
| `${{ *.request.headers }}` | Its headers, keyed by lower-case name | `${{ *.request.headers.x-correlation-id }}` |
| `${{ *.request.query }}` | Its query string, one value per name (the last one given), as `mock/wait/*` publishes it | `${{ *.request.query.page }}` |
| `${{ *.request.method }}`, `${{ *.request.path }}` | The call's method and path | `${{ *.request.path }}` |
| `${{ *.process.<step-id>.<return-key> }}` | A return of one of the mock's own `process:` steps, for this call | `${{ *.process.answer_id.value }}` |

Rules:

- A call-scoped reference may continue past what it names, into the value: dictionary keys, and list
  positions written as numbers — `${{ *.request.body.header.messageId }}`,
  `${{ *.request.body.items.0.id }}`. No other reference does; everywhere else a path into a value is an
  extraction step or a `validate/field`.
- They are in scope in the mock's `process:` steps, at any depth (a `flow/if` branch included), and in its
  `response_status`, `response_body` and `response_headers`. The compiler refuses them anywhere else, and
  refuses a `*.request.<field>` other than the five above or a `*.process.<id>` that is not one of that
  mock's steps.
- A `process:` step publishes under `*.process.<id>` only, never under its phase: `execution.<id>` does
  not name it. As everywhere, it publishes only what its `returns:` declares.
- Every other reference in the mock's reply — `env.*`, `setup.*`, `execution.*` — is read at the same
  moment, against a copy of the run's variables taken when the call arrives.
- A reference that resolves to nothing at call time does not fail the test: the mock answers 500 and logs
  why.

