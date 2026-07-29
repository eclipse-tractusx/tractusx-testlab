#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# distributed under the License is distributed on an "AS IS" BASIS
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Opus 4.6).
## It was reviewed and tested by a human committer.

"""Declarative function-key naming: canonical keys resolve and match legacy aliases."""

from __future__ import annotations

import pytest

import tractusx_testlab.steps  # noqa: F401 — trigger @step registrations
from tractusx_testlab.scripting.registry import StepRegistry

_DATASPACE = "saturn"

# Canonical function key -> legacy flat alias that must resolve to the same class.
_FUNCTION_KEY_ALIASES = {
    "connector/provider/create_asset": "create_asset",
    "connector/provider/create_policy": "create_policy",
    "connector/provider/create_contract_definition": "create_contract_definition",
    "connector/provider/delete_asset": "delete_asset",
    "connector/provider/delete_policy": "delete_policy",
    "connector/provider/delete_contract_definition": "delete_contract_definition",
    "connector/consumer/query_catalog": "query_catalog",
    "connector/consumer/query_catalog_by_asset_id": "query_catalog_by_asset_id",
    "connector/consumer/query_catalog_by_bpnl": "query_catalog_by_bpnl",
    "connector/consumer/query_catalog_with_filters": "query_catalog_with_filters",
    "connector/consumer/negotiate": "negotiate_contract",
    "connector/consumer/transfer": "transfer_data",
    "connector/consumer/extract_dataset": "extract_dataset",
    "connector/consumer/do_dsp": "do_dsp",
    "connector/consumer/do_dsp_with_bpnl": "do_dsp_with_bpnl",
    "connector/consumer/pull_data_filtered": "pull_data_filtered",
    "connector/consumer/pull_data_filtered_by_policy": "pull_data_filtered_by_policy",
    "connector/dataplane/http_request": "dataplane_call",
    "connector/dataplane/get_edr": "get_edr",
    "http/http_request": "http_request",
    "mock/api": "mock_endpoint",
    "mock/wait/http_request": "wait_for_call",
    "industry/notification/send": "send_notification",
    "industry/notification/discover_assets": "discover_notification_assets",
    "industry/dtr/create_shell_descriptor": "create_shell_descriptor",
    "industry/dtr/get_shell_descriptor": "get_shell_descriptor",
    "industry/dtr/create_submodel_descriptor": "create_submodel_descriptor",
    "industry/dtr/delete_shell_descriptor": "delete_shell_descriptor",
    "industry/semantic/validate": "validate_semantic_schema",
    "industry/submodel/upload_backend_data": "upload_backend_data",
    "util/json_path_extract": "json_path_extract",
    "util/load_schema": "load_schema",
    "util/generate_uuid": "generate_uuid",
    "util/export_variable": "export_variable",
    "util/import_variable": "import_variable",
}


class TestFunctionKeys:
    @pytest.mark.parametrize("function_key", sorted(_FUNCTION_KEY_ALIASES))
    def test_canonical_function_key_is_registered(self, function_key: str) -> None:
        step_cls = StepRegistry.get(function_key, _DATASPACE)

        assert step_cls is not None, f"Function key '{function_key}' is not registered"

    @pytest.mark.parametrize(
        "function_key,legacy_alias", sorted(_FUNCTION_KEY_ALIASES.items())
    )
    def test_legacy_alias_resolves_to_same_class(
        self, function_key: str, legacy_alias: str
    ) -> None:
        canonical_cls = StepRegistry.get(function_key, _DATASPACE)
        alias_cls = StepRegistry.get(legacy_alias, _DATASPACE)

        assert alias_cls is canonical_cls, (
            f"Legacy alias '{legacy_alias}' must resolve to the same class as "
            f"function key '{function_key}'"
        )
