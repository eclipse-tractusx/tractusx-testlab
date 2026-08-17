#################################################################################
# Eclipse Tractus-X - Software Development KIT
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
# License for the specific language govern in permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0
#################################################################################

"""Render the step catalog as Markdown from the steps' declared contracts.

The models on each step are the single source of truth for its interface, so
the reference page is generated from them rather than written by hand — a
parameter that is renamed in code cannot go stale in the docs.

Fields are read from ``model_fields`` rather than ``model_json_schema()``
because JSON Schema drops alias information, and the exact spelling a step
accepts (``schema:`` for the field declared as ``json_schema``) is exactly
what a script author needs to see.
"""

from __future__ import annotations

import re
import types
import typing
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.steps.base import BaseStep, StepValue

_PRIMITIVES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}

_NONE_TYPE = type(None)

#: Sphinx cross-reference roles used in docstrings, e.g. ``:class:`Foo```.
_SPHINX_ROLE = re.compile(r":[a-z]+:`~?([^`]+)`")
#: RST inline literals, which use two backticks where Markdown uses one.
_RST_LITERAL = re.compile(r"``([^`]+)``")


def to_markdown(text: str) -> str:
    """Convert the RST conventions used in docstrings to Markdown.

    Docstrings are written for mkdocstrings and the IDE, so they carry
    ``:class:`Foo``` roles and double-backtick literals; both render as noise
    in a Markdown table.
    """
    return _RST_LITERAL.sub(r"`\1`", _SPHINX_ROLE.sub(r"`\1`", text))


# ---------------------------------------------------------------------------
# Type and field rendering
# ---------------------------------------------------------------------------


def type_name(annotation: Any) -> str:
    """Render a type annotation the way a script author would recognise it."""
    if annotation is Any or annotation is None:
        return "any"

    origin = get_origin(annotation)
    if origin is typing.Literal:
        return " \\| ".join(f"`{arg}`" for arg in get_args(annotation))
    if origin in (Union, types.UnionType):
        members = [arg for arg in get_args(annotation) if arg is not _NONE_TYPE]
        return " \\| ".join(type_name(member) for member in members) or "any"
    if origin in (list, set, tuple):
        args = get_args(annotation)
        return f"list of {type_name(args[0])}" if args else "array"
    if origin is dict:
        return "object"

    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            return f"[{annotation.__name__}](#{annotation.__name__.lower()})"
        return _PRIMITIVES.get(annotation, annotation.__name__)
    return str(annotation)


def accepted_names(name: str, field: FieldInfo) -> list[str]:
    """Every key that populates *field*, canonical name first."""
    alias = field.validation_alias or field.alias
    if alias is None:
        return [name]
    choices = getattr(alias, "choices", None)
    if choices is not None:
        return [str(choice) for choice in choices]
    return [str(alias)]


def default_repr(field: FieldInfo) -> str:
    """Render a field's default, or an em dash when it is required."""
    if field.is_required():
        return "—"
    if field.default is not PydanticUndefined and field.default is not None:
        return f"`{field.default!r}`"
    if field.default_factory is not None:
        return f"`{field.default_factory()!r}`"
    return "`None`"


def nested_models(model: type[BaseModel]) -> list[type[BaseModel]]:
    """Return the nested Pydantic models reachable from *model*, depth-first."""
    found: list[type[BaseModel]] = []

    def walk(current: type[BaseModel]) -> None:
        for field in current.model_fields.values():
            for candidate in _annotation_models(field.annotation):
                if candidate not in found:
                    found.append(candidate)
                    walk(candidate)

    walk(model)
    return found


