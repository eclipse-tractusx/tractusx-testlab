# 4. Test File Syntax (`/tests/*.yaml`)

## 4.1 Header and Metadata **[SPEC]**

Very similar to the TCK declaration, with fewer fields because most of the context lives in the manifest.

```yaml
kind: test
syntax: v1-alpha

namespace: certificate-management-tck-v0.0.1
id: send-feedback-notification

metadata:
  name: "Send Feedback Notification"
  version: "1.0.0"
  description: >
    Send a CX-0135 CCMAPI status notification to the provider via EDC dataplane
    and await the provider's acknowledgment on a TestLab mock endpoint.
```

| Field | R/O | Notes |
|---|---|---|
| `kind` | R | `test`. |
| `syntax` | R | Must match the manifest's `syntax`. |
| `namespace` | R | **Must be the same `id` as the TCK manifest.** Binds the test to its TCK. |
| `id` | R | Descriptive ID of the test. Second segment of every event `id` this test emits. |
| `metadata.name` | R | Label for the user. |
| `metadata.version` | R | For version control. |
| `metadata.description` | O | Detailed text. |

## 4.2 Phases **[SPEC]**

Three phases, inspired by JUnit and PyTest. Each **contains a list of technical capability test steps /
building blocks**.

```yaml
setup:        # list of steps — same syntax as execution, WITHOUT `validate`
execution:    # list of steps — WITH `validate`
teardown:     # list of steps — same syntax as execution, WITHOUT `validate`
```

| Phase | R/O | `validate` allowed | Purpose |
|---|---|---|---|
| `setup` | O | ❌ | Pre-steps establishing preconditions. Runs START → PRE-STEP 1..N → END. |
| `execution` | R | ✅ | The test steps and their validations. |
| `teardown` | O | ❌ | After-steps, e.g. cleanup. |

**Execution control flow [SPEC]:**

```
START → TEST STEP 1 → [VALIDATION 1..n all pass] → TEST STEP 2 → [VALIDATION 2 FAILS]
                                                                        ↓
                                              TEST STEP N is skipped; test ABORTED → FAILED
```

> Continues to the next step **only if all validations passed**. If a validation fails, the test is aborted and
> then fails.

**[PROP]** `teardown` runs regardless of whether `execution` passed, failed or aborted — otherwise a failed
test leaves assets behind in a live dataspace. Teardown failures are reported as warnings and do not change the
test verdict.

> ⚠️ **[SPEC]** *Steps / building blocks are **not** meant to be usable in any phase.* Each capability declares
> which phases it is valid in; the compiler rejects a step used in a phase it does not support. **[PROP]** This
> is expressed as a `phases:` attribute on the `@step` annotation and published in the capability catalogue.
