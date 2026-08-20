################################################################################
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
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Fable 5).
## It was reviewed and tested by a human committer.

"""Every ratified operator, run as a real assertion on a real step's output.

``apply_operator`` is unit-tested on plain values. That is not the same claim:
an operator reaches a script through a ``uses`` string, a ``with`` block and an
``input`` naming a declared return, and each of those is somewhere it can be
lost. The IDE offers a dropdown of these twenty; this is what says all twenty
survive the trip.

The parametrisation is derived from the engine's own operator set, so an
operator added without a case here fails :meth:`test_every_ratified_operator_is_covered`
rather than quietly going untested.
"""

from __future__ import annotations

import pytest

from combinations.harness import Harness
from combinations.http_double import HttpDouble
from tractusx_testlab.steps.assertions.operators import OPERATORS, RANGE_OPERATORS

pytestmark = pytest.mark.asyncio

#: A document with something for each operator to bite on.
SUBJECT = {
    "state": "FINALIZED",
    "attempts": 3,
    "items": ["a", "b"],
    "empty": "",
    "missing": None,
    "id": "urn:uuid:1234",
}

#: ``operator`` → the ``with`` block that makes it hold against SUBJECT.
HOLDS: dict[str, dict] = {
    "equals": {"path": "state", "value": "FINALIZED"},
    "not_equals": {"path": "state", "value": "TERMINATED"},
    "not_null": {"path": "state"},
    "is_null": {"path": "missing"},
    "not_empty": {"path": "state"},
    "contains": {"path": "id", "value": "urn:uuid:"},
    "not_contains": {"path": "id", "value": "urn:bpn:"},
    "one_of": {"path": "state", "value": ["FINALIZED", "COMPLETED"]},
    "none_of": {"path": "state", "value": ["TERMINATED", "ERROR"]},
    "matches_regex": {"path": "id", "value": r"^urn:uuid:[0-9a-f]+$"},
    "gt": {"path": "attempts", "value": 2},
    "gte": {"path": "attempts", "value": 3},
    "lt": {"path": "attempts", "value": 4},
    "lte": {"path": "attempts", "value": 3},
    "has_key": {"value": "state"},
    "not_has_key": {"value": "nonesuch"},
    "length_equals": {"path": "items", "value": 2},
    "length_gt": {"path": "items", "value": 1},
    "length_lt": {"path": "items", "value": 5},
    "between": {"path": "attempts", "min": 1, "max": 5},
}

#: ``operator`` → a ``with`` block that must *not* hold, so a pass is a real pass.
FAILS: dict[str, dict] = {
    "equals": {"path": "state", "value": "TERMINATED"},
    "not_equals": {"path": "state", "value": "FINALIZED"},
    "not_null": {"path": "missing"},
    "is_null": {"path": "state"},
    "not_empty": {"path": "empty"},
    "contains": {"path": "id", "value": "urn:bpn:"},
    "not_contains": {"path": "id", "value": "urn:uuid:"},
    "one_of": {"path": "state", "value": ["TERMINATED"]},
    "none_of": {"path": "state", "value": ["FINALIZED"]},
    "matches_regex": {"path": "id", "value": r"^bpnl:"},
    "gt": {"path": "attempts", "value": 3},
    "gte": {"path": "attempts", "value": 4},
    "lt": {"path": "attempts", "value": 3},
    "lte": {"path": "attempts", "value": 2},
    "has_key": {"value": "nonesuch"},
    "not_has_key": {"value": "state"},
    "length_equals": {"path": "items", "value": 5},
    "length_gt": {"path": "items", "value": 9},
    "length_lt": {"path": "items", "value": 1},
    "between": {"path": "attempts", "min": 10, "max": 20},
}


def _step(url: str, operator: str, extra: dict) -> dict:
    """An HTTP step whose ``validate:`` block runs one operator on the body."""
    return {
        "id": "fetch",
        "uses": "http/http_request",
        "with": {"method": "GET", "url": url},
        "returns": {"response_body": {"type": "object"}},
        "validate": [
            {
                "uses": f"validate/field/{operator}",
                "with": {"input": "response_body", **extra},
            }
        ],
    }


class TestTheOperatorVocabularyIsComplete:
    async def test_every_ratified_operator_is_covered(self) -> None:
        assert set(HOLDS) == OPERATORS
        assert set(FAILS) == OPERATORS

    async def test_the_range_operator_is_the_only_one_taking_two_bounds(self) -> None:
        """A dropdown pairing one operator with one value can offer the rest."""
        two_bound = {op for op, params in HOLDS.items() if "min" in params}
        assert two_bound == set(RANGE_OPERATORS)


