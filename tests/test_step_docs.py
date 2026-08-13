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

"""Tests for the generated step reference page."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import pytest
from pydantic import BaseModel, Field

import tractusx_testlab.steps  # noqa: F401  — registers every step
from tractusx_testlab.scripting.registry import StepRegistry
from tractusx_testlab.scripting.step_docs import (
    accepted_names,
    default_repr,
    nested_models,
    render_catalog,
    to_markdown,
    type_name,
)

_GENERATED_PAGE = Path(__file__).resolve().parents[1] / "docs/specification/reference/steps.md"


class _Nested(BaseModel):
    leaf: str = "x"


class _Sample(BaseModel):
    plain: str
    optional_text: Optional[str] = None
    choice: Literal["a", "b"] = "a"
    items: list[_Nested] = Field(default_factory=list)
    anything: Any = None
    aliased: str = Field(default="", alias="legacy_name")


class TestTypeName:
    def test_primitive(self) -> None:
        assert type_name(str) == "string"

    def test_optional_drops_the_none_member(self) -> None:
        assert type_name(Optional[str]) == "string"

    def test_literal_lists_the_allowed_values(self) -> None:
        assert type_name(Literal["a", "b"]) == "`a` \\| `b`"

    def test_list_of_model_links_to_its_section(self) -> None:
        assert type_name(list[_Nested]) == "list of [_Nested](#_nested)"

    def test_any_is_reported_as_any(self) -> None:
        assert type_name(Any) == "any"

    def test_pipe_is_escaped_so_it_cannot_break_a_table_row(self) -> None:
        assert "\\|" in type_name(Literal["a", "b"])


class TestFieldRendering:
    def test_an_aliased_field_reports_its_accepted_spelling(self) -> None:
        assert accepted_names("aliased", _Sample.model_fields["aliased"]) == ["legacy_name"]

    def test_a_field_without_an_alias_reports_only_its_name(self) -> None:
        assert accepted_names("plain", _Sample.model_fields["plain"]) == ["plain"]

    def test_required_field_has_no_default(self) -> None:
        assert default_repr(_Sample.model_fields["plain"]) == "—"

    def test_default_factory_is_evaluated(self) -> None:
        assert default_repr(_Sample.model_fields["items"]) == "`[]`"

    def test_nested_models_are_discovered_through_a_list(self) -> None:
        assert nested_models(_Sample) == [_Nested]


class TestToMarkdown:
    def test_rst_literals_become_markdown_code(self) -> None:
        assert to_markdown("use ``datasets`` here") == "use `datasets` here"

    def test_sphinx_roles_are_unwrapped(self) -> None:
        assert to_markdown("see :class:`GenerateBpnParams`") == "see `GenerateBpnParams`"

    def test_plain_text_is_untouched(self) -> None:
        assert to_markdown("nothing to do") == "nothing to do"


class TestRenderCatalog:
    @pytest.fixture(scope="class")
    def page(self) -> str:
        return render_catalog(["connector/consumer/query_catalog", "util/generate_bpn"])

    def test_each_step_gets_a_heading(self, page: str) -> None:
        assert "### `connector/consumer/query_catalog`" in page

    def test_inputs_table_documents_canonical_spellings(self, page: str) -> None:
        assert "`counter_party_address`" in page
        assert "`provider_url`" not in page

    def test_the_published_offers_are_documented_as_output_fields(self, page: str) -> None:
        assert "`datasets`" in page

    def test_the_exports_channel_is_gone_from_the_page(self, page: str) -> None:
        assert "**Publishes**" not in page

    def test_nested_models_are_rendered_once(self, page: str) -> None:
        assert page.count("### FilterExpression") == 1

    def test_pass_through_payloads_are_flagged(self, page: str) -> None:
        assert "passed through unchanged" in page

    def test_bare_value_outputs_state_their_type(self) -> None:
        """A `StepValue` has no fields, so the page names its type instead."""
        page = render_catalog(["util/base64"])
        assert "Type: string" in page

    def test_every_registered_step_is_on_the_page(self) -> None:
        """There is no undeclared remainder — `@step` will not register one."""
        page = render_catalog()
        for step_type in StepRegistry.list_step_types():
            assert f"### `{step_type}`" in page


class TestGeneratedPage:
    def test_committed_page_matches_the_code(self) -> None:
        """The reference page is generated; regenerate it with ``testlab docs``."""
        assert _GENERATED_PAGE.exists(), f"{_GENERATED_PAGE} is missing; run 'testlab docs'"
        assert _GENERATED_PAGE.read_text(encoding="utf-8") == render_catalog(), (
            "docs/specification/reference/steps.md is out of date; run 'testlab docs'"
        )
