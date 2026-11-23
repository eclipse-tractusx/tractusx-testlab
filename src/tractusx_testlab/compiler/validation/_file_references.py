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

"""Checking a variable that names an ``env`` file instead of carrying a value.

A ``config/testdata/register`` variable is another name for a test data file
(:func:`tractusx_testlab.syntax.variables.reference_of`). What it may say is
narrow — one whole reference to a file the manifest declares — and is checked
here, apart from the rules for variables that carry their own value.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from tractusx_testlab.syntax import keys, patterns
from tractusx_testlab.syntax.variables import VariableVerb


def declared_asset_ids(env_data: dict[str, Any]) -> dict[str, set[str]]:
    """The ids each ``env`` asset block a variable may name declares, by block."""
    ids: dict[str, set[str]] = {}
    for block in ("testdata",):
        entries = env_data.get(block)
        if isinstance(entries, dict):
            ids[block] = {str(name) for name in entries}
        elif isinstance(entries, list):
            ids[block] = {
                str(item[keys.ID])
                for item in entries
                if isinstance(item, dict) and item.get(keys.ID)
            }
        else:
            ids[block] = set()
    return ids


def check_reference(
    entry: dict[str, Any], var_id: str, verb: VariableVerb, declared: set[str]
) -> Iterator[str]:
    """Check that a variable naming a file names one ``env`` declares, and only that.

    The variable carries no value and asks nobody for one: it is another name
    for the file. So ``with`` holds the reference alone, the reference is the
    whole of it, and the file it names is one the manifest declares — a
    misspelt id would otherwise compile and fail as an unresolved reference at
    the first step that read the variable.
    """
    block = verb.refers_to
    expected = f"'with: {{ ref: ${{{{ env.{block}.<id> }}}} }}'"
    with_block = entry.get(keys.WITH)
    if not isinstance(with_block, dict) or keys.REF not in with_block:
        yield (
            f"Variable '{var_id}' is a '{verb.uses}' with no 'with.ref'. It names "
            f"the file it stands for: write {expected}."
        )
        return
    extra = sorted(str(key) for key in with_block if key != keys.REF)
    if extra:
        yield (
            f"Variable '{var_id}' is a '{verb.uses}', which takes only 'with.ref' — "
            f"the file is its value — but also has '{', '.join(extra)}'. Write {expected}."
        )
    ref = with_block[keys.REF]
    full = patterns.EXPR_REF_FULL.match(ref) if isinstance(ref, str) else None
    path = full.group(1).strip() if full else ""
    prefix = f"env.{block}."
    if not path.startswith(prefix) or "." in path[len(prefix) :]:
        yield (
            f"Variable '{var_id}' has 'with.ref: {ref}', which is not a reference "
            f"to one file under env.{block}. Write {expected}."
        )
        return
    target = path[len(prefix) :]
    if target not in declared:
        known = ", ".join(sorted(declared)) or "none"
        yield (
            f"Variable '{var_id}' refers to 'env.{block}.{target}', which env.{block} "
            f"does not declare (declared: {known})."
        )
