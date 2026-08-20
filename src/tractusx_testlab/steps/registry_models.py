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

"""The AAS shapes both Digital Twin Registry step families are written in.

``DtrParams``, ``DescriptorPayload``, ``SpecificAssetId`` and
``ShellLookupOutput`` describe the Asset Administration Shell, not a side of
it — the provider registers a descriptor and the consumer reads one back, and
it is the same descriptor. They were declared twice, verbatim in both modules,
so a change to what a lookup returns had to be made in two places and was one
edit away from meaning two different things.

The readers that go with them are next door in
:mod:`tractusx_testlab.steps.registry_reading`.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from tractusx_sdk.dataspace.tools import encode_as_base64_url_safe

from tractusx_testlab.steps.shared_models import StepParams
from tractusx_testlab.steps.step_contract import StepPayload


class DtrParams(StepParams):
    """What every Digital Twin Registry step accepts.

    ``bpn`` selects the tenant the registry answers for; left out, the AAS
    service uses whatever it was configured with.
    """

    bpn: str | None = Field(
        default=None, description="BPN the registry request is made on behalf of."
    )


class DescriptorPayload(StepPayload):
    """An AAS descriptor as the registry returned it.

    The shape is defined by the AAS specification rather than by testlab, so
    the two keys every descriptor carries are named and the rest of the
    document round-trips untouched.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = Field(default=None, description="Identifier of the descriptor.")
    # The AAS API spells it ``idShort``; scripts read ``id_short`` and nothing
    # else, so the camelCase form is accepted on the way in and never written
    # on the way out.
    id_short: str | None = Field(
        default=None,
        validation_alias="idShort",
        description="Short, human-readable name.",
    )


def _as_document(result: Any) -> Any:
    """Render an SDK descriptor object as the plain document a script reads."""
    return result.to_dict() if hasattr(result, "to_dict") else result


class SpecificAssetId(BaseModel):
    """One ``specificAssetIds`` criterion a shell is searched by.

    Defined by the AAS specification rather than by testlab, so the two keys a
    lookup always sends are named and anything else — ``externalSubjectId`` for
    a criterion visible to one partner only — round-trips untouched.
    """

    model_config = ConfigDict(extra="allow")

    name: str = Field(description="Name of the asset identifier, e.g. 'partInstanceId'.")
    value: str = Field(description="Value that identifier must have.")


def _asset_ids_query(criteria: list[SpecificAssetId]) -> list[str]:
    """The criteria as the ``assetIds`` query values ``GET /lookup/shells`` expects.

    Each criterion travels as its own base64url-encoded JSON object — that is
    the AAS v3 encoding, not a testlab convention — and it is the same encoding
    whichever registry is being searched, so both sides read it from here.
    """
    return [
        encode_as_base64_url_safe(json.dumps(entry.model_dump(exclude_none=True)))
        for entry in criteria
    ]


class ShellLookupOutput(StepPayload):
    """Shells a registry read returned.

    The one output shape of every step that answers with a collection of shells,
    so a script reads ``shell_ids`` and ``shell_descriptors`` the same way
    whether the shells were searched for or listed, and whether the registry
    searched was the run's own or a counterparty's.
    """

    shell_ids: list[str] = Field(
        default_factory=list, description="Identifiers of the shells that matched."
    )
    shell_descriptors: list[dict] = Field(
        default_factory=list,
        description="The descriptor document of each matching shell.",
    )
