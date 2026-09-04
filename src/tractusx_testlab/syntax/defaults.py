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

"""Default values applied when optional YAML fields are omitted."""

# -- Document defaults --------------------------------------------------------
VERSION = "1.0"
DATASPACE_VERSION = "saturn"
NAME = ""
BASE_URL = ""

# -- Assertion defaults -------------------------------------------------------
ASSERTION_TYPE = "EXACT"
ASSERTION_SEVERITY = "HARD"
VALUE_SOURCE = "INLINE"

# -- Service defaults ---------------------------------------------------------
SERVICE_TYPE = "CONNECTOR_CONSUMER"
DMA_PATH = "/management"
# The AAS Part 2 registry API. `/api/v3.0` is the path the AAS specification
# used before it renumbered the prefix, and the one this constant held; no
# Tractus-X registry answers on it. The DTR's own OpenAPI document declares
# `version_prefix` with default `v3` and an enum that admits nothing else, and
# the registry chart's shipped test suite drives `/api/v3/shell-descriptors`.
AAS_API_PATH = "/api/v3"