class TestEveryOperatorAsARealAssertion:
    """Each operator, on the body of a real response, both ways round."""

    @pytest.mark.parametrize("operator", sorted(OPERATORS))
    async def test_the_operator_passes_when_it_should(
        self, harness: Harness, http: HttpDouble, operator: str
    ) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()

        outcome = await harness.run(_step(f"{base}/subject", operator, HOLDS[operator]))

        assert outcome.passed, outcome.assertion_messages("fetch")

    @pytest.mark.parametrize("operator", sorted(OPERATORS))
    async def test_the_operator_fails_when_it_should(
        self, harness: Harness, http: HttpDouble, operator: str
    ) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()

        outcome = await harness.run(_step(f"{base}/subject", operator, FAILS[operator]))

        assert not outcome.passed, f"{operator!r} passed on a case it must reject"
        assert outcome.assertion_messages("fetch")[0], "a failure must say why"


class TestBothSpellingsOfAnOperator:
    """``validate/field/equals`` and ``validate/field`` + ``operator:`` agree."""

    @pytest.mark.parametrize("operator", sorted(OPERATORS - RANGE_OPERATORS))
    async def test_the_suffix_and_the_operator_key_mean_the_same(
        self, harness: Harness, http: HttpDouble, operator: str
    ) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()
        params = HOLDS[operator]

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/subject"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": f"validate/field/{operator}",
                        "with": {"input": "response_body", **params},
                    },
                    {
                        "uses": "validate/field",
                        "with": {
                            "input": "response_body",
                            "operator": operator,
                            **params,
                        },
                    },
                ],
            }
        )

        assert outcome.passed, outcome.assertion_messages("fetch")


class TestAnAssertionThatCannotBeUnderstood:
    """An unusable assertion fails loudly instead of passing quietly."""

    async def test_an_unknown_operator_fails_and_lists_the_known_ones(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()

        outcome = await harness.run(
            _step(f"{base}/subject", "approximately", {"path": "state", "value": "F"})
        )

        assert not outcome.passed
        message = outcome.assertion_messages("fetch")[0]
        assert "approximately" in message
        assert "equals" in message

    async def test_an_unknown_check_names_the_three_that_exist(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/subject"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "assert/status_code",
                        "with": {"input": "response_body", "value": 200},
                    }
                ],
            }
        )

        assert not outcome.passed
        message = outcome.assertion_messages("fetch")[0]
        assert "validate/assert" in message
        assert "validate/field" in message
        assert "validate/schema" in message

    async def test_between_without_both_bounds_fails_and_says_so(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()

        outcome = await harness.run(
            _step(f"{base}/subject", "between", {"path": "attempts", "min": 1})
        )

        assert not outcome.passed
        assert "max" in outcome.assertion_messages("fetch")[0]


class TestAssertingAgainstAnEarlierStep:
    """An assertion compares against a value another step produced.

    The comparison value is written the way every other value in a script is
    written — ``${{ env.<name> }}``.  It used to be spelled ``@name`` here and
    dereferenced inside the assertion engine alone, which made the engine the one
    place in the system where a fourth reference syntax was understood.
    """

    async def test_a_response_is_checked_against_a_generated_id(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("POST", "/twins", {"id": "urn:uuid:fixed"})
        base = http.start()
        harness.seed(expected_id="urn:uuid:fixed")

        outcome = await harness.run(
            {
                "id": "create",
                "uses": "http/http_request",
                "with": {"method": "POST", "url": f"{base}/twins", "body": {}},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/field/equals",
                        "with": {
                            "input": "response_body",
                            "path": "id",
                            "value": "${{ env.expected_id }}",
                        },
                    }
                ],
            }
        )

        assert outcome.passed, outcome.assertion_messages("create")


class TestSchemaValidationInAChain:
    """``validate/schema`` checks a response the previous step fetched."""

    _SCHEMA = {
        "type": "object",
        "required": ["state", "attempts"],
        "properties": {
            "state": {"type": "string"},
            "attempts": {"type": "integer"},
        },
    }

    async def test_a_conforming_response_passes(self, harness: Harness, http: HttpDouble) -> None:
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()
        harness.seed(**{"env.schemas.state_schema": self._SCHEMA})

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/subject"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/schema",
                        "with": {"input": "response_body", "schema": self._SCHEMA},
                    }
                ],
            }
        )

        assert outcome.passed, outcome.assertion_messages("fetch")

    async def test_a_response_missing_a_required_field_fails(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/subject", {"state": "FINALIZED"})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/subject"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/schema",
                        "with": {"input": "response_body", "schema": self._SCHEMA},
                    }
                ],
            }
        )

        assert not outcome.passed
        assert "attempts" in outcome.assertion_messages("fetch")[0]


