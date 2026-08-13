################################################################################
# Eclipse Tractus-X - Tractus-X TestLab
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""The join between two steps: one publishes, the next one reads.

This is the seam the per-step contract tests cannot see. Each step here is
already known to produce what it declares; what is under test is the name the
next step has to spell to get it, and whether spelling it wrong is noticed.
"""

from __future__ import annotations

import pytest

from combinations.harness import Harness

pytestmark = pytest.mark.asyncio


class TestTheExecutionNamespace:
    """A prior step is read as ``${{ execution.<id>.<field> }}``.

    That is what the syntax reference (§5.2) specifies and what the IDE emits.
    The engine published under ``steps.`` instead until this was tested: the
    reference resolved to nothing, and — worse — an unresolved reference is
    left as its own template text, so the *literal* string
    ``${{ execution.mint.uuid }}`` was handed to the next step as its value.
    """

    async def test_a_step_reads_the_previous_steps_return(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_uuid",
                "returns": {"uuid": {"type": "string"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.mint.uuid }}"},
                "returns": {"value": {"type": "string"}},
            },
        )

        minted = outcome.output("mint")["uuid"]
        assert outcome.output("echo") == minted

    async def test_the_reference_is_not_left_as_its_own_text(
        self, harness: Harness
    ) -> None:
        """The failure this guards against did not look like a failure."""
        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_uuid",
                "returns": {"uuid": {"type": "string"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.mint.uuid }}"},
            },
        )
        assert "${{" not in str(outcome.output("echo"))

    async def test_the_flat_name_resolves_too(self, harness: Harness) -> None:
        """``returns`` also publishes the bare name, for a single producer."""
        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_uuid",
                "returns": {"uuid": {"type": "string"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ env.uuid }}"},
            },
        )
        assert outcome.output("echo") == outcome.output("mint")["uuid"]

    async def test_a_second_producer_takes_the_flat_name_over(
        self, harness: Harness
    ) -> None:
        """Why the qualified form exists: the flat one is last-writer-wins."""
        outcome = await harness.run(
            {"id": "first", "uses": "util/generate_uuid", "returns": {"uuid": {"type": "string"}}},
            {"id": "second", "uses": "util/generate_uuid", "returns": {"uuid": {"type": "string"}}},
            {"id": "flat", "uses": "util/log", "with": {"value": "${{ env.uuid }}"}},
            {
                "id": "qualified",
                "uses": "util/log",
                "with": {"value": "${{ execution.first.uuid }}"},
            },
        )

        assert outcome.output("flat") == outcome.output("second")["uuid"]
        assert outcome.output("qualified") == outcome.output("first")["uuid"]


class TestWhatDoesNotResolve:
    """A name that was never published, and how loudly that is said."""

    async def test_only_a_declared_return_gets_the_qualified_name(
        self, harness: Harness
    ) -> None:
        """Without ``returns:``, the value exists — but only under its bare name.

        Every step publishes its own fields as it runs, so ``uuid`` is set
        either way. The ``execution.<id>.<field>`` name is what ``returns:``
        buys, and it is the only one a second producer cannot overwrite.
        """
        outcome = await harness.run(
            {"id": "mint", "uses": "util/generate_uuid"},
        )
        assert outcome.variables["uuid"]
        assert "execution.mint.uuid" not in outcome.variables

    async def test_a_name_the_step_never_declared_resolves_to_nothing(
        self, harness: Harness
    ) -> None:
        """``generate_uuid`` publishes ``uuid`` and nothing else.

        Reading its dropped ``generated_id`` alias must not quietly find the
        value under the old name.
        """
        outcome = await harness.run(
            {
                "id": "mint",
                "uses": "util/generate_uuid",
                "returns": {"generated_id": {"type": "string"}},
            },
        )
        assert outcome.variables["generated_id"] is None

    async def test_an_unresolved_reference_is_passed_on_as_its_own_text(
        self, harness: Harness
    ) -> None:
        """Documented, not endorsed — a hazard a script author should know.

        A reference to a step that never ran is not an error at run time: the
        template text itself becomes the value. The compiler is where this is
        caught (``returns`` names are checked there); at run time it survives as
        a string that looks nothing like the value it stands for.
        """
        outcome = await harness.run(
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.never_ran.uuid }}"},
            },
        )
        assert outcome.output("echo") == "${{ execution.never_ran.uuid }}"


class TestReadingInsideAnOutput:
    """A dotted ``returns`` name reaches into a structured output."""

    async def test_a_path_into_a_declared_output_publishes_the_inner_value(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "parse",
                "uses": "util/parse_kv",
                "with": {"input": "dspEndpoint=https://provider/api/dsp;id=urn:uuid:42"},
                "returns": {"value.id": {"type": "string"}},
            },
        )
        assert outcome.variables["value.id"] == "urn:uuid:42"

    async def test_the_inner_value_is_readable_by_the_next_step(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "parse",
                "uses": "util/parse_kv",
                "with": {"input": "dspEndpoint=https://provider/api/dsp;id=urn:uuid:42"},
                "returns": {"value.id": {"type": "string"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.parse.value.id }}"},
            },
        )
        assert outcome.output("echo") == "urn:uuid:42"


class TestPhasesPublishUnderTheirOwnName:
    """``setup``, ``execution`` and ``teardown`` each namespace their steps."""

    @pytest.mark.parametrize(
        ("phase", "namespace"),
        [("setup", "setup"), ("execution", "execution"), ("teardown", "teardown")],
    )
    async def test_a_phase_publishes_under_its_own_name(
        self, harness: Harness, phase: str, namespace: str
    ) -> None:
        outcome = await harness.run(
            {"id": "mint", "uses": "util/generate_uuid", "returns": {"uuid": {"type": "string"}}},
            phase=phase,
        )
        assert f"{namespace}.mint.uuid" in outcome.variables

    async def test_execution_reads_what_setup_published(
        self, harness: Harness
    ) -> None:
        """The ordinary shape of a TCK: set something up, then use it."""
        await harness.run(
            {"id": "mint", "uses": "util/generate_uuid", "returns": {"uuid": {"type": "string"}}},
            phase="setup",
        )
        outcome = await harness.run(
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ setup.mint.uuid }}"},
            },
        )
        assert outcome.output("echo") == harness.context.get_variable("setup.mint.uuid")
