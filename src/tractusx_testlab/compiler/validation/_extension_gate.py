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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Holding a test to the experimental extensions its TCK enabled.

An extension's keys and steps are ordinary syntax to the models, which is what
lets the IDE schema describe them. Whether a TCK may *use* them is decided here:
a key, a ``with:`` parameter or a ``labs/`` step from an extension the manifest
does not list is an error, and an enabled extension runs its own checks.
"""

from __future__ import annotations

from typing import Any

from tractusx_testlab.compiler.validation.issues import ValidationIssue
from tractusx_testlab.extensions import EXTENSIONS, Extension
from tractusx_testlab.extensions.extension import written_steps
from tractusx_testlab.models import TckDefinition, TestDefinition
from tractusx_testlab.steps.step_extension import extensions_for


def experimental_warnings(tck: TckDefinition) -> list[ValidationIssue]:
    """One warning per enabled extension, so no one certifies on one unawares."""
    return [
        ValidationIssue(
            level="warning",
            message=(
                f"index.yaml enables the experimental extension '{name}' — "
                f"{EXTENSIONS[name].summary} It may change or be removed before it is "
                f"ratified."
            ),
            field="extensions",
        )
        for name in tck.extensions
    ]


def extension_findings(tck: TckDefinition, test: TestDefinition) -> list[ValidationIssue]:
    """Every use of an extension *tck* did not enable, and every enabled one's findings."""
    enabled = set(tck.extensions)
    issues: list[ValidationIssue] = []
    for phase, idx, step in written_steps(test):
        for extension in EXTENSIONS.values():
            if extension.name in enabled:
                continue
            for field, used in _uses_of(extension, step):
                issues.append(
                    ValidationIssue(
                        level="error",
                        message=(
                            f"{used} comes from the experimental extension "
                            f"'{extension.name}', which this TCK does not enable. Add "
                            f"'extensions: [{extension.name}]' to index.yaml to use it."
                        ),
                        step_index=idx,
                        field=field,
                        phase=phase,
                    )
                )
    for name in tck.extensions:
        check = EXTENSIONS[name].check
        if check is None:
            continue
        issues += [
            ValidationIssue(
                level="error",
                message=finding.message,
                step_index=finding.step_index,
                field=finding.field,
                phase=finding.phase,
            )
            for finding in check(tck, test)
        ]
    return issues


def _uses_of(extension: Extension, step: dict[str, Any]) -> list[tuple[str, str]]:
    """What in *step* belongs to *extension*, as (field, how the author wrote it)."""
    used = [(key, f"'{key}:'") for key in sorted(extension.step_keys & step.keys())]
    for check in step.get("validate") or []:
        if isinstance(check, dict):
            keys = sorted(extension.validation_keys & check.keys())
            used += [(f"validate.{key}", f"'{key}:' on a validation") for key in keys]
    uses = str(step.get("uses", ""))
    params = step.get("with") or {}
    for extension_cls in extensions_for(uses):
        if extension_cls.extension == extension.name:
            keys = sorted(extension_cls.param_keys() & params.keys())
            used += [(f"with.{key}", f"'{key}:' under 'with:' of '{uses}'") for key in keys]
    if extension.step_prefix and uses.startswith(extension.step_prefix):
        used.append(("uses", f"The step '{uses}'"))
    return used
