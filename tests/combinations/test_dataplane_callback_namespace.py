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
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0
################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: OpenAI Codex, Model: GPT-5.5).
## It was reviewed and tested by a human committer.

"""Exercise the shipped callback provisioning through the guarded HTTP boundary."""

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from tractusx_sdk.dataspace.services.connector.service_factory import ServiceFactory

from combinations.connector_double import ProviderDouble
from combinations.harness import Harness
from combinations.http_double import HttpDouble, Response
from tractusx_testlab.config.settings import TestlabConfig as LabConfig
from tractusx_testlab.models import Job, ServiceType, StepStatus
from tractusx_testlab.models.domain.infrastructure import Infrastructure
from tractusx_testlab.player.execution.context import StepContext
from tractusx_testlab.player.execution.dataspace_access import ENGINE_PROVIDER_SERVICE
from tractusx_testlab.server.mock_registry import clear_callback_manager, clear_mocks
from tractusx_testlab.services.instances import ServiceManager

pytestmark = pytest.mark.asyncio

_ROOT = Path("tests/e2e/connector-dtr-smoke")
_BPN = "BPNL000000000001"
_EDC_ID = "https://w3id.org/edc/v0.0.1/ns/id"


class _EngineServices(ServiceManager):
    """Keep the mock asset on the engine provider, not a SUT provider."""

    def __init__(self, provider: ProviderDouble) -> None:
        super().__init__()
        self.provider = provider

    def get(self, name: str, expected_type: ServiceType | None = None) -> object:
        if name == ENGINE_PROVIDER_SERVICE and expected_type == ServiceType.CONNECTOR_PROVIDER:
            return self.provider
        return super().get(name, expected_type)


@pytest.fixture(autouse=True)
def isolated_mocks() -> Iterator[None]:
    clear_mocks()
    clear_callback_manager()
    try:
        yield
    finally:
        clear_mocks()
        clear_callback_manager()


@pytest.fixture
def scenario() -> dict:
    return yaml.safe_load((_ROOT / "tests/dataplane_callback.yaml").read_text(encoding="utf-8"))


@pytest.fixture(params=["testlab:callback-regression:", "another-engine:run-b:"])
def callback_harness(request: pytest.FixtureRequest, http: HttpDouble) -> Harness:
    prefix = str(request.param)
    http.route(
        "POST",
        "/management/v3/policydefinitions",
        Response(body={"@id": prefix + "returned-access"}),
        Response(body={"@id": prefix + "returned-usage"}),
    )
    http.json_route(
        "POST", "/management/v3/contractdefinitions", {"@id": prefix + "returned-contract"}
    )
    root = http.start()
    base = root + "/management"
    # Agreement retirement goes through the SDK's management adapter, so the
    # engine provider double carries a real one aimed at the HTTP double.
    provider = ProviderDouble()
    provider.dma_adapter = ServiceFactory.get_connector_provider_service(
        dataspace_version="saturn",
        base_url=root,
        dma_path="/management",
        headers={"X-Api-Key": "offline-key"},
    ).dma_adapter
    context = StepContext(
        services=_EngineServices(provider),
        job=Job(job_id="callback-regression"),
        config=LabConfig(),
        infrastructure=Infrastructure.model_validate(
            {"engine": {"connector": {"management_url": base, "api_key": "offline-key"}}}
        ),
        resource_prefix=prefix,
    )
    harness = Harness(context)
    harness.seed(
        **{
            "execution.id": context.job.job_id,
            "execution.resource_prefix": prefix,
            "engine_bpnl": _BPN,
            "mock_server_external_url": "http://mock.local",
            "infrastructure.engine.connector.management_url": base,
            "infrastructure.engine.connector.api_key": "offline-key",
        }
    )
    context.seal("execution.resource_prefix")
    manifest = yaml.safe_load((_ROOT / "index.yaml").read_text(encoding="utf-8"))
    asset = next(v for v in manifest["env"]["variables"] if v["id"] == "callback_asset")
    context.set_template("callback_asset", asset["with"]["value"])
    # No setup output from an earlier scenario may satisfy this test's references.
    assert not any(name.startswith("setup.") for name in context.variables)
    return harness


