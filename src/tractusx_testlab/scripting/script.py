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

"""Runtime wrappers around parsed definitions with execution helpers."""

from __future__ import annotations

from pathlib import Path

from tractusx_testlab.models.authoring.definitions import (
    ScriptDefinition,
    TckDefinition,
    VariableDefinition,
)
from tractusx_testlab.models.authoring.infrastructure import InfrastructureConfig
from tractusx_testlab.models.runtime.inspection import TckInspectionResult
from tractusx_testlab.scripting._infrastructure import collect_infrastructure_requirements
from tractusx_testlab.scripting._inspection import build_inspection_result
from tractusx_testlab.scripting._variable_form import parse_variables_block
from tractusx_testlab.syntax import defaults


class TestScript:
    """Runtime wrapper for a single script definition."""

    __test__ = False  # Prevent pytest from collecting this class
    __slots__ = ("_skippable", "_test_id", "definition")

    def __init__(
        self,
        definition: ScriptDefinition,
        *,
        skippable: bool = False,
        test_id: str = "",
    ):
        """Initialize with a parsed script definition."""
        self.definition = definition
        self._skippable = skippable
        self._test_id = test_id

    @property
    def skippable(self) -> bool:
        """Whether the operator is allowed to skip this test at runtime."""
        return self._skippable

    @property
    def test_id(self) -> str:
        """The manifest entry filename (e.g. 'test-request.yaml') used for skip matching."""
        return self._test_id

    @property
    def name(self) -> str:
        """Script name from the definition metadata."""
        return self.definition.metadata.name

    @property
    def dataspace_version(self) -> str:
        """The ecosystem release this script runs against.

        Read from the ``dataspace:`` block, which is the only place it is
        stated; the flat field of the same name is gone. Used to pick a
        version-specific step implementation from the registry.
        """
        dataspace = self.definition.dataspace
        return dataspace.version if dataspace is not None else defaults.DATASPACE_VERSION

    @property
    def steps(self):
        """List of step definitions for the main execution phase."""
        return self.definition.execution

    @property
    def setup(self):
        """List of setup step definitions."""
        return self.definition.setup

    @property
    def teardown(self):
        """List of teardown step definitions."""
        return self.definition.teardown

    def step_count(self) -> int:
        """Return how many steps this script runs, across all three phases.

        Setup and teardown are steps: they invoke the same catalog, publish
        under the same rules and can fail the script. Counting only
        ``execution`` made ``testlab run`` announce "Steps: 2" for a run that
        went on to execute five, and gave the progress bar a total it passed.
        """
        return (
            len(self.definition.setup)
            + len(self.definition.execution)
            + len(self.definition.teardown)
        )

    @property
    def definition_version(self) -> str:
        """Test suite version from metadata."""
        return self.definition.metadata.version


class Tck:
    """Runtime wrapper for a TCK definition."""

    __slots__ = ("_scripts", "base_dir", "definition")

    def __init__(self, definition: TckDefinition, base_dir: Path | None = None):
        """Initialize with a TCK definition and optional base directory."""
        self.definition = definition
        self.base_dir = base_dir
        self._scripts: list[TestScript] = []

    @property
    def name(self) -> str:
        """TCK package name."""
        return self.definition.metadata.name

    @property
    def version(self) -> str:
        """TCK version string."""
        return self.definition.metadata.version

    @property
    def scripts(self) -> list[TestScript]:
        """List of wrapped test scripts in this TCK."""
        return self._scripts

    @property
    def id(self) -> str:
        """TCK ID from the manifest (used for logging and event payloads)."""
        return self.definition.id

    def script_count(self) -> int:
        """Return the number of scripts in this TCK."""
        return len(self._scripts)

    def total_steps(self) -> int:
        """Return the total step count across all scripts."""
        return sum(script.step_count() for script in self._scripts)

    def all_variables(self) -> dict[str, VariableDefinition]:
        """Return all variables declared in the TCK env block.

        Variables with ``runtime=True`` must be supplied by the caller at
        execution time.  Variables with a ``default`` value are optional.
        """
        raw = self.definition.env.variables if self.definition.env else None
        return parse_variables_block(raw)

    def required_variables(self) -> dict[str, VariableDefinition]:
        """Return only the variables that must be provided at runtime.

        A variable is required when it has ``source=input`` (i.e. ``runtime=True``)
        and no default value.  Use this to validate an incoming request before
        calling :py:meth:`~tractusx_testlab.player.execution.player.TestlabPlayer.run_tck`.
        """
        return {
            name: var
            for name, var in self.all_variables().items()
            if var.runtime and var.default is None
        }

    def inspect(self) -> TckInspectionResult:
        """Extract static metadata from this TCK without executing any steps.

        Returns general metadata (name, total steps, total validations) and
        per-step metadata (name, ``uses`` identifier, phase) for every script.

        Returns:
            A frozen :class:`~tractusx_testlab.models.runtime.inspection.TckInspectionResult`.
        """
        return build_inspection_result(self)

    def infrastructure_requirements(self) -> InfrastructureConfig:
        """Extract consolidated infrastructure requirements from this TCK.

        Returns the TCK-level ``infrastructure:`` block when present. Otherwise
        merges per-script ``infrastructure:`` blocks: ``required=True`` wins and
        the first non-``None`` standard wins per capability key.

        Returns:
            Merged :class:`~tractusx_testlab.models.authoring.infrastructure.InfrastructureConfig`;
            an empty config when nothing is declared.
        """
        return collect_infrastructure_requirements(self)

    def skippable_tests(self) -> list[str]:
        """Return the test IDs of scripts marked ``skippable: true`` in the TCK manifest.

        These are the IDs an operator may legally pass via the ``skip_tests``
        runtime variable to omit a test from a run.
        """
        return [s.test_id for s in self._scripts if s.skippable]

    @classmethod
    def from_single_script(
        cls,
        script_def: ScriptDefinition,
        base_dir: Path | None = None,
    ) -> Tck:
        """Wrap a single ScriptDefinition in a minimal TckDefinition and return a Tck."""
        from tractusx_testlab.models.authoring.definitions import (
            TckDefinition,
            TckMetadataDefinition,
        )

        tck_def = TckDefinition(
            kind="tck",
            syntax="v1-alpha",
            id=script_def.id,
            metadata=TckMetadataDefinition(
                name=script_def.metadata.name,
                description=script_def.metadata.description,
                version=script_def.metadata.version,
            ),
            tests=[],
        )
        instance = cls(tck_def, base_dir=base_dir)
        instance._scripts = [TestScript(script_def, skippable=False, test_id=script_def.id)]
        return instance
