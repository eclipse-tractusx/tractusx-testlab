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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""Checking that a credential is only ever written where it can be sent safely.

A binding's credential — ``${{ infrastructure.engine.connector.api_key }}`` —
is published to a test as a handle, not as text
(:mod:`tractusx_testlab.security.credentials`). The one place a handle may be
written is the whole value of a header of a step that sends it
(``credential_params`` — the ``headers`` of ``http/http_request``); there the
step checks the request goes to the binding's own origin before it puts the
key on the wire. Anywhere else — inside a longer string, in a URL, a body, a
query, another step's input, a check, a ``returns:`` — the run would refuse it,
so the compiler refuses it first, at the line that has to change.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.compiler.validation._variable_references import root_of
from tractusx_testlab.infrastructure.mapping import secret_keys
from tractusx_testlab.models import TestDefinition
from tractusx_testlab.security.credentials import CredentialMisuseError
from tractusx_testlab.syntax import keys, patterns


def credential_findings(test: TestDefinition) -> Iterator[tuple[str, int, str, str]]:
    """Every ``(phase, step index, field, message)`` where *test* misplaces a credential."""
    secrets = secret_keys()
    for phase, steps in (
        ("setup", test.setup),
        ("execution", test.execution),
        ("teardown", test.teardown),
    ):
        for idx, step_def in enumerate(steps):
            document = step_def.model_dump(by_alias=True, exclude_none=True)
            for where, reference in _misplaced(document, "", secrets):
                yield phase, idx, where, CredentialMisuseError(reference, where).args[0]


def misplaced_in_value(value: Any, where: str) -> Iterator[tuple[str, str]]:
    """Every credential reference in *value* — a manifest value may hold none at all."""
    yield from _references(value, where, secret_keys())


def _misplaced(step: dict[str, Any], at: str, secrets: frozenset[str]) -> Iterator[tuple[str, str]]:
    """The misplaced credential references of one step definition, its nesting included."""
    step_cls = StepRegistry.get_any(str(step.get(keys.USES, "")))
    carriers: frozenset[str] = getattr(step_cls, "credential_params", frozenset())
    nested: frozenset[str] = getattr(step_cls, "deferred_params", frozenset()) - getattr(
        step_cls, "template_params", frozenset()
    )
    for key, value in step.items():
        where = f"{at}{key}"
        if key != keys.WITH or not isinstance(value, dict):
            yield from _references(value, where, secrets)
            continue
        for param, item in value.items():
            param_at = f"{where}.{param}"
            if param in nested and isinstance(item, list):
                for index, child in enumerate(item):
                    if isinstance(child, dict):
                        yield from _misplaced(child, f"{param_at}[{index}].", secrets)
            elif param in carriers and isinstance(item, dict):
                for name, header in item.items():
                    if not _is_whole_credential(header, secrets):
                        yield from _references(header, f"{param_at}.{name}", secrets)
            else:
                yield from _references(item, param_at, secrets)


def _is_whole_credential(value: Any, secrets: frozenset[str]) -> bool:
    if not isinstance(value, str):
        return False
    full = patterns.EXPR_REF_FULL.match(value)
    return full is not None and root_of(full.group(1).strip()) in secrets


def _references(value: Any, where: str, secrets: frozenset[str]) -> Iterator[tuple[str, str]]:
    """``(where, reference)`` for each credential reference anywhere in *value*."""
    if isinstance(value, str):
        for match in patterns.EXPR_REF.finditer(value):
            if root_of(match.group(1).strip()) in secrets:
                yield where, root_of(match.group(1).strip())
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _references(item, f"{where}.{key}", secrets)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _references(item, f"{where}[{index}]", secrets)