async def test_shipped_setup_and_teardown_use_the_guarded_run_namespace(
    callback_harness: Harness, http: HttpDouble, scenario: dict
) -> None:
    opened = await callback_harness.run(*scenario["setup"], phase="setup")
    assert opened.passed, [(r.step_name, r.error) for r in opened.failures]
    assert len(http.received) == 3

    access, usage, contract = (call.body for call in http.received)
    prefix = callback_harness.context.resource_prefix
    assert all(body["@id"].startswith(prefix) for body in (access, usage, contract))
    access_id = opened.output("access_policy_id")
    usage_id = opened.output("usage_policy_id")
    contract_id = opened.output("contract_definition_id")
    assert (access_id, usage_id, contract_id) == (
        prefix + "returned-access",
        prefix + "returned-usage",
        prefix + "returned-contract",
    )
    assert all(
        returned != submitted["@id"]
        for returned, submitted in zip(
            (access_id, usage_id, contract_id), (access, usage, contract), strict=True
        )
    )
    assert contract["accessPolicyId"] == access_id
    assert contract["contractPolicyId"] == usage_id
    permission = access["policy"]["permission"]
    assert permission == [
        {
            "action": "access",
            "constraint": [
                {
                    "leftOperand": "BusinessPartnerNumber",
                    "operator": "isAnyOf",
                    "rightOperand": [_BPN],
                }
            ],
        }
    ]
    asset_id = opened.output("create_asset")["asset_id"]
    assert asset_id.startswith(prefix)
    assert contract["assetsSelector"] == [
        {"operandLeft": _EDC_ID, "operator": "like", "operandRight": prefix + "%"},
        {"operandLeft": _EDC_ID, "operator": "=", "operandRight": asset_id},
    ]

    deletes = [
        "/management/v3/contractdefinitions/" + contract_id,
        "/management/v3/assets/" + asset_id,
        "/management/v3/policydefinitions/" + usage_id,
        "/management/v3/policydefinitions/" + access_id,
    ]
    for path in deletes:
        http.json_route("DELETE", path, {})
    agreements = "/management/v3/contractagreements"
    http.json_route("POST", agreements + "/request", [{"@id": "agreement-1", "assetId": asset_id}])
    http.json_route("POST", agreements + "/retirements", None, status=204)
    closed = await callback_harness.run(*scenario["teardown"], phase="teardown")
    assert closed.passed, [(r.step_name, r.error) for r in closed.failures]
    # Agreements are retired after the contract definition is withdrawn and
    # before the asset they name is deleted: once by asset, once by ID.
    assert [(call.method, call.path) for call in http.received[3:]] == [
        ("DELETE", deletes[0]),
        ("POST", agreements + "/request"),
        ("POST", agreements + "/retirements"),
        ("POST", agreements + "/retirements"),
        *(("DELETE", path) for path in deletes[1:]),
    ]
    assert closed.output("retire_asset_agreements")["agreement_ids"] == ["agreement-1"]


async def test_missing_asset_setup_output_cannot_be_satisfied_by_another_scenario(
    callback_harness: Harness, http: HttpDouble, scenario: dict
) -> None:
    contract = next(step for step in scenario["setup"] if step["id"] == "create_contract")
    callback_harness.context.set_variable(
        "setup.access_policy_id.value", callback_harness.context.resource_prefix + "returned-access"
    )
    callback_harness.context.set_variable(
        "setup.usage_policy_id.value", callback_harness.context.resource_prefix + "returned-usage"
    )
    outcome = await callback_harness.run(contract, phase="setup")
    assert not outcome.passed
    assert "setup.create_asset.asset_id" in (outcome.error("create_contract") or "")
    assert http.received == []


@pytest.mark.parametrize("response_body", [{}, {"@id": None}])
async def test_invalid_creation_response_never_guesses_ids_for_contract_or_cleanup(
    callback_harness: Harness, http: HttpDouble, scenario: dict, response_body: dict
) -> None:
    http.json_route("POST", "/management/v3/policydefinitions", response_body)
    opened = await callback_harness.run(*scenario["setup"], phase="setup")
    assert not opened.passed
    assert opened.result("access_policy_id").status == StepStatus.FAILED
    assert opened.result("usage_policy_id").status == StepStatus.FAILED
    assert all(call.path != "/management/v3/contractdefinitions" for call in http.received)

    policy_cleanup = [
        step
        for step in scenario["teardown"]
        if step["id"] in {"delete_access_policy", "delete_usage_policy", "delete_contract"}
    ]
    closed = await callback_harness.run(*policy_cleanup, phase="teardown")
    assert not closed.passed
    assert all(call.method == "POST" for call in http.received)
