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

"""What a step promises to publish, and whether a path names one of those things.

Two places ask that question — a test's ``returns:`` and an assertion's
``input:`` — and both must answer it the way :mod:`~.extraction` will resolve
the name at run time, or a legitimate test is refused for naming something
that would have worked.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import UnionType
from typing import Any, Union, get_args, get_origin

from pydantic import RootModel

from tractusx_testlab.steps._checks.extraction import _split_path, declared_names


def publishes(step_cls: Any) -> frozenset[str] | None:
    """Every name *step_cls* promises, or ``None`` when it promises an open document.

    Two output shapes describe a document the step cannot enumerate in advance,
    and for both the honest answer is "anything":

    * a model declared ``extra="allow"`` publishes whatever the SUT sent
      alongside its own fields — ``notification/consumer/send`` spreads the
      receiver's answer at the top level, and a shell descriptor round-trips
      the keys it was given;
    * a ``RootModel`` over a mapping *is* that document — ``http/http_request``
      returns the response body itself and ``util/parse_kv`` returns keys the
      SUT chose. The runner publishes each of those keys as a context
      variable, and extraction reads them straight off the value.

    Anything else is a fixed set of fields, and a name outside it resolves to
    nothing. The synthetic ``root`` is dropped either way: it names the
    document rather than anything inside it, and never resolves.
    """
    model = getattr(step_cls, "output_model", None)
    config = getattr(model, "model_config", None) or {}
    if config.get("extra") == "allow":
        return None
    if _may_carry_named_keys(_root_annotation(model)):
        return None
    return declared_names(step_cls) - {"root"}


def _root_annotation(model: Any) -> Any:
    """The type a ``RootModel`` output wraps, or ``None`` for any other model."""
    if not (isinstance(model, type) and issubclass(model, RootModel)):
        return None
    field = model.model_fields.get("root")
    return None if field is None else field.annotation


def _may_carry_named_keys(annotation: Any) -> bool:
    """Whether a value of *annotation* can hold keys a test could name."""
    if annotation is Any:
        return True
    origin = get_origin(annotation)
    if origin in (Union, UnionType):
        return any(_may_carry_named_keys(arg) for arg in get_args(annotation))
    subject = origin or annotation
    return isinstance(subject, type) and issubclass(subject, Mapping)


def names_a_published_output(path: str, published: frozenset[str] | set[str] | None) -> bool:
    """Whether *path* starts at something in *published* — ``None`` meaning anything."""
    return True if published is None else _root_of(path) in published


def _root_of(path: str) -> str:
    """The output a path reads from, ignoring what it then does inside it.

    A dot inside a ``[...]`` predicate belongs to the predicate's value, and a
    predicate selects within the list its name points at rather than naming
    something else — so ``datasets[assetId='urn:x.y'].id`` reads ``datasets``,
    which is what a naive ``split(".")`` gets wrong twice over.
    """
    segments = _split_path(path)
    first = segments[0] if segments else path
    return first.split("[", 1)[0]
