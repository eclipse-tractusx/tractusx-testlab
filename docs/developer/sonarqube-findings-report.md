# SonarQube Findings Report — PR #16

> Generated: 2026-05-31
> Project: eclipse-tractusx_tractusx-testlab

## Summary

| Metric | Count |
|--------|-------|
| **Total Issues** | 30 |
| **Files Affected** | 16 |
| BLOCKER | 3 |
| CRITICAL | 7 |
| MAJOR | 11 |
| MINOR | 9 |

## Resolution Strategy

### Priority Order

1. **BLOCKER** — Security/reliability risks. Must fix before merge.
2. **CRITICAL** — Bugs and vulnerabilities. Must fix before merge.
3. **MAJOR** — Code smells with significant impact. Should fix.
4. **MINOR** — Low-impact code smells. Fix opportunistically.

### Batch Strategy

1. **Group by rule** — Many issues share the same rule (e.g., publicly writable directories, cognitive complexity). Fixing by rule type is fastest.
2. **Group by directory** — Fix all test files together, all compiler files together, etc.
3. **After each batch** — Re-scan fixed files with `mcp_sonarqube_analyze_file_list` to confirm.
4. **Track progress** — Check off files in the table below as they are cleaned.

---

## Top Rules by Frequency

| # | Rule | Severity | Count | Fix Strategy |
|---|------|----------|-------|--------------|
| 1 | `python:S5443` | CRITICAL | 5 | |
| 2 | `python:S125` | MAJOR | 5 | |
| 3 | `python:S8411` | BLOCKER | 3 | |
| 4 | `python:S3776` | CRITICAL | 2 | |
| 5 | `python:S7504` | MINOR | 2 | |

---

## File Checklist

### Stubs (1 files, 3 issues, 3 blocker+critical)

| Done | File | Total | B | C | Ma | Mi |
|:----:|------|:-----:|:-:|:-:|:--:|:--:|
| [x] | `stubs/ccm-sut/management.py` | 3 | 3 | 0 | 0 | 0 | <!-- FIXED: 3x python:S8411 — split stacked DELETE decorators into 3 handlers with path params in signature; rescan 0 findings -->

### Python Backend (5 files, 7 issues, 2 blocker+critical)

| Done | File | Total | B | C | Ma | Mi |
|:----:|------|:-----:|:-:|:-:|:--:|:--:|
| [x] | `src/tractusx_testlab/compiler/_ir_helpers.py` | 2 | 0 | 2 | 0 | 0 | <!-- RESOLVED BY REFACTOR: file split into compiler/ir/ (Phase 6); rescan of ir/_helpers.py, builder.py, _compilation.py, _assets.py shows 0 S3776 findings -->
| [ ] | `src/tractusx_testlab/compiler/_ir_compilation.py` | 2 | 0 | 0 | 2 | 0 |
| [ ] | `src/tractusx_testlab/compiler/_expressions.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `src/tractusx_testlab/server/streaming.py` | 1 | 0 | 0 | 0 | 1 |
| [ ] | `src/tractusx_testlab/steps/pull_data/_executor.py` | 1 | 0 | 0 | 0 | 1 |

### Test Files (10 files, 20 issues, 5 blocker+critical)

| Done | File | Total | B | C | Ma | Mi |
|:----:|------|:-----:|:-:|:-:|:--:|:--:|
| [x] | `tests/test_test_runner.py` | 4 | 0 | 4 | 0 | 0 |
| [x] | `tests/test_mock_server_integration.py` | 3 | 0 | 1 | 0 | 2 |
| [ ] | `tests/test_mocks.py` | 2 | 0 | 0 | 2 | 0 |
| [ ] | `tests/test_pause_endpoint.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `tests/test_pause_resume_events.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `tests/test_resume.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `tests/test_resume_endpoint.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `tests/test_models.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `tests/test_pause.py` | 1 | 0 | 0 | 1 | 0 |
| [ ] | `tests/test_precondition_execution.py` | 5 | 0 | 0 | 0 | 5 |

---

## Detailed Findings (BLOCKER + CRITICAL files only)

<details>
<summary><b>tests/test_test_runner.py</b> — 4 issues (4 blocker/critical)</summary>

| Line | Severity | Rule | Message |
|------|----------|------|---------|
| ? | CRITICAL | `python:S5443` | Make sure publicly writable directories are used safely here. |
| ? | CRITICAL | `python:S5443` | Make sure publicly writable directories are used safely here. |
| ? | CRITICAL | `python:S5443` | Make sure publicly writable directories are used safely here. |
| ? | CRITICAL | `python:S5443` | Make sure publicly writable directories are used safely here. |

</details>

<details>
<summary><b>stubs/ccm-sut/management.py</b> — 3 issues (3 blocker/critical)</summary>

| Line | Severity | Rule | Message |
|------|----------|------|---------|
| ? | BLOCKER | `python:S8411` | Add path parameter "asset_id" to the function signature. |
| ? | BLOCKER | `python:S8411` | Add path parameter "policy_id" to the function signature. |
| ? | BLOCKER | `python:S8411` | Add path parameter "contract_id" to the function signature. |

</details>

<details>
<summary><b>src/tractusx_testlab/compiler/_ir_helpers.py</b> — 2 issues (2 blocker/critical)</summary>

| Line | Severity | Rule | Message |
|------|----------|------|---------|
| ? | CRITICAL | `python:S3776` | Refactor this function to reduce its Cognitive Complexity from 23 to the 15 allowed. |
| ? | CRITICAL | `python:S3776` | Refactor this function to reduce its Cognitive Complexity from 34 to the 15 allowed. |

</details>

<details>
<summary><b>tests/test_mock_server_integration.py</b> — 3 issues (1 blocker/critical)</summary>

| Line | Severity | Rule | Message |
|------|----------|------|---------|
| ? | CRITICAL | `python:S5443` | Make sure publicly writable directories are used safely here. |
| ? | MINOR | `python:S7504` | Remove this unnecessary `list()` call on an already iterable object. |
| ? | MINOR | `python:S7504` | Remove this unnecessary `list()` call on an already iterable object. |

</details>
