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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5.5).
## It was reviewed and tested by a human committer.

"""A step that negotiates must be told which offer: no filter is no choice.

``pull_data_filtered``, ``pull_data_filtered_by_policy``, ``do_dsp`` and
``do_dsp_with_bpnl`` negotiate the first offer of the provider's catalog that
passes their ``filters``. With no filter that is whatever the provider lists
first — another team's asset, an asset left from an earlier run, a different
one tomorrow — and the run negotiates for it, transfers it and reports on it
as if it were the asset the test meant. So a step with no filter is refused
before it asks for the catalog, unless the test says
``allow_any_offer: true``: an explicit "any offer will do". The compiler warns
about the same step, so the refusal is never the first anyone hears of it.
"""

from __future__ import annotations

from pydantic import Field

from tractusx_testlab.models.primitives.exceptions import AuthoringError
from tractusx_testlab.steps.shared_models import FilterExpressionParams

#: The parameter that waives the guard, as a test writes it.
ALLOW_ANY_OFFER = "allow_any_offer"


class AnyOfferRefusedError(AuthoringError):
    """A negotiating step was given no filter and not told any offer will do."""

    code = "OFFER_FILTER_MISSING"

    def __init__(self) -> None:
        super().__init__(
            "No 'filters' were given, so this step would negotiate whichever offer the "
            "provider's catalog lists first. Give 'filters' that select the asset (e.g. its "
            "id), or set 'allow_any_offer: true' if any offer really will do."
        )


class OfferFilterParams(FilterExpressionParams):
    """Catalog filters for a step that negotiates the offer they select."""

    allow_any_offer: bool = Field(
        default=False,
        description=(
            "Negotiate the first offer the catalog lists when no 'filters' are given. Off by "
            "default: without filters the step is refused, since any asset the provider "
            "lists first would be negotiated."
        ),
    )

    def require_offer_filter(self) -> None:
        """Refuse to pick an offer blindly, unless the test said any will do.

        Raises:
            AnyOfferRefusedError: no filter, and ``allow_any_offer`` not set.
        """
        if not self.filters and not self.allow_any_offer:
            raise AnyOfferRefusedError()
