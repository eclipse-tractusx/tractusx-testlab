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

"""What static validation found — the findings, and the verdict they add up to."""

from __future__ import annotations

from dataclasses import dataclass, field


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