def _annotation_models(annotation: Any) -> list[type[BaseModel]]:
    """Pull every Pydantic model out of a possibly-generic annotation."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [
        model
        for arg in get_args(annotation)
        for model in _annotation_models(arg)
    ]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _field_rows(model: type[BaseModel], *, with_aliases: bool) -> list[str]:
    rows = []
    for name, field in model.model_fields.items():
        names = accepted_names(name, field)
        canonical = f"`{names[0]}`"
        also = ", ".join(f"`{alt}`" for alt in names[1:]) or "—"
        description = to_markdown((field.description or "").replace("\n", " "))
        cells = [canonical, type_name(field.annotation)]
        if with_aliases:
            cells += ["yes" if field.is_required() else "no", default_repr(field), also]
        cells.append(description)
        rows.append("| " + " | ".join(cells) + " |")
    return rows


def _table(model: type[BaseModel], header: list[str], *, with_aliases: bool) -> list[str]:
    rows = _field_rows(model, with_aliases=with_aliases)
    if not rows:
        return ["_No fields._", ""]
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * len(header)) + "|",
        *rows,
        "",
    ]


def _docstring(obj: Any) -> str:
    """First paragraph of a docstring, joined onto one line."""
    lines = (obj.__doc__ or "").strip().splitlines()
    paragraph: list[str] = []
    for line in lines:
        if not line.strip():
            break
        paragraph.append(line.strip())
    return to_markdown(" ".join(paragraph))


def _summary_and_body(obj: Any) -> tuple[str, str]:
    """Split a docstring into its first paragraph and the rest."""
    text = (obj.__doc__ or "").strip()
    head, _, tail = text.partition("\n\n")
    return to_markdown(" ".join(head.split())), to_markdown(" ".join(tail.split()))


def render_step(step_cls: type[BaseStep]) -> list[str]:
    """Render one step's interface as Markdown."""
    summary, body = _summary_and_body(step_cls)
    lines = [f"### `{step_cls.step_type}`", "", summary, ""]
    if body:
        lines += [body, ""]

    lines += ["**Inputs**", ""]
    lines += _table(
        step_cls.params_model,
        ["Parameter", "Type", "Required", "Default", "Also accepts", "Description"],
        with_aliases=True,
    )

    lines += ["**Output** — the value assertions and `returns:` read", ""]
    lines += ["_" + _docstring(step_cls.output_model) + "_", ""]
    lines += _output_shape(step_cls.output_model)

    return lines


def _output_shape(model: type[BaseModel]) -> list[str]:
    """Render an output contract, whichever of the two kinds it is.

    A `StepValue` has no fields — it *is* the value — so its type is stated in
    one line rather than as an empty table.
    """
    if issubclass(model, StepValue):
        return [f"Type: {type_name(_root_annotation(model))}", ""]

    lines = _table(model, ["Field", "Type", "Description"], with_aliases=False)
    if model.model_config.get("extra") == "allow":
        lines += ["Additional keys sent by the counterpart are passed through unchanged.", ""]
    return lines


def _root_annotation(model: type[BaseModel]) -> Any:
    """The type a `StepValue` wraps.

    Pydantic resolves `StepValue[None]` to a root annotation of either `None`
    or `NoneType` depending on import order; both mean the same thing, so both
    render as `NoneType` — otherwise the generated page would not be
    reproducible.
    """
    root = model.model_fields.get("root")
    annotation = root.annotation if root is not None else Any
    return _NONE_TYPE if annotation is None else annotation


def render_shared_models(step_classes: list[type[BaseStep]]) -> list[str]:
    """Render the nested objects referenced by the documented steps, once each."""
    collected: list[type[BaseModel]] = []
    for step_cls in step_classes:
        for model in (step_cls.params_model, step_cls.output_model):
            for nested in nested_models(model):
                if nested not in collected:
                    collected.append(nested)

    if not collected:
        return []

    lines = ["## Nested objects", ""]
    for model in sorted(collected, key=lambda m: m.__name__):
        lines += [f"### {model.__name__}", "", _docstring(model), ""]
        lines += _table(
            model,
            ["Field", "Type", "Required", "Default", "Also accepts", "Description"],
            with_aliases=True,
        )
        if model.model_config.get("extra") == "allow":
            lines += [
                "Additional keys sent by the counterpart are passed through unchanged.",
                "",
            ]
    return lines


def render_catalog(step_types: list[str] | None = None) -> str:
    """Render the full step reference page.

    Every registered step is documented: `@step` refuses to register one that
    has not declared its models, so there is no undocumented remainder to
    account for.
    """

    names = sorted(step_types or StepRegistry.list_step_types())
    step_classes = [cls for cls in (StepRegistry.get(name, "") for name in names) if cls]

    lines = [
        "# Step reference",
        "",
        "<!-- Generated by `testlab docs steps`. Do not edit by hand. -->",
        "",
        "Every step declares its interface as Pydantic models, and this page is "
        "generated from them, so it cannot drift from the implementation.",
        "",
        f"{len(step_classes)} steps.",
        "",
        "## Steps",
        "",
    ]

    for step_cls in step_classes:
        lines += render_step(step_cls)

    lines += render_shared_models(step_classes)

    return "\n".join(lines).rstrip() + "\n"
