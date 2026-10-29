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

"""A loaded API document is shared by every reader, so none of them can change it."""

from __future__ import annotations

import copy
import json
import pickle
from collections.abc import Callable
from typing import Any

import pytest
import yaml
from pydantic import BaseModel

from tractusx_testlab.openapi import FrozenDict, FrozenList, freeze


def _document() -> Any:
    return freeze({"paths": {"/a": {"get": {"tags": ["x"]}}}, "n": 1})


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d.__setitem__("x", 1),
        lambda d: d.__delitem__("n"),
        lambda d: d.pop("n"),
        lambda d: d.popitem(),
        lambda d: d.update(x=1),
        lambda d: d.setdefault("x", 1),
        lambda d: d.clear(),
        lambda d: d.__ior__({"x": 1}),
        lambda d: d["paths"]["/a"]["get"]["tags"].append("y"),
        lambda d: d["paths"]["/a"]["get"]["tags"].__setitem__(0, "y"),
        lambda d: d["paths"]["/a"]["get"]["tags"].extend(["y"]),
        lambda d: d["paths"]["/a"]["get"]["tags"].sort(),
        lambda d: d["paths"]["/a"]["get"]["tags"].__iadd__(["y"]),
    ],
)
def test_no_reader_can_change_it_at_any_depth(change: Callable[[Any], object]) -> None:
    document = _document()
    with pytest.raises(TypeError, match="read-only"):
        change(document)
    assert document == {"paths": {"/a": {"get": {"tags": ["x"]}}}, "n": 1}


def test_it_reads_as_plain_json_data() -> None:
    document = _document()
    assert isinstance(document, dict)
    assert isinstance(document["paths"]["/a"]["get"]["tags"], list)
    assert json.loads(json.dumps(document)) == document


def test_a_copy_is_the_document_itself() -> None:
    document = _document()
    assert copy.copy(document) is document
    assert copy.deepcopy(document) is document


def test_it_survives_pickling_still_read_only() -> None:
    restored = pickle.loads(pickle.dumps(_document()))
    assert isinstance(restored, FrozenDict)
    assert restored == _document()


def test_a_record_written_as_yaml_carries_plain_data() -> None:
    written = yaml.safe_dump(_document())
    assert "!!python" not in yaml.dump(_document())
    assert yaml.safe_load(written) == _document()


def test_a_model_field_of_any_type_keeps_it() -> None:
    class Params(BaseModel):
        api: Any

    assert isinstance(Params(api=_document()).api, FrozenDict)


def test_an_alias_shared_by_the_parser_stays_shared() -> None:
    shared: dict[str, Any] = {"a": [1]}
    frozen = freeze({"x": shared, "y": shared})
    assert frozen["x"] is frozen["y"]
    assert isinstance(frozen["x"]["a"], FrozenList)


def test_a_scalar_is_returned_as_it_is() -> None:
    assert freeze("text") == "text"
