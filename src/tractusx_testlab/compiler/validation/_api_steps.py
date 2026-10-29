"""Holding the ``labs`` API steps to the API files they name, before anything runs.

A step that calls an API file (ADR-0030 §5) names the document and an
operation in it; both are known when the TCK compiles, so a test naming an
operation the document does not have, a path placeholder it does not have, or
leaving out a required one is refused here, with the closest names, rather
than twenty steps into a run. The same holds for a sweep's ``operations`` and
for ``labs/validate/api_response`` under a step that is not an API call.

``labs/connector/dataplane/api_request`` reads ``dataplane_url`` and
``edr_token`` from an earlier step unless given. Which steps publish both is
read off their output contracts, not a list kept here, and a test with none of
them before the call is warned.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from functools import cache
from pathlib import Path
from typing import Any

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.compiler.validation.issues import ValidationIssue
from tractusx_testlab.extensions.extension import written_steps
from tractusx_testlab.models import TckDefinition, TestDefinition
from tractusx_testlab.openapi import ApiDocumentError, FrozenDict, load_api_document
from tractusx_testlab.openapi.operations import Operation, operation_index
from tractusx_testlab.player.loading._package_paths import UnsafePackagePathError, package_path
from tractusx_testlab.syntax.context_vars import DATAPLANE_URL, EDR_TOKEN

CALLS = frozenset({"labs/http/api_request", "labs/connector/dataplane/api_request"})
DATAPLANE_CALL = "labs/connector/dataplane/api_request"
SWEEP = "labs/http/api_sweep"
RESPONSE_CHECK = "labs/validate/api_response"
HTTP_METHODS = frozenset({"GET", "PUT", "POST", "DELETE", "OPTIONS", "HEAD", "PATCH", "TRACE"})

_API_REFERENCE = re.compile(r"^\$\{\{\s*env\.apis\.([a-z][a-z0-9_]*)\s*\}\}$")


def api_step_findings(
    tck: TckDefinition, test: TestDefinition, base_dir: Path
) -> list[ValidationIssue]:
    """Every problem of *test*'s API steps with the API files they name."""
    documents = _documents(tck, base_dir)
    providers = dataplane_providers()
    issues: list[ValidationIssue] = []
    provided = False
    for phase, idx, step in written_steps(test):
        uses = str(step.get("uses", ""))
        params = step.get("with") or {}

        report = _reporter(issues, phase, idx)

        if uses in CALLS or uses == SWEEP:
            _check_call(uses, params, documents, report)
        if uses == DATAPLANE_CALL and not provided and not _names_both(params):
            report(
                f"'{uses}' sends to the data plane an earlier step published, and no earlier step "
                f"publishes '{DATAPLANE_URL}' and '{EDR_TOKEN}' (e.g. "
                f"{', '.join(sorted(providers)[:3])}); give 'dataplane_url' and 'edr_token'.",
                "uses",
                "warning",
            )
        if uses == RESPONSE_CHECK:
            _check_response(params, None, documents, report, "with")
        for position, entry in enumerate(step.get("validate") or []):
            if isinstance(entry, dict) and entry.get("uses") == RESPONSE_CHECK:
                checked = entry.get("with") or {}
                _check_response(
                    checked, uses in CALLS, documents, report, f"validate[{position}].with"
                )
        provided = provided or uses in providers
    return issues


def _reporter(issues: list[ValidationIssue], phase: str, idx: int) -> Any:
    def report(message: str, field: str, level: str = "error") -> None:
        issues.append(ValidationIssue(level, message, step_index=idx, field=field, phase=phase))

    return report


@cache
def dataplane_providers() -> frozenset[str]:
    """The steps whose output contract publishes both ``dataplane_url`` and ``edr_token``."""
    found = set()
    for step_type in StepRegistry.list_step_types():
        step_cls = StepRegistry.get_any(step_type)
        fields = getattr(getattr(step_cls, "output_model", None), "model_fields", {}) or {}
        if DATAPLANE_URL in fields and EDR_TOKEN in fields:
            found.add(step_type)
    return frozenset(found)


def api_id_of(value: Any) -> str | None:
    """The id in ``${{ env.apis.<id> }}``, or ``None`` for anything else."""
    match = _API_REFERENCE.match(value) if isinstance(value, str) else None
    return match.group(1) if match else None


