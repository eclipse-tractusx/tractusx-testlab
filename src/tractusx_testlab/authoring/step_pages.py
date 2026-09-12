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

"""Publish the step reference as one page per module.

A single page holding every step is hard to navigate; split per module, the
site navigation lists every category and its modules. The pages are built
from the same pieces as :func:`~tractusx_testlab.authoring.step_catalog.render_catalog`.
"""

from __future__ import annotations

from tractusx_testlab.authoring.step_catalog import (
    GENERATED_NOTICE,
    intro,
    page_href,
    render_module_table,
    render_overview,
    render_validations,
    step_category,
    step_classes_for,
    step_link,
    step_module,
    step_page,
)
from tractusx_testlab.authoring.step_docs import render_shared_models, render_step, summary_and_body
from tractusx_testlab.steps.step_contract import BaseStep


def _pages_by_category(
    step_classes: list[type[BaseStep]],
) -> dict[str, dict[str, list[type[BaseStep]]]]:
    """Group steps by category, then by the page they are documented on."""
    grouped: dict[str, dict[str, list[type[BaseStep]]]] = {}
    for step_cls in step_classes:
        category = step_category(step_cls.step_type)
        pages = grouped.setdefault(category, {})
        pages.setdefault(step_page(step_cls.step_type), []).append(step_cls)
    return grouped


def _render_steps_page(title: str, members: list[type[BaseStep]], preamble: list[str]) -> str:
    lines = [f"# `{title}`", "", GENERATED_NOTICE, "", *preamble]
    for step_cls in members:
        lines += render_step(step_cls, level=2)
    lines += render_shared_models(members)
    return "\n".join(lines).rstrip() + "\n"


def render_pages(step_types: list[str] | None = None) -> dict[str, str]:
    """Render the step reference as one page per module.

    Returns the pages keyed by their path relative to the reference root:
    ``index.md`` (the overview), ``validations.md``, a category ``index.md``
    listing every step of the category (and documenting those without a
    module), and one page per module.
    """
    step_classes = step_classes_for(step_types)
    pages: dict[str, str] = {}

    overview = [
        "# Step reference",
        "",
        GENERATED_NOTICE,
        "",
        intro("../../tck-syntax/index.md"),
        "",
        f"{len(step_classes)} steps. The checks a step's outputs are held to are listed "
        "under [Validations](validations.md).",
        "",
        *render_overview(step_classes, page="index.md", title="Categories and modules"),
    ]
    pages["index.md"] = "\n".join(overview).rstrip() + "\n"

    condition_href = page_href(step_page("flow/if"), "condition", "validations.md")
    heading, *validations = render_validations(level=1, condition_href=condition_href)
    pages["validations.md"] = (
        "\n".join([heading, "", GENERATED_NOTICE, *validations]).rstrip() + "\n"
    )

    for category, category_pages in _pages_by_category(step_classes).items():
        index = f"{category}/index.md"
        members = [cls for group in category_pages.values() for cls in group]
        table = render_module_table(members, page=index)
        pages[index] = _render_steps_page(category, category_pages.get(index, []), table)
        for page, page_members in category_pages.items():
            if page == index:
                continue
            title = f"{category}/{step_module(page_members[0].step_type)}"
            table = ["| Step | Summary |", "|---|---|"]
            for step_cls in page_members:
                summary, _ = summary_and_body(step_cls)
                table.append(f"| {step_link(step_cls.step_type, page=page)} | {summary} |")
            pages[page] = _render_steps_page(title, page_members, [*table, ""])

    return pages


def render_nav(step_types: list[str] | None = None, *, root: str) -> list[str]:
    """Render the MkDocs ``nav`` entries of :func:`render_pages`' pages.

    One section per category, one entry per module; a category whose steps
    have no module is a single entry. *root* is the reference's directory
    relative to ``docs/``.
    """
    lines = [f"- Overview: {root}/index.md", f"- Validations: {root}/validations.md"]
    for category, category_pages in _pages_by_category(step_classes_for(step_types)).items():
        index = f"{category}/index.md"
        if list(category_pages) == [index]:
            lines.append(f"- {category}: {root}/{index}")
            continue
        lines += [f"- {category}:", f"  - Overview: {root}/{index}"]
        for page, members in category_pages.items():
            if page != index:
                lines.append(f"  - {step_module(members[0].step_type)}: {root}/{page}")
    return lines
