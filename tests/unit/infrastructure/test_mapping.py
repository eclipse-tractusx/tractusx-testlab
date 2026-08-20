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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""Unit tests for the three surfaces of an infrastructure binding."""

from __future__ import annotations

import pytest

from tractusx_testlab.infrastructure.mapping import (
    apply_overrides,
    capabilities,
    collect_overrides,
    context_key,
    env_key,
    flatten,
    known_keys,
    merge,
    overrides_from_env,
)
from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    InfrastructureConfig,
)
from tractusx_testlab.models.domain.infrastructure import (
    DtrBinding,
    EngineBindings,
    EngineDtrBinding,
    Infrastructure,
    SutBindings,
    SutConnectorBinding,
)
from tractusx_testlab.models.primitives.binding_errors import UnknownBindingKeyError


def _bound_sut() -> Infrastructure:
    return Infrastructure(
        sut=SutBindings(
            connector=SutConnectorBinding(
                management_url="https://sut.example.com/management",
                dsp_url="https://sut.example.com/api/v1/dsp",
            ),
        ),
    )


class TestKeyDerivation:
    """Every surface is generated from the model, so none can drift from another."""

    def test_every_field_has_a_context_key(self) -> None:
        assert "infrastructure.sut.connector.dsp_url" in known_keys()

    def test_multi_word_field_keeps_its_underscore(self) -> None:
        assert "infrastructure.engine.dtr.submodel_base_url" in known_keys()

    def test_env_key_is_the_upper_case_path(self) -> None:
        assert env_key("engine", "dtr", "submodel_base_url") == (
            "TESTLAB_ENGINE_DTR_SUBMODEL_BASE_URL"
        )

    def test_context_key_is_the_prefixed_path(self) -> None:
        assert context_key("sut", "dtr", "base_url") == "infrastructure.sut.dtr.base_url"

    def test_a_tck_can_require_every_capability_the_engine_can_bind(self) -> None:
        """The requirement vocabulary is the binding model — the two cannot drift.

        A capability the engine binds but no TCK can ask for is one whose absence
        surfaces as an empty URL mid-run instead of a named missing binding.
        """
        from tractusx_testlab.models.authoring.infrastructure import InfrastructureConfig

        declared: dict[str, dict[str, dict[str, bool]]] = {}
        for side, capability, _ in capabilities():
            declared.setdefault(side, {})[capability] = {"required": True}

        requirements = InfrastructureConfig.model_validate(declared)

        for side, capability, _ in capabilities():
            assert getattr(requirements, side)[capability].required


class TestFlatten:
    """A bound deployment is projected into the variable namespace, and only it."""

    def test_bound_fields_are_projected(self) -> None:
        projected = flatten(_bound_sut())
        assert projected["infrastructure.sut.connector.dsp_url"] == (
            "https://sut.example.com/api/v1/dsp"
        )

    def test_unbound_capability_projects_nothing(self) -> None:
        projected = flatten(_bound_sut())
        assert not any(key.startswith("infrastructure.sut.dtr.") for key in projected)

    def test_defaults_of_an_unbound_capability_are_not_published(self) -> None:
        """An api_key_header for a connector that does not exist is noise."""
        projected = flatten(Infrastructure())
        assert projected == {}

    def test_defaults_of_a_bound_capability_are_published(self) -> None:
        projected = flatten(_bound_sut())
        assert projected["infrastructure.sut.connector.api_key_header"] == "x-api-key"


class TestCollectOverrides:
    """Binding overrides are picked out of a variable store, and typos are named."""

    def test_binding_keys_are_collected(self) -> None:
        collected = collect_overrides(
            {"infrastructure.sut.dtr.base_url": "https://dtr.example.com", "other": "x"}
        )
        assert collected == {"infrastructure.sut.dtr.base_url": "https://dtr.example.com"}

    def test_the_seeded_service_name_is_not_a_binding(self) -> None:
        """``infrastructure.sut.connector`` is a service name written back by the seeder."""
        assert collect_overrides({"infrastructure.sut.connector": "__sut_connector__"}) == {}

    def test_a_misspelled_field_is_rejected(self) -> None:
        with pytest.raises(UnknownBindingKeyError) as error:
            collect_overrides({"infrastructure.sut.connector.managment_url": "x"})
        assert "managment_url" in str(error.value)

    def test_rejection_suggests_the_closest_legal_key(self) -> None:
        with pytest.raises(UnknownBindingKeyError) as error:
            collect_overrides({"infrastructure.sut.connector.dspurl": "x"})
        assert "Did you mean" in str(error.value)
        assert "infrastructure.sut.connector.dsp_url" in str(error.value)

    def test_rejection_names_what_this_tck_needs_and_not_the_whole_model(self) -> None:
        """The list beside a typo is the run's obligations, not every legal key."""
        requirements = InfrastructureConfig(
            sut={"connector": CapabilityRequirement(required=True)},
        )
        with pytest.raises(UnknownBindingKeyError) as error:
            collect_overrides({"infrastructure.sut.connector.typo": "x"}, requirements)
        message = str(error.value)
        assert "infrastructure.sut.connector.dsp_url" in message
        assert "infrastructure.sut.connector.participant_id" in message
        # A capability this TCK never asked for is not the operator's problem.
        assert "infrastructure.engine.dtr.submodel_base_url" not in message

    def test_an_unknown_side_is_rejected(self) -> None:
        with pytest.raises(UnknownBindingKeyError):
            collect_overrides({"infrastructure.other.connector.base_url": "x"})


