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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""YAML compile/validate endpoint — parse + validate without execution."""

from __future__ import annotations

import logging

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from tractusx_testlab.compiler.validation.validator import ScriptValidator
from tractusx_testlab.models.authoring.definitions import ScriptDefinition, TckDefinition
from tractusx_testlab.models.primitives.enums import ScriptKind
from tractusx_testlab.scripting.parser import YamlParser
from tractusx_testlab.syntax import defaults

_logger = logging.getLogger(__name__)
_validator = ScriptValidator()

compile_router = APIRouter(tags=["compile"])


def _error(path: str, message: str) -> dict[str, str]:
    """Build a single structured error entry."""
    return {"path": path, "message": message}


@compile_router.post("/compile")
async def compile_yaml(request: Request) -> JSONResponse:
    """Validate a raw YAML body and return structured errors or success.

    Always returns HTTP 200 — validation errors are application-level.
    """
    raw = await request.body()
    if not raw:
        return JSONResponse(
            content={
                "status": "error",
                "errors": [_error("", "Request body is empty")],
            }
        )

    data = _parse_yaml_body(raw)
    if isinstance(data, JSONResponse):
        return data

    kind = _resolve_script_kind(data)
    if isinstance(kind, JSONResponse):
        return kind

    parsed = _parse_script(data, kind)
    if isinstance(parsed, JSONResponse):
        return parsed

    errors = _run_semantic_validation(parsed, kind)
    if errors:
        return JSONResponse(content={"status": "error", "errors": errors})

    _logger.debug("YAML compile OK (kind=%s)", kind.value)
    return JSONResponse(content={"status": "ok", "errors": []})


def _parse_yaml_body(raw: bytes) -> dict | JSONResponse:
    """Parse raw bytes as YAML, returning dict or error response."""
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return JSONResponse(
            content={
                "status": "error",
                "errors": [_error("", f"Invalid YAML syntax: {exc}")],
            }
        )

    if not isinstance(data, dict):
        return JSONResponse(
            content={
                "status": "error",
                "errors": [_error("", "YAML root must be a mapping")],
            }
        )
    return data


def _resolve_script_kind(data: dict) -> ScriptKind | JSONResponse:
    """Determine script kind from data, returning error response if invalid."""
    kind_value = data.get("kind")
    has_tests = "tests" in data

    try:
        if kind_value:
            return ScriptKind(kind_value)
        return ScriptKind.TCK if has_tests else ScriptKind.TEST
    except ValueError:
        return JSONResponse(
            content={
                "status": "error",
                "errors": [_error("kind", f"Unknown script kind: {kind_value!r}")],
            }
        )


def _parse_script(
    data: dict,
    kind: ScriptKind,
) -> JSONResponse | ScriptDefinition | TckDefinition:
    """Parse the YAML data into a script/tck definition or return error response."""
    parser = YamlParser()
    try:
        if kind == ScriptKind.TCK:
            return parser.parse_tck_from_dict(data)
        return parser.parse_script_from_dict(data)
    except ValidationError as exc:
        errors = [_error(".".join(str(loc) for loc in e["loc"]), e["msg"]) for e in exc.errors()]
        return JSONResponse(content={"status": "error", "errors": errors})
    except (ValueError, KeyError, TypeError) as exc:
        return JSONResponse(
            content={
                "status": "error",
                "errors": [_error("", f"Validation failed: {exc}")],
            }
        )


def _run_semantic_validation(
    parsed: ScriptDefinition | TckDefinition,
    kind: ScriptKind,
) -> list[dict[str, str]]:
    """Run semantic validation and return list of error dicts (empty if OK)."""
    errors: list[dict[str, str]] = []

    name = getattr(parsed, "name", None) or (
        parsed.metadata.name if hasattr(parsed, "metadata") else None
    )
    if not name or not name.strip():
        errors.append(_error("name", "Script name is required and must not be empty"))

    if kind == ScriptKind.TEST and isinstance(parsed, ScriptDefinition):
        # The release comes from the script's own ``dataspace`` block when it has
        # one, and otherwise from the default. It is not required here: a test
        # file belongs to a TCK, and it is the manifest that declares which
        # ecosystem release the suite certifies against — none of the shipped
        # example's test files carry the block, and demanding it rejected
        # correctly-authored files.
        dataspace = getattr(parsed, "dataspace", None)
        dataspace_version = (
            dataspace.version
            if dataspace is not None and dataspace.version
            else defaults.DATASPACE_VERSION
        )

        result = _validator.validate(parsed, version=dataspace_version)
        for issue in result.issues:
            path = _build_issue_path(issue)
            errors.append(_error(path, issue.message))

    return errors


def _build_issue_path(issue) -> str:
    """Build a structured path string from a validation issue."""
    path = issue.field or ""
    if issue.phase:
        return (
            f"{issue.phase}[{issue.step_index}].{path}"
            if path
            else f"{issue.phase}[{issue.step_index}]"
        )
    if issue.step_index is not None:
        return f"steps[{issue.step_index}].{path}" if path else f"steps[{issue.step_index}]"
    return path
