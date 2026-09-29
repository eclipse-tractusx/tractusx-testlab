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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5.1).
## It was reviewed and tested by a human committer.

"""What a compilation reports while it runs — the stages, and each test it checks.

A compile of a real kit takes seconds: reading every test, checking it,
checking the manifest against the JSON schemas, building the execution plan,
packing the assets and sealing the archive. The CLI printed nothing until all
of it was done, so a person watching saw an empty console and could not tell a
slow compile from a stuck one.

The compiler says where it is through a :class:`CompileProgress`; how that is
shown is the caller's business (the CLI draws a spinner and a line per stage,
``cli._compile_report``). A caller that wants nothing gets :data:`SILENT`.
"""

from __future__ import annotations

from typing import Protocol


class CompileProgress(Protocol):
    """Receives a compilation's stages as they happen."""

    def stage(self, label: str, total: int | None = None) -> None:
        """A stage begins, ending the one before it. *total* counts its items, when known."""

    def item(self, label: str) -> None:
        """One item of the current stage begins — a test being checked."""

    def fail(self) -> None:
        """The stage under way failed; nothing follows it."""

    def finish(self) -> None:
        """The last stage has ended."""


class _Silent:
    """Progress nobody is shown."""

    __slots__ = ()

    def stage(self, label: str, total: int | None = None) -> None:
        pass

    def item(self, label: str) -> None:
        pass

    def fail(self) -> None:
        pass

    def finish(self) -> None:
        pass


#: The progress of a compilation nobody watches — the default everywhere.
SILENT: CompileProgress = _Silent()
