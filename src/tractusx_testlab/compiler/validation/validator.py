#################################################################################
# Eclipse Tractus-X - Software Development KIT
#
# Copyright (c) 2026 Catena-X Autonomotive Network e.V.
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Static validation of test scripts before compilation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from tractusx_testlab.models import ScriptDefinition, StepDefinition, TckDefinition
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps._checks.extraction import declared_names
from tractusx_testlab.steps.assertions.vocabulary import resolve as resolve_assertion
from tractusx_testlab.syntax import defaults


@dataclass(slots=True)
class ValidationIssue:
    """A single validation finding."""
    level: str  # "error" | "warning"
    message: str
    step_index: Optional[int] = None
    field: Optional[str] = None
    phase: Optional[str] = None


@dataclass(slots=True)
class ValidationResult:
    """Aggregated validation outcome."""
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)

    def add_error(self, msg: str, **kw) -> None:
        self.issues.append(ValidationIssue(level="error", message=msg, **kw))

    def add_warning(self, msg: str, **kw) -> None:
        self.issues.append(ValidationIssue(level="warning", message=msg, **kw))


_VAR_REF = re.compile(r"\$\{(\w+)}")


class ScriptValidator:
    """Validates a ScriptDefinition for correctness before execution."""

    def validate_tck(self, tck: TckDefinition, base_dir: Path, version: Optional[str] = None) -> ValidationResult:
        """Validate all test files referenced by a TCK manifest."""
        combined = ValidationResult()
        for entry in tck.tests:
            test_path = base_dir / "tests" / entry.id
            if not test_path.is_file():
                combined.add_error(f"Referenced test file not found: tests/{entry.id}")
                continue
            from tractusx_testlab.scripting.parser import YamlParser
            try:
                script = YamlParser.parse_script(test_path)
            except ValidationError as exc:
                # Format kind: error log
                issues = "; ".join(f"{e['loc'][0]}: {e['msg']}" for e in exc.errors())
                combined.add_error(f"tests/{entry.id}: parse error — {issues}")
                continue
            except Exception as exc:  # noqa: BLE001
                combined.add_error(f"tests/{entry.id}: failed to parse — {exc}")
                continue
            result = self.validate(script, version=version)
            # Validate tck id and test namespace
            if script.namespace != tck.id:
                result.add_error(
                    f"namespace '{script.namespace}' must match the TCK id '{tck.id}'.",
                    field="namespace",
                )
            for issue in result.issues:
                issue.message = f"tests/{entry.id}: {issue.message}"
                combined.issues.append(issue)
        return combined

    def validate(self, script: ScriptDefinition, version: Optional[str] = None) -> ValidationResult:
        result = ValidationResult()
        declared_vars: set[str] = set()

        # Collect variables declared in the script header (in TCK env)
        declared_vars.update(getattr(script, "variables", {}))

        # Validate setup steps
        for idx, step_def in enumerate(script.setup):
            self._validate_step(step_def, idx, declared_vars, version, result, phase="setup")

        # Validate each step
        for idx, step_def in enumerate(script.execution):
            self._validate_step(step_def, idx, declared_vars, version, result)

        return result

    def _validate_step(
        self,
        step_def: StepDefinition,
        idx: int,
        declared_vars: set[str],
        version: Optional[str],
        result: ValidationResult,
        phase: str = "main",
    ) -> None:
        effective_version = version or defaults.DATASPACE_VERSION

        # Check step type is registered
        step_cls = StepRegistry.get(step_def.uses, effective_version)
        if step_cls is None:
            if step_def.uses not in StepRegistry.list_step_types():
                result.add_error(
                    f"Unknown step type '{step_def.uses}'",
                    step_index=idx,
                    field="uses",
                    phase=phase,
                )
            elif version:
                result.add_warning(
                    f"Step '{step_def.uses}' has no version-specific implementation for '{version}'",
                    step_index=idx,
                    phase=phase,
                )

        # Check variable references in with_ params resolve
        self._check_var_refs(step_def.with_ or {}, idx, declared_vars, result)

        # Enforce plain-string validate inputs for inline validate assertions.
        self._validate_inline_assert_inputs(step_def, idx, result, phase)

        # If returns is set, auto-declare the output variables
        self._validate_returns(step_def, step_cls, idx, result, phase)
        for key in (step_def.returns or {}):
            declared_vars.add(key)

    def _validate_returns(
        self,
        step_def: StepDefinition,
        step_cls: Optional[type],
        step_idx: int,
        result: ValidationResult,
        phase: str,
    ) -> None:
        """Check every ``returns:`` name against what the step actually publishes.

        A name the step never declares resolves to nothing at run time, so the
        variable reads as empty several steps later and the failure surfaces far
        from its cause. The step said what it produces; saying so here turns a
        typo into a compile error instead of a mystery.
        """
        returns = step_def.returns or {}
        if not returns or step_cls is None:
            return
        declared = declared_names(step_cls)
        for name in returns:
            # A dotted name reaches inside a declared output; only the first
            # segment has to be something the step publishes.
            root = name.split(".", 1)[0]
            if root in declared:
                continue
            result.add_error(
                f"'returns' name '{name}' is not produced by step "
                f"'{step_def.uses}'. It publishes: {', '.join(sorted(declared))}.",
                step_index=step_idx,
                field="returns",
                phase=phase,
            )

    def _check_var_refs(
        self, params: dict, step_idx: int, declared: set[str], result: ValidationResult
    ) -> None:
        for key, value in params.items():
            if isinstance(value, str):
                for match in _VAR_REF.finditer(value):
                    var_name = match.group(1)
                    if var_name not in declared:
                        result.add_warning(
                            f"Variable '${{{var_name}}}' referenced in param '{key}' "
                            f"is not declared in this script's variables block at step {step_idx} "
                            f"(may be provided via shared_variables, runtime_vars, or output propagation)",
                            step_index=step_idx,
                            field=key,
                        )
            elif isinstance(value, dict):
                self._check_var_refs(value, step_idx, declared, result)

    def _validate_inline_assert_inputs(
        self,
        step_def: StepDefinition,
        step_idx: int,
        result: ValidationResult,
        phase: str,
    ) -> None:
        """Check that every assertion names a real check and a declared input.

        An assertion the engine cannot resolve is rejected here rather than at
        run time, where it would surface as a failing check on a passing SUT.
        ``with.input`` must be a plain string naming one of the step's
        ``returns`` (e.g. ``"edr_token"``), not a ``${{ ... }}`` expression.
        """
        valid_keys = set(step_def.returns or {})
        for assertion in step_def.validate or []:
            params = assertion.with_ or {}
            resolved = resolve_assertion(assertion.uses, params)
            if isinstance(resolved, str):
                result.add_error(
                    resolved, step_index=step_idx, field="validate.uses", phase=phase,
                )
                continue
            input_value = params.get("input")
            if not isinstance(input_value, str):
                result.add_error(
                    "'validate.with.input' must be a plain string.",
                    step_index=step_idx,
                    field="validate.with.input",
                    phase=phase,
                )
                continue
            if valid_keys and input_value not in valid_keys:
                result.add_error(
                    f"'validate.with.input' value '{input_value}' is not declared in "
                    f"'returns'. Valid keys: {sorted(valid_keys)}.",
                    step_index=step_idx,
                    field="validate.with.input",
                    phase=phase,
                )
