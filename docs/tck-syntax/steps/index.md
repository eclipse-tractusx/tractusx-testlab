# 5. Step / Building Block Syntax

**[SPEC]** Based on GitHub Actions syntax. `execution` is an array of steps executed in sequential order.

## 5.1 Anatomy

```yaml
execution:
  - id: <unique-key-in-test-for-step>
    uses: <function-key mapped to a backend function with an @step annotation>
    name: <text description of what is being executed/tested>
    with:
      input-key-1: <input configuration data from standard>
      input-key-2: <input configuration data from standard>   # can be taken from a variable
      input-key-n: <…>
    returns:
      return-key-1:
        type: <string | object | number | bool | array>
        class: <semantic type>        # optional
      return-key-n:
        type: <data type>
        # …
    validate:
      - uses: <validation-function-key>
        name: <what this check is for>        # optional
        with:
          input: return-key-1 # key from the returned value
          # … more params, depending on the validation function
```

| Field | R/O | Notes |
|---|---|---|
| `id` | R | Unique within the test. Used to reference this step's outputs and as the third segment of event IDs. |
| `uses` | R | Capability key, mapped to a backend function carrying the `@step` annotation. |
| `name` | R | Text description of what is being executed/tested. Shown live in Mission Control and in the report. |
| `with` | O | Input parameters of the function named in `uses` — GitHub Actions style. Values may come from variables. |
| `returns` | O | Declares which outputs this step generates, so the user configuring the steps (and the compiler) knows what is available downstream. |
| `returns.<key>.type` | R | `string` \| `object` \| `number` \| `bool` \| `array`. |
| `returns.<key>.class` | O | Semantic type for the return (e.g. `AuthToken`, `DataplaneUrl`, `StatusCode`, `ResponseBody`, `Policy`). |
| `validate` | R in `execution` | Array of validations. Same syntax as a step, **but with no return**. |
| `validate[].uses` | R | Validation function key. |
| `validate[].name` | O | What this check is for, in the author's words. Nothing in the engine reads it; the run report calls the check by it, so a step carrying four `validate/assert` entries says which requirement each one covers. Falls back to `uses` when absent. |
| `validate[].with` | R | Inputs depend on the selected validation function; they validate the step's `returns` variables. |
| `cac` | O **[PROP]** | CAC identifiers (`<standard-id>:<standard-version>:<cac-id>`) this step verifies. Also accepted on each `validate[]` entry, where it replaces the step's. Implemented; the standard must be in `metadata.standards`. See [§9.1](../extensions.md#91-cac-traceability-cac-p1). |
| `if` | O | Guards the step on run state: `success()`, `failure()`, `always()`, `steps.<id>.outcome == '…'`, `vars.<name>`. When false, the step is skipped. Not accepted on validations. To branch on a value a step returned, use `flow/if`. See [§9.2](../extensions.md#92-conditionals-flowif-p2). |
| `expects` | O **[PROP]** | `pass` (default) \| `fail` — negative-test support. See [§9.3](../extensions.md#93-negative-tests-expects-and-validateerror-p3). |
