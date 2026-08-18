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
## This code was partially generated using artificial intelligence (AI) (Tool: Copilot, Model: Claude Sonnet 4.6).
## It was reviewed and tested by a human committer.

"""Helper to consolidate InfrastructureConfig requirements from a Tck instance."""

from __future__ import annotations

from collections.abc import Iterable

from tractusx_testlab.models.authoring.infrastructure import (
    CapabilityRequirement,
    InfrastructureConfig,
)


def merge_requirements(configs: Iterable[InfrastructureConfig]) -> InfrastructureConfig:
    """Merge per-script requirement blocks into the one a run is checked against.

    ``required=True`` wins over ``required=False`` for the same capability, and
    the first non-``None`` ``standard`` wins: a TCK whose second test certifies
    nothing does not erase what its first test certifies.

    This is the rule the compiler writes into the package manifest and the
    player enforces before the first step, so an operator reading a compiled
    package sees exactly what the run will demand of them.
    """
    engine: dict[str, CapabilityRequirement] = {}
    sut: dict[str, CapabilityRequirement] = {}

    for config in configs:
        _merge_side(engine, config.engine)
        _merge_side(sut, config.sut)

    return InfrastructureConfig(engine=engine, sut=sut)


def collect_infrastructure_requirements(tck: object) -> InfrastructureConfig:
    """Collect and merge infrastructure requirements from a :class:`Tck`.

    Priority rules:

    1. If a TCK-level ``infrastructure:`` block is declared it is returned as-is —
       per-script blocks are ignored.
    2. Otherwise each script's ``infrastructure:`` block is merged using:
       - ``required=True`` wins over ``required=False`` for the same capability key.
       - The first non-``None`` ``standard`` wins.
    3. When no blocks are declared at any level, an empty
       :class:`InfrastructureConfig` is returned.

    Args:
        tck: A :class:`~tractusx_testlab.scripting.script.Tck` instance.

    Returns:
        The merged or directly declared :class:`InfrastructureConfig`.
    """
    tck_definition = getattr(tck, "definition", None)
    if tck_definition is not None:
        tck_infra = getattr(tck_definition, "infrastructure", None)
        if tck_infra is not None:
            return tck_infra

    scripts = getattr(tck, "scripts", None) or []
    declared = [
        infrastructure
        for infrastructure in (
            getattr(getattr(script, "definition", None), "infrastructure", None)
            for script in scripts
        )
        if infrastructure is not None
    ]
    return merge_requirements(declared)


def _merge_side(
    target: dict[str, CapabilityRequirement],
    source: dict,
) -> None:
    """Merge one side (engine or sut) of an InfrastructureConfig into *target* in-place.

    Merge rules: ``required=True`` wins; first non-``None`` ``standard`` wins.
    """
    for key, req in source.items():
        if key not in target:
            target[key] = req
        else:
            existing = target[key]
            target[key] = CapabilityRequirement(
                required=existing.required or req.required,
                standard=existing.standard if existing.standard is not None else req.standard,
            )
