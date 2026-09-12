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

"""Assemble the step reference from the rendered step contracts.

:mod:`~tractusx_testlab.authoring.step_docs` renders one step at a time; this
module lays the reference out around them — the per-module overview, the steps
grouped by category and module, and the ``validate:`` vocabulary the steps'
outputs are checked with.

:func:`render_catalog` renders the reference as a single document, for reading
on stdout; :mod:`~tractusx_testlab.authoring.step_pages` publishes the same
pieces as one page per module.
"""

from __future__ import annotations

import posixpath

from tractusx_testlab.authoring.registry import StepRegistry
from tractusx_testlab.authoring.step_docs import (
    render_shared_models,
    render_step,
    step_anchor,
    summary_and_body,
)
from tractusx_testlab.steps.assertions.operators import TABLE, Arity
from tractusx_testlab.steps.assertions.vocabulary import DEFAULT_OPERATOR, AssertionKind
from tractusx_testlab.steps.step_contract import BaseStep


def step_category(step_type: str) -> str:
    """The category a step id is grouped under — its first segment."""
    return step_type.split("/", 1)[0]


def step_module(step_type: str) -> str:
    """The module of a step id — the segments between category and function.

    Empty for a category with no sub-division, such as ``util/base64``.
    """
    segments = step_type.split("/")
    return "/".join(segments[1:-1])


def step_page(step_type: str) -> str:
    """The page a step is documented on, relative to the reference root.

    ``connector/provider/wizard/create_asset`` lives on
    ``connector/provider-wizard.md``; a step without a module lives on its
    category's ``index.md``. Every step page is one directory deep, so the
    pages link to each other the same way wherever they sit.
    """
    module = step_module(step_type)
    page = module.replace("/", "-") if module else "index"
    return f"{step_category(step_type)}/{page}.md"


def page_href(target: str, anchor: str, page: str | None) -> str:
    """Link to *anchor* on *target*, as seen from *page* (``None``: one document)."""
    if page is None or page == target:
        return f"#{anchor}"
    return f"{posixpath.relpath(target, posixpath.dirname(page) or '.')}#{anchor}"


def step_link(step_type: str, text: str | None = None, *, page: str | None = None) -> str:
    href = page_href(step_page(step_type), step_anchor(step_type), page)
    return f"[`{text or step_type}`]({href})"


def _modules(step_classes: list[type[BaseStep]]) -> dict[tuple[str, str], list[type[BaseStep]]]:
    """Group steps by ``(category, module)``, keeping the id order."""
    grouped: dict[tuple[str, str], list[type[BaseStep]]] = {}
    for step_cls in step_classes:
        key = (step_category(step_cls.step_type), step_module(step_cls.step_type))
        grouped.setdefault(key, []).append(step_cls)
    return grouped


def render_overview(
    step_classes: list[type[BaseStep]], *, page: str | None = None, title: str = "Overview"
) -> list[str]:
    """Render what is available per module, one row per ``category/module``."""
    lines = [
        f"## {title}",
        "",
        "| Category | Module | Steps |",
        "|---|---|---|",
    ]
    for (category, module), members in _modules(step_classes).items():
        steps = ", ".join(
            step_link(cls.step_type, cls.step_type.rsplit("/", 1)[-1], page=page) for cls in members
        )
        lines.append(f"| `{category}` | {f'`{module}`' if module else '—'} | {steps} |")
    return [*lines, ""]


def render_module_table(
    step_classes: list[type[BaseStep]], *, page: str | None = None
) -> list[str]:
    """Render one category's steps with their module and summary."""
    lines = ["| Module | Step | Summary |", "|---|---|---|"]
    for step_cls in step_classes:
        module = step_module(step_cls.step_type)
        summary, _ = summary_and_body(step_cls)
        link = step_link(step_cls.step_type, page=page)
        lines.append(f"| {f'`{module}`' if module else '—'} | {link} | {summary} |")
    return [*lines, ""]


#: What each ``validate:`` kind is for and which ``with:`` keys it reads on top
#: of the operator's operands. Keyed by the kind itself, so a kind added to the
#: vocabulary without a description here fails the page generation.
_ASSERTION_KINDS: dict[AssertionKind, tuple[str, str]] = {
    AssertionKind.ASSERT: (
        "Compare the output named by `input` under `operator`.",
        "`input`, `operator`, operands, `severity`",
    ),
    AssertionKind.FIELD: (
        "Compare the value at `path` inside the output named by `input` under `operator`.",
        "`input`, `path`, `operator`, operands, `severity`",
    ),
    AssertionKind.SCHEMA: (
        "Validate the output named by `input` against the JSON Schema given as `schema`.",
        "`input`, `schema`, `severity`",
    ),
}

