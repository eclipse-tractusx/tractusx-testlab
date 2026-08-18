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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Skip-resolution helper — validates operator-requested skip IDs against the TCK.

Extracted from ``player.py`` to keep each module under 300 lines and to isolate
the pure skip-validation logic from the execution coordinator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tractusx_testlab.models.primitives.exceptions import SkipNotAllowedError

if TYPE_CHECKING:
    from tractusx_testlab.scripting.script import Tck


def resolve_skip_ids(tck: Tck, runtime_vars: dict | None) -> frozenset[str]:
    """Return the resolved set of test IDs to skip, validating each is allowed.

    Reads the ``skip_tests`` key from *runtime_vars* and cross-references it
    against the TCK's test entries.  Raises :class:`SkipNotAllowedError` before
    any test executes when:

    * A requested ID does not exist in the TCK's test list.
    * A requested ID exists but the entry is not marked ``skippable: true``.

    Args:
        tck: The loaded TCK to validate against.
        runtime_vars: Optional runtime variable dict that may contain ``skip_tests``
            (a list of test-file IDs such as ``["test-cert.yaml"]``).

    Returns:
        Frozen set of test IDs the player must skip during this run.

    Raises:
        SkipNotAllowedError: If any requested test ID is unknown or not skippable.
    """
    raw = (runtime_vars or {}).get("skip_tests") or []
    if not raw:
        return frozenset()

    skip_ids: list[str] = list(raw) if not isinstance(raw, str) else [raw]

    all_test_ids = {s.test_id for s in tck.scripts}
    skippable_ids = {s.test_id for s in tck.scripts if s.skippable}

    unknown = [sid for sid in skip_ids if sid not in all_test_ids]
    if unknown:
        raise SkipNotAllowedError(unknown, reason="not found in TCK tests list")

    not_allowed = [sid for sid in skip_ids if sid not in skippable_ids]
    if not_allowed:
        raise SkipNotAllowedError(not_allowed)

    return frozenset(skip_ids)
