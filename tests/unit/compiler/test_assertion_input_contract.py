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

"""A ``validate.with.input`` must name something the step actually publishes.

The check used to key off the step's ``returns:`` block, which is optional — so
a step without one was not checked at all, and an input naming nothing was
extracted as ``None``, compared, and reported as the SUT failing.

The bound is what extraction will resolve, not what looks tidy: a step whose
output *is* the SUT's document publishes keys nobody can enumerate, and those
stay nameable.
"""

from __future__ import annotations

from tractusx_testlab.compiler.validation.validator import ScriptValidator
from tractusx_testlab.models import ScriptDefinition, StepDefinition


def _errors_for(uses: str, input_name: str, returns: dict | None = None) -> list[str]:
    step = StepDefinition(
        id="s1",
        uses=uses,
        returns=returns,
        validate=[
            {"uses": "validate/assert", "with": {"input": input_name, "operator": "not_null"}}
        ],
    )
    script = ScriptDefinition(
        syntax="v1-alpha",
        kind="test",
        id="t",
        namespace="n",
        metadata={"name": "t"},
        execution=[step],
    )
    result = ScriptValidator().validate(script)
    return [issue.message for issue in result.issues if issue.level == "error"]


class TestAssertionInputsAreChecked:
    def test_a_step_without_returns_still_has_its_input_checked(self) -> None:
        errors = _errors_for("connector/consumer/get_edr", "fetch_data")
        assert len(errors) == 1
        assert "fetch_data" in errors[0]

    def test_the_error_names_what_the_step_does_publish(self) -> None:
        errors = _errors_for("connector/consumer/get_edr", "fetch_data")
        assert "edr_token" in errors[0]

    def test_a_universal_response_field_is_accepted_without_returns(self) -> None:
        assert _errors_for("connector/consumer/get_edr", "status_code") == []

    def test_a_declared_output_is_accepted_without_returns(self) -> None:
        assert _errors_for("connector/consumer/get_edr", "edr_token") == []

    def test_a_path_into_a_declared_output_is_accepted(self) -> None:
        assert _errors_for("connector/consumer/get_edr", "data_address.endpoint") == []

    def test_an_output_outside_a_narrower_returns_block_is_still_accepted(self) -> None:
        # `returns:` names what the script wants to reuse later. It does not
        # narrow what the engine can extract, so it must not narrow what an
        # assertion may name either.
        assert (
            _errors_for(
                "connector/consumer/get_edr",
                "status_code",
                {"edr_token": {"type": "string"}},
            )
            == []
        )

    def test_an_unknown_step_is_not_second_guessed(self) -> None:
        # The unknown-step error is the finding; guessing at its outputs is not.
        errors = _errors_for("no/such/step", "whatever")
        assert all("validate.with.input" not in message for message in errors)


class TestPathsThatResolveAreNotRefused:
    """The check must agree with what extraction will actually resolve."""

    def test_a_predicate_on_the_first_segment_is_accepted(self) -> None:
        # `datasets` is published; the predicate selects within it, and its
        # value may contain the dots a naive split would shred.
        assert (
            _errors_for("connector/consumer/query_catalog", "datasets[assetId='urn:x.y'].id") == []
        )

    def test_a_step_publishing_an_open_document_accepts_any_name(self) -> None:
        # `notification/consumer/send` spreads the receiver's answer at the top
        # level, so its keys cannot be listed ahead of time.
        assert _errors_for("notification/consumer/send", "notificationId") == []

    def test_a_closed_output_model_is_still_checked(self) -> None:
        errors = _errors_for("connector/consumer/query_catalog", "not_a_real_output")
        assert len(errors) == 1

    def test_the_synthetic_root_field_is_never_offered_as_a_name(self) -> None:
        # A root model's `root` names the document rather than anything in it,
        # and resolves to nothing at run time — the very silence being fixed.
        errors = _errors_for("connector/consumer/get_edr", "nope")
        assert "root" not in errors[0].split("It publishes:")[1]

    def test_a_step_returning_the_documents_own_keys_accepts_any_of_them(self) -> None:
        # `connector/dataplane/http_request` returns the response body itself,
        # and the runner publishes each of its keys as a context variable.
        assert _errors_for("connector/dataplane/http_request", "anything_the_sut_sent") == []
