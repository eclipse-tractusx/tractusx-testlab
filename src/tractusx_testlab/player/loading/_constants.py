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

"""YAML key constants and defaults used by the local parser."""

# --- YAML key names (avoids SDK syntax dependency) ---
K_TYPE, K_NAME, K_VERSION, K_DESCRIPTION = "type", "name", "version", "description"
K_KIND, K_PARAMS, K_EXPECT, K_SERVICES = "kind", "params", "validate", "services"
K_VARIABLES, K_SETUP, K_STEPS, K_TEARDOWN = "variables", "setup", "steps", "teardown"
K_OUTPUTS = "outputs"
K_IMPORT, K_IMPORTS, K_TESTS = "import", "imports", "tests"
K_DATASPACE_VERSION, K_ALLOW_SDK_CALLS = "dataspace_version", "allow_sdk_calls"
K_BASE_URL, K_AUTH = "base_url", "auth"
K_TIMEOUT_S, K_STORE_IN_MEMORY, K_IF = "timeout_s", "store_in_memory", "if"
K_PATH, K_VALUE, K_SOURCE, K_SEVERITY = "path", "value", "source", "severity"

DEFAULT_ASSERTION_TYPE, DEFAULT_ASSERTION_SEVERITY = "EXACT", "HARD"
DEFAULT_ASSERTION_SOURCE, DEFAULT_NAME = "INLINE", ""
DEFAULT_VERSION, DEFAULT_SERVICE_TYPE, DEFAULT_BASE_URL = "1.0", "CONNECTOR_CONSUMER", ""

# Maps deprecated YAML service types to SDK-compatible enum values
SERVICE_TYPE_ALIASES: dict[str, str] = {
    "EDC_CONNECTOR_SATURN": "CONNECTOR_CONSUMER",
    "EDC_CONNECTOR_JUPITER": "CONNECTOR_CONSUMER",
    "EDC_CONNECTOR": "CONNECTOR_CONSUMER",
    "DIGITAL_TWIN_REGISTRY": "DTR",
    "DISCOVERY_FINDER": "DTR",
}