class TestAnAssertionReferencesWhatTheRunProduced:
    """``${{ … }}`` inside a ``validate:`` block resolves like anywhere else.

    Only the step's own ``with:`` used to be resolved. An assertion comparing
    against an earlier step's return, or naming a schema declared in ``env``,
    therefore received its own template text — and reported a mismatch against
    a string nobody wrote, which reads exactly like a real failure of the
    system under test.
    """

    async def test_a_value_reference_is_resolved_before_comparing(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        http.json_route("GET", "/state", {"id": "part-1"})
        base = http.start()
        harness.seed(expected_id="part-1")

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/state"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/field/equals",
                        "with": {
                            "input": "response_body",
                            "path": "id",
                            "value": "${{ env.expected_id }}",
                        },
                    }
                ],
            }
        )

        assert outcome.passed, outcome.assertion_messages("fetch")

    async def test_a_mismatch_reports_the_resolved_value_not_the_reference(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """The message a TCK author reads has to name what was compared."""
        http.json_route("GET", "/state", {"id": "part-2"})
        base = http.start()
        harness.seed(expected_id="part-1")

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/state"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/field/equals",
                        "with": {
                            "input": "response_body",
                            "path": "id",
                            "value": "${{ env.expected_id }}",
                        },
                    }
                ],
            }
        )

        message = outcome.assertion_messages("fetch")[0]
        assert "part-1" in message and "part-2" in message
        assert "${{" not in message

    async def test_an_earlier_steps_return_is_comparable(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """A reference resolves the name a ``returns:`` block declared.

        ``response_body.id`` is declared as such, so it exists as a name. A
        reference is a flat lookup, not a walk — see the test below.
        """
        http.json_route("POST", "/parts", {"id": "part-1"}, status=201)
        http.json_route("GET", "/parts", {"id": "part-1"})
        base = http.start()

        outcome = await harness.run(
            {
                "id": "create",
                "uses": "http/http_request",
                "with": {"method": "POST", "url": f"{base}/parts", "body": {}},
                "returns": {"response_body.id": {"type": "string"}},
            },
            {
                "id": "read_back",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/parts"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/field/equals",
                        "with": {
                            "input": "response_body",
                            "path": "id",
                            "value": "${{ execution.create.response_body.id }}",
                        },
                    }
                ],
            },
        )

        assert outcome.passed, outcome.assertion_messages("read_back")

    async def test_a_schema_declared_in_env_is_resolved(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """``${{ env.schemas.<id> }}`` is the form the IDE documents and emits."""
        http.json_route("GET", "/subject", SUBJECT)
        base = http.start()
        harness.seed(
            **{
                "schemas.state_schema": {
                    "type": "object",
                    "required": ["state", "attempts"],
                }
            }
        )

        outcome = await harness.run(
            {
                "id": "fetch",
                "uses": "http/http_request",
                "with": {"method": "GET", "url": f"{base}/subject"},
                "returns": {"response_body": {"type": "object"}},
                "validate": [
                    {
                        "uses": "validate/schema",
                        "with": {
                            "input": "response_body",
                            "schema": "${{ env.schemas.state_schema }}",
                        },
                    }
                ],
            }
        )

        assert outcome.passed, outcome.assertion_messages("fetch")

    async def test_a_path_not_declared_in_returns_does_not_resolve(
        self, harness: Harness, http: HttpDouble
    ) -> None:
        """A reference is a name, not a path — the walk happens in ``returns:``.

        ``${{ execution.create.response_body.id }}`` finds nothing unless
        ``response_body.id`` was declared, because resolution looks the whole
        dotted string up as one key. It used to resolve to its own template text
        and flow on as data; it now fails the step and names the reference, which
        is the difference between a typo the author sees and one they do not.
        """
        http.json_route("POST", "/parts", {"id": "part-1"}, status=201)
        base = http.start()

        outcome = await harness.run(
            {
                "id": "create",
                "uses": "http/http_request",
                "with": {"method": "POST", "url": f"{base}/parts", "body": {}},
                "returns": {"response_body": {"type": "object"}},
            },
            {
                "id": "echo",
                "uses": "util/log",
                "with": {"value": "${{ execution.create.response_body.id }}"},
            },
        )

        assert not outcome.passed
        assert "execution.create.response_body.id" in (outcome.error("echo") or "")