#: The ``with:`` keys each operator arity reads as its operands.
_ARITY_OPERANDS: dict[Arity, str] = {
    Arity.UNARY: "—",
    Arity.BINARY: "`value`",
    Arity.RANGE: "`min`, `max`",
}

_MESSAGE_PLACEHOLDERS = {
    "{actual!r}": "<input>",
    "{expected!r}": "<value>",
    "{expected[0]!r}": "<min>",
    "{expected[1]!r}": "<max>",
}


def _failure_message(template: str) -> str:
    for placeholder, operand in _MESSAGE_PLACEHOLDERS.items():
        template = template.replace(placeholder, operand)
    return f"`{template}`"


def render_validations(*, level: int = 2, condition_href: str = "#condition") -> list[str]:
    """Render the ``validate:`` vocabulary: the assertion kinds and their operators.

    *level* is the heading level of the section; *condition_href* is where the
    `flow/if` Condition model is documented, relative to the page rendered.
    """
    sub = "#" * (level + 1)
    lines = [
        f"{'#' * level} Validations",
        "",
        "A step's `validate:` entries check the outputs it published. `input` names one of "
        "the step's output fields — a dotted name reaches inside it. The operator is given "
        "either in `with:` (`validate/assert` + `operator: equals`) or as a suffix of `uses` "
        f"(`validate/assert/equals`); when neither names one, `{DEFAULT_OPERATOR}` applies. "
        "`severity` is `HARD` (default, fails the step) or `SOFT` (reported as a warning).",
        "",
        f"{sub} Assertion kinds",
        "",
        "| `uses` | Checks | Reads from `with:` |",
        "|---|---|---|",
    ]
    for kind in AssertionKind:
        checks, keys = _ASSERTION_KINDS[kind]
        lines.append(f"| `validate/{kind.value}` | {checks} | {keys} |")

    lines += [
        "",
        f"{sub} Operators",
        "",
        "The same operators are used by `validate/assert`, `validate/field` and the "
        f"[Condition]({condition_href}) of `flow/if`. An operand the operator does not read is "
        "rejected rather than ignored.",
        "",
        "| Operator | Operands | Fails with |",
        "|---|---|---|",
    ]
    for operator in TABLE:
        lines.append(
            f"| `{operator.name}` | {_ARITY_OPERANDS[operator.arity]} "
            f"| {_failure_message(operator.message)} |"
        )
    return [*lines, ""]


GENERATED_NOTICE = "<!-- Generated by `testlab docs`. Do not edit by hand. -->"


def intro(tck_syntax_href: str) -> str:
    return (
        "Every step a test can name in `uses:`, with the parameters it accepts under `with:` "
        "and the output fields it publishes — the names `returns:`, `validate:` and later "
        "steps read. The reference is generated from the steps' declared Pydantic models, so "
        "it cannot drift from the implementation. For where these blocks sit in a test file, "
        f"see the [TCK syntax]({tck_syntax_href})."
    )


def step_classes_for(step_types: list[str] | None) -> list[type[BaseStep]]:
    names = sorted(step_types or StepRegistry.list_step_types())
    return [cls for cls in (StepRegistry.get_any(name) for name in names) if cls]


def render_catalog(step_types: list[str] | None = None) -> str:
    """Render the full step reference page.

    Every registered step is documented: `@step` refuses to register one that
    has not declared its models, so there is no undocumented remainder to
    account for. An overview lists what each module offers; the steps follow,
    grouped by category, then the ``validate:`` vocabulary and nested objects.
    """

    step_classes = step_classes_for(step_types)

    lines = [
        "# Step reference",
        "",
        GENERATED_NOTICE,
        "",
        intro("../tck-syntax/index.md"),
        "",
        f"{len(step_classes)} steps.",
        "",
        *render_overview(step_classes),
    ]

    category = None
    for step_cls in step_classes:
        if step_category(step_cls.step_type) != category:
            category = step_category(step_cls.step_type)
            members = [cls for cls in step_classes if step_category(cls.step_type) == category]
            lines += [f"## `{category}`", "", *render_module_table(members)]
        lines += render_step(step_cls)

    lines += render_validations()
    lines += render_shared_models(step_classes)

    return "\n".join(lines).rstrip() + "\n"
