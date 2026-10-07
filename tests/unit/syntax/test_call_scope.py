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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""``syntax.call_scope`` — reading a call-scoped reference, and into what it names."""

from __future__ import annotations

import pytest

from tractusx_testlab.config.settings import TestlabConfig as Settings
from tractusx_testlab.models import Job, UnresolvedReferenceError
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.loading.resolver import resolve_str
from tractusx_testlab.services.instances import ServiceManager
from tractusx_testlab.syntax import call_scope

_VARIABLES = {
    "*.request.body": {"header": {"messageId": "m-1"}, "items": [{"id": "a"}, {"id": "b"}]},
    "*.process.answer.value": {"requestStatus": "COMPLETED"},
}


def _lookup(reference: str) -> object:
    return call_scope.lookup(reference, _VARIABLES.__contains__, _VARIABLES.__getitem__)


class TestLookup:
    def test_a_variable_named_whole_is_its_value(self) -> None:
        assert _lookup("*.process.answer.value") == {"requestStatus": "COMPLETED"}

    def test_a_path_reaches_into_the_longest_variable_it_starts_with(self) -> None:
        assert _lookup("*.request.body.header.messageId") == "m-1"

    def test_a_number_indexes_a_list(self) -> None:
        assert _lookup("*.request.body.items.1.id") == "b"

    def test_a_key_the_value_lacks_is_missing(self) -> None:
        assert _lookup("*.request.body.header.nope") is call_scope.MISSING

    def test_an_index_past_the_end_is_missing(self) -> None:
        assert _lookup("*.request.body.items.2") is call_scope.MISSING

    def test_a_root_nothing_published_is_missing(self) -> None:
        assert _lookup("*.process.other.value") is call_scope.MISSING


class TestNames:
    @pytest.mark.parametrize("reference", ["*.request.body", "*.process.x.value"])
    def test_a_star_reference_is_call_scoped(self, reference: str) -> None:
        assert call_scope.is_call_scoped(reference)

    @pytest.mark.parametrize("reference", ["execution.x.value", "env.request", "request.body"])
    def test_any_other_reference_is_not(self, reference: str) -> None:
        assert not call_scope.is_call_scoped(reference)

    def test_every_request_field_has_a_root(self) -> None:
        assert call_scope.request_roots() == {
            "*.request.body",
            "*.request.headers",
            "*.request.query",
            "*.request.method",
            "*.request.path",
        }


class TestTheResolverReadsThem:
    @pytest.fixture()
    def context(self) -> StepContext:
        context = StepContext(ServiceManager(), Job(job_id="j"), Settings())
        for name, value in _VARIABLES.items():
            context.set_variable(name, value)
        context.set_variable("execution.doc.value", {"id": "d"})
        return context

    def test_a_path_into_a_call_scoped_value_resolves(self, context: StepContext) -> None:
        assert resolve_str("${{ *.request.body.header.messageId }}", context) == "m-1"

    def test_it_interpolates_like_any_reference(self, context: StepContext) -> None:
        assert resolve_str("urn:uuid:${{ *.request.body.items.0.id }}", context) == "urn:uuid:a"

    def test_a_path_that_leads_nowhere_is_unresolved(self, context: StepContext) -> None:
        with pytest.raises(UnresolvedReferenceError):
            resolve_str("${{ *.request.body.header.nope }}", context)

    def test_any_other_reference_still_names_a_variable_whole(self, context: StepContext) -> None:
        with pytest.raises(UnresolvedReferenceError):
            resolve_str("${{ execution.doc.value.id }}", context)
