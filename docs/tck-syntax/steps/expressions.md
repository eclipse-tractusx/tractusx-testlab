# 5.2 Expression / Reference Syntax **[OBS]**

Values are interpolated with `${{ … }}`.

| Form | Resolves to | Example |
|---|---|---|
| `${{ env.<var-id> }}` | A manifest variable's value, whatever its type | `${{ env.ccm_usage_policy }}` |
| `${{ env.schemas.<schema-id> }}` | A declared JSON Schema | `${{ env.schemas.certificate_schema }}` |
| `${{ env.testdata.<testdata-id> }}` | A declared test data file's content | `${{ env.testdata.send_feedback_body }}` |
| `${{ execution.<step-id>.<return-key> }}` | A prior step's declared return | `${{ execution.pull_notification_endpoint.edr_token }}` |
| `${{ setup.<step-id>.<return-key> }}` **[PROP]** | A setup step's return | `${{ setup.create_asset.asset_id }}` |

> **Resolved.** Slide 29 referenced a compound `sut_connector` variable with `counter_party_*` return keys,
> while slide 20 declared one variable per value. One value per variable is normative, and a variable is
> referenced by its id alone — `${{ env.sut_counter_party_address }}`. A variable that published several
> named artifacts was the reason a reference had to name one, and the reason the same value had two
> spellings; there is now nothing to name. Counter-party address and id are not variables at all: they come
> from the SUT's infrastructure binding ([§3.4 `infrastructure`](../manifest/dataspace-infrastructure.md#34-infrastructure-spec)).

Rules **[PROP]**:

- References resolve **only backwards** within the same test, plus `env` / `testdata` globally.
- Referencing a step in a later phase, a later step, or another test is a compile error.
- Whole-value references may be unquoted; embedded references must be quoted:
  `path: "/companycertificate/request"` vs `dataplane_url: "${{ execution.x.dataplane_url }}"`.
