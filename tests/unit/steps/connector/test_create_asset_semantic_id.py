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

"""An asset's semantic id is spelled out for the SDK, not handed to it.

tractusx-sdk 0.8.2's ``build_properties`` raises ``NameError`` on any asset
with a ``semantic_id`` (E2E run 34633071862), so the step writes the property
and the context prefix the SDK would have written, and passes no
``semantic_id`` at all.
"""

from __future__ import annotations

from tractusx_testlab.steps.connector.provision.asset import CreateAssetParams

_SEMANTIC_ID = "urn:samm:io.catenax.serial_part:3.0.0#SerialPart"
_AAS_SEMANTICS = "https://admin-shell.io/aas/3/0/HasSemantics/"


def _definition(asset: dict) -> dict:
    return CreateAssetParams(asset=asset).definition()


class TestSemanticId:
    def test_it_becomes_the_property_and_the_prefix(self) -> None:
        definition = _definition({"base_url": "http://b", "semantic_id": _SEMANTIC_ID})
        assert definition["properties"] == {"aas-semantics:semanticId": {"@id": _SEMANTIC_ID}}
        assert definition["context"]["aas-semantics"] == _AAS_SEMANTICS
        assert "semantic_id" not in definition

    def test_the_default_context_is_kept_alongside(self) -> None:
        """Sending a context replaces the SDK's default, so the default rides along."""
        context = _definition({"base_url": "http://b", "semantic_id": _SEMANTIC_ID})["context"]
        assert context["edc"] == "https://w3id.org/edc/v0.0.1/ns/"
        assert context["cx-taxo"] == "https://w3id.org/catenax/taxonomy#"
        assert context["dct"] == "http://purl.org/dc/terms/"

    def test_a_declared_context_is_kept_too(self) -> None:
        context = _definition(
            {"base_url": "http://b", "semantic_id": _SEMANTIC_ID, "@context": {"x": "http://x#"}}
        )["context"]
        assert context["x"] == "http://x#"
        assert context["aas-semantics"] == _AAS_SEMANTICS

    def test_without_one_nothing_is_added(self) -> None:
        definition = _definition({"base_url": "http://b"})
        assert definition["properties"] is None
        assert definition["context"] is None
