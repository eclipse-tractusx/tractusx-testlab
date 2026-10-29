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

"""``env.apis`` entries: an id, a file under apis/, and a type — inferred when omitted."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from tractusx_testlab.models import TckDefinition
from tractusx_testlab.models.authoring import ApiDefinition


@pytest.mark.parametrize(
    ("source", "inferred"),
    [
        ("ich.yaml", "application/vnd.oai.openapi"),
        ("ich.yml", "application/vnd.oai.openapi"),
        ("ICH.YAML", "application/vnd.oai.openapi"),
        ("v2/ich.json", "application/vnd.oai.openapi+json"),
    ],
)
def test_the_type_is_inferred_from_the_extension(source: str, inferred: str) -> None:
    assert ApiDefinition(id="ich", source=source).type == inferred


@pytest.mark.parametrize(
    "declared",
    [
        "application/vnd.oai.openapi",
        "application/vnd.oai.openapi+json",
        "application/yaml",
        "application/json",
    ],
)
def test_a_declared_type_wins_over_the_extension(declared: str) -> None:
    assert ApiDefinition(id="ich", source="ich.txt", type=declared).type == declared


def test_a_type_that_cannot_be_inferred_says_what_to_do() -> None:
    with pytest.raises(ValidationError, match=r"type cannot be inferred from 'ich\.txt'"):
        ApiDefinition(id="ich", source="ich.txt")


@pytest.mark.parametrize("declared", ["text/yaml", "application/xml", "application/openapi+yaml"])
def test_another_media_type_is_refused(declared: str) -> None:
    with pytest.raises(ValidationError, match="application/vnd.oai.openapi"):
        ApiDefinition(id="ich", source="ich.yaml", type=declared)


@pytest.mark.parametrize("api_id", ["ich", "ich_v2", "a1"])
def test_an_id_is_one_snake_case_segment(api_id: str) -> None:
    assert ApiDefinition(id=api_id, source="a.yaml").id == api_id


@pytest.mark.parametrize("api_id", ["ich.v2", "ICH", "1ich", "ich-hub", "", "a" * 51])
def test_an_id_that_cannot_be_a_reference_segment_is_refused(api_id: str) -> None:
    with pytest.raises(ValidationError, match="id"):
        ApiDefinition(id=api_id, source="a.yaml")


@pytest.mark.parametrize("key", ["base_url", "connector", "auth", "via"])
def test_no_transport_setting_is_accepted(key: str) -> None:
    """How an API is reached is the steps' decision, never the entry's."""
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ApiDefinition.model_validate({"id": "ich", "source": "a.yaml", key: "x"})


def test_an_empty_source_is_refused() -> None:
    with pytest.raises(ValidationError, match="source"):
        ApiDefinition(id="ich", source="")


def test_a_manifest_declares_them_under_env_apis() -> None:
    manifest: dict[str, Any] = {
        "syntax": "v1-alpha",
        "id": "api-tck",
        "metadata": {"name": "API TCK"},
        "env": {"apis": [{"id": "ich", "source": "ich.yaml"}]},
    }
    [api] = TckDefinition.model_validate(manifest).env.apis  # type: ignore[union-attr]
    assert (api.id, api.source, api.type) == ("ich", "ich.yaml", "application/vnd.oai.openapi")
