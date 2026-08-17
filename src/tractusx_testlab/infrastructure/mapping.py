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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""The three surfaces of an infrastructure binding, all derived from one model.

A binding field is written in three places — a config file, an environment
variable, and a ``${{ }}`` reference inside a test — and all three forms are
generated here by walking :class:`Infrastructure`. Nothing in this module
enumerates a capability or a field by hand, so a field added to the model
appears on every surface at once and the surfaces cannot drift apart:

===================  ===========================================  ==================================================
Surface              Form                                         Example
===================  ===========================================  ==================================================
Config file          ``<side>.<capability>.<field>``              ``sut.connector.dsp_url``
Context variable     ``infrastructure.<side>.<capability>.<field>``  ``infrastructure.sut.connector.dsp_url``
Environment          ``TESTLAB_<SIDE>_<CAPABILITY>_<FIELD>``      ``TESTLAB_SUT_CONNECTOR_DSP_URL``
===================  ===========================================  ==================================================

Environment variables are read by generating the full set of legal names and
looking each one up, rather than by splitting names apart. The capability and
field cannot be recovered from ``TESTLAB_ENGINE_DTR_SUBMODEL_BASE_URL`` by
counting underscores — both halves carry them — and a generated set has no
ambiguity to resolve.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from typing import Any

from tractusx_testlab.models.domain.infrastructure import (
    CapabilityBinding,
    Infrastructure,
    capability_bindings,
)
from tractusx_testlab.models.primitives.exceptions import UnknownBindingKeyError

#: Prefix every infrastructure binding carries inside the variable namespace.
CONTEXT_PREFIX = "infrastructure."

#: Prefix every TestLab environment variable carries.
ENV_PREFIX = "TESTLAB_"

#: Segment count of a full context key: ``infrastructure.<side>.<cap>.<field>``.
_KEY_SEGMENTS = 4


def capabilities() -> tuple[tuple[str, str, type[CapabilityBinding]], ...]:
    """Return every ``(side, capability, binding_type)`` the model declares."""
    return capability_bindings()


def context_key(side: str, capability: str, field: str) -> str:
    """Return the context-variable form of one binding field."""
    return f"{CONTEXT_PREFIX}{side}.{capability}.{field}"


def env_key(side: str, capability: str, field: str) -> str:
    """Return the environment-variable form of one binding field."""
    return f"{ENV_PREFIX}{side}_{capability}_{field}".upper()


def known_keys() -> dict[str, tuple[str, str, str]]:
    """Return every legal context key, mapped to its ``(side, capability, field)``."""
    return {
        context_key(side, capability, field): (side, capability, field)
        for side, capability, binding_type in capabilities()
        for field in binding_type.model_fields
    }


def _iter_bound(infrastructure: Infrastructure) -> Iterator[tuple[str, str, CapabilityBinding]]:
    """Yield each capability of *infrastructure* that was actually bound."""
    for side, capability, _ in capabilities():
        binding = infrastructure.binding(side, capability)
        if binding is not None and binding.is_bound():
            yield side, capability, binding


def flatten(infrastructure: Infrastructure) -> dict[str, str]:
    """Project *infrastructure* onto the context keys a test can reference.

    Only bound capabilities are projected, and only their non-empty fields: an
    unbound connector has nothing to say, and publishing its defaults would put
    an ``api_key_header`` in the namespace for a connector that does not exist.
    """
    projected: dict[str, str] = {}
    for side, capability, binding in _iter_bound(infrastructure):
        for field in type(binding).model_fields:
            value = getattr(binding, field, "")
            if value not in (None, ""):
                projected[context_key(side, capability, field)] = str(value)
    return projected


def collect_overrides(variables: Mapping[str, Any]) -> dict[str, Any]:
    """Return the binding overrides a variable store carries.

    An operator supplies bindings on the CLI (``--var
    infrastructure.sut.dtr.base_url=…``) or in a run-config, so they arrive as
    ordinary variables and are picked back out here. Shorter keys are left
    alone: ``infrastructure.sut.connector`` is the seeded service name, not a
    field, and a key of the full shape naming no field is a typo the operator
    is told about rather than one that is dropped.
    """
    legal = known_keys()
    overrides: dict[str, Any] = {}
    for key, value in variables.items():
        if not isinstance(key, str) or not key.startswith(CONTEXT_PREFIX):
            continue
        if len(key.split(".")) != _KEY_SEGMENTS:
            continue
        if key not in legal:
            raise UnknownBindingKeyError(key, sorted(legal))
        overrides[key] = value
    return overrides


def overrides_from_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return the binding overrides the environment carries, in context-key form."""
    source = os.environ if environ is None else environ
    overrides: dict[str, str] = {}
    for side, capability, binding_type in capabilities():
        for field in binding_type.model_fields:
            value = source.get(env_key(side, capability, field))
            if value is not None:
                overrides[context_key(side, capability, field)] = value
    return overrides


def apply_overrides(
    infrastructure: Infrastructure,
    overrides: Mapping[str, Any],
) -> Infrastructure:
    """Return *infrastructure* with *overrides* applied, leaving the original untouched.

    Overrides are context-keyed and always win — they are the last word an
    operator gets, after the profile, the config file, and the environment.
    Values are stored as text because every surface they arrive from is text,
    and a binding field is an address or a credential either way.
    """
    if not overrides:
        return infrastructure

    legal = known_keys()
    data = infrastructure.model_dump()
    for key, value in overrides.items():
        located = legal.get(key)
        if located is None:
            raise UnknownBindingKeyError(key, sorted(legal))
        side, capability, field = located
        data[side][capability][field] = "" if value is None else str(value)
    return Infrastructure.model_validate(data)


def merge(base: Infrastructure, overlay: Infrastructure) -> Infrastructure:
    """Return *base* with every field *overlay* states written over it.

    Layering config sources means an overlay that binds only a DTR must not
    erase the connector underneath it, so what is written is what the overlay
    was actually given — not what it defaults to. A ``api_key_header`` nobody
    typed is a default, and a default must never overwrite a value someone did
    type on the layer below.
    """
    data = base.model_dump()
    stated = overlay.model_dump(exclude_unset=True)
    for side, capabilities_stated in stated.items():
        for capability, fields_stated in (capabilities_stated or {}).items():
            for field, value in (fields_stated or {}).items():
                data[side][capability][field] = value
    return Infrastructure.model_validate(data)
