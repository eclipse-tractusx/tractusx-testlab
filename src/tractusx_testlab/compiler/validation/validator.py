#################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
#
# Copyright (c) 2026 Contributors to the Eclipse Foundation
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
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Static validation of test scripts before compilation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from tractusx_testlab.infrastructure.mapping import known_keys
from tractusx_testlab.models import ScriptDefinition, StepDefinition, TckDefinition
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps._checks.extraction import declared_names
from tractusx_testlab.steps.assertions.vocabulary import check_operands
from tractusx_testlab.steps.assertions.vocabulary import resolve as resolve_assertion
from tractusx_testlab.syntax import defaults, patterns


@dataclass(slots=True)
class ValidationIssue:
    """A single validation finding."""
    level: str  # "error" | "warning"
    message: str
    step_index: int | None = None
    field: str | None = None
    phase: str | None = None


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




def _format_errors(exc: ValidationError) -> str:
    """Render Pydantic's errors with the full path to each offending key.

    Only ``loc[0]`` used to be printed, so a misspelled key three levels down
    reported as ``execution: Extra inputs are not permitted`` — the author was
    told which *phase* was wrong out of a file with dozens of steps in it, and
    not which step or which key. The path is the whole value of the message.
    """
    lines = []
    for error in exc.errors():
        where = ".".join(str(part) for part in error["loc"]) or "<root>"
        lines.append(f"{where}: {error['msg']}")
    return "; ".join(lines)


def _root_of(reference: str) -> str:
    """The part of a reference that has to exist for the rest to be reachable.

    ``env.sut_bpn.value`` hangs off the manifest variable ``env.sut_bpn``;
    ``execution.fetch.response_body`` off the step ``execution.fetch``;
    ``infrastructure.sut.connector.dsp_url`` off the binding key, which is four
    segments. Checking the root is what can be checked statically — how deep a
    declared output can be walked is the step's business, not the manifest's.
    """
    parts = reference.split(".")
    if parts[0] == "infrastructure":
        return ".".join(parts[:4])
    if parts[0] == "env" and len(parts) > 1 and parts[1] in ("testdata", "schemas"):
        return ".".join(parts[:3])
    return ".".join(parts[:2]) if len(parts) > 1 else reference


def _scope_of(tck: TckDefinition, script: ScriptDefinition) -> frozenset[str]:
    """Every name a reference in *script* may legally resolve to.

    Assembled from the manifest's ``env`` block, the script's own step ids, and
    the infrastructure binding keys. This is the namespace the runtime will
    actually have, so a name missing from here is a name that will be missing
    from the run.
    """
    names: set[str] = set()

    env = tck.env
    if env is not None:
        for variable_id in _env_variable_ids(env.variables):
            names.add(f"env.{variable_id}")
        for testdata in env.testdata or []:
            names.add(f"env.testdata.{testdata.id}")
        for schema in env.schemas or []:
            names.add(f"env.schemas.{schema.id}")

    for phase, steps in (
        ("setup", script.setup),
        ("execution", script.execution),
        ("teardown", script.teardown),
    ):
        for step in steps:
            if step.id:
                names.add(f"{phase}.{step.id}")

    names.update(known_keys())
    return frozenset(names)


def _env_variable_ids(variables: object) -> list[str]:
    """Ids of the manifest's declared variables, whichever shape they arrive in."""
    if isinstance(variables, list):
        return [str(v["id"]) for v in variables if isinstance(v, dict) and "id" in v]
    if isinstance(variables, dict):
        return [str(key) for key in variables]
    return []


class ScriptValidator:
    """Validates a ScriptDefinition for correctness before execution."""

    def validate_tck(self, tck: TckDefinition, base_dir: Path, version: str | None = None) -> ValidationResult:
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
                combined.add_error(
                    f"tests/{entry.id}: parse error — {_format_errors(exc)}"
                )
                continue
            except Exception as exc:
                combined.add_error(f"tests/{entry.id}: failed to parse — {exc}")
                continue
            result = self.validate(script, version=version, scope=_scope_of(tck, script))
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

    def validate(
        self,
        script: ScriptDefinition,
        version: str | None = None,
        scope: frozenset[str] | None = None,
    ) -> ValidationResult:
        """Check *script*, resolving its references against *scope*.

        *scope* is every name the run will be able to supply — the TCK's ``env``
        entries, its steps' ids, and the infrastructure bindings. Passed as
        ``None`` (a script validated on its own, with no manifest around it),
        reference checking is skipped rather than guessed at: warning about every
        reference in a file whose namespace is not visible is noise, and noise is
        what got the previous check ignored.
        """
        result = ValidationResult()
        declared = set(scope) if scope is not None else None

        for idx, step_def in enumerate(script.setup):
            self._validate_step(step_def, idx, declared, version, result, phase="setup")

        for idx, step_def in enumerate(script.execution):
            self._validate_step(step_def, idx, declared, version, result)

        return result

    def _validate_step(
        self,
        step_def: StepDefinition,
        idx: int,
        declared: set[str] | None,
        version: str | None,
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
        self._check_var_refs(step_def.with_ or {}, idx, declared, result)

        # Enforce plain-string validate inputs for inline validate assertions.
        self._validate_inline_assert_inputs(step_def, idx, result, phase)

        self._validate_returns(step_def, step_cls, idx, result, phase)

    def _validate_returns(
        self,
        step_def: StepDefinition,
        step_cls: type | None,
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
        self, params: dict, step_idx: int, declared: set[str] | None, result: ValidationResult
    ) -> None:
        """Reject a reference to a name nothing in this TCK supplies.

        An error rather than a warning, because at run time it is now fatal
        (F-A02): the reference used to survive as its own template text and the
        warning was the only hint. It said "may be provided via shared_variables,
        runtime_vars, or output propagation" — which was true of every reference,
        so the warning carried no information and was correctly ignored.
        """
        if declared is None:
            return
        for key, value in params.items():
            if isinstance(value, str):
                for match in patterns.EXPR_REF.finditer(value):
                    reference = match.group(1)
                    if _root_of(reference) in declared:
                        continue
                    result.add_error(
                        f"'${{{{ {reference} }}}}' in param '{key}' names nothing this "
                        f"TCK supplies. Available: {', '.join(sorted(declared)[:12])}"
                        f"{'…' if len(declared) > 12 else ''}.",
                        step_index=step_idx,
                        field=key,
                    )
            elif isinstance(value, dict):
                self._check_var_refs(value, step_idx, declared, result)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        self._check_var_refs(item, step_idx, declared, result)

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
        for assertion in step_def.assertions or []:
            params = assertion.with_ or {}
            resolved = resolve_assertion(assertion.uses, params)
            if isinstance(resolved, str):
                result.add_error(
                    resolved, step_index=step_idx, field="validate.uses", phase=phase,
                )
                continue
            if resolved.operator is not None:
                mismatch = check_operands(resolved.operator, params)
                if mismatch:
                    result.add_error(
                        mismatch, step_index=step_idx, field="validate.with", phase=phase,
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
