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

"""Well-known context variable names used for inter-step data passing.

Every step publishes all of its return outputs: each top-level output field
becomes a context variable of the same name.  The constants here are the
names downstream steps read back as parameter fallbacks — they must match
the field names of the producing steps' output models, and using constants
prevents silent typo breakage.
"""

# Catalog query results
CATALOG_ASSET_ID = "catalog_asset_id"
CATALOG_POLICY = "catalog_policy"

# Contract negotiation
NEGOTIATION_ID = "negotiation_id"
AGREEMENT_ID = "agreement_id"

# Transfer / EDR
TRANSFER_ID = "transfer_id"
#: Data-plane URL a completed transfer returns; the only name for it.
DATAPLANE_URL = "dataplane_url"
EDR_TOKEN = "edr_token"

# DSP protocol (direct, non-management-API)
DSP_CATALOG = "dsp_catalog"
DSP_OFFER = "dsp_offer"
DSP_OFFER_ID = "dsp_offer_id"

# DSP negotiation state
DSP_NEGOTIATION_PROVIDER_PID = "dsp_negotiation_provider_pid"
DSP_NEGOTIATION_CONSUMER_PID = "dsp_negotiation_consumer_pid"
DSP_NEGOTIATION_STATE = "dsp_negotiation_state"
DSP_CONTRACT_AGREEMENT_ID = "contract_agreement_id"

# DSP transfer state
DSP_TRANSFER_PROVIDER_PID = "dsp_transfer_provider_pid"
DSP_TRANSFER_CONSUMER_PID = "dsp_transfer_consumer_pid"
DSP_TRANSFER_STATE = "dsp_transfer_state"
