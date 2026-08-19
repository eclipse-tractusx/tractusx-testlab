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
## This code was partially generated using artificial intelligence (AI) (Tool: Claude Code, Model: Claude Opus 5).
## It was reviewed and tested by a human committer.

"""What the authoring models allow at a given point in a document.

A rejected key is only half an answer; the author needs the keys that *would*
have been accepted, and that is a question about the model, not about the
failure. The path is walked as an annotation cursor rather than a class cursor,
so ``list[StepDefinition]`` and ``dict[str, ReturnFieldDefinition]`` are stepped
through the same way the YAML nests them.

Read against ``model_fields`` rather than against the generated JSON Schema:
the schema knows the shape but not which spelling the loader binds, and a key
that only binds through a ``validation_alias`` would be listed under the wrong
name.
"""

from __future__ import annotations

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel

from tractusx_testlab.syntax.yaml_marks import Path as DocPath

#: Blocks there is only ever one of, which read as "the metadata", not "a
#: metadata". Everything else is one of many and takes an indefinite article.
_MASS = frozenset({"metadata", "env", "infrastructure", "dataspace"})


def noun_for(model: type[BaseModel]) -> str:
    """``ReturnFieldDefinition`` reads back to the author as "a return field"."""
    if model.__name__.endswith("Params"):
        # A step's input contract is never named in a script — the author wrote
        # a `with:` block, and that is what the message has to call it.
        return "the step's `with:` block"
    name = model.__name__.removesuffix("Definition") or model.__name__
    words = "".join(f" {c.lower()}" if c.isupper() else c for c in name).strip()
    if words in _MASS:
        return f"the {words}"
    article = "an" if words[:1] in "aeiou" else "a"
    return f"{article} {words}"


def model_at(model: type[BaseModel] | None, path: DocPath) -> type[BaseModel] | None:
    """The model whose fields the keys at *path* belong to, or None if unknown.

    The path is walked as an annotation cursor rather than a class cursor: a
    sequence position unwraps ``list[Step]`` to ``Step``, and a mapping key
    unwraps ``dict[str, ReturnField]`` to ``ReturnField``, so the same walk
    handles the collections the syntax is built out of.
    """
    cursor: Any = model
    for part in path:
        cursor = _unwrap_optional(cursor)
        if isinstance(part, int):
            cursor = _element_of(cursor, 0)
            continue
        if get_origin(cursor) is dict:
            cursor = _element_of(cursor, 1)
            continue
        owner = _as_model(cursor)
        if owner is None:
            return None
        field = _field_by_alias(owner, part)
        if field is None:
            return None
        cursor = field
    return _as_model(_unwrap_optional(cursor))


def keys_of(model: type[BaseModel]) -> list[str]:
    """Every key the author may write on *model*, spelled as the YAML spells it."""
    return sorted(
        str(field.validation_alias or field.alias or name)
        for name, field in model.model_fields.items()
    )


def _field_by_alias(model: type[BaseModel], key: str) -> Any:
    """The annotation of the field *key* names, honouring the YAML aliases."""
    for name, field in model.model_fields.items():
        if key in (name, field.alias, field.validation_alias):
            return field.annotation
    return None


def _as_model(annotation: Any) -> type[BaseModel] | None:
    return (
        annotation if isinstance(annotation, type) and issubclass(annotation, BaseModel) else None
    )


def _unwrap_optional(annotation: Any) -> Any:
    """``X | None`` is ``X`` as far as "what may be written here" is concerned."""
    if get_origin(annotation) in (Union, types.UnionType):
        remaining = [arg for arg in get_args(annotation) if arg is not type(None)]
        if len(remaining) == 1:
            return remaining[0]
    return annotation


def _element_of(annotation: Any, position: int) -> Any:
    args = get_args(annotation)
    return args[position] if len(args) > position else None
