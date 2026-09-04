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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""The e2e scenarios' setup and teardown, driven without a dataspace.

The offline drives that already exist run the `execution:` phase. That left the
two phases that provision and unprovision the SUT — four steps each, on both
connector scenarios — reachable only by building a Kubernetes cluster, which is
where the one bug this file would have caught went unnoticed: a `validate:` in
`setup:` fails the script before a single execution step runs, and the job says
only "exit code 1".

The provider double records the keywords the steps hand to the SDK, so what
these tests pin is the contract between testlab and `tractusx-sdk`: which
policy rules survive the rewrite into ODRL spelling, which id a definition is
published under, and that teardown asks for exactly the ids setup created.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from combinations.connector_double import ConsumerDouble, ProviderDouble, ServicesDouble
from combinations.harness import Harness, build_context

pytestmark = pytest.mark.asyncio

_TCK = Path("tests/e2e/connector-dtr-smoke")
_SCENARIOS = _TCK / "tests"

#: The two scenarios that provision their own SUT, and the asset each publishes.
_PROVISIONED = {
    "connector_negotiation.yaml": "testlab-e2e-smoke-asset",
    "dsp_step_by_step.yaml": "testlab-e2e-stepwise-asset",
}


def _scenario(name: str) -> dict:
    """The shipped scenario, read rather than restated."""
    return yaml.safe_load((_SCENARIOS / name).read_text(encoding="utf-8"))


def _env_variables() -> dict[str, Any]:
    """The manifest's `env:` entries, keyed the way a script addresses them."""
    manifest = yaml.safe_load((_TCK / "index.yaml").read_text(encoding="utf-8"))
    return {entry["id"]: entry["with"]["value"] for entry in manifest["env"]["variables"]}


def _harness(provider: ProviderDouble) -> Harness:
    """A harness whose provider is *provider* and whose consumer is never asked."""
    consumer = ConsumerDouble({"dcat:dataset": []}, "http://dataplane.invalid")
    harness = Harness(build_context(services=ServicesDouble(consumer, provider)))
    variables = _env_variables()
    harness.seed(**{f"env.{name}": value for name, value in variables.items()}, **variables)
    return harness


async def _run_phase(harness: Harness, name: str, phase: str):
    """Drive one phase of a scenario and return its step results."""
    return (await harness.run(*_scenario(name)[phase], phase=phase)).results


def _failures(results) -> list[str]:
    """Every reason a step in *results* did not pass, as a reader would see them."""
    reasons: list[str] = []
    for result in results:
        if result.error:
            reasons.append(f"{result.step_name}: {result.error}")
        reasons += [
            f"{result.step_name}: {check.message}"
            for check in result.assertions
            if not check.passed
        ]
    return reasons


@pytest.mark.parametrize("scenario", sorted(_PROVISIONED))
async def test_setup_provisions_the_sut_without_a_dataspace(scenario: str) -> None:
    """Every setup step passes its own assertions against the SDK's real surface."""
    provider = ProviderDouble()
    harness = _harness(provider)

    results = await _run_phase(harness, scenario, "setup")

    assert _failures(results) == [], f"{scenario} setup: {_failures(results)}"


@pytest.mark.parametrize("scenario,asset_id", sorted(_PROVISIONED.items()))
async def test_setup_publishes_the_asset_the_execution_phase_negotiates_for(
    scenario: str, asset_id: str
) -> None:
    """The asset id the catalog is later filtered on is the one setup created.

    A scenario that provisions one asset and queries for another still passes
    every setup assertion and then finds an empty catalog, which reads as a
    broken dataspace rather than as a typo.
    """
    provider = ProviderDouble()
    harness = _harness(provider)

    await _run_phase(harness, scenario, "setup")

    assert [created["asset_id"] for created in provider.created] == [asset_id]


async def test_a_policys_constraints_reach_the_connector_in_odrl_spelling() -> None:
    """Rules are handed over as `permission`/`constraint`, not `permissions`/`constraints`.

    The connector reads a policy as JSON-LD. A rule whose conditions sit under
    the plural key carries no constraint it can see, so it answers "policy must
    contain at least one permission" about a policy the manifest plainly wrote
    one into — and it does so only against a live connector.
    """
    provider = ProviderDouble()
    harness = _harness(provider)

    await _run_phase(harness, "dsp_step_by_step.yaml", "setup")

    registered = {policy["policy_id"]: policy for policy in provider.registered_policies}
    usage = registered["testlab-e2e-smoke-usage-policy"]
    assert usage["permissions"], "the usage policy reached the connector without a permission"
    assert usage["permissions"][0]["constraint"], "the permission carried no constraint"


async def test_teardown_removes_exactly_what_setup_created() -> None:
    """The ids teardown deletes are the ids setup returned, for both scenarios.

    Teardown reads `setup.<id>.<output>`, so renaming an output leaves the
    dataspace holding an asset, two policies and a contract definition that the
    next run then collides with — a failure attributed to the run after the one
    that caused it.
    """
    for scenario, asset_id in _PROVISIONED.items():
        provider = ProviderDouble()
        harness = _harness(provider)

        setup = await _run_phase(harness, scenario, "setup")
        teardown = await _run_phase(harness, scenario, "teardown")

        assert _failures(setup) == [], f"{scenario} setup: {_failures(setup)}"
        assert _failures(teardown) == [], f"{scenario} teardown: {_failures(teardown)}"
        assert provider.assets.deleted == [asset_id]
        assert sorted(provider.policies.deleted) == [
            "testlab-e2e-smoke-access-policy",
            "testlab-e2e-smoke-usage-policy",
        ]
        assert len(provider.contract_definitions.deleted) == 1


async def test_the_contract_definition_binds_both_policies_and_the_asset() -> None:
    """The published definition names the two policies setup registered.

    `create_contract_definition` builds the model itself rather than going
    through the SDK helper, so nothing but a test checks that the ids it was
    given are the ids it posts.
    """
    provider = ProviderDouble()
    harness = _harness(provider)

    await _run_phase(harness, "dsp_step_by_step.yaml", "setup")

    posted = provider.contract_definitions.posted
    assert len(posted) == 1
    body = posted[0].to_data()
    assert "testlab-e2e-smoke-access-policy" in body
    assert "testlab-e2e-smoke-usage-policy" in body
    assert "testlab-e2e-stepwise-asset" in body
