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

"""A bound API document: read as the document, recorded as its summary with its id."""

from __future__ import annotations

import copy
import json
import pickle

import yaml

from tests.unit.openapi.documents import shop
from tractusx_testlab.logging import wire
from tractusx_testlab.openapi import BoundApiDocument, recorded


def test_it_reads_as_the_document_and_knows_its_id() -> None:
    document = shop()
    assert isinstance(document, dict) and document["info"]["title"] == "Shop"
    assert document.api_id == "shop"


def test_every_record_shows_the_summary_with_the_id() -> None:
    document = shop()
    summary = document.__recorded__()["api_document"]
    assert set(summary) == {"id", "openapi", "title", "version", "sha256"}
    assert summary["id"] == "shop" and summary["sha256"] == document.sha256
    assert wire.redact_secrets({"api": document}) == {"api": {"api_document": summary}}
    assert yaml.safe_load(yaml.safe_dump({"api": document})) == {"api": {"api_document": summary}}


def test_recorded_summarises_only_what_holds_a_document() -> None:
    plain = {"a": [1, {"b": 2}]}
    assert recorded(plain) is plain
    params = {"api": shop(), "operation": "health", "nested": [shop()]}
    written = json.dumps(recorded(params))
    assert "components" not in written and written.count('"id": "shop"') == 2


def test_copies_are_the_document_itself_and_pickling_keeps_the_id() -> None:
    document = shop()
    assert copy.deepcopy(document) is document
    revived = pickle.loads(pickle.dumps(document))
    assert isinstance(revived, BoundApiDocument)
    assert revived.api_id == "shop" and revived.__recorded__() == document.__recorded__()
