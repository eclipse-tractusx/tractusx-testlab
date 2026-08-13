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

``util/generate_uuid`` is the producer throughout: it needs nothing, and it
answers differently every call, which is what makes "the second producer took
the name over" a fact rather than a coincidence.
"""

from __future__ import annotations

import pytest

from combinations.harness import Harness

pytestmark = pytest.mark.asyncio


def _mint(step_id: str = "mint") -> dict:
    """A producer step declaring one return."""
    return {
        "id": step_id,
        "uses": "util/generate_uuid",
        "returns": {"value": {"type": "string"}},
    }


class TestTheExecutionNamespace:
    """A prior step is read as ``${{ execution.<id>.<field> }}``.

    That is what the syntax reference (§5.2) specifies and what the IDE emits.
    The engine published under ``steps.`` instead until this was tested: the
    reference resolved to nothing, and — worse — an unresolved reference is
    left as its own template text, so the *literal* string
    ``${{ execution.mint.value }}`` was handed to the next step as its value.
    """

    async def test_a_step_reads_the_previous_steps_return(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            _mint(),
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.mint.value }}"},
            },
        )

        assert outcome.output("echo") == outcome.output("mint")

    async def test_the_reference_is_not_left_as_its_own_text(
        self, harness: Harness
    ) -> None:
        """The failure this guards against did not look like a failure."""
        outcome = await harness.run(
            _mint(),
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.mint.value }}"},
            },
        )
        assert "${{" not in str(outcome.output("echo"))

    async def test_the_flat_name_resolves_too(self, harness: Harness) -> None:
        """A step's field is also readable under its bare name."""
        outcome = await harness.run(
            _mint(),
            {"id": "echo", "uses": "util/log", "with": {"value": "${{ env.value }}"}},
        )
        assert outcome.output("echo") == outcome.output("mint")

    async def test_a_second_producer_takes_the_flat_name_over(
        self, harness: Harness
    ) -> None:
        """Why the qualified form exists: the flat one is last-writer-wins."""
        outcome = await harness.run(
            _mint("first"),
            _mint("second"),
            {"id": "flat", "uses": "util/log", "with": {"value": "${{ env.value }}"}},
            {
                "id": "qualified",
                "uses": "util/log",
                "with": {"value": "${{ execution.first.value }}"},
            },
        )

        assert outcome.output("flat") == outcome.output("second")
        assert outcome.output("qualified") == outcome.output("first")


class TestWhatDoesNotResolve:
    """A name that was never published, and how loudly that is said."""

    async def test_only_a_declared_return_gets_the_qualified_name(
        self, harness: Harness
    ) -> None:
        """Without ``returns:``, the value exists — but only under its bare name.

        A step with an object payload publishes each of its fields as it runs,
        so ``full_mock_url`` is set either way. The ``execution.<id>.<field>``
        name is what ``returns:`` buys, and it is the only one a second
        producer cannot overwrite.
        """
        outcome = await harness.run(
            {"id": "endpoint", "uses": "mock/api", "with": {"path": "/callback"}}
        )

        assert outcome.variables["full_mock_url"]
        assert "execution.endpoint.full_mock_url" not in outcome.variables

    async def test_a_bare_value_has_no_field_name_to_publish_under(
        self, harness: Harness
    ) -> None:
        """Which is why ``returns:`` is the only way to name one.

        ``util/generate_uuid`` returns the UUID itself, not an object with a
        field in it, so there is nothing to publish flatly — the value is
        reachable through ``returns:`` and through assertions, and nowhere else.
        """
        outcome = await harness.run({"id": "mint", "uses": "util/generate_uuid"})

        assert outcome.output("mint")
        assert "value" not in outcome.variables

    async def test_a_name_the_step_never_declared_resolves_to_nothing(
        self, harness: Harness
    ) -> None:
        """A guess at a step's internals must not find anything."""
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
                "with": {"value": "${{ execution.never_ran.value }}"},
            },
        )
        assert outcome.output("echo") == "${{ execution.never_ran.value }}"


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
        outcome = await harness.run(_mint(), phase=phase)
        assert f"{namespace}.mint.value" in outcome.variables

    async def test_execution_reads_what_setup_published(
        self, harness: Harness
    ) -> None:
        """The ordinary shape of a TCK: set something up, then use it."""
        await harness.run(_mint(), phase="setup")
        outcome = await harness.run(
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ setup.mint.value }}"},
            },
        )
        assert outcome.output("echo") == harness.context.get_variable("setup.mint.value")


class TestAWithKeyTheStepDoesNotDeclare:
    """An unknown ``with:`` key is refused, not dropped.

    This is what makes the IDE↔engine parameter check worth running: if a block
    emitted a parameter the engine had since renamed, the step fails outright
    rather than running on with the value silently discarded.
    """

    async def test_an_unknown_parameter_fails_the_step(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "parse",
                "uses": "util/parse_kv",
                "with": {"input": "a=1", "seperator": ";"},
            },
        )

        assert not outcome.passed
        assert "seperator" in (outcome.error("parse") or "")

    async def test_the_error_names_the_step_it_came_from(
        self, harness: Harness
    ) -> None:
        outcome = await harness.run(
            {
                "id": "parse",
                "uses": "util/parse_kv",
                "with": {"input": "a=1", "nonesuch": 1},
            },
        )
        assert "util/parse_kv" in (outcome.error("parse") or "")