class TestApplyOverrides:
    """Overrides win, and the deployment they are applied to is left alone."""

    def test_override_wins(self) -> None:
        resolved = apply_overrides(
            _bound_sut(), {"infrastructure.sut.connector.dsp_url": "https://other/api/v1/dsp"}
        )
        assert resolved.sut.connector.dsp_url == "https://other/api/v1/dsp"

    def test_original_is_untouched(self) -> None:
        original = _bound_sut()
        apply_overrides(original, {"infrastructure.sut.connector.dsp_url": "https://other"})
        assert original.sut.connector.dsp_url == "https://sut.example.com/api/v1/dsp"

    def test_unrelated_fields_survive(self) -> None:
        resolved = apply_overrides(
            _bound_sut(), {"infrastructure.sut.dtr.base_url": "https://dtr.example.com"}
        )
        assert resolved.sut.connector.management_url == "https://sut.example.com/management"

    def test_non_string_values_are_stored_as_text(self) -> None:
        resolved = apply_overrides(
            Infrastructure(), {"infrastructure.sut.connector.participant_id": 42}
        )
        assert resolved.sut.connector.participant_id == "42"

    def test_unknown_key_is_rejected(self) -> None:
        with pytest.raises(UnknownBindingKeyError):
            apply_overrides(Infrastructure(), {"infrastructure.sut.connector.nope": "x"})


class TestOverridesFromEnv:
    """The environment is read by generated name, never by splitting one apart."""

    def test_reads_a_binding_field(self) -> None:
        overrides = overrides_from_env({"TESTLAB_SUT_DTR_BASE_URL": "https://dtr.example.com"})
        assert overrides == {"infrastructure.sut.dtr.base_url": "https://dtr.example.com"}

    def test_reads_a_multi_word_field(self) -> None:
        overrides = overrides_from_env(
            {"TESTLAB_ENGINE_DTR_SUBMODEL_BASE_URL": "https://backend.example.com"}
        )
        assert overrides == {
            "infrastructure.engine.dtr.submodel_base_url": "https://backend.example.com"
        }

    def test_ignores_unrelated_variables(self) -> None:
        assert overrides_from_env({"TESTLAB_SERVER_PORT": "8100"}) == {}


class TestMerge:
    """Layering states what a layer was given, never what it defaults to."""

    def test_overlay_field_wins(self) -> None:
        base = _bound_sut()
        overlay = Infrastructure(sut=SutBindings(dtr=DtrBinding(base_url="https://dtr")))
        assert merge(base, overlay).sut.dtr.base_url == "https://dtr"

    def test_base_survives_where_the_overlay_is_silent(self) -> None:
        base = _bound_sut()
        overlay = Infrastructure(sut=SutBindings(dtr=DtrBinding(base_url="https://dtr")))
        assert merge(base, overlay).sut.connector.dsp_url == ("https://sut.example.com/api/v1/dsp")

    def test_a_default_never_overwrites_a_stated_value(self) -> None:
        base = Infrastructure(
            sut=SutBindings(
                connector=SutConnectorBinding(
                    management_url="https://sut/management",
                    api_key_header="X-Custom",
                ),
            ),
        )
        overlay = Infrastructure(
            sut=SutBindings(connector=SutConnectorBinding(api_key="secret")),
        )
        merged = merge(base, overlay)
        assert merged.sut.connector.api_key_header == "X-Custom"
        assert merged.sut.connector.api_key == "secret"

    def test_engine_and_sut_layer_independently(self) -> None:
        base = Infrastructure(
            engine=EngineBindings(
                dtr=EngineDtrBinding(submodel_base_url="https://backend"),
            ),
        )
        merged = merge(base, _bound_sut())
        assert merged.engine.dtr.submodel_base_url == "https://backend"
        assert merged.sut.connector.management_url == "https://sut.example.com/management"