def _documents(tck: TckDefinition, base_dir: Path) -> dict[str, FrozenDict]:
    """The API files of *tck* that load, by id; the manifest check reports the others."""
    loaded: dict[str, FrozenDict] = {}
    for api in (tck.env.apis if tck.env else None) or []:
        try:
            loaded[api.id] = load_api_document(
                package_path(base_dir / "apis", api.source), str(api.type)
            ).content
        except (ApiDocumentError, UnsafePackagePathError):
            continue
    return loaded


def _names_both(params: Mapping[str, Any]) -> bool:
    return params.get("dataplane_url") is not None and params.get("edr_token") is not None


def _document(
    params: Mapping[str, Any], documents: dict[str, FrozenDict], report: Any, field: str
) -> FrozenDict | None:
    value = params.get("api")
    api_id = api_id_of(value)
    if api_id is None:
        report(
            "'api' must be an API file of the TCK, written '${{ env.apis.<id> }}'.", f"{field}.api"
        )
        return None
    return documents.get(api_id)  # an undeclared id is reported as an unresolved reference


def _operation(document: FrozenDict, name: Any, report: Any, field: str) -> Operation | None:
    if not isinstance(name, str) or "${{" in name:
        return None
    index = operation_index(document)
    found = index.find(name)
    if found is None:
        hints = index.suggestions(name)
        hint = f" Did you mean {', '.join(repr(h) for h in hints)}?" if hints else ""
        report(f"The API file has no operation '{name}'.{hint}", field)
    return found


def _check_call(
    uses: str, params: Mapping[str, Any], documents: dict[str, FrozenDict], report: Any
) -> None:
    document = _document(params, documents, report, "with")
    if uses == SWEEP:
        bad = [m for m in params.get("methods") or [] if str(m).upper() not in HTTP_METHODS]
        if bad:
            report(
                f"'methods' names {', '.join(map(str, bad))}, which are not HTTP methods.",
                "with.methods",
            )
        if document is None:
            return
        for key in ("operations", "exclude"):
            for name in params.get(key) or []:
                _operation(document, name, report, f"with.{key}")
        known = operation_index(document).tags
        for tag in params.get("tags") or []:
            if tag not in known:
                report(f"No operation of the API file is tagged '{tag}'.", "with.tags", "warning")
        return
    if "operation" not in params:
        report(f"'{uses}' needs 'operation': an operationId or 'METHOD /path'.", "with.operation")
        return
    operation = (
        _operation(document, params["operation"], report, "with.operation") if document else None
    )
    if operation is not None:
        for message, field in _parameter_problems(operation, params):
            report(message, field)


def _parameter_problems(
    operation: Operation, params: Mapping[str, Any]
) -> Iterator[tuple[str, str]]:
    placeholders = [name for _, name in operation.template if name]
    given = params.get("path_params", {})
    if isinstance(given, Mapping):
        for name in given:
            if name not in placeholders:
                yield (
                    f"'{operation.path}' has no placeholder '{name}' (it has: {', '.join(placeholders) or 'none'}).",
                    "with.path_params",
                )
        for name in placeholders:
            if name not in given:
                yield (
                    f"'{operation.key}' needs path parameter '{name}' in 'path_params'.",
                    "with.path_params",
                )
    query = params.get("query", {})
    if isinstance(query, Mapping):
        for parameter in operation.parameters_in("query"):
            if parameter.required and parameter.name not in query:
                yield (
                    f"'{operation.key}' needs query parameter '{parameter.name}' in 'query'.",
                    "with.query",
                )
    if operation.body_required and params.get("body") is None:
        yield f"'{operation.key}' requires a request body; give 'body'.", "with.body"


def _check_response(
    params: Mapping[str, Any],
    under_call: bool | None,
    documents: dict[str, FrozenDict],
    report: Any,
    field: str,
) -> None:
    """``labs/validate/api_response``: it must know its document and operation.

    *under_call* is ``None`` for the check used as a step, which may read the
    answer the last API call published.
    """
    if under_call is False and not ("api" in params and "operation" in params):
        report(
            f"'{RESPONSE_CHECK}' under a step that is not a labs API call needs 'api' and "
            "'operation': its output does not say which operation answered.",
            field,
        )
        return
    if "api" not in params:
        return
    document = _document(params, documents, report, field)
    if document is not None and "operation" in params:
        _operation(document, params["operation"], report, f"{field}.operation")
